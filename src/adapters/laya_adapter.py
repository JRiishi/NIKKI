import os
import time
import torch
from typing import Dict, Any, List, Optional, Union
from src.adapters.base import BaseModelAdapter

class LayaAdapter(BaseModelAdapter):
    """
    Adapter for Convai Innovations Laya (System 1 Decision Engine).
    Provides non-autoregressive, calibrated typed decisions (choice, score, noul).
    Runs strictly locally on NVIDIA GPU (or CPU fallback) without external API dependencies.
    """

    def __init__(
        self,
        model_path: str = r"D:\AI_Models\Laya\typed-decisions",
        device: str = "cuda:0",
        fast: bool = False
    ):
        self.model_path = model_path
        self.target_device = device
        self.fast = fast
        self.agent = None
        self._is_loaded = False
        self.last_load_time_s = 0.0

    def load(self) -> None:
        if self._is_loaded and self.agent is not None:
            return

        import laya
        t0 = time.perf_counter()
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Local Laya weights not found at: {self.model_path}")

        # Enforce offline mode for Hugging Face
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        device_to_use = self.target_device if torch.cuda.is_available() else "cpu"
        self.agent = laya.load(self.model_path, device=device_to_use, fast=self.fast)
        self.last_load_time_s = time.perf_counter() - t0
        self._is_loaded = True

    def unload(self) -> None:
        if self.agent is not None:
            del self.agent
            self.agent = None
        self._is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    def is_loaded(self) -> bool:
        return self._is_loaded and self.agent is not None

    def predict(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute single-pass non-autoregressive decision inference.
        `questions` schema:
          {
            "question_id": {
              "type": "choice" | "score" | "noul",
              "instructions": "...",
              "criteria": ... # dict or list depending on type
            }
          }
        """
        if not self.is_loaded():
            self.load()

        t0 = time.perf_counter()
        raw_res = self.agent.predict(state, questions)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "answers": raw_res.get("answers", {}),
            "usage": raw_res.get("usage", {}),
            "latency_ms": round(latency_ms, 2),
            "device": str(self.agent.device)
        }

    def get_resource_usage(self) -> Dict[str, Any]:
        vram_allocated_mb = 0.0
        vram_reserved_mb = 0.0
        if torch.cuda.is_available():
            vram_allocated_mb = round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
            vram_reserved_mb = round(torch.cuda.memory_reserved() / (1024 * 1024), 2)

        return {
            "loaded": self.is_loaded(),
            "device": str(self.agent.device) if self.agent else self.target_device,
            "vram_allocated_mb": vram_allocated_mb,
            "vram_reserved_mb": vram_reserved_mb,
            "load_time_s": round(self.last_load_time_s, 3)
        }

    def health_check(self) -> Dict[str, Any]:
        test_state = "Health ping"
        test_q = {
            "ping": {
                "type": "noul",
                "instructions": "Is this a valid service health ping?"
            }
        }
        try:
            res = self.predict(test_state, test_q)
            return {
                "status": "healthy",
                "inference_latency_ms": res["latency_ms"],
                "device": res["device"],
                "vram_mb": self.get_resource_usage()["vram_allocated_mb"]
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
