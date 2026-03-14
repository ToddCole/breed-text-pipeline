import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CORE_TEXT_FIELDS = [
    "description", "temperament", "exercise_needs", "grooming",
    "training", "coat_type", "origin", "group", "breed_type",
    "signature_line",
]

SEO_FIELDS = [
    "seo_title", "meta_description", "faq_content", "schema_jsonld",
]

TEXT_FIELDS = CORE_TEXT_FIELDS + SEO_FIELDS

TRAIT_FIELDS = [
    "size",
    "energy_level", "good_with_kids", "training_ease", "grooming_needs",
    "barking_level", "shedding_level", "apartment_friendly", "good_with_pets",
    "drooling_tendency", "separation_anxiety_risk", "climate_suitability",
    "noise_sensitivity", "heat_tolerance", "cold_tolerance",
    "weight_min", "weight_max", "height_min", "height_max",
    "lifespan_min", "lifespan_max", "optimal_temp_min", "optimal_temp_max",
]

_TOKEN_LIMITS = {
    "signature_line":   60,
    "seo_title":        60,
    "meta_description": 120,
    "faq_content":      800,
    "schema_jsonld":    600,
    "description":      400,
    "temperament":      80,
    "exercise_needs":   80,
    "grooming":         80,
    "training":         60,
    # Single-word fields
    "coat_type":        10,
    "origin":           10,
    "group":            10,
    "breed_type":       10,
}
_DEFAULT_TOKEN_LIMIT = 400

_TARGET_LENGTHS = {
    "description":     "2–3 paragraphs, ~250–300 words — cover heritage, personality, and honest trade-offs",
    "temperament":     "1–2 punchy sentences — capture the personality, not a trait list",
    "exercise_needs":  "ONE short sentence, 18–22 words max — specific daily requirement, dry and honest",
    "grooming":        "1–2 sentences — practical and specific, one touch of humour",
    "training":        "1 sentence if possible — wry and honest about what owners are in for",
    "coat_type":       "one word only (e.g. Smooth, Wiry, Curly, Double, Silky)",
    "origin":          "one word only — the country of origin (e.g. Germany, France)",
    "group":           "one word only (e.g. Toy, Herding, Sporting, Hound, Working)",
    "breed_type":      "one word only (e.g. Purebred, Hybrid)",
    "signature_line":  "one punchy sentence, 15 words max",
    "seo_title":       "under 60 characters",
    "meta_description": "under 160 characters",
    "faq_content":     "3–5 Q&A pairs as plain text",
    "schema_jsonld":   "valid JSON-LD markup for a dog breed",
}


_SYSTEM_PROMPT = """\
You are the editorial voice of Pawfect Match, a smart, funny, dog-loving breed discovery platform.

You write like a sharp magazine editor who knows dogs and has no patience for generic pet-site sludge.

Your tone:
- warm
- observant
- dryly funny
- specific
- affectionate without being sentimental

Core rules:
- Every line must sound human-written, not AI-smoothed or bland.
- Prefer concrete images, comparisons and observations over abstract praise.
- If a sentence could apply to 20 other breeds, rewrite it.
- If a phrase sounds like a pet insurance website, delete it.
- Humour should come from truth, not gimmicks.

Never use phrases like:
- loyal companion
- great family pet
- highly intelligent breed
- affectionate and playful
- eager to please
- thrives with proper training
- active household
- protective nature
- early socialisation is important
- regular grooming required
- needs plenty of exercise

Style requirements:
- Use clean Australian/British English spelling.
- Use metric units only: kg, cm, km.
- No headings, labels, markdown, quotation marks or preamble.
- Respond with only the requested content.

Good writing in this voice sounds like:
Training an Anatolian Shepherd is less like teaching a student and more like negotiating with a seasoned colleague who’s been doing the job longer than you have.

At times it seems capable of generating enough loose fur to build another dog entirely.

The coat appears immune to grooming trends. Brush it, tidy it, admire it. It will still look like it just finished supervising livestock in a light breeze.

Before finalising, silently check:
1. Does this sound specific to this breed?
2. Does it contain at least one concrete observation or image?
3. Would a good human editor actually write it this way?
4. Is any phrase generic enough to belong on a thousand dog blogs?

If any answer is no, rewrite it before responding.
"""

