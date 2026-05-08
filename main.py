import os
import json
import re
import time
from typing import List, Dict, Optional, Tuple
from openai import OpenAI, RateLimitError, APIError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

If I had more time, I would:
1. Implement an image generation agent to create illustrations for each part of the story arc.
2. Add a 'Memory' component to allow for multi-turn interactions where kids can change the story mid-way or ask for sequels.
3. Enhance the Judge to be more specialized (e.g., a 'Vocabulary Judge' and a 'Safety Judge').
4. Implement a better UI (perhaps a simple Streamlit or Gradio app) to display the block diagram and the story progress.
5. Add a local small LLM (like Llama-3-8B) as a secondary fallback if the cloud API is unavailable.
6. Make an app that allows parents to customize the story parameters (e.g., moral lessons, character names, settings) and see the impact on the generated story in real-time.
7. Visualization of the A/B testing results and prompt performance metrics in a dashboard format, showing trends over time and across different categories.
"""

# Fallback "Canned Stories" for when the API is down or failing
FALLBACK_STORIES = [
    {
        "title": "Sparky the Brave Little Firefly",
        "content": "Once upon a time, in a lush green meadow, lived Sparky, a firefly whose light was a bit dimmer than the others. While his friends could light up the entire willow tree, Sparky could only produce a tiny flicker. One night, a thick fog rolled in, and all the fireflies got lost. Because Sparky's light was soft and steady, it didn't reflect off the fog like the others. He calmly led everyone back to their cozy hollow. Sparky learned that even a small light can guide the way when things get cloudy.",
        "category": "Fable"
    },
    {
        "title": "Luna's Moonlit Adventure",
        "content": "Luna was a curious rabbit who wondered why the moon changed shapes. One night, she climbed the Tallest Hill to ask the Wise Old Owl. The Owl explained that the moon was like a giant cookie that the night sky took little nibbles of, and then baked a new one every month. Luna giggled and fell asleep under the stars, happy to know the sky had a sweet tooth. From then on, she always left a tiny carrot out for the 'Moon Baker'.",
        "category": "Adventure"
    }
]

class PromptPerformanceTracker:
    """Simple local tracker for prompt effectiveness and A/B testing metrics."""
    def __init__(self, log_file: str = "prompt_metrics.jsonl"):
        self.log_file = log_file

    def log_run(self, prompt_version: str, category: str, attempts: int, final_score: int, success: bool, latency: float):
        entry = {
            "timestamp": time.time(),
            "prompt_version": prompt_version,
            "category": category,
            "attempts": attempts,
            "final_score": final_score,
            "success": success,
            "latency_seconds": round(latency, 2)
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

class BedtimeStoryAgent:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Warning: OPENAI_API_KEY not found in environment. Please set it in a .env file.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def call_model(self, messages: List[Dict[str, str]], max_tokens: int = 3000, temperature: float = 0.7) -> str:
        """
        Generic wrapper for calling the OpenAI Chat Completion API with error handling.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages, # type: ignore
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            return "ERROR_RATE_LIMIT"
        except APIError as e:
            if "insufficient_quota" in str(e):
                return "ERROR_QUOTA"
            return f"ERROR_API: {str(e)}"
        except Exception as e:
            return f"ERROR_GENERAL: {str(e)}"

