import os
import json
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
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
"""

class BedtimeStoryAgent:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Warning: OPENAI_API_KEY not found in environment. Please set it in a .env file.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def call_model(self, messages: List[Dict[str, str]], max_tokens: int = 3000, temperature: float = 0.7) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages, # type: ignore
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Error: {str(e)}"

class StoryOrchestrator:
    def __init__(self, agent: BedtimeStoryAgent):
        self.agent = agent

    def categorize_request(self, user_input: str) -> str:
        messages = [
            {"role": "system", "content": "Categorize this bedtime story request into one of these: Fable, Adventure, Mystery, Sci-Fi, or General. Return ONLY the category name."},
            {"role": "user", "content": user_input}
        ]
        category = self.agent.call_model(messages, max_tokens=10, temperature=0).strip()
        return category if category in ["Fable", "Adventure", "Mystery", "Sci-Fi", "General"] else "General"

    def generate_story(self, user_input: str, category: str, feedback: Optional[str] = None) -> str:
        system_prompt = f"""You are a master bedtime story teller for children aged 5-10. 
Create a {category} story based on the user's request. 
Follow a classic story arc: Inciting Incident, Rising Action, Climax, and Resolution. 
Keep the tone warm and engaging. Ensure the vocabulary and themes are appropriate for children aged 5-10."""
        
        user_prompt = f"Request: {user_input}"
        if feedback:
            user_prompt += f"\n\nPrevious draft feedback: {feedback}\nPlease refine the story based on this feedback."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self.agent.call_model(messages, temperature=0.8)

    def judge_story(self, story: str) -> Tuple[int, str, bool]:
        system_prompt = """You are a critical editor for children's literature. Evaluate the following story for a 5-10 year old audience.
Criteria:
1. Age-appropriateness (language and themes).
2. Narrative arc quality (clear beginning, middle, and end).
3. Engagement level.
4. Positive message or moral.

Provide a score (1-10), specific feedback, and a decision (PASS/FAIL). PASS if score is 8 or higher.
Format your response as a JSON object: {"score": int, "feedback": "string", "decision": "PASS/FAIL"}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Story to evaluate:\n\n{story}"}
        ]
        
        eval_resp = self.agent.call_model(messages, temperature=0.2)
        try:
            # Clean up the response in case the model adds extra text
            start = eval_resp.find('{')
            end = eval_resp.rfind('}') + 1
            eval_json = json.loads(eval_resp[start:end])
            return eval_json["score"], eval_json["feedback"], eval_json["decision"] == "PASS"
        except Exception:
            # Fallback if JSON parsing fails
            return 5, "Could not parse judge's evaluation properly.", False

    def tell_story(self, user_input: str, max_retries: int = 2):
        print(f"\n[Orchestrator] Categorizing request...")
        category = self.categorize_request(user_input)
        print(f"[Orchestrator] Category: {category}")
        
        current_feedback = None
        final_story = ""
        
        for i in range(max_retries + 1):
            attempt_str = f"Attempt {i+1}"
            print(f"\n[Orchestrator] {attempt_str}: Generating story...")
            story = self.generate_story(user_input, category, current_feedback)
            
            print(f"[Orchestrator] {attempt_str}: Judging story...")
            score, feedback, is_pass = self.judge_story(story)
            print(f"[Judge] Score: {score}/10")
            print(f"[Judge] Feedback: {feedback}")
            
            if is_pass:
                print(f"[Orchestrator] Judge passed the story!")
                final_story = story
                break
            else:
                print(f"[Orchestrator] Judge requested improvements.")
                current_feedback = feedback
                final_story = story # Keep the last one as fallback
        
        return final_story, category

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
