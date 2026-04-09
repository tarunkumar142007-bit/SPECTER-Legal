import os
import json
import anthropic
from flask import Flask, request, jsonify, render_template

import multi_agent   # ← parallel execution engine
import verifier      # needed for should_block_analysis helper

app = Flask(__name__)
os.environ["ANTHROPIC_API_KEY"] = "AIzaSyCJWyKOHD-jqHdRkBJX8cpcVE5jiIz266s"

client = anthropic.Anthropic()


@app.route("/")
def index():
    return render_template("index.html")


# ── MAIN ANALYSIS ENDPOINT — now uses parallel pipeline ───────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Full pipeline: VERIFIER + ORACLE (parallel) → PHANTOM + COUNSELOR (parallel)

    Request JSON:
    {
        "document":   "full contract text",
        "user_type":  "student|freelancer|employee|tenant|founder|null",
        "language":   "english|hindi|tamil|telugu|...",
        "image":      "<base64 string>",   (optional — scanned contract image)
        "media_type": "image/jpeg"         (optional — defaults to image/jpeg)
    }
    """
    data       = request.get_json()
    document   = data.get("document", "").strip()
    user_type  = data.get("user_type", None)
    language   = data.get("language", "english")
    image_b64  = data.get("image", "").strip()
    media_type = data.get("media_type", "image/jpeg")

    if not document:
        return jsonify({"error": "No document provided. Paste text or upload a PDF first."}), 400

    # Run the full parallel pipeline (all 4 agents, 2-phase concurrency)
    try:
        result = multi_agent.run_pipeline_sync(
            document=document,
            user_type=user_type,
            language=language,
            image_b64=image_b64,
            media_type=media_type,
        )
    except Exception as e:
        return jsonify({"error": f"Pipeline failed: {str(e)}"}), 500

    return jsonify(result)


# ── What-If Scenario Simulator ────────────────────────────────────────────────
@app.route("/ask", methods=["POST"])
def ask():
    """
    User asks 'What happens if I miss a payment?' — gets a plain-English
    answer grounded in the actual clauses of their document.
    """
    data        = request.get_json()
    question    = data.get("question", "").strip()
    document    = data.get("document", "").strip()
    oracle_data = data.get("oracle_data", {})
    language    = data.get("language", "english")

    if not question or not document:
        return jsonify({"error": "Question and document are both required."}), 400

    lang_map = {
        "hindi":   "Hindi (हिंदी) — use simple everyday Hindi, not legal Hindi",
        "tamil":   "Tamil (தமிழ்) — use simple everyday Tamil",
        "telugu":  "Telugu (తెలుగు) — use simple everyday Telugu",
        "english": "plain simple English",
    }
    lang_instruction = f"Respond in {lang_map.get(language, 'plain simple English')}."

    system = f"""You are COUNSELOR from SPECTER Legal — a plain-language contract expert.
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


if __name__ == "__main__":
    print("\n⚖️  SPECTER Legal Web Server Starting...")
    print("🚀 Multi-agent parallel pipeline active")
    print("   Phase 1: VERIFIER + ORACLE  (simultaneous)")
    print("   Phase 2: PHANTOM + COUNSELOR (simultaneous)")
    print("📡 Open: http://localhost:5000\n")
    app.run(debug=True, port=5000)
