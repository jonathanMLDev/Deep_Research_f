"""
Investigate Cursor Subscription vs API Key Mechanics and Plan Comparison

Usage:
    python -m tasks.investigate_cursor_plans
"""

from deep_research.main_process import execute_main_process

OUTPUT_PATH = "report_for_cursor_plans"


def create_research_query() -> str:
    return """Generate a report addressing:

1) Subscription vs. API Key Mechanics
- Integration: Can an existing direct Claude (Anthropic) or ChatGPT (OpenAI) subscription be used within Cursor via OAuth or similar, or are they strictly separate? Cursor allows API keys, but can web-based account subscriptions be used directly?
- Cost Conversion: What is the “conversion rate” of dollars to tokens? Does $1 on an API key buy the same amount of prompts/completions as $1 of a monthly subscription?

2) Cursor Plan Comparison (Pro vs. Teams vs. Enterprise)
- Pooled Usage: How does pooled usage work in Enterprise? Can high-usage users automatically draw from unused allotments of others?
- Administrative Control: On Teams, how do usage-limit notifications work, and how does an admin top up a specific user?
- Tiered Deployment: Can most employees be on a smaller plan (e.g., $40/mo) while power users are on higher/all-you-can-eat plans within the same org account?
- Value Parity: Does $20 on Teams provide the same prompts/tokens as $20 on Enterprise?

Deliver a concise, evidence-backed report with clear citations, tables where helpful, and emphasis on concrete mechanics, pricing, and admin controls."""


def main():
    query = create_research_query()
    report_path, summary_path = execute_main_process(
        query,
        output_path=OUTPUT_PATH,
        report_prefix="cursor_plans_analysis",
        task_name="investigate_cursor_plans",
        report_title="Cursor Subscription and Plan Mechanics",
        thread_id="cursor_plans",
        recursion_limit=15,
    )

    print(f"[✓] Report saved to: {report_path}")
    if summary_path:
        print(f"[✓] Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
