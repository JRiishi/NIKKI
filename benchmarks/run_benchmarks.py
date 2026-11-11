import os
import sys
import time
import json
from pathlib import Path
import psutil
import torch

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import config
from src.service.model_service import LocalModelService

def get_vram_and_ram():
    vram_used = 0.0
    if torch.cuda.is_available():
        free_b, total_b = torch.cuda.mem_get_info()
        vram_used = round((total_b - free_b) / (1024 * 1024), 2)
    ram_used = round(psutil.virtual_memory().used / (1024 * 1024), 2)
    return vram_used, ram_used

def run_benchmarks():
    print("=" * 70)
    print("AUTONOMOUS SOFTWARE ENGINEERING AGENT — BENCHMARK SUITE")
    print("=" * 70)

    service = LocalModelService()
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": {
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "cpu": os.environ.get("PROCESSOR_IDENTIFIER", "Intel Core i7-14700K"),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
        "models": {}
    }

    # -------------------------------------------------------------
    # 1. BENCHMARK: LAYA (Specialized System 1 Decision Model)
    # -------------------------------------------------------------
    print("\n>>> Benchmarking LAYA (System 1 Decision Engine: typed-decisions)")
    vram_before, ram_before = get_vram_and_ram()
    t_start = time.perf_counter()
    service.load_model("laya_decision")
    t_load = time.perf_counter() - t_start

    laya_task_state = (
        "Customer Bug Report: Users report that when clicking 'Export CSV' on the billing dashboard, "
        "the page hangs indefinitely and returns HTTP 504 Gateway Timeout. Error logs show high memory "
        "exhaustion in ExportWorkerThread when query result exceeds 50,000 rows. Needs investigation and fix."
    )
    laya_questions = {
        "task_category": {
            "type": "choice",
            "instructions": "Classify this software engineering issue into one category:",
            "criteria": {
                "bugfix": "Fixing defect or crash in existing functionality",
                "feature": "Building brand new user feature",
                "infra": "Cloud infrastructure and CI/CD operations",
                "security": "Remediating security vulnerability"
            }
        },
        "severity": {
            "type": "score",
            "instructions": "Rate the severity from 0 (trivial) to 3 (critical outage):",
            "criteria": ["P3 - Trivial", "P2 - Minor inconvenience", "P1 - Significant degraded service", "P0 - Total outage"]
        },
        "requires_hotfix": {
            "type": "noul",
            "instructions": "Does this issue require a high-priority hotfix deployment?",
            "criteria": {"true": "Requires expedited hotfix", "false": "Can wait for next scheduled release"}
        }
    }

    # Run warm-up and 3 timed iterations
    latencies = []
    laya_output = None
    for i in range(3):
        res = service.decide(laya_task_state, laya_questions, model_key="laya_decision")
        latencies.append(res["latency_ms"])
        laya_output = res

    vram_peak, ram_peak = get_vram_and_ram()
    avg_latency = round(sum(latencies) / len(latencies), 2)
    print(f" - Model load time: {t_load:.2f} s")
    print(f" - Average forward pass latency: {avg_latency} ms (runs: {latencies})")
    print(f" - Peak VRAM: {vram_peak} MB | Peak RAM: {ram_peak} MB")
    print(" - Output choices & probabilities:")
    for qid, ans in laya_output["answers"].items():
        val = ans.get("choice") or ans.get("score") or ans.get("noul")
        print(f"   * {qid}: {val} (conf: {ans.get('confidence', 'N/A')})")

    results["models"]["laya_decision"] = {
        "load_time_s": round(t_load, 2),
        "avg_latency_ms": avg_latency,
        "runs_ms": latencies,
        "peak_vram_mb": vram_peak,
        "peak_ram_mb": ram_peak,
        "answers": laya_output["answers"],
        "device": laya_output["device"]
    }

    # -------------------------------------------------------------
    # 2. BENCHMARK: QWEN LIGHTWEIGHT (Qwen3.5:2B)
    # -------------------------------------------------------------
    print("\n>>> Benchmarking QWEN LIGHTWEIGHT (Qwen3.5:2B - Triage, Extraction, Fast Loop)")
    service.load_model("qwen_lightweight")

    # Task A: Extraction
    extraction_prompt = (
        "Extract the core functional requirements from this product idea as a concise JSON list with keys 'id', 'title', 'priority':\n"
        "'We need an automated pull request reviewer that scans Python diffs for missing type hints, "
        "security vulnerabilities like SQL injection, and runs pytest on isolated containers before reporting inline comments.'"
    )
    t0 = time.perf_counter()
    resp_2b_a = service.generate_text("qwen_lightweight", extraction_prompt, temperature=0.1)
    vram_peak_2b, ram_peak_2b = get_vram_and_ram()

    # Task B: Classification
    classify_prompt = (
        "Classify the following user request into exactly one category: [ARCHITECTURE, REFACTOR, BUGFIX, DOCUMENTATION]. "
        "Request: 'The database connection pool frequently runs out of handles under peak traffic during nightly batch jobs.'\n"
        "Category:"
    )
    resp_2b_b = service.generate_text("qwen_lightweight", classify_prompt, temperature=0.0)

    print(f" - 2B Eval Speed: {resp_2b_a['eval_tok_per_sec']} tokens/s")
    print(f" - 2B Prompt Eval Speed: {resp_2b_a['prompt_eval_tok_per_sec']} tokens/s")
    print(f" - 2B Tokens Generated: {resp_2b_a['eval_tokens']} tokens in {resp_2b_a['total_duration_s']} s")
    print(f" - 2B Peak VRAM: {vram_peak_2b} MB | Peak RAM: {ram_peak_2b} MB")
    print(f" - Classification sample output: {resp_2b_b['response'].strip()}")

    results["models"]["qwen_lightweight"] = {
        "eval_tok_per_sec": resp_2b_a["eval_tok_per_sec"],
        "prompt_eval_tok_per_sec": resp_2b_a["prompt_eval_tok_per_sec"],
        "eval_tokens": resp_2b_a["eval_tokens"],
        "total_duration_s": resp_2b_a["total_duration_s"],
        "peak_vram_mb": vram_peak_2b,
        "peak_ram_mb": ram_peak_2b,
        "sample_output_classification": resp_2b_b["response"].strip()
    }

    # -------------------------------------------------------------
    # 3. BENCHMARK: QWEN PRIMARY (Qwen3.5:9B)
    # -------------------------------------------------------------
    print("\n>>> Benchmarking QWEN PRIMARY (Qwen3.5:9B - Complex Reasoning, Architecture, Code Understanding)")
    service.load_model("qwen_primary")

    # Task C: Code Analysis & Bug Finding
    code_snippet = '''
def process_refund(order_id, user_id, amount):
    tx = db.get_transaction(order_id)
    if tx.status == "COMPLETED":
        refund_gateway.call(user_id, amount)
        tx.status = "REFUNDED"
        db.save(tx)
        return True
    return False
'''
    code_prompt = (
        f"Analyze this Python snippet for concurrency bugs, idempotency flaws, and failure modes. "
        f"Provide a root-cause explanation and the fixed implementation:\n```python{code_snippet}```"
    )
    resp_9b_code = service.generate_text("qwen_primary", code_prompt, temperature=0.2)

    # Task D: Structured Plan Generation
    plan_prompt = (
        "Generate a structured 4-phase technical development plan for creating a distributed task scheduler "
        "with Redis and asyncio in Python. For each phase include: Objective, Key Components, and Verification Test."
    )
    resp_9b_plan = service.generate_text("qwen_primary", plan_prompt, temperature=0.2)
    vram_peak_9b, ram_peak_9b = get_vram_and_ram()

    print(f" - 9B Eval Speed: {resp_9b_code['eval_tok_per_sec']} tokens/s")
    print(f" - 9B Prompt Eval Speed: {resp_9b_code['prompt_eval_tok_per_sec']} tokens/s")
    print(f" - 9B Tokens Generated: {resp_9b_code['eval_tokens']} tokens in {resp_9b_code['total_duration_s']} s")
    print(f" - 9B Peak VRAM: {vram_peak_9b} MB | Peak RAM: {ram_peak_9b} MB")

    results["models"]["qwen_primary"] = {
        "eval_tok_per_sec": resp_9b_code["eval_tok_per_sec"],
        "prompt_eval_tok_per_sec": resp_9b_code["prompt_eval_tok_per_sec"],
        "eval_tokens": resp_9b_code["eval_tokens"],
        "total_duration_s": resp_9b_code["total_duration_s"],
        "peak_vram_mb": vram_peak_9b,
        "peak_ram_mb": ram_peak_9b,
        "code_response_summary": resp_9b_code["response"][:300] + "..."
    }

    # Save benchmark results
    out_path = Path(__file__).resolve().parent / "benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Benchmark results successfully saved to: {out_path}")

    return results

if __name__ == "__main__":
    run_benchmarks()

