import os
import psutil
import torch
from typing import Dict, Any, Optional, List, Union
from config.settings import config, ModelSpec
from src.adapters.ollama_adapter import OllamaAdapter
from src.adapters.laya_adapter import LayaAdapter

class LocalModelService:
    """
    Central local model management service.
    Orchestrates memory budgets, lazy loading, proactive unloading,
    health monitoring, and decoupled inference dispatch.
    Zero external cloud API dependencies.
    """

    def __init__(self):
        # Enforce offline flags at the system level
        if config.offline_mode:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_DATASETS_OFFLINE"] = "1"

        self.adapters: Dict[str, Any] = {}
        self._init_adapters()

    def _init_adapters(self) -> None:
        for name, spec in config.models.items():
            if spec.runtime == "ollama":
                self.adapters[name] = OllamaAdapter(
                    model_name=spec.model_id,
                    host=config.ollama_host,
                    context_length=spec.context_length,
                    default_temperature=spec.temperature
                )
            elif spec.runtime == "laya_native":
                self.adapters[name] = LayaAdapter(
                    model_path=spec.local_path or str(config.laya_dir),
                    device=config.device
                )

    def get_adapter(self, model_key: str):
        if model_key not in self.adapters:
            raise KeyError(f"Unknown model key '{model_key}'. Available: {list(self.adapters.keys())}")
        return self.adapters[model_key]

    def load_model(self, model_key: str) -> None:
        """
        Memory-aware loading. Checks VRAM threshold before loading.
        """
        spec = config.models[model_key]
        current_vram = self.get_vram_usage()
        avail_vram_mb = current_vram["total_mb"] - current_vram["used_mb"]

        if avail_vram_mb < spec.vram_budget_mb:
            # Not enough headroom, unload other models first
            print(f"[ModelService] Low VRAM headroom ({avail_vram_mb:.0f}MB available, needs {spec.vram_budget_mb}MB). Evicting other models...")
            for k, adapter in self.adapters.items():
                if k != model_key and adapter.is_loaded():
                    print(f"[ModelService] Evicting model {k}...")
                    adapter.unload()

        adapter = self.get_adapter(model_key)
        adapter.load()

    def unload_model(self, model_key: str) -> None:
        adapter = self.get_adapter(model_key)
        adapter.unload()

    def unload_all(self) -> None:
        for adapter in self.adapters.values():
            adapter.unload()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def generate_text(
        self,
        model_key: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        context_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Dispatch text generation to generative LLM (Qwen).
        """
        adapter = self.get_adapter(model_key)
        if not isinstance(adapter, OllamaAdapter):
            raise TypeError(f"Model '{model_key}' does not support free-form text generation.")
        return adapter.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            context_length=context_length
        )

    def chat(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        context_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Dispatch multi-turn chat to conversational LLM (Qwen).
        """
        adapter = self.get_adapter(model_key)
        if not isinstance(adapter, OllamaAdapter):
            raise TypeError(f"Model '{model_key}' does not support conversational chat.")
        return adapter.chat(
            messages=messages,
            temperature=temperature,
            context_length=context_length
        )

    def decide(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Dict[str, Any]],
        model_key: str = "laya_decision"
    ) -> Dict[str, Any]:
        """
        Dispatch structured typed decision to System 1 decision engine (Laya).
        """
        adapter = self.get_adapter(model_key)
        if not isinstance(adapter, LayaAdapter):
            raise TypeError(f"Model '{model_key}' is not a Laya typed decision adapter.")
        return adapter.predict(state=state, questions=questions)

    def get_vram_usage(self) -> Dict[str, float]:
        total_mb = 16311.0  # RTX 5060 Ti 16GB
        used_mb = 0.0
        free_mb = total_mb

        if torch.cuda.is_available():
            free_b, total_b = torch.cuda.mem_get_info()
            total_mb = round(total_b / (1024 * 1024), 2)
            free_mb = round(free_b / (1024 * 1024), 2)
            used_mb = round(total_mb - free_mb, 2)

        return {
            "total_mb": total_mb,
            "used_mb": used_mb,
            "free_mb": free_mb,
            "utilization_pct": round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0
        }

    def get_system_ram_usage(self) -> Dict[str, float]:
        vm = psutil.virtual_memory()
        return {
            "total_mb": round(vm.total / (1024 * 1024), 2),
            "available_mb": round(vm.available / (1024 * 1024), 2),
            "used_mb": round(vm.used / (1024 * 1024), 2),
            "percent": vm.percent
        }

    def health_check(self) -> Dict[str, Any]:
        results = {}
        for name, adapter in self.adapters.items():
            results[name] = adapter.health_check()
        vram = self.get_vram_usage()
        ram = self.get_system_ram_usage()
        return {
            "models": results,
            "vram": vram,
            "ram": ram,
            "offline_mode": config.offline_mode
        }

