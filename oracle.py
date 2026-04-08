import anthropic
import json

client = anthropic.Anthropic()

ORACLE_SYSTEM = """You are ORACLE — a predictive contract risk engine inside the SPECTER Legal Intelligence System.
Scan legal documents and identify ALL risks, obligations, traps, and unfavourable clauses.
Assign risk scores based on how unfavourable each clause is to the person signing.

Return ONLY a raw JSON object (no markdown, no backticks, no extra text):
{
  "document_type": "rental agreement|employment contract|freelance contract|terms and conditions|NDA|other",
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
      "original_text": "exact quote from document max 80 words",
      "plain_english": "what this clause actually means in one sentence",
      "why_risky": "why this is dangerous for the signer",
      "favourable_to": "signer|other_party|neutral"
    }
  ],
  "hidden_obligations": ["obligation 1", "obligation 2"],
  "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "oracle_assessment": "2-3 sentence cold analytical verdict on this document"
}"""


def analyze(document_text: str, document_type: str = "auto") -> dict:
    """
    ORACLE scans a legal document for all risks, obligations, and dangerous clauses.
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=ORACLE_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Analyse this legal document"
                f"{' (type: ' + document_type + ')' if document_type != 'auto' else ''}:\n\n"
                f"{document_text}"
            )
        }]
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
