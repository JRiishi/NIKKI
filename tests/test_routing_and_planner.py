import unittest
from src.gateway.request_gateway import RequestGateway
from src.router.laya_engine import LayaRouterEngine
from src.planner.smart_planner import SmartPlanner
from src.memory.working_memory import TaskNode
from src.service.model_service import LocalModelService

class TestRoutingAndPlanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = LocalModelService()
        cls.gateway = RequestGateway()
        cls.router = LayaRouterEngine(cls.service)
        cls.planner = SmartPlanner(cls.service)

    def test_01_gateway_intent_classification(self):
        req1 = self.gateway.validate_and_route("Fix null pointer exception when processing payment")
        self.assertEqual(req1.inferred_category, "bugfix")

        req2 = self.gateway.validate_and_route("Refactor user model to decouple auth token storage")
        self.assertEqual(req2.inferred_category, "refactoring")

        with self.assertRaises(ValueError):
            self.gateway.validate_and_route("   ")

    def test_02_laya_router_deterministic_fast_path(self):
        task_test = TaskNode(id="t1", title="Run pytest on billing module", description="Execute unit tests")
        routing = self.router.route_task(task_test)
        self.assertEqual(routing["assigned_to"], "deterministic_worker")
        self.assertEqual(routing["confidence"], 1.0)

    def test_03_laya_router_decision_head(self):
        task_code = TaskNode(
            id="t2",
            title="Implement distributed lock with Redis",
            description="Write Redis lock implementation with lease TTL renewal."
        )
        routing = self.router.route_task(task_code)
        self.assertIn("assigned_to", routing)
        self.assertIn(routing["assigned_to"], ["coder_worker_9b", "fast_worker_2b", "deterministic_worker"])
        self.assertGreater(routing["confidence"], 0.0)

    def test_04_smart_planner_dag_generation(self):
        plan = self.planner.create_plan(
            goal="Add rate limiting middleware using sliding window algorithm in FastAPI",
            category="feature"
        )
        self.assertIsInstance(plan, list)
        self.assertGreaterEqual(len(plan), 2)
        # Verify first task has no unfulfilled dependencies
        self.assertEqual(len(plan[0].dependencies), 0)

if __name__ == "__main__":
    unittest.main()

