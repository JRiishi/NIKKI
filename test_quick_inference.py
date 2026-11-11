import urllib.request
import json
import time

def test_gen(model, prompt):
    print(f"Testing {model}...")
    url = "http://127.0.0.1:11434/api/generate"
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 2048, "temperature": 0.1}
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    t_tot = time.time() - t0
    eval_c = res.get("eval_count", 0)
    eval_d = res.get("eval_duration", 1) / 1e9
    tps = eval_c / eval_d if eval_d > 0 else 0
    resp_text = res.get("response", "").replace("\n", " ")
    print(f"  Response in {t_tot:.2f}s | {eval_c} tokens at {tps:.2f} tok/s")
    print(f"  Sample: {resp_text[:140]}...")

if __name__ == "__main__":
    test_gen("qwen3.5:2b", "What are 3 essential principles of high-reliability microservices?")
    test_gen("qwen3.5:9b", "Explain how an ACID transaction is implemented using Write-Ahead Logging (WAL).")

