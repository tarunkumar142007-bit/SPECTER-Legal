import os
from flask import Flask, request, jsonify, render_template
import oracle
import phantom
import counselor
import anthropic
import json
import verifier

app = Flask(__name__)
os.environ["ANTHROPIC_API_KEY"] = "your_api_key_here"

client = anthropic.Anthropic()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data       = request.get_json()
    document   = data.get("document", "").strip()
    user_type  = data.get("user_type", None)
    language   = data.get("language", "english")
    image_b64  = data.get("image", "")
    media_type = data.get("media_type", "image/jpeg")

    if not document:
        return jsonify({"error": "No document provided"}), 400

    result = {}

    # ── Step 0: VERIFIER ──────────────────────────────────────────────────────
    try:
        if image_b64:
            verifier_data = verifier.verify_from_base64(image_b64, media_type)
        else:
            verifier_data = verifier.verify_from_text(document)
        result["verifier"] = verifier_data
    except Exception as e:
        verifier_data = {"trust_verdict": "UNVERIFIABLE", "proceed_with_analysis": True}
        result["verifier"] = {"error": str(e), "proceed_with_analysis": True}

    # Block pipeline if FORGED
    if verifier.should_block_analysis(verifier_data):
        result["blocked"] = True
        result["block_reason"] = (
            "VERIFIER detected signs of document forgery. "
            "Analysis blocked to protect user. Please verify document authenticity manually."
        )
        return jsonify(result), 200

    # ── Step 1: ORACLE ────────────────────────────────────────────────────────
    try:
        oracle_data = oracle.analyze(document)
        result["oracle"] = oracle_data
    except Exception as e:
        return jsonify({"error": f"ORACLE failed: {str(e)}"}), 500

    # ── Step 2: PHANTOM ───────────────────────────────────────────────────────
    try:
        phantom_data = phantom.generate_reports(oracle_data, document, user_type, language)
        result["phantom"] = phantom_data
    except Exception as e:
        phantom_data = {}
        result["phantom"] = {"error": str(e)}

    # ── Step 3: COUNSELOR ─────────────────────────────────────────────────────
    try:
        counselor_data = counselor.advise(oracle_data, phantom_data, document, language)
        result["counselor"] = counselor_data
    except Exception as e:
        result["counselor"] = {"error": str(e)}

    result["document_preview"] = document[:300] + "..." if len(document) > 300 else document
    return jsonify(result)


# ── FEATURE 4: What-If Scenario Simulator ────────────────────────────────────
@app.route("/ask", methods=["POST"])
def ask():
    data        = request.get_json()
    question    = data.get("question", "").strip()
    document    = data.get("document", "").strip()
    oracle_data = data.get("oracle_data", {})
    language    = data.get("language", "english")

    if not question or not document:
        return jsonify({"error": "Question and document required"}), 400

    lang_map = {
        "hindi":   "Hindi (हिंदी) — use simple everyday Hindi, not legal Hindi",
        "tamil":   "Tamil (தமிழ்) — use simple everyday Tamil",
        "telugu":  "Telugu (తెలుగు) — use simple everyday Telugu",
        "english": "plain simple English",
    }
    lang_instruction = f"Respond in {lang_map.get(language, 'plain simple English')}."

    system = f"""You are COUNSELOR from SPECTER Legal — a plain-language contract expert.
A user has a question about a legal document they may sign.
Answer ONLY based on what the document actually says.
Be direct, plain, and simple — no legal jargon at all.
Maximum 3 short sentences. Start with the direct answer.
{lang_instruction}"""

    user_content = (
        f"Document excerpt:\n{document[:2000]}\n\n"
        f"Clause analysis:\n{json.dumps(oracle_data.get('clauses', []))}\n\n"
        f"Question: {question}"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user_content}]
        )
        return jsonify({"answer": response.content[0].text.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Standalone verify endpoint (image or text) ────────────────────────────────
@app.route("/verify", methods=["POST"])
def verify_route():
    data       = request.get_json()
    image_b64  = data.get("image", "").strip()
    media_type = data.get("media_type", "image/jpeg")
    document   = data.get("document", "").strip()
    doc_type   = data.get("document_type", "auto")

    if not image_b64 and not document:
        return jsonify({"error": "Provide either 'image' (base64) or 'document' (text)"}), 400

    try:
        if image_b64:
            result = verifier.verify_from_base64(image_b64, media_type)
        else:
            result = verifier.verify_from_text(document, doc_type)
    except Exception as e:
        return jsonify({"error": f"VERIFIER failed: {str(e)}"}), 500

    return jsonify(result)


if __name__ == "__main__":
    print("\n⚖️  SPECTER Legal Web Server Starting...")
    print("📡 Open: http://localhost:5000\n")
    app.run(debug=True, port=5000)
