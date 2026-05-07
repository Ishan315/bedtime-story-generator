import unittest
from unittest.mock import MagicMock, patch
import json
from main import BedtimeStoryAgent, StoryOrchestrator, FALLBACK_STORIES

class TestBedtimeStorySystem(unittest.TestCase):
    def setUp(self):
        self.mock_agent = MagicMock(spec=BedtimeStoryAgent)
        with patch("builtins.open", MagicMock()):
            self.orchestrator = StoryOrchestrator(self.mock_agent, prompt_version="v1")
        # Separate mocks for different prompts to match expected format keys
        self.orchestrator._load_prompt = MagicMock()
        self.orchestrator._load_prompt.side_effect = lambda f: {
            "categorizer.md": "Categorize {user_input}",
            "storyteller.md": "{category} {feedback_block} {user_input}",
            "judge.md": "{story}"
        }.get(f, "")

    def test_judge_robust_json_parsing(self):
        """Test that the judge can extract JSON even with surrounding text."""
        messy_response = "Certainly! Here is the evaluation: {\"score\": 9, \"feedback\": \"Great story!\", \"decision\": \"PASS\"} I hope this helps!"
        self.mock_agent.call_model.return_value = messy_response
        
        score, feedback, is_pass = self.orchestrator.judge_story("Some story")
        
        self.assertEqual(score, 9)
        self.assertEqual(feedback, "Great story!")
        self.assertTrue(is_pass)

    def test_fallback_on_quota_error(self):
        """Test that the orchestrator returns a fallback story if the API returns a quota error."""
        # Categorize succeeds, but generate_story returns a quota error
        self.mock_agent.call_model.side_effect = ["Adventure", "ERROR_QUOTA"]
        
        story, category = self.orchestrator.tell_story("A space adventure")
        
        # Check if the returned story is one of our fallback stories
        fallback_titles = [s['title'] for s in FALLBACK_STORIES]
        self.assertTrue(any(title in story for title in fallback_titles))
        self.assertIn(category, ["Fable", "Adventure"])

    def test_best_draft_fallback(self):
        """Test that the orchestrator returns the best draft if judge never passes it."""
        # 1. Category: General
        # 2. Attempt 1: Story A
        # 3. Judge 1: Score 5, FAIL
        # 4. Attempt 2: Story B
        # 5. Judge 2: Score 6, FAIL
        self.mock_agent.call_model.side_effect = [
            "General", 
            "Story A", json.dumps({"score": 5, "feedback": "Bad", "decision": "FAIL"}),
            "Story B", json.dumps({"score": 6, "feedback": "Better", "decision": "FAIL"})
        ]
        
        story, category = self.orchestrator.tell_story("A story", max_retries=1)
        
        self.assertEqual(story, "Story B")
        self.assertEqual(category, "General")

    def test_categorize_failure_defaults_to_general(self):
        """Test that categorization failure defaults to 'General'."""
        self.mock_agent.call_model.return_value = "ERROR_API"
        category = self.orchestrator.categorize_request("Anything")
        self.assertEqual(category, "General")

if __name__ == "__main__":
    unittest.main()
