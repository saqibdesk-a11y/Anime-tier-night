"""Shared AI helpers for every game: Gemini, Mistral and Cerebras, with built-in keys,
retries, model fallback and image input (for judging drawings)."""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


OPENAI_STYLE = {"cerebras": "https://api.cerebras.ai/v1", "mistral": "https://api.mistral.ai/v1"}
PROVIDER_NAMES = {"gemini": "Gemini", "cerebras": "Cerebras", "mistral": "Mistral"}
# built-in keys come from the host's environment (Render > Environment), never from the code
BUILTIN_KEYS = {p: os.environ.get(p.upper() + "_API_KEY", "").strip() for p in PROVIDER_NAMES}
BUILTIN_ORDER = [p for p in ("gemini", "mistral", "cerebras") if BUILTIN_KEYS[p]]
_builtin_calls = []
_calls_lock = threading.Lock()
_default_models = {}


def builtin_allowed(per_hour=40):
    """Caps roasts on the built-in keys so one busy room can't burn the whole quota."""
    now = time.time()
    with _calls_lock:
        _builtin_calls[:] = [t for t in _builtin_calls if now - t < 3600]
        if len(_builtin_calls) >= per_hour:
            return False
        _builtin_calls.append(now)
        return True


def builtin_models(provider, key, vision=False):
    """Up to 3 models to try in order, so one overloaded model doesn't sink the request."""
    cache = (provider, vision)
    if cache not in _default_models:
        models = list_models(provider, key)
        prefs = {"gemini": ["flash-lite", "flash-latest", "flash"],
                 "mistral": (["mistral-medium-latest", "mistral-small-latest", "pixtral-large-latest"] if vision
                             else ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"]),
                 "cerebras": ["gpt-oss", "llama-3.3", "qwen", "llama"]}[provider]
        picks = []
        # newest versions sort last, so search from the end
        for want in prefs:
            for m in reversed(models):
                if want in m and "preview" not in m and m not in picks and (want == "flash-lite" or "lite" not in m):  # lite: fastest, most quota
                    picks.append(m)
                    break
        picks = picks[:3] or models[:1]
        if not picks:
            raise AIError("no usable models were found for this key.")
        _default_models[cache] = picks
        time.sleep(1.2)  # free tiers allow about one call per second
    return _default_models[cache]


def ask_builtin(system, prompt, images=None, timeout=60):
    """Tries every built-in AI and model in turn. Returns (json_reply, provider_name, model).
    images: list of (mime_type, raw_bytes); only Gemini and Mistral can see them."""
    providers = [p for p in BUILTIN_ORDER if not images or p in ("gemini", "mistral")]
    if not providers:
        raise AIError("no built-in AI is set up on this server" + (" that can see pictures." if images else "."))
    if not builtin_allowed():
        raise AIError("the built-in AI is busy (too many requests this hour). Try again soon.")
    tried = []
    for p in providers:
        key = BUILTIN_KEYS[p]
        try:
            models = builtin_models(p, key, vision=bool(images))
        except AIError as e:
            tried.append(f"{PROVIDER_NAMES[p]}: {e}")
            continue
        for m in models:
            try:
                return complete(p, key, m, system, prompt, images, timeout), PROVIDER_NAMES[p], m
            except AIError as e:
                tried.append(f"{PROVIDER_NAMES[p]} {m}: {e}")
                if e.code not in BUSY + (404, "timeout"):
                    break
    raise AIError(" | ".join(tried))


GEMINI = "https://generativelanguage.googleapis.com/v1beta"


class AIError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


BUSY = (429, 500, 502, 503, 504)


def http_json(url, key_headers, body=None, timeout=90):
    # busy or rate-limited AIs usually answer on a second or third try
    for wait in (2.5, 6, None):
        try:
            return http_json_once(url, key_headers, body, timeout)
        except AIError as e:
            if e.code not in BUSY or wait is None:
                raise
            time.sleep(wait)


def http_json_once(url, key_headers, body, timeout):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "AnimeTierNight/1.0", **key_headers}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(detail)
            detail = (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else (j.get("message") or j.get("detail") or j.get("error") or detail)
        except ValueError:
            pass
        reason = {401: "the API key was rejected", 403: "the API key isn't allowed to use this",
                  404: "that model wasn't found", 429: "it's out of quota or rate limited"}.get(e.code, f"it returned error {e.code}")
        raise AIError(f"{reason}. {str(detail)[:200]}".strip(), e.code)
    except TimeoutError:
        raise AIError(f"took longer than {timeout}s and timed out.", "timeout")
    except Exception as e:
        if "timed out" in str(e):
            raise AIError(f"took longer than {timeout}s and timed out.", "timeout")
        raise AIError(f"couldn't reach it ({e.__class__.__name__}).")


def auth(provider, key):
    return {"x-goog-api-key": key} if provider == "gemini" else {"Authorization": "Bearer " + key}


def list_models(provider, key):
    if provider == "gemini":
        res = http_json(GEMINI + "/models?pageSize=200", auth(provider, key), timeout=20)
        ids = [m["name"].split("/", 1)[-1] for m in res.get("models", [])
               if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        ids = [i for i in ids if not any(s in i for s in ("embedding", "aqa", "imagen", "tts", "image", "live", "veo"))]
    else:
        res = http_json(OPENAI_STYLE[provider] + "/models", auth(provider, key), timeout=20)
        ids = [m["id"] for m in res.get("data", [])
               if not any(s in m["id"] for s in ("embed", "moderation", "ocr", "transcribe", "voxtral"))]
    return sorted(set(ids))


def complete(provider, key, model, system, prompt, images=None, timeout=45):
    images = [(mime, base64.b64encode(raw).decode("ascii")) for mime, raw in (images or [])]
    if provider == "gemini":
        parts = [{"text": prompt}] + [{"inline_data": {"mime_type": m, "data": d}} for m, d in images]
        res = http_json(f"{GEMINI}/models/{urllib.parse.quote(model)}:generateContent", auth(provider, key), {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}}, timeout=timeout)
        parts = ((res.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    else:
        res = http_json(OPENAI_STYLE[provider] + "/chat/completions", auth(provider, key), {
            "model": model, "temperature": 0.95,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt if not images else
                          [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": f"data:{m};base64,{d}"} for m, d in images]}]},
            timeout=timeout)
        text = ((res.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise AIError("it answered, but not in the expected format. Try again or switch model.")
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        raise AIError("it answered, but the reply was cut off or malformed. Try again or switch model.")


