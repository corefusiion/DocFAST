"""AI Client for DocFAST: supports Google Gemini, OpenAI, Claude and OpenCode/Ollama.
Uses pure standard library (urllib.request) so it remains ultra-lightweight and fast.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "url_key": "https://aistudio.google.com/apikey",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"],
        "default_model": "gemini-2.5-flash",
        "supports_vision": True,
    },
    "openai": {
        "name": "OpenAI (ChatGPT)",
        "url_key": "https://platform.openai.com/api-keys",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini", "gpt-4.5-preview"],
        "default_model": "gpt-4o-mini",
        "supports_vision": True,
    },
    "claude": {
        "name": "Anthropic Claude",
        "url_key": "https://console.anthropic.com/settings/keys",
        "models": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        "default_model": "claude-3-7-sonnet-20250219",
        "supports_vision": True,
    },
    "opencode": {
        "name": "OpenCode / Ollama / Local",
        "url_key": "http://localhost:11434",
        "models": ["llama3.3", "qwen2.5-coder", "deepseek-r1", "mistral"],
        "default_model": "llama3.3",
        "default_base_url": "http://localhost:11434/v1",
        "supports_vision": False,
    },
}


def test_connection(provider: str, api_key: str, model: str, base_url: str = "") -> tuple[bool, str]:
    """Test API connection with a simple 'Olá' ping."""
    try:
        reply = send_message(
            prompt="Responda apenas 'Conectado com sucesso!' em uma linha.",
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=12,
        )
        if reply and len(reply.strip()) > 0:
            return True, reply.strip()
        return False, "Resposta vazia recebida do modelo."
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")
            data = json.loads(body)
            if "error" in data:
                err_msg = data["error"].get("message") or data["error"]
                return False, f"HTTP {e.code}: {err_msg}"
        except Exception:
            pass
        return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Erro de rede: {e.reason}"
    except Exception as e:
        return False, f"Erro: {str(e)}"


def send_message(
    prompt: str,
    image_bytes: bytes | None = None,
    history: list[dict[str, Any]] | None = None,
    provider: str = "gemini",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    system_instruction: str = "Você é o assistente inteligente DocFAST integrado ao Windows. Responda em Português de forma clara, prestativa e formatada em Markdown com destaques quando útil.",
    timeout: int = 30,
) -> str:
    """Send text and optional image to the chosen LLM provider."""
    provider = provider.lower()
    info = PROVIDERS.get(provider, PROVIDERS["gemini"])
    model = model or info["default_model"]

    if provider == "gemini":
        return _call_gemini(prompt, image_bytes, history, api_key, model, system_instruction, timeout)
    elif provider == "openai":
        return _call_openai(prompt, image_bytes, history, api_key, model, system_instruction, timeout, base_url="https://api.openai.com/v1")
    elif provider == "claude":
        return _call_claude(prompt, image_bytes, history, api_key, model, system_instruction, timeout)
    elif provider == "opencode":
        b_url = base_url or info.get("default_base_url", "http://localhost:11434/v1")
        return _call_openai(prompt, image_bytes, history, api_key or "sk-local", model, system_instruction, timeout, base_url=b_url)
    else:
        raise ValueError(f"Provedor desconhecido: {provider}")


def _call_gemini(
    prompt: str,
    image_bytes: bytes | None,
    history: list[dict[str, Any]] | None,
    api_key: str,
    model: str,
    system_instruction: str,
    timeout: int,
) -> str:
    if not api_key:
        raise ValueError("Chave de API do Gemini não configurada. Configure em Configurações → Ajuda AI.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = []

    # Include recent history if provided
    if history:
        for msg in history[-8:]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    # Current user turn
    user_parts: list[dict[str, Any]] = [{"text": prompt}]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        user_parts.append({"inline_data": {"mime_type": "image/png", "data": b64}})
    contents.append({"role": "user", "parts": user_parts})

    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        candidates = res.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return "".join(p.get("text", "") for p in parts)
        return "Nenhuma resposta gerada pelo modelo."


def _call_openai(
    prompt: str,
    image_bytes: bytes | None,
    history: list[dict[str, Any]] | None,
    api_key: str,
    model: str,
    system_instruction: str,
    timeout: int,
    base_url: str = "https://api.openai.com/v1",
) -> str:
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        raise ValueError("Chave de API não configurada. Configure em Configurações → Ajuda AI.")

    url = f"{base_url.rstrip('/')}/chat/completions"
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_instruction}]

    if history:
        for msg in history[-8:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "temperature": 0.4}
    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=data_bytes, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choices = res.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "")
        return "Nenhuma resposta retornada pela OpenAI."


def _call_claude(
    prompt: str,
    image_bytes: bytes | None,
    history: list[dict[str, Any]] | None,
    api_key: str,
    model: str,
    system_instruction: str,
    timeout: int,
) -> str:
    if not api_key:
        raise ValueError("Chave de API da Anthropic Claude não configurada. Configure em Configurações → Ajuda AI.")

    url = "https://api.anthropic.com/v1/messages"
    messages: list[dict[str, Any]] = []

    if history:
        for msg in history[-8:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        user_content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": prompt},
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "system": system_instruction,
        "max_tokens": 2048,
        "messages": messages,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    req = urllib.request.Request(url, data=data_bytes, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        content_list = res.get("content", [])
        if content_list:
            return "".join(c.get("text", "") for c in content_list if c.get("type") == "text")
        return "Nenhuma resposta retornada pelo Claude."
