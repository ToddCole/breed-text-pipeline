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
    # Short-form fields — target 35 words, 80 tokens gives headroom without chopping
    "exercise_needs":   80,
    "grooming":         80,
    "training":         80,
    "coat_type":        80,
    "origin":           80,
    "group":            50,
    "breed_type":       50,
}
_DEFAULT_TOKEN_LIMIT = 400

_TARGET_LENGTHS = {
    "description":     "3–4 sentences",
    "temperament":     "2–3 sentences",
    "exercise_needs":  "35 words max — one or two tight sentences",
    "grooming":        "35 words max — one or two tight sentences",
    "training":        "35 words max — one or two tight sentences",
    "coat_type":       "35 words max — one tight sentence",
    "origin":          "35 words max — one tight sentence",
    "group":           "a short phrase",
    "breed_type":      "a short phrase",
    "signature_line":  "one punchy sentence, 15 words max",
    "seo_title":       "under 60 characters",
    "meta_description": "under 160 characters",
    "faq_content":     "3–5 Q&A pairs as plain text",
    "schema_jsonld":   "valid JSON-LD markup for a dog breed",
}

_SYSTEM_PROMPT = (
    "You are a dog breed content writer. Voice: warm, helpful, informative. "
    "Dog-lover tone. Plain English. No hype words. "
    "Respond with ONLY the content — no preamble, no labels, no quotes around the text."
)

_ACTION_INSTRUCTIONS = {
    "generate":      "Write a {field} for this breed. Aim for {target_length}.",
    "rewrite":       "Rewrite the following {field}, keeping facts but improving clarity.",
    "engaging":      "Make this {field} more engaging and vivid while staying accurate.",
    "shorten":       "Shorten to roughly half its length, keeping key points.",
    "expand":        "Expand with more useful detail for someone considering this breed.",
    "improve_tone":  "Rewrite to better match a warm, friendly tone without losing accuracy.",
}

_ACTIONS_WITH_CURRENT = {"rewrite", "engaging", "shorten", "expand", "improve_tone"}


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

    if action in _ACTIONS_WITH_CURRENT and current_text.strip():
        return f"{prefix}{instruction}\n\nCurrent text:\n{current_text.strip()}"

    return f"{prefix}{instruction}"


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
