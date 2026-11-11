import unittest
import tempfile
from pathlib import Path
from src.memory.state_db import StateDatabase
from src.memory.working_memory import WorkingMemory, TaskNode
from src.memory.project_memory import ProjectMemory, compute_file_hash
from src.memory.execution_history import ExecutionHistory
from src.memory.retriever import ContextRetriever

class TestMemorySystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_state.db"
        self.db = StateDatabase(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_session_and_working_memory(self):
        wm = WorkingMemory(self.db, session_id="test_sess_01")
        wm.initialize_session("Build a distributed cache module.")

        task1 = TaskNode(id="t1", title="Design schema", description="Create key-value schema", dependencies=[])
        task2 = TaskNode(id="t2", title="Implement cache", description="Write cache class", dependencies=["t1"])
        wm.set_task_graph([task1, task2])

        # Initially, only t1 is runnable (t2 depends on t1)
        next_task = wm.get_next_runnable_task()
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task.id, "t1")

        # Complete t1
        wm.update_task_status("t1", status="COMPLETED", outputs={"schema": "dict[str, Any]"})
        next_task = wm.get_next_runnable_task()
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task.id, "t2")

        # Complete t2
        wm.update_task_status("t2", status="COMPLETED")
        self.assertTrue(wm.is_goal_complete())

    def test_02_project_memory_and_staleness(self):
        pm = ProjectMemory(self.db)
        pm.record_decision("Cache Backend", "Use Redis for shared state.")
        pm.record_convention("Docstrings", "Google style docstrings required.")

        test_file = Path(self.temp_dir.name) / "sample.py"
        test_file.write_text("print('hello world')", encoding="utf-8")

        pm.record_file_summary(test_file, "Prints hello world")
        self.assertFalse(pm.is_file_stale(test_file))

        # Modify file and verify staleness
        test_file.write_text("print('hello world 2')", encoding="utf-8")
        self.assertTrue(pm.is_file_stale(test_file))

    def test_03_execution_history_and_retriever(self):
        eh = ExecutionHistory(self.db, session_id="test_sess_02")
        eh.record_tool_call("write_file", {"path": "main.py"}, "Success", "SUCCESS", 12.5, "t1")
        eh.record_tool_call("run_lint", {"file": "main.py"}, "Syntax error", "ERROR", 5.0, "t1")

        recent = eh.get_recent_traces(limit=5)
        self.assertEqual(len(recent), 2)
        errors = eh.get_recent_errors(limit=5)
        self.assertEqual(len(errors), 1)

        wm = WorkingMemory(self.db, session_id="test_sess_02")
        wm.initialize_session("Test Goal")
        pm = ProjectMemory(self.db)
        task = TaskNode(id="t1", title="Test Task", description="Testing retriever")
        wm.set_task_graph([task])

        retriever = ContextRetriever(wm, pm, eh)
        ctx = retriever.get_task_context("t1")
        self.assertIn("HIGH-LEVEL GOAL", ctx)
        self.assertIn("write_file", ctx)

    def test_04_multiple_set_task_graph_no_conflict(self):
        """Verify calling set_task_graph multiple times in same session does not raise IntegrityError."""
        wm = WorkingMemory(self.db, session_id="test_sess_03")
        wm.initialize_session("Multi-run session")

        # First run
        t1 = TaskNode(id="task_1", title="First run t1", dependencies=[])
        t2 = TaskNode(id="task_2", title="First run t2", dependencies=["task_1"])
        wm.set_task_graph([t1, t2])
        self.assertEqual(len(wm.tasks), 2)

        # Second run with same task IDs in same session (must upsert / clear cleanly)
        t1_new = TaskNode(id="task_1", title="Second run t1 updated", dependencies=[])
        t2_new = TaskNode(id="task_2", title="Second run t2 updated", dependencies=["task_1"])
        t3_new = TaskNode(id="task_3", title="Second run t3 new", dependencies=["task_2"])
        wm.set_task_graph([t1_new, t2_new, t3_new])
        self.assertEqual(len(wm.tasks), 3)

        tasks_in_db = self.db.get_tasks_for_session("test_sess_03")
        self.assertEqual(len(tasks_in_db), 3)
        self.assertEqual(tasks_in_db[0]["title"], "Second run t1 updated")

if __name__ == "__main__":
    unittest.main()

