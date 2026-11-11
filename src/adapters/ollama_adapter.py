import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from src.adapters.base import BaseModelAdapter

def ensure_ollama_running(host: str = "http://127.0.0.1:11434", model_dir: Optional[str] = None, max_wait_s: int = 10) -> bool:
    """
    Check if local Ollama daemon is responsive; if not, attempt to start it automatically.
    """
    clean_host = host.rstrip("/")
    try:
        req = urllib.request.Request(f"{clean_host}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    target_model_dir = model_dir or os.environ.get("OLLAMA_MODELS", "D:\\AI_Models\\Ollama")
    try:
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(target_model_dir)
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS

        subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )

        t_start = time.time()
        while time.time() - t_start < max_wait_s:
            time.sleep(1)
            try:
                req = urllib.request.Request(f"{clean_host}/api/tags")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False

class OllamaAdapter(BaseModelAdapter):
    """
    Adapter for models running inside local Ollama instance (Qwen3.5:9B, Qwen3.5:2B).
    Provides structured generation, timing metrics, VRAM inspection, and dynamic unloading.
    Communicates purely over localhost HTTP (127.0.0.1:11434).
    """

    def __init__(
        self,
        model_name: str,
        host: str = "http://127.0.0.1:11434",
        context_length: int = 8192,
        default_temperature: float = 0.2
    ):
        self.model_name = model_name
        self.host = host.rstrip("/")
        self.context_length = context_length
        self.default_temperature = default_temperature

    def _post(self, endpoint: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
        url = f"{self.host}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            # Auto-recovery: try to start Ollama if stopped
            if ensure_ollama_running(self.host):
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return json.loads(resp.read().decode("utf-8"))
                except Exception:
                    pass
            raise ConnectionError(f"Failed to connect to Ollama at {url}: {e}. Ensure Ollama is running ('ollama serve').")

    def _get(self, endpoint: str, timeout: int = 10) -> Dict[str, Any]:
        url = f"{self.host}{endpoint}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if ensure_ollama_running(self.host):
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return json.loads(resp.read().decode("utf-8"))
                except Exception:
                    pass
            raise ConnectionError(f"Failed to connect to Ollama at {url}: {e}. Ensure Ollama is running ('ollama serve').")

    def load(self, keep_alive: str = "30m") -> None:
        """
        Warm up and load model into GPU memory with keep_alive duration.
        """
        payload = {
            "model": self.model_name,
            "prompt": "",
            "keep_alive": keep_alive
        }
        self._post("/api/generate", payload)

    def unload(self) -> None:
        """
        Immediately evict the model from GPU VRAM by setting keep_alive to 0.
        """
        payload = {
            "model": self.model_name,
            "keep_alive": 0
        }
        try:
            self._post("/api/generate", payload)
        except Exception:
            pass

    def is_loaded(self) -> bool:
        """
        Inspect currently loaded models via /api/ps.
        """
        try:
            data = self._get("/api/ps")
            models = data.get("models", [])
            for m in models:
                if m.get("name") == self.model_name or m.get("model") == self.model_name:
                    return True
            return False
        except Exception:
            return False

    def get_resource_usage(self) -> Dict[str, Any]:
        try:
            data = self._get("/api/ps")
            models = data.get("models", [])
            for m in models:
                if m.get("name") == self.model_name or m.get("model") == self.model_name:
                    vram_mb = round(m.get("size_vram", 0) / (1024 * 1024), 2)
                    size_mb = round(m.get("size", 0) / (1024 * 1024), 2)
                    return {
                        "loaded": True,
                        "model": self.model_name,
                        "vram_mb": vram_mb,
                        "size_mb": size_mb,
                        "expires_at": m.get("expires_at"),
                        "details": m.get("details", {})
                    }
            return {
                "loaded": False,
                "model": self.model_name,
                "vram_mb": 0.0,
                "size_mb": 0.0
            }
        except Exception as e:
            return {"loaded": False, "error": str(e)}

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        context_length: Optional[int] = None,
        raw: bool = False,
        keep_alive: str = "30m"
    ) -> Dict[str, Any]:
        """
        Execute synchronous prompt completion and capture performance metrics.
        """
        ctx_len = context_length or self.context_length
        temp = temperature if temperature is not None else self.default_temperature

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "raw": raw,
            "keep_alive": keep_alive,
            "options": {
                "num_ctx": ctx_len,
                "temperature": temp
            }
        }
        if system:
            payload["system"] = system

        t0 = time.perf_counter()
        resp = self._post("/api/generate", payload)
        wall_time_s = time.perf_counter() - t0

        total_duration_s = resp.get("total_duration", 0) / 1e9
        load_duration_s = resp.get("load_duration", 0) / 1e9
        prompt_eval_count = resp.get("prompt_eval_count", 0)
        prompt_eval_duration_s = resp.get("prompt_eval_duration", 0) / 1e9
        eval_count = resp.get("eval_count", 0)
        eval_duration_s = resp.get("eval_duration", 0) / 1e9

        prompt_eval_tok_per_sec = (prompt_eval_count / prompt_eval_duration_s) if prompt_eval_duration_s > 0 else 0.0
        eval_tok_per_sec = (eval_count / eval_duration_s) if eval_duration_s > 0 else 0.0

        return {
            "model": self.model_name,
            "response": resp.get("response", ""),
            "prompt_tokens": prompt_eval_count,
            "eval_tokens": eval_count,
            "total_duration_s": round(total_duration_s or wall_time_s, 3),
            "load_duration_s": round(load_duration_s, 3),
            "prompt_eval_tok_per_sec": round(prompt_eval_tok_per_sec, 2),
            "eval_tok_per_sec": round(eval_tok_per_sec, 2),
            "wall_time_s": round(wall_time_s, 3)
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        context_length: Optional[int] = None,
        keep_alive: str = "30m"
    ) -> Dict[str, Any]:
        """
        Execute chat message completion.
        """
        ctx_len = context_length or self.context_length
        temp = temperature if temperature is not None else self.default_temperature

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {
                "num_ctx": ctx_len,
                "temperature": temp
            }
        }

        t0 = time.perf_counter()
        resp = self._post("/api/chat", payload)
        wall_time_s = time.perf_counter() - t0

        msg = resp.get("message", {})
        total_duration_s = resp.get("total_duration", 0) / 1e9
        eval_count = resp.get("eval_count", 0)
        eval_duration_s = resp.get("eval_duration", 0) / 1e9
        eval_tok_per_sec = (eval_count / eval_duration_s) if eval_duration_s > 0 else 0.0

        return {
            "model": self.model_name,
            "message": msg,
            "content": msg.get("content", ""),
            "prompt_tokens": resp.get("prompt_eval_count", 0),
            "eval_tokens": eval_count,
            "eval_tok_per_sec": round(eval_tok_per_sec, 2),
            "total_duration_s": round(total_duration_s or wall_time_s, 3),
            "wall_time_s": round(wall_time_s, 3)
        }

    def health_check(self) -> Dict[str, Any]:
        try:
            tags = self._get("/api/tags")
            models = [m.get("name") for m in tags.get("models", [])]
            return {
                "status": "healthy",
                "host": self.host,
                "model_present": any(self.model_name in m for m in models),
                "loaded": self.is_loaded()
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

