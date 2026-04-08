import anthropic
import json

client = anthropic.Anthropic()

# FEATURE 2: Language map
LANGUAGE_MAP = {
    "hindi":   "Hindi (हिंदी). Use simple everyday Hindi — NOT formal or legal Hindi.",
    "tamil":   "Tamil (தமிழ்). Use simple everyday Tamil.",
    "telugu":  "Telugu (తెలుగు). Use simple everyday Telugu.",
    "malayalam": "Malayalam (മലയാളം). Use simple everyday Malayalam.",
    "bengali": "Bengali (বাংলা). Use simple everyday Bengali.",
    "kannada": "Kannada (ಕನ್ನಡ). Use simple everyday Kannada.",
    "marathi": "Marathi (मराठी). Use simple everyday Marathi.",
    "english": "plain, simple English.",
}

COUNSELOR_SYSTEM_BASE = """You are COUNSELOR — the action engine of SPECTER Legal Intelligence System.
You receive a legal document risk assessment and PHANTOM's analysis.
Your job is to produce THREE actionable outputs:

1. REWRITTEN CLAUSES — Rewrite the most dangerous clauses in fairer language the user can propose.
2. NEGOTIATION SCRIPT — A word-for-word script the user can say/send to push back on risky terms.
3. FINAL CHECKLIST — A before-you-sign checklist personalised to this document.

Return ONLY a raw JSON object (no markdown, no backticks, no extra text):
{{
  "rewritten_clauses": [
    {{
      "clause_id": "C001",
      "title": "clause title",
      "original_summary": "what the original clause said",
      "rewritten": "the fairer version of this clause in plain legal-ish language",
      "why_better": "one sentence: how this protects the signer"
    }}
  ],
  "negotiation_script": {{
    "opening": "how to start the conversation with the other party",
    "key_asks": [
      {{"ask": "specific change to request", "justification": "why this is reasonable"}}
    ],
    "closing": "how to end the negotiation message professionally"
  }},
  "before_you_sign_checklist": [
    {{"item": "checklist item", "why": "why this matters", "done": false}}
  ],
  "counselor_verdict": "final one-paragraph plain-English advice on whether and how to proceed"
}}"""


def advise(
    oracle_data: dict,
    phantom_data: dict,
    document_text: str,
    language: str = "english",        # FEATURE 2: language parameter
) -> dict:
    """
    COUNSELOR produces:
    - Rewritten versions of risky clauses
    - A negotiation script the user can actually send
    - A before-you-sign checklist
    - A final plain-English verdict

    Languages supported: english, hindi, tamil, telugu, malayalam, bengali, kannada, marathi
    """
    # FEATURE 2: Inject language instruction into system prompt
    lang_instruction = LANGUAGE_MAP.get(language, "plain, simple English.")
    lang_note = f"\nLANGUAGE: Write ALL text fields (opening, verdict, checklist items, etc.) in {lang_instruction}\n" if language != "english" else ""

    system = COUNSELOR_SYSTEM_BASE + lang_note

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system,
        messages=[{
            "role": "user",
            "content": (
                f"ORACLE risk report:\n{json.dumps(oracle_data)}\n\n"
                f"PHANTOM analysis:\n{json.dumps({k: v for k, v in phantom_data.items() if k != '_meta'})}\n\n"
                f"Original document excerpt:\n{document_text[:2000]}"
            )
        }]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
