from __future__ import annotations
import os, json, requests

SYSTEM_PROMPT = (
    "You are an expert meeting notes assistant. Produce crisp, action-oriented outputs.\n"
    "Return JSON with keys: summary, decisions (list), actions (list of {owner,text,due_date?}). Keep it concise."
)
USER_PROMPT_TEMPLATE = (
    "Transcript:\n---\n{transcript}\n---\nInstructions:\n"
    "1) Provide a clear meeting summary (<= 8 bullet points).\n"
    "2) List explicit decisions.\n"
    "3) Extract actionable items with owners if mentioned (use 'TBD' if unknown). "
    "Try to infer due dates if any hint.\nReturn JSON only."
)

def summarize_ollama(transcript: str, model: str = None, host: str = None):
    host = host or os.getenv("OLLAMA_HOST","http://localhost:11434")
    model = model or os.getenv("OLLAMA_MODEL","mistral")
    prompt = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE.format(transcript=transcript[:10000])}"
    r = requests.post(f"{host}/api/generate", json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}})
    r.raise_for_status()
    content = r.json().get("response","")
    # Try to parse JSON robustly
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start:end+1])
        except Exception:
            pass
    return {"summary":"","decisions":[],"actions":[]}
