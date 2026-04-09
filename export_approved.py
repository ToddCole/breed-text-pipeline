"""
Export all approved breeds to a markdown file for use as Claude Project knowledge.

Usage:
    python export_approved.py [output_file]

Output defaults to: approved_breeds_export.md
"""

import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from ai_assistant import CORE_TEXT_FIELDS, SEO_FIELDS, TRAIT_FIELDS  # noqa: E402


def main():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)

    sb = create_client(url, key)

    all_fields = ["name", "slug"] + CORE_TEXT_FIELDS + SEO_FIELDS + TRAIT_FIELDS
    resp = (
        sb.table("breeds")
        .select(",".join(all_fields))
        .eq("content_status", "approved")
        .order("name")
        .execute()
    )
    breeds = resp.data or []

    if not breeds:
        print("No approved breeds found.")
        sys.exit(0)

    out_path = sys.argv[1] if len(sys.argv) > 1 else "approved_breeds_export.md"

    lines = [
        "# Pawfect Match — Approved Breed Copy",
        f"_Exported {date.today()} · {len(breeds)} breeds_",
        "",
        "Use this document as reference for voice, tone, and format when writing new breed copy.",
        "Every entry below has been human-reviewed and approved.",
        "",
    ]

    for breed in breeds:
        name = breed.get("name", "Unknown")
        lines.append(f"---\n\n## {name}")
        lines.append(f"**Slug:** `{breed.get('slug', '')}`\n")

        # Core text fields
        for field in CORE_TEXT_FIELDS:
            val = (breed.get(field) or "").strip()
            if val:
                label = field.replace("_", " ").title()
                lines.append(f"**{label}:** {val}\n")

        # SEO fields
        seo_vals = {f: (breed.get(f) or "").strip() for f in SEO_FIELDS}
        if any(seo_vals.values()):
            lines.append("**SEO:**")
            for field in SEO_FIELDS:
                val = seo_vals[field]
                if val:
                    label = field.replace("_", " ").title()
                    lines.append(f"- {label}: {val}")
            lines.append("")

        # Trait summary (compact)
        trait_parts = []
        for field in TRAIT_FIELDS:
            val = breed.get(field)
            if val is not None:
                trait_parts.append(f"{field.replace('_', ' ')}: {val}")
        if trait_parts:
            lines.append(f"**Traits:** {', '.join(trait_parts)}\n")

        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Exported {len(breeds)} approved breeds to: {out_path}")


if __name__ == "__main__":
    main()
