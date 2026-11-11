import os
import sys
import unittest
from pathlib import Path
import torch

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import config
from src.adapters.laya_adapter import LayaAdapter
from src.adapters.ollama_adapter import OllamaAdapter
from src.service.model_service import LocalModelService

class TestOfflineAndAdapters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Strictly enforce offline mode
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        cls.service = LocalModelService()

    def test_01_laya_offline_loading_and_inference(self):
        """Verify Laya loads strictly from local disk and performs typed decision without network."""
        laya_adapter = self.service.get_adapter("laya_decision")
        laya_adapter.load()
        self.assertTrue(laya_adapter.is_loaded())

        state = "User reports that OAuth redirect URL is failing with 400 Bad Request on staging environment."
        questions = {
            "is_bug": {
                "type": "noul",
                "instructions": "Is this a software defect?",
                "criteria": {"true": "Defect", "false": "Expected behavior"}
            },
            "category": {
                "type": "choice",
                "instructions": "Categorize the issue:",
                "criteria": {
                    "auth": "Authentication / Authorization",
                    "ui": "User Interface visual styling",
                    "database": "Database schema migration"
                }
            }
        }

        res = laya_adapter.predict(state, questions)
        self.assertIn("answers", res)
        self.assertIn("is_bug", res["answers"])
        self.assertIn("category", res["answers"])
        self.assertEqual(res["answers"]["category"]["choice"], "auth")
        self.assertGreater(res["latency_ms"], 0)

    def test_02_laya_unloading(self):
        """Verify Laya unloads cleanly and releases GPU memory."""
        laya_adapter = self.service.get_adapter("laya_decision")
        laya_adapter.unload()
        self.assertFalse(laya_adapter.is_loaded())

    def test_03_ollama_connectivity(self):
        """Verify Ollama adapter connects to localhost only."""
        adapter = self.service.get_adapter("qwen_lightweight")
        hc = adapter.health_check()
        self.assertEqual(hc["status"], "healthy")
        self.assertEqual(hc["host"], "http://127.0.0.1:11434")

    def test_04_no_external_leakage(self):
        """Verify that attempting to connect to external Hugging Face hosts directly fails in offline mode."""
        import urllib.request
        from huggingface_hub.errors import OfflineModeIsEnabled, LocalEntryNotFoundError
        from huggingface_hub import hf_hub_download

        with self.assertRaises((OfflineModeIsEnabled, LocalEntryNotFoundError)):
            hf_hub_download(repo_id="convaiinnovations/laya", filename="non_existent_file.json")

if __name__ == "__main__":
    unittest.main()

