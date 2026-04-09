"""
multi-agent.py — SPECTER Legal Parallel Execution Engine
=========================================================
Runs all 4 SPECTER agents concurrently using asyncio + ThreadPoolExecutor.
Each agent gets its own Claude call. PHANTOM and COUNSELOR need ORACLE's output
first, so the pipeline is:

  Phase 1 (parallel): VERIFIER + ORACLE  ──┐
  Phase 2 (parallel): PHANTOM + COUNSELOR ← (after ORACLE finishes)

Total wall-clock time drops from ~4 sequential calls → ~2 parallel phases.

No OpenAI or Gemini keys needed — all agents use the same Anthropic API.
The Gemini free-tier approach from the original multi-agent.py was removed
because (a) you only have Gemini free API and (b) mixing LLMs here adds no
value — each SPECTER agent already has a distinct specialised prompt.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import oracle
import phantom
import counselor
import verifier

# Shared thread pool — Anthropic SDK is sync, so we run each call in a thread
_executor = ThreadPoolExecutor(max_workers=4)


# ── Async wrappers for each synchronous agent ─────────────────────────────────

async def run_verifier(document: str) -> dict:
    """VERIFIER: authenticity + completeness check (text mode)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: verifier.verify_from_text(document)
    )


async def run_verifier_image(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """VERIFIER: full 7/7 visual checks from a scanned image."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: verifier.verify_from_base64(image_b64, media_type)
    )


async def run_oracle(document: str) -> dict:
    """ORACLE: raw structured data extraction — clauses, risks, dates, obligations."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: oracle.analyze(document)
    )


async def run_phantom(oracle_data: dict, document: str,
                      user_type: str | None = None,
                      language: str = "english") -> dict:
    """PHANTOM: plain-English brief + SIGN/NEGOTIATE/AVOID decision report."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: phantom.generate_reports(oracle_data, document, user_type, language)
    )


async def run_counselor(oracle_data: dict, phantom_data: dict,
                        document: str, language: str = "english") -> dict:
    """COUNSELOR: rewritten clauses, negotiation script, checklist."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: counselor.advise(oracle_data, phantom_data, document, language)
    )


# ── Main parallel pipeline ────────────────────────────────────────────────────

async def run_pipeline(
    document:   str,
    user_type:  str | None = None,
    language:   str = "english",
    image_b64:  str = "",
    media_type: str = "image/jpeg",
) -> dict:
    """
    Full SPECTER pipeline with maximum parallelism.

    Phase 1 — VERIFIER + ORACLE run simultaneously:
        Neither depends on the other, so they fire at the same time.

    Phase 2 — PHANTOM + COUNSELOR run simultaneously:
        Both need ORACLE's output, but COUNSELOR also needs PHANTOM's output.
        To maximise speed, we run them in parallel but COUNSELOR uses a
        lightweight ORACLE-only brief while PHANTOM enriches the result.
        (If strict PHANTOM→COUNSELOR ordering is required, set
         STRICT_ORDER=True below.)

    Returns a dict matching the /analyze endpoint response format.
    """

    STRICT_ORDER = False  # Set True if COUNSELOR must wait for PHANTOM
    result = {}

    # ── Phase 1: VERIFIER + ORACLE in parallel ────────────────────────────────
    verifier_task = (
        run_verifier_image(image_b64, media_type) if image_b64
        else run_verifier(document)
    )

    verifier_data, oracle_data = await asyncio.gather(
        verifier_task,
        run_oracle(document),
        return_exceptions=True,
    )

    # Handle exceptions from Phase 1
    if isinstance(verifier_data, Exception):
        verifier_data = {
            "trust_verdict": "UNVERIFIABLE",
            "proceed_with_analysis": True,
            "verifier_summary": f"VERIFIER error: {verifier_data}",
            "checks": {},
            "red_flags": [],
            "missing_clauses": [],
            "verification_note": "",
        }
    result["verifier"] = verifier_data

    if isinstance(oracle_data, Exception):
        return {**result, "error": f"ORACLE failed: {oracle_data}"}
    result["oracle"] = oracle_data

    # Block pipeline only on confirmed FORGED
    if verifier.should_block_analysis(verifier_data):
        result["blocked"] = True
        result["block_reason"] = (
            "VERIFIER detected signs of document forgery. "
            "Analysis blocked. Verify this document manually before proceeding."
        )
        return result

    # ── Phase 2: PHANTOM + COUNSELOR ─────────────────────────────────────────
    if STRICT_ORDER:
        # Sequential: wait for PHANTOM before running COUNSELOR
        try:
            phantom_data = await run_phantom(oracle_data, document, user_type, language)
        except Exception as e:
            phantom_data = {}
            result["phantom"] = {"error": str(e)}
        else:
            result["phantom"] = phantom_data

        try:
            counselor_data = await run_counselor(oracle_data, phantom_data, document, language)
            result["counselor"] = counselor_data
        except Exception as e:
            result["counselor"] = {"error": str(e)}

    else:
        # Parallel: PHANTOM and COUNSELOR fire at the same time.
        # COUNSELOR gets an empty phantom_data dict and relies on oracle_data directly.
        # This saves ~2-3 seconds for the user.
        phantom_result, counselor_result = await asyncio.gather(
            run_phantom(oracle_data, document, user_type, language),
            run_counselor(oracle_data, {}, document, language),
            return_exceptions=True,
        )

        if isinstance(phantom_result, Exception):
            result["phantom"] = {"error": str(phantom_result)}
        else:
            result["phantom"] = phantom_result

        if isinstance(counselor_result, Exception):
            result["counselor"] = {"error": str(counselor_result)}
        else:
            result["counselor"] = counselor_result

    result["document_preview"] = (
        document[:300] + "..." if len(document) > 300 else document
    )
    return result


# ── Convenience sync wrapper (for non-async callers like Flask) ───────────────

def run_pipeline_sync(
    document:   str,
    user_type:  str | None = None,
    language:   str = "english",
    image_b64:  str = "",
    media_type: str = "image/jpeg",
) -> dict:
    """
    Synchronous entry point for Flask routes.
    Runs the full async parallel pipeline and blocks until complete.
    """
    return asyncio.run(run_pipeline(
        document=document,
        user_type=user_type,
        language=language,
        image_b64=image_b64,
        media_type=media_type,
    ))
