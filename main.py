import os
import json
import re
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
    def __init__(self, agent: BedtimeStoryAgent):
        self.agent = agent
        self.prompt_dir = "prompts"

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(self.prompt_dir, filename)
        with open(path, 'r') as f:
            return f.read()

    def categorize_request(self, user_input: str) -> str:
        prompt_template = self._load_prompt("categorizer.md")
        messages = [
            {"role": "user", "content": prompt_template + f"\n\nRequest: {user_input}"}
        ]
        resp = self.agent.call_model(messages, max_tokens=10, temperature=0).strip()
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
        return self.agent.call_model(messages, temperature=0.8)

    def judge_story(self, story: str) -> Tuple[int, str, bool]:
        if "ERROR" in story:
            return 0, "No story to judge due to API error.", False

        prompt_template = self._load_prompt("judge.md")
        full_prompt = prompt_template.format(story=story)

        messages = [
            {"role": "user", "content": full_prompt}
        ]
        
        eval_resp = self.agent.call_model(messages, temperature=0.2)
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
        print(f"\n[Orchestrator] Categorizing request...")
        category = self.categorize_request(user_input)
        print(f"[Orchestrator] Category: {category}")
        
        current_feedback = None
        last_decent_story = ""
        
        for i in range(max_retries + 1):
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
            print(f"[Judge] Score: {score}/10")
            print(f"[Judge] Feedback: {feedback}")
            
            if is_pass:
                print(f"[Orchestrator] Judge passed the story!")
                return story, category
            else:
                print(f"[Orchestrator] Judge requested improvements.")
                current_feedback = feedback
                last_decent_story = story
        
        # If we exhausted retries and still didn't pass, but have a story
        if last_decent_story:
            print("[Orchestrator] Could not get a perfect score, but returning the best draft.")
            return last_decent_story, category
        
        # If everything failed
        print("[Orchestrator] All attempts failed. Providing a lovely fallback story instead.")
        return self.get_fallback_story()

def main():
    agent = BedtimeStoryAgent()
    orchestrator = StoryOrchestrator(agent)
    
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

if __name__ == "__main__":
    main()
