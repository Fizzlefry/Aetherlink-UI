from __future__ import annotations
from typing import List
import os
import json
import http.client
import urllib.parse

class BaseEmbedder:
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Minimal, dependency-free HTTP client to avoid adding SDKs
        body = json.dumps({"model": self.model, "input": texts})
        conn = http.client.HTTPSConnection("api.openai.com")
        conn.request("POST", "/v1/embeddings", body=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return [d["embedding"] for d in data["data"]]

class OllamaEmbedder(BaseEmbedder):
    def __init__(self, model: str, base_url: str):
        self.model = model
        parsed = urllib.parse.urlparse(base_url or "http://localhost:11434")
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.scheme = parsed.scheme

    def embed(self, texts: List[str]) -> List[List[float]]:
        # Ollama embeds endpoint
        results: List[List[float]] = []
        for t in texts:
            body = json.dumps({"model": self.model, "prompt": t})
            if self.scheme == "https":
                conn = http.client.HTTPSConnection(self.host, self.port)
            else:
                conn = http.client.HTTPConnection(self.host, self.port)
            conn.request("POST", "/api/embeddings", body=body, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            conn.close()
            results.append(data["embedding"])
        return results

class GeminiEmbedder(BaseEmbedder):
    # Placeholder (text-only fallback if not available)
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        # For now, fallback: hash-based pseudo-embeddings to keep flow unblocked (replace with real Gemini Embeddings API when desired)
        import hashlib, random
        random.seed(1337)
        vecs = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            # downsample to 256 dims
            vec = [(b-128)/128.0 for b in h] * 4  # 32*4=128; double again
            vecs.append(vec[:256])
        return vecs

def build_embedder(provider: str, model: str, settings) -> BaseEmbedder:
    p = provider.lower()
    if p == "openai":
        key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY missing for openai embedder")
        return OpenAIEmbedder(model, key)
    if p == "ollama":
        base = getattr(settings, "OLLAMA_BASE_URL", None) or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaEmbedder(model, base)
    if p == "gemini":
        key = getattr(settings, "GOOGLE_API_KEY", None) or os.environ.get("GOOGLE_API_KEY")
        if not key:
            # Fallback to pseudo-embeddings if key missing; non-fatal for local dev
            return GeminiEmbedder(model, "FAKE")
        return GeminiEmbedder(model, key)
    raise ValueError(f"Unknown EMBED_PROVIDER={provider}")
