from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple, cast, AsyncIterator
from dataclasses import dataclass

import httpx

from .config import get_settings

@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]

class BaseModelClient:
    async def ahealth(self) -> Tuple[bool, Dict[str, Any]]:
        raise NotImplementedError

    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list[ToolSpec]] = None
    ) -> Dict[str, Any]:
        """
        Returns either:
        - {"text": "response text"}
        - {"tool_call": {"name": "tool_name", "arguments": {...}}}
        """
        raise NotImplementedError

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list[ToolSpec]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Yield dict chunks:
        - {'type':'text','delta':'...'}
        - {'type':'tool_call','name':...,'args_json':...}
        """
        # Default non-streaming fallback: single text chunk
        result = await self.chat(prompt, system=system, context=context, tools=tools)
        if "text" in result:
            yield {"type": "text", "delta": result["text"]}
        elif "tool_call" in result:
            tc = result["tool_call"]
            args_str = json.dumps(tc.get("arguments", {}))
            yield {"type": "tool_call", "name": tc["name"], "args_json": args_str}


class OpenAIClient(BaseModelClient):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self.base = "https://api.openai.com/v1"

    async def ahealth(self) -> Tuple[bool, Dict[str, Any]]:
        # Lightweight model call
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{self.base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "Reply with 'pong'"}],
                        "max_tokens": 5,
                        "temperature": 0,
                    },
                )
                ok = r.status_code == 200
                data = cast(Dict[str, Any], r.json()) if ok else {"status": r.status_code, "text": r.text[:500]}
                reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                return ok and "pong" in reply.lower(), {"provider": "openai", "model": self.model}
        except Exception as e:
            return False, {"provider": "openai", "model": self.model, "error": str(e)}

    def _to_openai_tools(self, tools: list[ToolSpec]) -> list[Dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema
            }
        } for t in tools]

    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list[ToolSpec]] = None
    ) -> Dict[str, Any]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        
        json_payload: Dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "temperature": 0.2,
        }
        if tools:
            json_payload["tools"] = self._to_openai_tools(tools)
            json_payload["tool_choice"] = "auto"
        
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=json_payload,
            )
            r.raise_for_status()
            data = cast(Dict[str, Any], r.json())
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message", {})
            
            # Tool call?
            tool_calls = message.get("tool_calls")
            if tool_calls and len(tool_calls) > 0:
                tc = tool_calls[0]
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args_dict = json.loads(args_str)
                except json.JSONDecodeError:
                    args_dict = {}
                return {"tool_call": {"name": func.get("name", ""), "arguments": args_dict}}
            
            # Text response
            return {"text": message.get("content", "")}


class GeminiClient(BaseModelClient):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self.base = "https://generativelanguage.googleapis.com/v1beta"

    async def ahealth(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{self.base}/models/{self.model}:generateContent?key={self.api_key}",
                    json={"contents": [{"parts": [{"text": "Reply with 'pong'"}]}]},
                )
                ok = r.status_code == 200
                data = cast(Dict[str, Any], r.json()) if ok else {"status": r.status_code, "text": r.text[:500]}
                text = ""
                if ok:
                    cands = data.get("candidates") or []
                    if cands and "content" in cands[0]:
                        parts = (cands[0]["content"].get("parts") or [])
                        if parts:
                            text = parts[0].get("text", "")
                return ok and "pong" in (text or "").lower(), {"provider": "gemini", "model": self.model}
        except Exception as e:
            return False, {"provider": "gemini", "model": self.model, "error": str(e)}

    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list[ToolSpec]] = None
    ) -> Dict[str, Any]:
        # Gemini: tool/function calling not yet implemented, return text only
        text = f"{system}\n\n{prompt}" if system else prompt
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base}/models/{self.model}:generateContent?key={self.api_key}",
                json={"contents": [{"parts": [{"text": text}]}]},
            )
            r.raise_for_status()
            data = cast(Dict[str, Any], r.json())
            cands = data.get("candidates") or []
            if cands and "content" in cands[0]:
                parts = (cands[0]["content"].get("parts") or [])
                if parts:
                    return {"text": parts[0].get("text", "")}
            return {"text": ""}


class OllamaClient(BaseModelClient):
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base = base_url.rstrip("/")

    async def ahealth(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{self.base}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "Reply with 'pong'"}],
                        "stream": False,
                    },
                )
                ok = r.status_code == 200
                data = cast(Dict[str, Any], r.json()) if ok else {"status": r.status_code, "text": r.text[:500]}
                text = ""
                if ok:
                    # Ollama chat returns {"message":{"content": "..."}}
                    msg = data.get("message") or {}
                    text = msg.get("content", "")
                return ok and "pong" in (text or "").lower(), {"provider": "ollama", "model": self.model}
        except Exception as e:
            return False, {"provider": "ollama", "model": self.model, "error": str(e)}

    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list[ToolSpec]] = None
    ) -> Dict[str, Any]:
        # Ollama: no native tool calling, graceful fallback to text
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
            )
            r.raise_for_status()
            data = cast(Dict[str, Any], r.json())
            content = (data.get("message") or {}).get("content", "")
            return {"text": content}


def build_model_client() -> BaseModelClient:
    s = get_settings()
    prov = (s.MODEL_PROVIDER or "ollama").lower()
    if prov == "openai":
        if not s.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")
        return OpenAIClient(model=s.MODEL_NAME, api_key=s.OPENAI_API_KEY)
    if prov == "gemini":
        if not s.GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY not set")
        return GeminiClient(model=s.MODEL_NAME, api_key=s.GOOGLE_API_KEY)
    # default: ollama
    return OllamaClient(model=s.MODEL_NAME, base_url=s.OLLAMA_BASE_URL)
