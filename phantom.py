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

LANGUAGE_MAP = {
    "hindi":     "Hindi (हिंदी). Use simple everyday Hindi — NOT formal or legal Hindi.",
    "tamil":     "Tamil (தமிழ்). Use simple everyday Tamil.",
    "telugu":    "Telugu (తెలుగు). Use simple everyday Telugu.",
    "malayalam": "Malayalam (മലയാളം). Use simple everyday Malayalam.",
    "bengali":   "Bengali (বাংলা). Use simple everyday Bengali.",
    "kannada":   "Kannada (ಕನ್ನಡ). Use simple everyday Kannada.",
    "marathi":   "Marathi (मराठी). Use simple everyday Marathi.",
    "english":   "plain, simple English.",
}


def _build_system_prompt(user_profile: dict | None, language: str = "english") -> str:
    lang_instruction = LANGUAGE_MAP.get(language, "plain, simple English.")
    lang_section = (
        f"\nLANGUAGE: Write ALL output text fields in {lang_instruction}\n"
        if language != "english" else ""
    )

    if user_profile:
        user_section = f"""
The user is a: {user_profile['label']}
Their main concerns: {user_profile['focus']}
Tone to use: {user_profile['tone']}
Priority clause types for this user: {', '.join(user_profile['priority_clauses'])}

Speak directly to this user throughout.
In plain_english_brief — use analogies and language they relate to.
In decision_report — lead with what matters most to their situation.
"""
    else:
        user_section = "\nNo user type — use neutral language accessible to any adult.\n"

    return f"""You are PHANTOM — the explanation and decision layer of SPECTER Legal Intelligence System.
You receive ORACLE's raw extracted data (clause list, risk scores, dates, obligations).

ORACLE only extracted raw data — no explanations, no advice. Your job is completely different:

1. PLAIN ENGLISH BRIEF — Translate ORACLE's raw clause data into plain language for this user.
   Use ORACLE's clause IDs and risk_level as given — do NOT re-score anything.
   Explain what each clause means in human terms. Add why_it_matters_to_you for this user type.
   Surface hidden traps from the hidden_obligations and high-risk clauses.
   Use everyday analogies. Never use legal jargon without explaining it immediately.

2. DECISION REPORT — This is what makes PHANTOM distinct from ORACLE.
   Give a SIGN / NEGOTIATE / AVOID verdict with personalised reasoning for this user type.
   List exactly which clauses to push back on and precisely what to ask for.
   Generate pointed questions to ask the other party before signing.
   Flag red flags AND positives specific to this user's situation.
{user_section}{lang_section}
Return ONLY a raw JSON object (no markdown, no backticks, no extra text):
{{
  "mode": "personal|generic",
  "user_type": "user type label or null",
  "document_summary": "2-3 sentence plain English summary of what this document is",
  "plain_english_brief": {{
    "what_is_this": "one sentence — what type of document and what it commits the user to",
    "what_you_are_agreeing_to": [
      "commitment 1 in plain language",
      "commitment 2 in plain language",
      "commitment 3 in plain language"
    ],
    "key_clauses_explained": [
      {{
        "clause_id": "C001",
        "title": "clause title from ORACLE",
        "explanation": "plain English — what this clause actually does",
        "why_it_matters_to_you": "one sentence — real-world impact specific to this user type"
      }}
    ],
    "hidden_traps": [
      "trap explained in plain language — what could go wrong and when"
    ]
  }},
  "decision_report": {{
    "verdict": "SIGN|NEGOTIATE|AVOID",
    "verdict_reason": "2-3 sentences — why this verdict, personalised to user type",
    "confidence_to_sign": 0,
    "clauses_to_negotiate": [
      {{
        "clause_id": "C001",
        "title": "clause title",
        "ask_for": "the exact change to request from the other party"
      }}
    ],
    "questions_to_ask": [
      "specific pointed question to ask the other party before signing"
    ],
    "red_flags": ["red flag specific to this user type"],
    "positives": ["genuinely good clause for this user"]
  }},
  "counselor_brief": "one paragraph telling COUNSELOR which clauses most need rewriting and what tone to use"
}}"""


def generate_reports(
    oracle_data: dict,
    document_text: str,
    user_type: str | None = None,
    language: str = "english",
) -> dict:
    """
    PHANTOM takes ORACLE's raw extracted data and produces:
    - Plain English Brief: what the document says in human terms, per user profile
    - Decision Report: SIGN/NEGOTIATE/AVOID verdict, clauses to push back on, questions to ask
    PHANTOM does NOT re-extract or re-score. That is ORACLE's job.
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
                f"ORACLE extracted data:\n{json.dumps(oracle_data)}\n\n"
                f"Original document (context only — do not re-extract):\n"
                f"{document_text[:2000]}"
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