class StoryOrchestrator:
    def __init__(self, story_agent: BedtimeStoryAgent, judge_agent: BedtimeStoryAgent, prompt_version: str = "v1"):
        self.story_agent = story_agent
        self.judge_agent = judge_agent
        self.prompt_dir = "prompts"
        self.prompt_version = prompt_version
        self.tracker = PromptPerformanceTracker()

    def _load_prompt(self, filename: str) -> str:
        # Check if a versioned prompt exists, otherwise fallback to the root prompt dir
        path = os.path.join(self.prompt_dir, self.prompt_version, filename)
        if not os.path.exists(path):
            path = os.path.join(self.prompt_dir, filename)
        
        with open(path, 'r') as f:
            return f.read()

    def categorize_request(self, user_input: str) -> str:
        prompt_template = self._load_prompt("categorizer.md")
        messages = [
            {"role": "user", "content": prompt_template + f"\n\nRequest: {user_input}"}
        ]
        resp = self.story_agent.call_model(messages, max_tokens=10, temperature=0).strip()
        if "ERROR" in resp:
            return "General"
        return resp if resp in ["Fable", "Adventure", "Mystery", "Sci-Fi", "General"] else "General"

    def generate_story(self, user_input: str, category: str, feedback: Optional[str] = None) -> str:
        prompt_template = self._load_prompt("storyteller.md")
        
        feedback_block = ""
        if feedback:
            feedback_block = f"Previous draft feedback: {feedback}\nPlease refine the story based on this feedback."
        
        full_prompt = prompt_template.format(
            category=category,
            feedback_block=feedback_block,
            user_input=user_input
        )

        messages = [
            {"role": "user", "content": full_prompt}
        ]
        return self.story_agent.call_model(messages, temperature=0.8)

    def judge_story(self, story: str) -> Tuple[int, str, bool]:
        if "ERROR" in story:
            return 0, "No story to judge due to API error.", False

        prompt_template = self._load_prompt("judge.md")
        full_prompt = prompt_template.format(story=story)

        messages = [
            {"role": "user", "content": full_prompt}
        ]
        
        eval_resp = self.judge_agent.call_model(messages, temperature=0.2)
        if "ERROR" in eval_resp:
            return 5, f"Judge encountered an API error: {eval_resp}", False

        try:
            # More robust JSON extraction using regex
            match = re.search(r'\{.*\}', eval_resp, re.DOTALL)
            if match:
                eval_json = json.loads(match.group())
                return int(eval_json["score"]), eval_json["feedback"], eval_json["decision"] == "PASS"
            else:
                raise ValueError("No JSON found")
        except Exception as e:
            # Fallback if JSON parsing fails, try to look for score and decision manually
            score_match = re.search(r'"score":\s*(\d+)', eval_resp)
            score = int(score_match.group(1)) if score_match else 5
            is_pass = "PASS" in eval_resp
            return score, "The judge's response format was slightly messy, but I extracted what I could.", is_pass

    def get_fallback_story(self) -> Tuple[str, str]:
        import random
        story_data = random.choice(FALLBACK_STORIES)
        story_text = f"Title: {story_data['title']}\n\n{story_data['content']}"
        return story_text, story_data['category']

    def tell_story(self, user_input: str, max_retries: int = 1):
        start_time = time.time()
        print(f"\n[Orchestrator] Categorizing request...")
        category = self.categorize_request(user_input)
        print(f"[Orchestrator] Category: {category}")
        
        current_feedback = None
        last_decent_story = ""
        final_score = 0
        success = False
        attempts = 0
        
        for i in range(max_retries + 1):
            attempts += 1
            attempt_str = f"Attempt {i+1}"
            print(f"\n[Orchestrator] {attempt_str}: Generating story...")
            story = self.generate_story(user_input, category, current_feedback)
            
            if "ERROR" in story:
                print(f"[Orchestrator] API Error encountered: {story}")
                if "QUOTA" in story or "RATE_LIMIT" in story:
                    print("[Orchestrator] Quota exceeded or Rate limited. Switching to a fallback story...")
                    return self.get_fallback_story()
                continue # Try next attempt if it's a transient error

            print(f"[Orchestrator] {attempt_str}: Judging story...")
            score, feedback, is_pass = self.judge_story(story)
            final_score = score
            print(f"[Judge] Score: {score}/10")
            print(f"[Judge] Feedback: {feedback}")
            
            if is_pass:
                print(f"[Orchestrator] Judge passed the story!")
                success = True
                latency = time.time() - start_time
                self.tracker.log_run(self.prompt_version, category, attempts, final_score, success, latency)
                return story, category
            else:
                print(f"[Orchestrator] Judge requested improvements.")
                current_feedback = feedback
                last_decent_story = story
        
        latency = time.time() - start_time
        self.tracker.log_run(self.prompt_version, category, attempts, final_score, success, latency)

        # If we exhausted retries and still didn't pass, but have a story
        if last_decent_story:
            print("[Orchestrator] Could not get a perfect score, but returning the best draft.")
            return last_decent_story, category
        
        # If everything failed
        print("[Orchestrator] All attempts failed. Providing a lovely fallback story instead.")
        return self.get_fallback_story()

def main():
    # Best practice: use a smaller, faster model for generation and a larger, smarter model for judging.
    story_agent = BedtimeStoryAgent(model="gpt-3.5-turbo")
    judge_agent = BedtimeStoryAgent(model="gpt-4o")
    
    # You can change the prompt_version here to test A/B versions
    orchestrator = StoryOrchestrator(story_agent=story_agent, judge_agent=judge_agent, prompt_version="v1")
    
    print("=== Welcome to the Bedtime Story Agent ===")
    user_input = input("What kind of story do you want to hear? ")
    
    if not user_input.strip():
        user_input = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."
        print(f"Using default request: {user_input}")

    story, category = orchestrator.tell_story(user_input)
    
    print("\n" + "="*50)
    print(f"FINAL STORY (Category: {category})")
    print("="*50 + "\n")
    print(story)
    print("\n" + "="*50)
    print("\n[Analytics] Performance metrics logged to prompt_metrics.jsonl")
    print("[Analytics] Run 'python view_stats.py' to see aggregated results.")

if __name__ == "__main__":
    main()
