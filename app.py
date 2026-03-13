import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

from ai_assistant import (  # noqa: E402
    CORE_TEXT_FIELDS,
    SEO_FIELDS,
    TEXT_FIELDS,
    TRAIT_FIELDS,
    generate_suggestions,
)


# ── Supabase helpers ────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@st.cache_data(ttl=300)
def load_breeds() -> list[dict]:
    sb = get_supabase()
    resp = (
        sb.table("breeds")
        .select("id,name,slug,content_status")
        .order("name")
        .execute()
    )
    return resp.data


@st.cache_data(ttl=60)
def load_breed_detail(breed_id: str) -> dict:
    sb = get_supabase()
    fields = ",".join(TEXT_FIELDS + TRAIT_FIELDS)
    resp = (
        sb.table("breeds")
        .select(fields)
        .eq("id", breed_id)
        .single()
        .execute()
    )
    return resp.data


def save_breed_fields(breed_id: str, updates: dict):
    sb = get_supabase()
    sb.table("breeds").update(updates).eq("id", breed_id).execute()
    load_breeds.clear()
    load_breed_detail.clear()


# ── Session state init ──────────────────────────────────────────────────────────

def _init_session():
    defaults = {
        "selected_breed_id": None,
        "draft": {},
        "dirty": False,
        "suggestions": {},
        "ai_loading_field": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Status helpers ──────────────────────────────────────────────────────────────

_STATUS_ICON = {
    "pending":     "⬜",
    "in_progress": "🔵",
    "reviewed":    "👁",
    "approved":    "✅",
}

_STATUS_LABEL = {
    "pending":     "Pending",
    "in_progress": "In Progress",
    "reviewed":    "Reviewed",
    "approved":    "Approved",
}


def _status_icon(status: str) -> str:
    return _STATUS_ICON.get(status or "pending", "⬜")


# ── Sidebar ─────────────────────────────────────────────────────────────────────

def render_sidebar(breeds: list[dict]) -> None:
    with st.sidebar:
        st.title("Breed Content Editor")

        total = len(breeds)
        approved = sum(1 for b in breeds if b.get("content_status") == "approved")
        st.progress(approved / total if total else 0)
        st.caption(f"{approved} / {total} approved")
        st.divider()

        status_options = ["all", "pending", "in_progress", "reviewed", "approved"]
        status_labels = ["All", "⬜ Pending", "🔵 In Progress", "👁 Reviewed", "✅ Approved"]
        filter_idx = st.selectbox(
            "Filter by status",
            options=range(len(status_options)),
            format_func=lambda i: status_labels[i],
            label_visibility="collapsed",
        )
        selected_filter = status_options[filter_idx]

        filtered = (
            breeds
            if selected_filter == "all"
            else [b for b in breeds if (b.get("content_status") or "pending") == selected_filter]
        )

        selected_id = st.session_state.selected_breed_id
        is_dirty = st.session_state.dirty

        for breed in filtered:
            icon = _status_icon(breed.get("content_status"))
            dirty_marker = " ●" if (breed["id"] == selected_id and is_dirty) else ""
            label = f"{icon} {breed['name']}{dirty_marker}"
            is_selected = breed["id"] == selected_id

            if st.button(
                label,
                key=f"btn_{breed['id']}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                if selected_id != breed["id"]:
                    _switch_breed(breed["id"])


# ── Shared AI panel ─────────────────────────────────────────────────────────────

def render_ai_panel(breed: dict, detail: dict, field_options: list[str], panel_key: str) -> None:
    st.subheader("AI Assistant")

    active_field = st.selectbox(
        "Field to work on",
        options=field_options,
        format_func=lambda f: f.replace("_", " ").title(),
        key=f"ai_field_{breed['id']}_{panel_key}",
    )

    current_text = st.session_state.draft.get(active_field, "")

    actions = {
        "generate":     "✨ Generate",
        "rewrite":      "✍️ Rewrite",
        "engaging":     "🔥 Make Engaging",
        "shorten":      "✂️ Shorten",
        "expand":       "📝 Expand",
        "improve_tone": "🎨 Improve Tone",
    }

    loading = st.session_state.ai_loading_field == active_field

    cols = st.columns(3)
    clicked_action = None
    for i, (action, label) in enumerate(actions.items()):
        with cols[i % 3]:
            if st.button(
                label,
                key=f"ai_{action}_{breed['id']}_{active_field}_{panel_key}",
                use_container_width=True,
                disabled=loading,
            ):
                clicked_action = action

    if clicked_action:
        st.session_state.ai_loading_field = active_field
        st.session_state.suggestions.pop(active_field, None)
        with st.spinner(f"Generating suggestions for {active_field.replace('_', ' ')}…"):
            try:
                suggestions = generate_suggestions(
                    clicked_action, active_field, current_text, {**breed, **detail}
                )
                st.session_state.suggestions[active_field] = suggestions
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"AI error: {e}")
        st.session_state.ai_loading_field = None
        st.rerun()

    field_suggestions = st.session_state.suggestions.get(active_field, [])
    if field_suggestions:
        st.divider()
        st.caption(f"Suggestions for **{active_field.replace('_', ' ').title()}**")
        for idx, suggestion in enumerate(field_suggestions):
            with st.container(border=True):
                st.write(suggestion)
                a_col, d_col = st.columns(2)
                with a_col:
                    if st.button(
                        "✓ Accept",
                        key=f"accept_{breed['id']}_{active_field}_{idx}_{panel_key}",
                        use_container_width=True,
                        type="primary",
                    ):
                        breed_id = breed["id"]
                        current_status = breed.get("content_status") or "pending"
                        updates = {active_field: suggestion}
                        if current_status == "pending":
                            updates["content_status"] = "in_progress"
                        save_breed_fields(breed_id, updates)
                        st.session_state.draft[active_field] = suggestion
                        st.session_state[f"accept_pending_{breed_id}_{active_field}"] = suggestion
                        st.session_state.dirty = False
                        st.session_state.suggestions.pop(active_field, None)
                        st.rerun()
                with d_col:
                    if st.button(
                        "✕ Discard",
                        key=f"discard_{breed['id']}_{active_field}_{idx}_{panel_key}",
                        use_container_width=True,
                    ):
                        remaining = [s for i, s in enumerate(field_suggestions) if i != idx]
                        if remaining:
                            st.session_state.suggestions[active_field] = remaining
                        else:
                            st.session_state.suggestions.pop(active_field, None)
                        st.rerun()


# ── Edit tab ────────────────────────────────────────────────────────────────────

def render_edit_tab(breed: dict, detail: dict) -> None:
    breed_id = breed["id"]
    status = breed.get("content_status") or "pending"

    # Init draft from DB on first load for this breed
    if not st.session_state.draft:
        st.session_state.draft = {f: detail.get(f) or "" for f in TEXT_FIELDS}
        st.session_state.dirty = False

    left, right = st.columns([0.6, 0.4])

    # ── Left: edit panel ────────────────────────────────────────────────────────
    with left:
        breeds = load_breeds()
        breed_ids = [b["id"] for b in breeds]
        current_idx = breed_ids.index(breed_id) if breed_id in breed_ids else 0

        h_col, nav_col = st.columns([0.7, 0.3])
        with h_col:
            st.subheader(breed["name"])
            st.caption(
                f"{_status_icon(status)} {_STATUS_LABEL.get(status, status)}  |  "
                f"slug: `{breed['slug']}`"
            )
        with nav_col:
            p_col, n_col = st.columns(2)
            with p_col:
                if st.button("← Prev", use_container_width=True, disabled=current_idx == 0):
                    _switch_breed(breed_ids[current_idx - 1])
            with n_col:
                if st.button("Next →", use_container_width=True, disabled=current_idx == len(breed_ids) - 1):
                    _switch_breed(breed_ids[current_idx + 1])

        st.divider()

        for field in CORE_TEXT_FIELDS:
            pending_key = f"accept_pending_{breed_id}_{field}"
            ver_key = f"ta_ver_{breed_id}_{field}"
            version = st.session_state.get(ver_key, 0)
            if pending_key in st.session_state:
                st.session_state.draft[field] = st.session_state.pop(pending_key)
                version += 1
                st.session_state[ver_key] = version
            widget_key = f"ta_{breed_id}_{field}_{version}"
            new_val = st.text_area(
                label=field.replace("_", " ").title(),
                value=st.session_state.draft[field],
                key=widget_key,
                height=100 if field not in ("description", "temperament") else 140,
            )
            if new_val != st.session_state.draft[field]:
                st.session_state.draft[field] = new_val
                st.session_state.dirty = True

        st.divider()

        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button(
                "💾 Save",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.dirty,
            ):
                _do_save(breed_id, status)

        with btn_col2:
            if st.button(
                "👁 Mark Reviewed",
                use_container_width=True,
                disabled=status != "in_progress",
            ):
                save_breed_fields(breed_id, {"content_status": "reviewed"})
                st.session_state.dirty = False
                st.rerun()

        with btn_col3:
            can_approve = status in ("in_progress", "reviewed")
            if st.button(
                "✅ Approve",
                use_container_width=True,
                disabled=not can_approve,
            ):
                save_breed_fields(breed_id, {"content_status": "approved"})
                st.session_state.dirty = False
                st.rerun()

    # ── Right: AI panel ─────────────────────────────────────────────────────────
    with right:
        render_ai_panel(breed, detail, CORE_TEXT_FIELDS, "edit")


# ── SEO tab ─────────────────────────────────────────────────────────────────────

def render_seo_tab(breed: dict, detail: dict) -> None:
    breed_id = breed["id"]
    status = breed.get("content_status") or "pending"

    # Draft is shared with edit tab — ensure it's initialised
    if not st.session_state.draft:
        st.session_state.draft = {f: detail.get(f) or "" for f in TEXT_FIELDS}
        st.session_state.dirty = False

    left, right = st.columns([0.6, 0.4])

    with left:
        st.subheader("SEO & Structured Data")
        st.caption(breed["name"])
        st.divider()

        # seo_title — text_input with char count
        _field = "seo_title"
        _pending_key = f"accept_pending_{breed_id}_{_field}"
        _ver_key = f"ta_ver_{breed_id}_{_field}"
        _version = st.session_state.get(_ver_key, 0)
        if _pending_key in st.session_state:
            st.session_state.draft[_field] = st.session_state.pop(_pending_key)
            _version += 1
            st.session_state[_ver_key] = _version
        seo_title_val = st.text_input(
            label="SEO Title",
            value=st.session_state.draft.get("seo_title", ""),
            key=f"ta_{breed_id}_seo_title_{_version}",
            help="Target: under 60 characters",
        )
        char_count = len(seo_title_val)
        color = "red" if char_count > 60 else "gray"
        st.caption(f":{color}[{char_count}/60 characters]")
        if seo_title_val != st.session_state.draft.get("seo_title", ""):
            st.session_state.draft["seo_title"] = seo_title_val
            st.session_state.dirty = True

        # meta_description — text_area with char count
        _field = "meta_description"
        _pending_key = f"accept_pending_{breed_id}_{_field}"
        _ver_key = f"ta_ver_{breed_id}_{_field}"
        _version = st.session_state.get(_ver_key, 0)
        if _pending_key in st.session_state:
            st.session_state.draft[_field] = st.session_state.pop(_pending_key)
            _version += 1
            st.session_state[_ver_key] = _version
        meta_desc_val = st.text_area(
            label="Meta Description",
            value=st.session_state.draft.get("meta_description", ""),
            key=f"ta_{breed_id}_meta_description_{_version}",
            height=80,
            help="Target: under 160 characters",
        )
        meta_chars = len(meta_desc_val)
        meta_color = "red" if meta_chars > 160 else "gray"
        st.caption(f":{meta_color}[{meta_chars}/160 characters]")
        if meta_desc_val != st.session_state.draft.get("meta_description", ""):
            st.session_state.draft["meta_description"] = meta_desc_val
            st.session_state.dirty = True

        # faq_content
        _field = "faq_content"
        _pending_key = f"accept_pending_{breed_id}_{_field}"
        _ver_key = f"ta_ver_{breed_id}_{_field}"
        _version = st.session_state.get(_ver_key, 0)
        if _pending_key in st.session_state:
            st.session_state.draft[_field] = st.session_state.pop(_pending_key)
            _version += 1
            st.session_state[_ver_key] = _version
        faq_val = st.text_area(
            label="FAQ Content",
            value=st.session_state.draft.get("faq_content", ""),
            key=f"ta_{breed_id}_faq_content_{_version}",
            height=200,
            help="Plain Q&A pairs, e.g.: Q: Are Beagles good with kids?\nA: Yes, very much so.",
        )
        if faq_val != st.session_state.draft.get("faq_content", ""):
            st.session_state.draft["faq_content"] = faq_val
            st.session_state.dirty = True

        # schema_jsonld
        _field = "schema_jsonld"
        _pending_key = f"accept_pending_{breed_id}_{_field}"
        _ver_key = f"ta_ver_{breed_id}_{_field}"
        _version = st.session_state.get(_ver_key, 0)
        if _pending_key in st.session_state:
            st.session_state.draft[_field] = st.session_state.pop(_pending_key)
            _version += 1
            st.session_state[_ver_key] = _version
        jsonld_val = st.text_area(
            label="Schema JSON-LD",
            value=st.session_state.draft.get("schema_jsonld", ""),
            key=f"ta_{breed_id}_schema_jsonld_{_version}",
            height=200,
            help="JSON-LD structured data markup for this breed.",
        )
        if jsonld_val != st.session_state.draft.get("schema_jsonld", ""):
            st.session_state.draft["schema_jsonld"] = jsonld_val
            st.session_state.dirty = True

        st.divider()

        if st.button(
            "💾 Save SEO",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.dirty,
        ):
            _do_save(breed_id, status)

    with right:
        render_ai_panel(breed, detail, SEO_FIELDS, "seo")


# ── Preview tab ─────────────────────────────────────────────────────────────────

def render_preview_tab(breed: dict, detail: dict) -> None:
    draft = st.session_state.draft or {f: detail.get(f) or "" for f in TEXT_FIELDS}

    st.subheader(breed["name"])
    st.caption(f"slug: `{breed['slug']}`")

    # Signature line callout
    sig = draft.get("signature_line", "")
    if sig:
        st.info(f"*{sig}*")

    st.divider()

    col_a, col_b = st.columns(2)

    text_left = ["description", "temperament", "exercise_needs", "grooming"]
    text_right = ["training", "coat_type", "origin", "group", "breed_type"]

    with col_a:
        for field in text_left:
            val = draft.get(field, "")
            if val:
                st.markdown(f"**{field.replace('_', ' ').title()}**")
                st.write(val)
                st.write("")

    with col_b:
        for field in text_right:
            val = draft.get(field, "")
            if val:
                st.markdown(f"**{field.replace('_', ' ').title()}**")
                st.write(val)
                st.write("")

    # SEO preview card
    seo_title = draft.get("seo_title", "")
    meta_desc = draft.get("meta_description", "")
    if seo_title or meta_desc:
        st.divider()
        st.subheader("SEO Preview")
        with st.container(border=True):
            if seo_title:
                st.markdown(f"**{seo_title} | ProudPets**")
            else:
                st.markdown(f"**{breed['name']} | ProudPets**")
            if meta_desc:
                st.caption(meta_desc)
            else:
                st.caption("*(no meta description yet)*")

    # Numeric traits in expander
    numeric_traits = [f for f in TRAIT_FIELDS if detail.get(f) is not None]
    if numeric_traits:
        with st.expander("Breed Traits (read-only)"):
            t_cols = st.columns(3)
            for i, field in enumerate(numeric_traits):
                with t_cols[i % 3]:
                    st.metric(
                        label=field.replace("_", " ").title(),
                        value=detail[field],
                    )


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _do_save(breed_id: str, current_status: str):
    updates = dict(st.session_state.draft)
    if current_status == "pending":
        updates["content_status"] = "in_progress"
    save_breed_fields(breed_id, updates)
    st.session_state.dirty = False
    st.success("Saved.")
    st.rerun()


def _switch_breed(new_id: str):
    st.session_state.selected_breed_id = new_id
    st.session_state.draft = {}
    st.session_state.dirty = False
    st.session_state.suggestions = {}
    st.session_state.ai_loading_field = None
    st.rerun()


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Breed Content Editor", layout="wide")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        st.error(
            "Missing Supabase credentials. Copy `.env.example` → `.env` and fill in "
            "`SUPABASE_URL` and `SUPABASE_SERVICE_KEY`."
        )
        st.stop()

    _init_session()
    breeds = load_breeds()
    render_sidebar(breeds)

    selected_id = st.session_state.selected_breed_id
    breed = next((b for b in breeds if b["id"] == selected_id), None)

    if breed is None:
        st.title("Breed Content Editor")
        st.info("Select a breed from the sidebar to get started.")
        return

    detail = load_breed_detail(selected_id)

    edit_tab, seo_tab, preview_tab = st.tabs(["✏️ Edit", "🔍 SEO", "👁 Preview"])
    with edit_tab:
        render_edit_tab(breed, detail)
    with seo_tab:
        render_seo_tab(breed, detail)
    with preview_tab:
        render_preview_tab(breed, detail)


if __name__ == "__main__":
    main()
