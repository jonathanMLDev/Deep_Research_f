"""
Task: Where and How to Collect C++ Compiler Error Messages and Responses for a C++ Copilot

This task tells you where and how to collect data on C++ compiler error messages
and corresponding fixes/responses for training or fine-tuning a C++ copilot.

Usage:
    # Print guide location and summary (no API keys required)
    python -m tasks.collect_cpp_compiler_error_data

    # Run deep research to discover additional sources and tools (requires .env with API keys)
    python -m tasks.collect_cpp_compiler_error_data --research
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Resolve task directory and guide path
TASKS_DIR = Path(__file__).resolve().parent
GUIDE_PATH = TASKS_DIR / "README_cpp_compiler_error_data_collection.md"
OUTPUT_PATH = "report_for_cpp_compiler_error_data"


def get_guide_content() -> str:
    """Read the data collection guide markdown."""
    if not GUIDE_PATH.exists():
        return f"Guide not found at: {GUIDE_PATH}"
    return GUIDE_PATH.read_text(encoding="utf-8")


def create_research_query() -> str:
    """Create a research query to discover more sources and methods for C++ compiler error data."""
    return """Research and summarize: **Where and how can one collect data on C++ compiler error messages and corresponding fixes or responses** for building a C++ copilot (an AI assistant that suggests fixes for compiler errors)?

Focus on:

1. **Public datasets or corpora** (academic or industry) that pair C++ compiler errors with fixes or explanations.
2. **Sources of real user errors**: Stack Overflow, GitHub, Reddit, forums — and practical methods (APIs, dumps, scraping) to extract (error message, code before, code after / fix).
3. **Compiler test suites** (GCC, Clang, MSVC) or similar that provide invalid code and expected diagnostics; how to run and harvest them.
4. **Tools or pipelines** (open source or documented) for generating or collecting such pairs (e.g. synthetic mutation + compile, or IDE/CI log parsing).
5. **Best practices** for schema, storage format (e.g. JSONL), and licensing/attribution when using Stack Overflow, GitHub, or compiler tests.

Provide a concise, actionable report with links and short instructions where possible. Prefer sources that are freely usable or well-documented.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Where and how to collect C++ compiler error data for a C++ copilot."
    )
    parser.add_argument(
        "--research",
        default=True,
        action="store_true",
        help="Run deep research (Tavily + LLM) to find additional sources and tools; requires API keys in .env",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not print the guide excerpt; only print the guide path.",
    )
    args = parser.parse_args()

    console = Console()

    # Always print where the guide is
    console.print(
        Panel(
            f"[bold]Data collection guide[/bold]\n\n"
            f"Full guide path:\n[green]{GUIDE_PATH.resolve()}[/green]\n\n"
            f"Open this file for: what to collect, where to collect (Stack Overflow, GitHub, "
            f"compiler test suites, Godbolt, Reddit, synthetic), how to collect (APIs, parsing, "
            f"local compilation, LLM-assisted), suggested JSON schema, workflow, and legal notes.",
            title="C++ Compiler Error Data for Copilot",
            border_style="blue",
        )
    )

    if not args.no_show:
        content = get_guide_content()
        if content.startswith("Guide not found"):
            console.print(f"[yellow]{content}[/yellow]")
        else:
            # Print only the first part (What to collect + Where) so it's not overwhelming
            head = content.split("## 3. How to Collect")[0]
            console.print(
                Panel(
                    Markdown(head), title="Guide summary (excerpt)", border_style="blue"
                )
            )
            console.print(
                "\n[dim]... see full guide in README_cpp_compiler_error_data_collection.md[/dim]\n"
            )

    if args.research:
        try:
            from deep_research.main_process import execute_main_process
        except ImportError:
            console.print(
                "[red]Cannot run research: deep_research.main_process not found.[/red]"
            )
            sys.exit(1)

        console.print(
            "[bold]Running deep research for additional sources and tools...[/bold]\n"
        )
        execute_main_process(
            create_research_query(),
            output_path=OUTPUT_PATH,
            report_prefix="cpp_compiler_error_data",
            task_name="collect_cpp_compiler_error_data",
            report_title="C++ Compiler Error Data Collection: Sources and Methods",
            preface_lines=[
                "This report supplements the static guide in tasks/README_cpp_compiler_error_data_collection.md.",
                "It focuses on public datasets, APIs, tools, and best practices for collecting (error message, code, fix) pairs.",
            ],
            thread_id="cpp_compiler_error_data",
        )
        console.print(f"\n[green]Report saved under {OUTPUT_PATH}/[/green]")
    else:
        console.print(
            "[dim]Tip: run with --research to run deep research for more sources and tools (requires .env with API keys).[/dim]"
        )


if __name__ == "__main__":
    main()
