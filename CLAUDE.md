# Proud Pets Text Pipeline

## Project Overview
A Streamlit editor for breed text content. Reads/writes directly to the Supabase `breeds` table. Integrates Claude AI for generating and improving field copy.

## Structure
- `app.py` — main Streamlit UI (sidebar, edit/SEO/preview tabs, AI panel)
- `ai_assistant.py` — Claude API helpers (prompt building, parallel suggestion generation)
- `requirements.txt` — dependencies
- `.env` — credentials (not committed)

## Running
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supabase Schema

### Editable text fields (in `ai_assistant.py`)

**Core text fields** (Edit tab):
`description`, `temperament`, `exercise_needs`, `grooming`, `training`, `coat_type`, `origin`, `group`, `breed_type`, `signature_line`

**SEO fields** (SEO tab):
`seo_title`, `meta_description`, `faq_content`, `schema_jsonld`

**Status field**: `content_status` — `pending | in_progress | reviewed | approved`

### Numeric/trait fields (AI context only, not edited here)
`size`, `energy_level`, `good_with_kids`, `training_ease`, `grooming_needs`, `barking_level`, `shedding_level`, `apartment_friendly`, `good_with_pets`, `drooling_tendency`, `separation_anxiety_risk`, `climate_suitability`, `noise_sensitivity`, `heat_tolerance`, `cold_tolerance`, `weight_min/max`, `height_min/max`, `lifespan_min/max`, `optimal_temp_min/max`

## Required SQL Migration (run once in Supabase SQL editor)
```sql
-- New columns (content_status and signature_line/SEO may already exist — IF NOT EXISTS is safe)
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS content_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS signature_line TEXT;
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS seo_title TEXT;
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS meta_description TEXT;
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS faq_content TEXT;
ALTER TABLE breeds ADD COLUMN IF NOT EXISTS schema_jsonld TEXT;

-- Safe constraint (skip if already exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'breeds_content_status_check'
  ) THEN
    ALTER TABLE breeds ADD CONSTRAINT breeds_content_status_check
      CHECK (content_status IN ('pending', 'in_progress', 'reviewed', 'approved'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS breeds_content_status_idx ON breeds (content_status);
```

Also add to `.env`:
```
ANTHROPIC_API_KEY=your-key-here
```

## Status Workflow
- `pending → in_progress` — auto on Save
- `in_progress → reviewed` — "Mark Reviewed" button
- `reviewed / in_progress → approved` — "Approve" button

## AI Suggestions
- Uses `claude-opus-4-6` via Anthropic API
- Generates 2 suggestions in parallel (ThreadPoolExecutor)
- Token limits: `signature_line`/`seo_title` → 60, `meta_description` → 120, `faq_content` → 800, `schema_jsonld` → 600, all others → 400
- Actions: generate, rewrite, make engaging, shorten, expand, improve tone

## Key Patterns
- `draft` in session state is the single source of truth for text areas
- Widget keys include `breed_id` — forces fresh widget on breed switch
- On breed switch: clear draft, suggestions, dirty flag, then `st.rerun()`
- Draft init guard: only re-init from DB when `draft` is empty `{}`
- Edit tab shows `CORE_TEXT_FIELDS`; SEO tab shows `SEO_FIELDS`; both share the same `draft` dict
