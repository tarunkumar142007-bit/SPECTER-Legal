import anthropic
import base64
import json
import re
from pathlib import Path

client = anthropic.Anthropic()

# ── Verdict colours used by briefing.py ──────────────────────────────────────
TRUST_COLORS = {
    "TRUSTED":       "green",
    "LIKELY_REAL":   "cyan",
    "SUSPICIOUS":    "yellow",
    "UNVERIFIABLE":  "dim",
    "FORGED":        "red",
}

VERIFIER_SYSTEM = """You are VERIFIER — the document execution & authenticity checker of SPECTER Legal.
You receive a scanned contract image (or extracted text) and must answer one question BEFORE analysis begins:
"Is this document real, complete, and safe to analyse?"

Check ALL of the following and report honestly:

1. SIGNATURES
   - Are signature fields present for all named parties?
   - Are they actually signed (ink/digital) or blank?
   - Do signatures appear on the right pages (execution page)?

2. STAMPS & SEALS
   - Is a notary/company/government stamp visible where expected?
   - Is it legible or suspiciously blurry/copy-pasted?

3. DATE CONSISTENCY
   - Is a signing date present?
   - Does the signing date come after the effective date?
   - Does signing date come before any expiry/end date?
   - Are clause dates internally consistent (e.g. notice period end > start)?

4. PARTY COMPLETENESS
   - Are all parties named in the opening clause?
   - Do all named parties have a corresponding signature block?
   - Are addresses/identifiers present for each party?

5. DOCUMENT COMPLETENESS
   - Do clause/section numbers run continuously (no jumps like 1,2,4,5)?
   - Are there any "continued on page X" references with no following page?
   - Does the document have a clear ending (signature block or "END OF AGREEMENT")?
   - Are there blank sections that should be filled in?

6. DOCUMENT IDENTITY
   - Does the document title match what its content describes?
   - Are there clauses that belong to a completely different document type?

7. TAMPERING SIGNALS
   - Are there inconsistent fonts, font sizes, or spacing that suggest text was inserted?
   - Are dates or amounts written in a different hand/font than the rest?
   - Any visible correction fluid, overwriting, or suspicious whitespace?

Return ONLY a raw JSON object (no markdown, no backticks):
{
  "trust_verdict": "TRUSTED|LIKELY_REAL|SUSPICIOUS|UNVERIFIABLE|FORGED",
  "trust_score": 0-100,
  "proceed_with_analysis": true|false,
  "verifier_summary": "2-3 sentence plain-English verdict on document authenticity",
  "checks": {
    "signatures": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "stamps_seals": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "date_consistency": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "party_completeness": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "document_completeness": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "document_identity": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    },
    "tampering_signals": {
      "status": "pass|warn|fail|na",
      "finding": "one sentence finding"
    }
  },
  "missing_clauses": ["list of standard clauses absent for this document type"],
  "red_flags": ["list of specific authenticity red flags found, empty if none"],
  "verification_note": "what the user should do before signing based on these findings"
}

Trust verdict guide:
- TRUSTED:      All checks pass, document appears complete and authentic
- LIKELY_REAL:  Minor warnings only, safe to proceed with analysis
- SUSPICIOUS:   Multiple warnings or one fail — user should seek clarification
- UNVERIFIABLE: Cannot assess (image too blurry, text-only input with no visual cues)
- FORGED:       Clear signs of tampering, fabrication, or inconsistency"""


# ── Core verify functions ─────────────────────────────────────────────────────

def verify_from_image(image_path: str) -> dict:
    """
    Primary path: verify a scanned contract image.
    Sends the image directly to Claude Vision for visual authenticity checks.
    
    Args:
        image_path: local file path to JPG/PNG/WEBP/GIF of the contract
    
    Returns:
        VERIFIER result dict
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Detect media type
    ext = path.suffix.lower()
    media_type_map = {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
        ".gif":  "image/gif",
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=VERIFIER_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    }
                },
                {
                    "type": "text",
                    "text": "Verify this legal document image for authenticity, completeness, and integrity. Run all 7 checks."
                }
            ]
        }]
    )

    return _parse_response(response)


def verify_from_text(document_text: str, document_type: str = "auto") -> dict:
    """
    Fallback path: verify from extracted text when no image is available.
    Visual checks (stamps, signatures) will be UNVERIFIABLE, but structural
    checks (date consistency, party completeness, missing clauses) still run.
    
    Args:
        document_text: full text of the legal document
        document_type: optional hint ("rental_agreement", "nda", etc.)
    
    Returns:
        VERIFIER result dict
    """
    doc_hint = f" (document type hint: {document_type})" if document_type != "auto" else ""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=VERIFIER_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Verify this legal document text{doc_hint} for completeness and integrity.\n"
                f"NOTE: This is text-only input — visual checks (signatures, stamps, tampering) "
                f"must be marked as 'na' with finding 'Not assessable from text only.'\n\n"
                f"{document_text[:4000]}"
            )
        }]
    )

    return _parse_response(response)


def verify_from_base64(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """
    Web API path: verify from base64-encoded image (used by Flask /verify endpoint).
    
    Args:
        image_b64: base64 encoded image string
        media_type: MIME type of the image
    
    Returns:
        VERIFIER result dict
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=VERIFIER_SYSTEM,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    }
                },
                {
                    "type": "text",
                    "text": "Verify this legal document image for authenticity, completeness, and integrity. Run all 7 checks."
                }
            ]
        }]
    )

    return _parse_response(response)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_response(response) -> dict:
    """Parse Claude's response into a clean dict, with safe fallback."""
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Extract JSON block if Claude added commentary
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        # Hard fallback — return unverifiable result
        return {
            "trust_verdict": "UNVERIFIABLE",
            "trust_score": 0,
            "proceed_with_analysis": True,
            "verifier_summary": "VERIFIER could not parse the document. Proceeding with standard analysis.",
            "checks": {k: {"status": "na", "finding": "Parse error."} for k in [
                "signatures", "stamps_seals", "date_consistency",
                "party_completeness", "document_completeness",
                "document_identity", "tampering_signals"
            ]},
            "missing_clauses": [],
            "red_flags": ["VERIFIER response parse failed — manual review recommended"],
            "verification_note": "Could not verify document automatically. Review manually before signing."
        }


def get_trust_color(verdict: str) -> str:
    """Returns Rich console color for a trust verdict."""
    return TRUST_COLORS.get(verdict, "white")


def should_block_analysis(verifier_data: dict) -> bool:
    """
    Returns True only if VERIFIER detected a FORGED document.
    SUSPICIOUS still proceeds — we warn but don't block.
    """
    return verifier_data.get("trust_verdict") == "FORGED"
