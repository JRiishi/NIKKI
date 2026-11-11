import unittest
import os
from pathlib import Path
from src.orchestrator.orchestrator import AgentOrchestrator
from src.service.model_service import LocalModelService

class TestEndToEndAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = LocalModelService()
        cls.orchestrator = AgentOrchestrator(model_service=cls.service)

    @classmethod
    def tearDownClass(cls):
        target_file = Path("src/string_utils.py")
        if target_file.exists():
            try:
                target_file.unlink(missing_ok=True)
            except Exception:
                pass
        test_file = Path("tests/test_string_utils.py")
        if test_file.exists():
            try:
                test_file.unlink(missing_ok=True)
            except Exception:
                pass

    def test_01_orchestrator_execution_lifecycle(self):
        """Test full agent lifecycle: gateway -> planner -> laya router -> worker -> verification."""
        goal = "Create a python module `src/string_utils.py` with a function `slugify(text: str) -> str` that lowercases, replaces spaces with hyphens, and removes non-alphanumeric characters."
        
        result = self.orchestrator.run(goal)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "COMPLETED")
        self.assertGreaterEqual(result.tasks_completed, 1)
        self.assertIsNotNone(result.verification)
        self.assertTrue(result.verification.passed)

        # Verify created file
        target_file = Path("src/string_utils.py")
        if target_file.exists():
            content = target_file.read_text(encoding="utf-8")
            self.assertIn("slugify", content)

if __name__ == "__main__":
    unittest.main()

