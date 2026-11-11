import unittest
from src.service.model_service import LocalModelService
from src.gateway.interactive_session import InteractiveSession

class TestInteractiveSession(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.service = LocalModelService()

    def test_01_greeting_does_not_trigger_execution(self):
        session = InteractiveSession(model_service=self.service)
        reply, goal = session.handle_message("Hello")
        self.assertIsNotNone(reply)
        self.assertIsNone(goal, "Greeting should not trigger code execution.")
        self.assertTrue("nikki" in reply.lower(), f"Expected 'nikki' in reply, got: {reply}")

    def test_02_approval_without_discussion_is_rejected(self):
        session = InteractiveSession(model_service=self.service)
        reply, goal = session.handle_message("approve")
        self.assertIsNone(goal, "Empty session cannot be approved.")
        self.assertIn("haven't discussed a project plan", reply)

    def test_03_discussion_and_approval_flow(self):
        session = InteractiveSession(model_service=self.service)
        reply, goal = session.handle_message("I want to build a utility src/slug.py to slugify text.")
        self.assertIsNotNone(reply)
        self.assertIsNone(goal)

        # Give approval
        reply_app, approved_goal = session.handle_message("approve")
        self.assertIsNotNone(approved_goal)
        self.assertIn("Plan approved", reply_app)

if __name__ == "__main__":
    unittest.main()