_ACTION_INSTRUCTIONS = {
    "generate":      "Write a {field} for this breed in Pawfect Match tone. Aim for {target_length}.",
    "rewrite":       "Rewrite the following {field} in Pawfect Match tone — keep the facts, lift the voice.",
    "engaging":      "Make this {field} more vivid and characterful. Stay accurate, sharpen the wit.",
    "shorten":       "Tighten to roughly half the length. Cut padding, keep personality.",
    "expand":        "Expand with more specific, useful detail. Keep the Pawfect Match voice throughout.",
    "improve_tone":  "Rewrite in Pawfect Match tone — warm, witty, specific, never generic.",
}

_ACTIONS_WITH_CURRENT = {"rewrite", "engaging", "shorten", "expand", "improve_tone"}

# Extra per-field instructions appended to the prompt (verify facts, constrain format)
_FIELD_NOTES = {
    "exercise_needs": (
    "Be specific about the daily exercise reality for this breed. Avoid vague phrases like 'needs plenty of exercise'. "
    "Say what kind of activity suits them and what happens when they don't get enough. Tie the need for exercise to "
    "the breed's original job or temperament where possible. One dry, accurate line is better than two generic ones."
    ),
    "grooming": (
        "Be specific to this breed's actual coat type and maintenance reality. "
        "Avoid generic phrases like 'regular grooming required' or 'brush weekly'. "
        "Find the angle that makes this breed's grooming situation distinct — "
        "the irony, the hidden catch, the surprising ease, the time commitment, the smell, "
        "the shed-to-owner-sanity ratio. One specific observation beats three vague ones. "
        "Do NOT copy or echo the examples — use them only to calibrate tone and specificity."
    ),
    "training": (
        "Be honest and breed-specific. Capture what owners actually experience — "
        "the stubbornness, the bribability, the selective attention, the surprising aptitude "
        "or the humbling independence. Avoid generic praise ('highly intelligent', 'eager to please') "
        "unless it's earned with a specific observation that makes it feel true. "
        "One wry, accurate sentence beats two bland ones. "
        "Do NOT copy or echo the examples — use them only to calibrate tone and specificity."
    ),
    "origin":     (
        "Verify the breed's true country of origin from your knowledge. "
        "Return only that single country name — no explanation, no extra words."
    ),
    "breed_type": (
        "Verify whether this is a recognised purebred or a hybrid/mixed breed. "
        "Return only the single correct term (e.g. Purebred) — no explanation."
    ),
}


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-key-here":
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def build_trait_summary(breed: dict) -> str:
    parts = []
    for field in TRAIT_FIELDS:
        val = breed.get(field)
        if val is not None and val != "":
            parts.append(f"{field.replace('_', ' ')}: {val}")
    return ", ".join(parts) if parts else "no trait data available"


def build_user_prompt(action: str, field: str, current_text: str, breed: dict) -> str:
    target_length = _TARGET_LENGTHS.get(field, "an appropriate length")
    instruction = _ACTION_INSTRUCTIONS[action].format(
        field=field.replace("_", " "),
        target_length=target_length,
    )

    prefix = f"Breed: {breed.get('name', 'Unknown')}\nTraits: {build_trait_summary(breed)}\n\n"

    field_note = _FIELD_NOTES.get(field, "")

    if action in _ACTIONS_WITH_CURRENT and current_text.strip():
        base = f"{prefix}{instruction}\n\nCurrent text:\n{current_text.strip()}"
    else:
        base = f"{prefix}{instruction}"

    return f"{base}\n\n{field_note}" if field_note else base


def _call_api(action: str, field: str, current_text: str, breed: dict) -> str:
    client = get_anthropic_client()
    prompt = build_user_prompt(action, field, current_text, breed)
    max_tokens = _TOKEN_LIMITS.get(field, _DEFAULT_TOKEN_LIMIT)

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_suggestions(
    action: str,
    field: str,
    current_text: str,
    breed: dict,
    n: int = 1,
) -> list[str]:
    """Return n suggestions by running n API calls near-concurrently."""
    with ThreadPoolExecutor(max_workers=n) as executor:
        futures = [
            executor.submit(_call_api, action, field, current_text, breed)
            for _ in range(n)
        ]
        results = [f.result() for f in futures]
    return results
