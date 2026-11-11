import unittest
import tempfile
from pathlib import Path
from src.tools.file_tools import ReadFileTool, WriteFileTool, PatchFileTool, ListDirTool
from src.tools.test_tools import RunLintTool
from src.tools.terminal_tools import RunCommandTool
from src.tools.registry import ToolRegistry, PermissionGate, AutonomyMode, PermissionTier

class TestToolsAndSafety(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_file_tools(self):
        f = self.tmp / "test.txt"
        w_tool = WriteFileTool()
        w_res = w_tool.execute(path=str(f), content="line1\nline2\nline3\n")
        self.assertTrue(w_res.success)

        r_tool = ReadFileTool()
        r_res = r_tool.execute(path=str(f), start_line=2, end_line=3)
        self.assertTrue(r_res.success)
        self.assertEqual(r_res.output["content"], "line2\nline3\n")

        p_tool = PatchFileTool()
        p_res = p_tool.execute(path=str(f), target="line2", replacement="line_patched")
        self.assertTrue(p_res.success)
        self.assertIn("line_patched", f.read_text(encoding="utf-8"))

    def test_02_lint_tool(self):
        valid_py = self.tmp / "valid.py"
        valid_py.write_text("def add(a, b):\n    return a + b\n")

        invalid_py = self.tmp / "invalid.py"
        invalid_py.write_text("def add(a, b\n    return a + b\n")

        lint_tool = RunLintTool()
        self.assertTrue(lint_tool.execute(file_path=str(valid_py)).success)

        bad_res = lint_tool.execute(file_path=str(invalid_py))
        self.assertFalse(bad_res.success)
        self.assertIn("SyntaxError", bad_res.error)

    def test_03_permission_gate_and_blocked_commands(self):
        cmd_tool = RunCommandTool()
        res = cmd_tool.execute(command="rm -rf /")
        self.assertFalse(res.success)
        self.assertIn("prohibited dangerous substring", res.error)

        # Supervised gate check
        gate = PermissionGate(mode=AutonomyMode.SUPERVISED)
        registry = ToolRegistry(permission_gate=gate)
        # Attempt writing in supervised mode without approval callback
        denied_res = registry.execute("write_file", path="dummy.txt", content="denied")
        self.assertFalse(denied_res.success)
        self.assertIn("Permission denied", denied_res.error)

if __name__ == "__main__":
    unittest.main()

