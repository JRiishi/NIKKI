# Local AI Model Inference Environment

This repository establishes a completely local, high-performance AI inference infrastructure designed as the foundation for an Autonomous Software Engineering Agent.

## System Hardware Verified
- **GPU**: NVIDIA GeForce RTX 5060 Ti (16 GB dedicated GDDR6/GDDR7 VRAM, Blackwell architecture)
- **GPU Driver**: 617.14 (CUDA Driver / UMD 13.4, Compute Capability sm_120)
- **CPU**: Intel Core i7-14700K (20 cores, 28 logical processors)
- **RAM**: 32 GB DDR5 (31.71 GB detected)
- **Storage**: Dedicated storage on `D:\AI_Models` (~250 GB free space)
- **Environment**: Native Windows 11 Build 26200 (64-bit PowerShell)

---

## Installed Models

| Role | Model Identifier | Architecture / Checkpoint | Quantization | Size | Local Path | License | Primary Responsibilities |
|---|---|---|---|---|---|---|---|
| **Primary Intelligence** | `qwen3.5:9b` | Qwen 3.5 Dense (9B parameters) | Q4_K_M (4-bit) | ~5.6 GB | `D:\AI_Models\Ollama` | Apache 2.0 | Complex requirement reasoning, architecture analysis, code understanding, debugging, structured plan generation. |
| **Lightweight Intelligence** | `qwen3.5:2b` | Qwen 3.5 Dense (2B parameters) | Q4_K_M (4-bit) | ~1.6 GB | `D:\AI_Models\Ollama` | Apache 2.0 | High-speed request classification, requirement extraction, light parsing, prompt triage. |
| **Specialized System 1 Decisions** | `convaiinnovations/laya` | ModernBERT-large (~421M parameters) | `typed-decisions` (fp16) | ~850 MB | `D:\AI_Models\Laya\typed-decisions` | Apache 2.0 | Non-autoregressive single-pass (~30ms) typed decisions: task classification, priority scoring, triage, routing. |

---

## Inference Runtimes
1. **Ollama (v0.40.11)**:
   - Configured with `OLLAMA_MODELS=D:\AI_Models\Ollama`.
   - Native CUDA 13 hardware acceleration (`cuda_v13`) targeting RTX 5060 Ti.
   - Manages KV cache, GPU offloading, and context windows (8192 for 9B, 4096 for 2B).
2. **PyTorch (v2.11.0+cu128) + Laya SDK (v0.3.20)**:
   - Direct Python native inference running on `cuda:0` with `torch.float16` / autocast.
   - Direct loading of safetensors from `D:\AI_Models\Laya\typed-decisions`.

---

## Directory Layout
```
c:\Users\Riishabh Jain\Desktop\Niiki\
├── .env                  # Active runtime configuration (offline flags, paths, model IDs)
├── .env.example          # Template configuration
├── README.md             # This document
├── config/
│   └── settings.py       # Pydantic structured configuration & model specs
├── src/
│   ├── adapters/
│   │   ├── base.py           # BaseModelAdapter abstract interface
│   │   ├── ollama_adapter.py # Ollama localhost HTTP adapter (Qwen)
│   │   └── laya_adapter.py   # Laya native Python GPU adapter
│   └── service/
│       └── model_service.py  # Unified LocalModelService with VRAM-aware memory manager
├── benchmarks/
│   ├── run_benchmarks.py     # Repeatable benchmark suite
│   └── benchmark_results.json# Captured performance & latency metrics
└── tests/
    └── test_offline_and_adapters.py # Automated offline & adapter test suite
```

---

## How to Operate Fully Offline

All models run 100% locally with zero cloud API dependencies:
1. Environment variables set:
   ```bash
   HF_HUB_OFFLINE=1
   TRANSFORMERS_OFFLINE=1
   HF_DATASETS_OFFLINE=1
   OFFLINE_MODE=true
   ```
2. Ollama operates strictly against `http://127.0.0.1:11434`.
3. Laya reads local weights from `D:\AI_Models\Laya\typed-decisions` directly without connecting to Hugging Face.

---

## Starting and Stopping Inference

### 1. Starting Ollama Server
In PowerShell:
```powershell
$env:OLLAMA_MODELS = "D:\AI_Models\Ollama"
ollama serve
```

### 2. Running Benchmarks
```powershell
python benchmarks\run_benchmarks.py
```

### 3. Running Test Suite
```powershell
python -m unittest discover tests
```

### 4. Memory Management & Model Unloading
To prevent VRAM contention:
- The `LocalModelService` checks available VRAM before loading. If VRAM headroom is lower than the model budget, it automatically evicts inactive models.
- Explicit unload:
  ```python
  service.unload_model("qwen_primary")
  service.unload_model("laya_decision")
  service.unload_all()
  ```

