import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT

load_dotenv()

app = Flask(__name__)

MODEL_NAME = "gemini-3.1-flash-lite"
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_ITEM_CHARS = 3000


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def clean_history(history):
    if not isinstance(history, list):
        return []

    cleaned = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue

        cleaned.append(
            {
                "role": role,
                "content": content[:MAX_HISTORY_ITEM_CHARS],
            }
        )

    return cleaned


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"error": "Please enter a message."}), 400

        if len(message) > MAX_MESSAGE_CHARS:
            return jsonify(
                {"error": f"Message is too long. Maximum is {MAX_MESSAGE_CHARS} characters."}
            ), 400

        history = clean_history(data.get("history", []))

        conversation = []
        for item in history:
            conversation.append(
                types.Content(
                    role="user" if item["role"] == "user" else "model",
                    parts=[types.Part.from_text(text=item["content"])],
                )
            )

        conversation.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)],
            )
        )

        client = get_client()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=conversation,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=700,
            ),
        )

        answer = (response.text or "").strip()

        if not answer:
            answer = "I couldn't generate a response. Please try asking a carpenter-workshop question."

        return jsonify({"answer": answer})

    except Exception as exc:
        app.logger.exception("Gemini request failed")
        return jsonify(
            {
                "error": "Sorry, I couldn't complete that request. Please check your Gemini API configuration."
            }
        ), 500


if __name__ == "__main__":
    app.run(debug=True)
