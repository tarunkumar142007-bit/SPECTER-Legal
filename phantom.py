import anthropic
import json

client = anthropic.Anthropic()

# ── User Type Profiles ────────────────────────────────────────────────────────
USER_PROFILES = {
    "student": {
        "label": "Student",
        "focus": "hostel agreements, internship contracts, tuition terms",
        "tone": "simple and reassuring, explain every legal term, avoid jargon completely",
        "priority_clauses": ["auto_renewal", "penalty", "termination"],
        "icon": "ST",
    },
    "freelancer": {
        "label": "Freelancer / Contractor",
        "focus": "payment terms, IP ownership, project scope, termination",
        "tone": "direct and practical, focus on money and rights, peer-level",
        "priority_clauses": ["payment", "ip_ownership", "termination", "non_compete"],
        "icon": "FL",
    },
    "employee": {
        "label": "Employee",
        "focus": "salary, non-compete, notice period, data clauses, benefits",
        "tone": "balanced and thorough, highlight long-term implications",
        "priority_clauses": ["non_compete", "confidentiality", "termination", "liability"],
        "icon": "EM",
    },
    "tenant": {
        "label": "Tenant / Renter",
        "focus": "deposit, maintenance responsibility, early exit penalties, rent increases",
        "tone": "warm and clear, explain tenant rights, flag landlord-favoured terms",
        "priority_clauses": ["penalty", "termination", "payment", "liability"],
        "icon": "TN",
    },
    "founder": {
        "label": "Startup Founder",
        "focus": "equity, IP assignment, liability caps, data sharing, exit clauses",
        "tone": "terse and technical, respect expertise, flag business-critical terms",
        "priority_clauses": ["ip_ownership", "liability", "data_sharing", "termination"],
        "icon": "FD",
    },
}

MANAGER_PROFILE = {
    "sign_off": "— SPECTER Legal Intelligence System",
    "tone": "professional, objective, action-first",
}

# FEATURE 2: Language map
LANGUAGE_MAP = {
    "hindi":   "Hindi (हिंदी). Use simple everyday Hindi — NOT formal or legal Hindi.",
    "tamil":   "Tamil (தமிழ்). Use simple everyday Tamil.",
    "telugu":  "Telugu (తెలుగు). Use simple everyday Telugu.",
    "english": "plain, simple English.",
}


def _build_system_prompt(user_profile: dict | None, language: str = "english") -> str:
    # FEATURE 2: Language instruction injected into prompt
    lang_instruction = LANGUAGE_MAP.get(language, "plain, simple English.")
    lang_section = f"\nLANGUAGE: Write ALL output text fields in {lang_instruction}\n" if language != "english" else ""

    if user_profile:
        user_section = f"""
The user is a: {user_profile['label']}
Their main concerns: {user_profile['focus']}
Tone to use: {user_profile['tone']}
Priority clause types to highlight: {', '.join(user_profile['priority_clauses'])}

Tailor BOTH reports specifically for this user type.
In the plain English brief — speak directly to them.
In the decision report — prioritise what matters most to their situation.
"""
    else:
        user_section = """
No specific user type provided — use neutral, clear language accessible to any adult.
"""

    return f"""You are PHANTOM — the explanation and decision layer of SPECTER Legal Intelligence System.
You receive ORACLE's risk assessment of a legal document and generate TWO reports:

1. PLAIN ENGLISH BRIEF — Translate the legal document into simple, clear language.
   - Explain what the document actually says, clause by clause
   - Use everyday analogies where helpful
   - Never use legal jargon without immediately explaining it
   - Be honest about risks without being alarmist

2. DECISION REPORT — Help the user decide what to do.
   - Give a clear SIGN / NEGOTIATE / AVOID verdict with reasoning
   - List exactly which clauses to push back on and why
   - Suggest specific questions to ask the other party
   - Give a confidence score for signing (0-100%)
{user_section}{lang_section}
Return ONLY a raw JSON object (no markdown, no backticks, no extra text):
{{
  "mode": "personal|generic",
  "user_type": "user type label or null",
  "document_summary": "2-3 sentence plain English summary of what this document is",
  "plain_english_brief": {{
    "what_is_this": "one sentence — what type of document and what it covers",
    "what_you_are_agreeing_to": ["commitment 1", "commitment 2", "commitment 3"],
    "key_clauses_explained": [
      {{"clause_id": "C001", "title": "clause title", "explanation": "plain English explanation"}}
    ],
    "hidden_traps": ["trap 1 explained simply", "trap 2 explained simply"]
  }},
  "decision_report": {{
    "verdict": "SIGN|NEGOTIATE|AVOID",
    "verdict_reason": "2-3 sentences explaining the verdict",
    "confidence_to_sign": 0,
    "clauses_to_negotiate": [
      {{"clause_id": "C001", "title": "title", "ask_for": "what to request instead"}}
    ],
    "questions_to_ask": ["question 1", "question 2", "question 3"],
    "red_flags": ["red flag 1", "red flag 2"],
    "positives": ["positive clause 1", "positive clause 2"]
  }},
  "counselor_brief": "one paragraph briefing for COUNSELOR on what rewrites are most needed"
}}"""


def generate_reports(
    oracle_data: dict,
    document_text: str,
    user_type: str | None = None,
    language: str = "english",        # FEATURE 2: language parameter
) -> dict:
    """
    PHANTOM reads ORACLE's report and generates:
    - Plain English Brief (what the document says, simply)
    - Decision Report (should you sign? what to negotiate?)

    Modes:
    - Personal: tailored to a specific user type (student/freelancer/employee/tenant/founder)
    - Generic: neutral language for any user

    Languages supported: english, hindi, tamil, telugu
    """
    user_profile = None
    if user_type:
        user_profile = USER_PROFILES.get(user_type.strip().lower())

    system_prompt = _build_system_prompt(user_profile, language)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": (
                f"ORACLE risk report:\n{json.dumps(oracle_data)}\n\n"
                f"Original document:\n{document_text[:3000]}"
            )
        }]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    result = json.loads(raw)

    result["_meta"] = {
        "mode": "personal" if user_profile else "generic",
        "user_type_key": user_type,
        "user_profile": user_profile,
        "language": language,
    }
    return result


def get_user_profile(key: str) -> dict | None:
    return USER_PROFILES.get(key.strip().lower())


def list_user_types() -> list:
    return list(USER_PROFILES.keys())
