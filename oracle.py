import anthropic
import json

client = anthropic.Anthropic()

ORACLE_SYSTEM = """You are ORACLE — the data extraction engine of SPECTER Legal Intelligence System.
Your ONLY job is to extract structured data from the legal document.
Do NOT explain, summarise, or advise. Just extract facts and scores.
PHANTOM will do all explanation. COUNSELOR will do all advising.

Return ONLY a raw JSON object (no markdown, no backticks, no extra text):
{
  "document_type": "rental_agreement|employment_contract|freelance_contract|terms_and_conditions|nda|service_agreement|other",
  "parties": [
    {"role": "employer|employee|landlord|tenant|client|contractor|party_a|party_b", "name": "extracted name or null"}
  ],
  "effective_date": "extracted date or null",
  "expiry_date": "extracted date or null",
  "duration": "extracted duration string or null",
  "overall_risk_score": 0-100,
  "signing_risk": 0-100,
  "financial_risk": 0-100,
  "legal_obligation_risk": 0-100,
  "exit_difficulty_risk": 0-100,
  "risk_verdict": "CRITICAL|HIGH|MEDIUM|LOW",
  "clauses": [
    {
      "id": "C001",
      "title": "short clause name",
      "type": "penalty|termination|auto_renewal|liability|data_sharing|ip_ownership|payment|non_compete|confidentiality|other",
      "risk_level": "critical|high|medium|low",
      "original_text": "exact quote from document, max 80 words",
      "favourable_to": "signer|other_party|neutral"
    }
  ],
  "key_dates": [
    {"label": "what this date is", "date": "the date", "clause_id": "C001"}
  ],
  "financial_obligations": [
    {"label": "what must be paid", "amount": "amount or null", "trigger": "when it applies", "clause_id": "C001"}
  ],
  "hidden_obligations": ["obligation 1", "obligation 2"],
  "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0}
}"""


def analyze(document_text: str, document_type: str = "auto") -> dict:
    """
    ORACLE extracts raw structured data from a legal document.
    No explanations — just facts, scores, and clause metadata.
    PHANTOM receives this and does all explanation and decision-making.
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=ORACLE_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Extract all structured data from this legal document"
                f"{' (type: ' + document_type + ')' if document_type != 'auto' else ''}:\n\n"
                f"{document_text}"
            )
        }]
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
