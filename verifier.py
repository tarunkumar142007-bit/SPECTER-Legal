import anthropic
import base64
import json
import re
from pathlib import Path

client = anthropic.Anthropic()

TRUST_COLORS = {
    "TRUSTED":       "green",
    "LIKELY_REAL":   "cyan",
    "SUSPICIOUS":    "yellow",
    "UNVERIFIABLE":  "dim",
    "FORGED":        "red",
}

# ── IMAGE mode — all 7 checks via Claude Vision ───────────────────────────────
VERIFIER_SYSTEM_IMAGE = """You are VERIFIER — the document authenticity checker of SPECTER Legal.
You are analysing a SCANNED or PHOTOGRAPHED legal document image.
All 7 checks are applicable. Run every one carefully using what you can see.

Return ONLY a raw JSON object (no markdown, no backticks):
{
  "input_mode": "image",
  "verification_coverage": "7/7",
  "trust_verdict": "TRUSTED|LIKELY_REAL|SUSPICIOUS|UNVERIFIABLE|FORGED",
  "trust_score": 0-100,
  "proceed_with_analysis": true|false,
  "verifier_summary": "2-3 sentence plain-English verdict on document authenticity",
  "checks": {
    "signatures":            {"status": "pass|warn|fail",    "finding": "are signatures present AND actually signed — not blank blocks?"},
    "stamps_seals":          {"status": "pass|warn|fail|na", "finding": "stamp/seal present, legible, not copy-pasted?"},
    "date_consistency":      {"status": "pass|warn|fail",    "finding": "are all dates internally consistent and logical?"},
    "party_completeness":    {"status": "pass|warn|fail",    "finding": "all named parties present with signature blocks?"},
    "document_completeness": {"status": "pass|warn|fail",    "finding": "clause numbers continuous, no missing pages, no blank fields?"},
    "document_identity":     {"status": "pass|warn|fail",    "finding": "does the document title match its content?"},
    "tampering_signals":     {"status": "pass|warn|fail",    "finding": "any inconsistent fonts, spacing, corrections, or overwriting visible?"}
  },
  "missing_clauses": ["standard clauses absent for this document type"],
  "red_flags": ["specific red flags, empty list if none"],
  "verification_note": "what the user should do before signing"
}

Trust verdict guide:
- TRUSTED:      All checks pass
- LIKELY_REAL:  Minor warnings only
- SUSPICIOUS:   Multiple warnings or one fail
- UNVERIFIABLE: Image too blurry to assess
- FORGED:       Clear signs of tampering or fabrication"""


# ── TEXT mode — 4 checks, 3 explicitly skipped ───────────────────────────────
VERIFIER_SYSTEM_TEXT = """You are VERIFIER — the document completeness checker of SPECTER Legal.
You are analysing DIGITAL TEXT of a legal document (copy-pasted or born-digital PDF).

CRITICAL RULE: Three checks require visual inspection of a physical document.
You MUST set status "skipped" for these — never guess or fabricate pass/fail:
  - signatures        → cannot see if actually signed from text
  - stamps_seals      → cannot see a physical stamp from text
  - tampering_signals → cannot detect font/spacing issues from text

Run ONLY these 4 checks that are genuinely possible from text:
1. DATE CONSISTENCY     — are signing, effective, expiry dates internally consistent?
2. PARTY COMPLETENESS   — all parties named in opening also present in signature block?
3. DOCUMENT COMPLETENESS — clause numbers continuous? blank fields? broken references?
4. DOCUMENT IDENTITY    — does the title match what the content actually says?
5. MISSING CLAUSES      — what standard clauses for this document type are absent?

Return ONLY a raw JSON object (no markdown, no backticks):
{
  "input_mode": "text",
  "verification_coverage": "4/7",
  "trust_verdict": "TRUSTED|LIKELY_REAL|SUSPICIOUS|UNVERIFIABLE",
  "trust_score": 0-100,
  "proceed_with_analysis": true|false,
  "verifier_summary": "2-3 sentence verdict focused on completeness and structure",
  "checks": {
    "signatures":            {"status": "skipped", "finding": "Requires scanned image — cannot verify from text."},
    "stamps_seals":          {"status": "skipped", "finding": "Requires scanned image — cannot verify from text."},
    "date_consistency":      {"status": "pass|warn|fail", "finding": "one sentence finding"},
    "party_completeness":    {"status": "pass|warn|fail", "finding": "one sentence finding"},
    "document_completeness": {"status": "pass|warn|fail", "finding": "one sentence finding"},
    "document_identity":     {"status": "pass|warn|fail", "finding": "one sentence finding"},
    "tampering_signals":     {"status": "skipped", "finding": "Requires scanned image — cannot verify from text."}
  },
  "missing_clauses": ["specific clauses missing for this document type"],
  "red_flags": ["structural or logical issues found, empty list if none"],
  "scan_prompt": "Upload a scanned image to unlock full 7/7 verification including tampering detection and signature checks.",
  "verification_note": "what the user should do before signing"
}

Trust verdict (text mode — FORGED not available without visual proof):
- TRUSTED:      All 4 checks pass, no missing critical clauses
- LIKELY_REAL:  Minor warnings only
- SUSPICIOUS:   Structural issues — bad dates, missing parties, clause gaps
- UNVERIFIABLE: Text too incomplete to assess"""


# ── Public API ────────────────────────────────────────────────────────────────

def verify_from_image(image_path: str) -> dict:
    """Verify a scanned contract from a local file path. All 7 checks."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    ext = path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp", ".gif": "image/gif",
    }
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    return verify_from_base64(image_data, media_type_map.get(ext, "image/jpeg"))


def verify_from_base64(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """Verify from base64-encoded image. All 7 checks including visual ones."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=VERIFIER_SYSTEM_IMAGE,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Verify this scanned legal document. Run all 7 authenticity checks."}
            ]
        }]
    )
    return _parse_response(response)


def verify_from_text(document_text: str, document_type: str = "auto") -> dict:
    """Verify from digital text. 4 text-based checks only. 3 visual checks marked skipped."""
    doc_hint = f" (document type: {document_type})" if document_type != "auto" else ""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=VERIFIER_SYSTEM_TEXT,
        messages=[{
            "role": "user",
            "content": f"Verify this digital legal document{doc_hint}:\n\n{document_text[:4000]}"
        }]
    )
    return _parse_response(response)


def _parse_response(response) -> dict:
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {
            "input_mode": "unknown",
            "verification_coverage": "0/7",
            "trust_verdict": "UNVERIFIABLE",
            "trust_score": 0,
            "proceed_with_analysis": True,
            "verifier_summary": "VERIFIER could not parse response. Proceeding with analysis.",
            "checks": {k: {"status": "skipped", "finding": "Parse error."} for k in [
                "signatures", "stamps_seals", "date_consistency",
                "party_completeness", "document_completeness",
                "document_identity", "tampering_signals"
            ]},
            "missing_clauses": [],
            "red_flags": ["VERIFIER parse failed — manual review recommended"],
            "verification_note": "Could not verify automatically. Review manually before signing."
        }


def get_trust_color(verdict: str) -> str:
    return TRUST_COLORS.get(verdict, "white")


def should_block_analysis(verifier_data: dict) -> bool:
    """Block pipeline only on FORGED (image mode only)."""
    return verifier_data.get("trust_verdict") == "FORGED"
