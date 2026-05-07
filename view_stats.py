import json
import os
from collections import defaultdict

def analyze_metrics(log_file="prompt_metrics.jsonl"):
    if not os.path.exists(log_file):
        print(f"Error: {log_file} not found. Run the main script first to generate metrics.")
        return

    # Group metrics by prompt version
    stats = defaultdict(lambda: {
        "runs": 0,
        "total_score": 0,
        "total_attempts": 0,
        "successes": 0,
        "total_latency": 0.0
    })

    with open(log_file, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                v = data["prompt_version"]
                stats[v]["runs"] += 1
                stats[v]["total_score"] += data["final_score"]
                stats[v]["total_attempts"] += data["attempts"]
                stats[v]["total_latency"] += data["latency_seconds"]
                if data["success"]:
                    stats[v]["successes"] += 1
            except Exception as e:
                print(f"Warning: Skipping malformed line: {e}")

    # Print Report
    print("\n" + "="*80)
    print(f"{'Prompt Version':<20} | {'Success %':<10} | {'Avg Score':<10} | {'Avg Attempts':<15} | {'Avg Latency (s)':<15}")
    print("-" * 80)

    for version, data in sorted(stats.items()):
        count = data["runs"]
        success_rate = (data["successes"] / count) * 100
        avg_score = data["total_score"] / count
        avg_attempts = data["total_attempts"] / count
        avg_latency = data["total_latency"] / count

        print(f"{version:<20} | {success_rate:>8.1f}% | {avg_score:>9.2f} | {avg_attempts:>14.2f} | {avg_latency:>14.2f}")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    analyze_metrics()
