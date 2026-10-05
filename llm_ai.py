#"""LLM prediction adapters for Gemini and OpenAI.
#API keys are passed in at runtime; this module never logs them.
#"""
import os
import json
import re
import aiohttp

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
LLM_TIMEOUT = aiohttp.ClientTimeout(total=float(os.getenv("LLM_TIMEOUT", "20")))

GEMINI_SYSTEM_PROMPT = """You are Gemini AI operating as an independent BIG/SMALL historical-sequence analyst. Analyze ONLY the supplied historical results. Do not use or reference ChatGPT, other models, or an ensemble. Do not claim certainty or guaranteed profit. Return ONLY valid JSON with keys prediction, confidence, reason. prediction must be BIG or SMALL. confidence must be 0-100. reason must be short."""

CHATGPT_SYSTEM_PROMPT = """You are ChatGPT AI operating as an independent BIG/SMALL historical-sequence analyst. Analyze ONLY the supplied historical results. Do not use or reference Gemini, other models, or an ensemble. Do not claim certainty or guaranteed profit. Return ONLY valid JSON with keys prediction, confidence, reason. prediction must be BIG or SMALL. confidence must be 0-100. reason must be short."""


def _history_text(history_docs, max_items=120):
    vals = []
    for d in list(history_docs or [])[:max_items]:
        if isinstance(d, dict):
            v = str(d.get("size", "")).upper()
        else:
            v = str(d).upper()
        if v in ("BIG", "SMALL"):
            vals.append(v)
    return " ".join(vals)


def _parse_json(text):
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        text = m.group(0)
    data = json.loads(text)
    pred = str(data.get("prediction", "")).upper()
    if pred not in ("BIG", "SMALL"):
        raise ValueError("Invalid prediction")
    conf = max(0.0, min(100.0, float(data.get("confidence", 50))))
    reason = str(data.get("reason", "LLM analysis"))[:240]
    return {"prediction": pred, "confidence": conf, "reason": reason}


async def _post_json(url, headers, payload):
    async with aiohttp.ClientSession(timeout=LLM_TIMEOUT) as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"LLM HTTP {resp.status}: {body[:300]}")
            return json.loads(body)


async def gemini_predict(history_docs, api_key, model=None):
    if not api_key:
        raise ValueError("Gemini API key is not configured")
    model = model or GEMINI_MODEL
    prompt = f"{GEMINI_SYSTEM_PROMPT}\nHistorical results, newest to oldest:\n{_history_text(history_docs)}\nPredict the next result."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 180, "responseMimeType": "application/json"},
    }
    data = await _post_json(url, {"x-goog-api-key": api_key, "Content-Type": "application/json"}, payload)
    text = ""
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("text"):
                text += part["text"]
    return _parse_json(text)


async def openai_predict(history_docs, api_key, model=None):
    if not api_key:
        raise ValueError("OpenAI API key is not configured")
    model = model or OPENAI_MODEL
    prompt = f"{CHATGPT_SYSTEM_PROMPT}\nHistorical results, newest to oldest:\n{_history_text(history_docs)}\nPredict the next result."
    payload = {
        "model": model,
        "instructions": CHATGPT_SYSTEM_PROMPT,
        "input": prompt,
        "max_output_tokens": 180,
        "store": False,
    }
    data = await _post_json(
        "https://api.openai.com/v1/responses",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload,
    )
    text = data.get("output_text", "")
    if not text:
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in ("output_text", "text"):
                    text += content.get("text", "")
    return _parse_json(text)
