# Prompt Analytics & A/B Testing Plan

## Objective
Implement a lightweight, non-bloating analytics feature to evaluate the effectiveness of different prompt versions, enabling iterative improvements (A/B testing) to the Bedtime Story Agent.

## Key Metrics to Track
1.  **Average Judge Score**: The final score assigned by the Judge.
2.  **Average Attempts**: The number of refinement loops required to reach a "PASS".
3.  **Latency**: The total time taken (in seconds) for the generation and judging process.
4.  **Success Rate**: The percentage of interactions that result in a "PASS" decision from the Judge within the allowed retries.

## Implementation Steps

### Phase 1: Data Collection (Local JSONL)
1.  **`PromptPerformanceTracker` Class**: Create a new class in `main.py` (or a dedicated `analytics.py` file if preferred to avoid bloat) responsible for logging.
2.  **JSONL Storage**: Implement appending to a `prompt_metrics.jsonl` file. This format is lightweight, append-only (safe), and easy to migrate later.
    *   *Schema*: `{ "timestamp": float, "prompt_version": str, "category": str, "attempts": int, "final_score": int, "success": bool, "latency_seconds": float }`
3.  **Integration**: Update `StoryOrchestrator` to accept a `prompt_version` identifier (defaulting to "v1"). At the end of `tell_story`, record the metrics using the tracker.
4.  **A/B Test Support**: Modify the `_load_prompt` method to optionally look for versioned folders (e.g., `prompts/v1/`, `prompts/v2/`) based on the initialized `prompt_version`.

### Phase 2: Analysis & Viewing
1.  **`view_stats.py`**: Create a separate, standalone script to read the `prompt_metrics.jsonl` file.
2.  **Reporting**: This script will aggregate the data grouped by `prompt_version` and print a clean, comparative summary of the Key Metrics to the console.

### Phase 3: Future Migration (SQLite)
*   *Note for future iterations*: The `PromptPerformanceTracker` interface will be designed so that swapping the backend from JSONL to SQLite (using Python's built-in `sqlite3`) requires minimal changes to the orchestrator logic.

## Verification
*   Run the main script multiple times (potentially forcing different prompt versions).
*   Run `view_stats.py` and verify that metrics are correctly aggregated and displayed.
