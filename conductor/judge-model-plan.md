# Judge Model Separation Plan

## Objective
Implement best practices for LLM-as-a-Judge by separating the generation model from the evaluation model. Using the same model for both generation and judging often leads to "self-bias" (the model overrating its own outputs). Using a stronger model (like GPT-4o) for the Judge ensures a more objective, high-quality evaluation.

## Proposed Changes

1. **Architectural Update (`main.py`)**:
   - Modify `StoryOrchestrator` to accept two distinct agents during initialization: `story_agent` and `judge_agent`.
   - Update the `judge_story` method to use `self.judge_agent.call_model(...)`.
   - Keep `categorize_request` and `generate_story` using `self.story_agent.call_model(...)`.

2. **Instantiation Update (`main.py`)**:
   - In the `main()` function, instantiate two `BedtimeStoryAgent` objects:
     ```python
     story_agent = BedtimeStoryAgent(model="gpt-3.5-turbo")
     judge_agent = BedtimeStoryAgent(model="gpt-4o") # Or gpt-4-turbo
     orchestrator = StoryOrchestrator(story_agent=story_agent, judge_agent=judge_agent, prompt_version="v1")
     ```

3. **Documentation Update**:
   - Update `SYSTEM_DESIGN.md` to explicitly state that the Judge utilizes a distinct, higher-capacity model (GPT-4o) to prevent self-bias and ensure rigorous evaluation.
   - Mention this architectural improvement in `README.md` under "Key Features".

## Verification
- Run `test_main.py` (requires updating the test setup to mock both agents).
- Verify the script runs and routes calls to the correct models.
