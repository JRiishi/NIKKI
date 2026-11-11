import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODELS_DIR = Path(os.environ.get("MODELS_DIR", r"D:\AI_Models"))
DEFAULT_OLLAMA_DIR = DEFAULT_MODELS_DIR / "Ollama"
DEFAULT_LAYA_DIR = DEFAULT_MODELS_DIR / "Laya" / "typed-decisions"

class ModelSpec(BaseModel):
    name: str
    runtime: str = "ollama"  # ollama | laya_native
    model_id: str
    local_path: Optional[str] = None
    quantization: str = "Q4_K_M"
    context_length: int = 8192
    temperature: float = 0.2
    vram_budget_mb: int = 6000
    description: str = ""

class SystemConfig(BaseModel):
    ollama_host: str = Field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
    models_dir: Path = DEFAULT_MODELS_DIR
    ollama_dir: Path = DEFAULT_OLLAMA_DIR
    laya_dir: Path = DEFAULT_LAYA_DIR
    offline_mode: bool = Field(default_factory=lambda: os.environ.get("OFFLINE_MODE", "true").lower() in ("1", "true"))
    device: str = "cuda:0"
    max_concurrent_models: int = 2
    vram_threshold_mb: int = 14000  # RTX 5060 Ti 16GB total; keep headroom

    models: Dict[str, ModelSpec] = {
        "qwen_primary": ModelSpec(
            name="qwen_primary",
            runtime="ollama",
            model_id="qwen3.5:9b",
            quantization="Q4_K_M (4-bit)",
            context_length=8192,
            temperature=0.2,
            vram_budget_mb=6200,
            description="Stronger model for complex reasoning, architecture planning, code comprehension, and debugging."
        ),
        "qwen_lightweight": ModelSpec(
            name="qwen_lightweight",
            runtime="ollama",
            model_id="qwen3.5:2b",
            quantization="Q4_K_M (4-bit)",
            context_length=4096,
            temperature=0.1,
            vram_budget_mb=2000,
            description="Lightweight model for quick triage, classification, light parsing, and fast response loops."
        ),
        "laya_decision": ModelSpec(
            name="laya_decision",
            runtime="laya_native",
            model_id="convaiinnovations/laya",
            local_path=str(DEFAULT_LAYA_DIR),
            quantization="fp16",
            context_length=512,
            temperature=1.0,
            vram_budget_mb=1000,
            description="Specialized non-autoregressive System 1 decision engine for deterministic routing and typed choices."
        )
    }

config = SystemConfig()

