"""
Investigate Boost C++ Library Usage Spike (2013-2016)

This script investigates the reasons for the significant usage spike in Boost C++ Library
during versions 1.53.0-1.61.0 (2013-2016), with particular focus on version 1.55.0
which shows the highest spike.

Usage:
    python -m tasks.investigate_boost_spike
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from deep_research.main_process import execute_main_process

# Initialize console for rich output
console = Console()

OUTPUT_PATH = "report_for_boost_spike"


def read_boost_distribution_data():
    """Read Boost version distribution data from data/boost_distribution.md"""
    data_file = Path(__file__).parent.parent / "data" / "boost_distribution.md"

    if not data_file.exists():
        console.print(
            f"[yellow]Warning: {data_file} not found. Proceeding without data.[/yellow]"
        )
        return None

    try:
        with open(data_file, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read {data_file}: {e}[/yellow]")
        return None


def create_research_query(distribution_data: str = None) -> str:
    """
    Create a research query to investigate the Boost usage spike.

    Args:
        distribution_data: Optional Boost distribution data from markdown file

    Returns:
        Research query string
    """
    # Extract key data points
    spike_info = """
Key Data Points from Boost Version Distribution:
- Version 1.53.0 (2013-02-04): 58 confirmed + 281 unconfirmed = 339 total repositories
- Version 1.54.0 (2013-07-01): 90 confirmed + 267 unconfirmed = 357 total repositories
- Version 1.55.0 (2013-11-11): 91 confirmed + 714 unconfirmed = 805 total repositories (SPIKE)
- Version 1.56.0 (2014-08-07): 46 confirmed + 273 unconfirmed = 319 total repositories
- Version 1.57.0 (2014-11-03): 21 confirmed + 459 unconfirmed = 480 total repositories
- Version 1.58.0 (2015-04-17): 72 confirmed + 373 unconfirmed = 445 total repositories
- Version 1.59.0 (2015-08-13): 20 confirmed + 418 unconfirmed = 438 total repositories
- Version 1.60.0 (2015-12-17): 28 confirmed + 395 unconfirmed = 423 total repositories
- Version 1.61.0 (2016-05-13): 18 confirmed + 337 unconfirmed = 355 total repositories

The spike is most pronounced in version 1.55.0 (November 2013) with 714 unconfirmed repositories,
which is approximately 2.5x higher than surrounding versions.
"""

    query = f"""Investigate the reasons for the significant usage spike in Boost C++ Library during versions 1.53.0-1.61.0 (2013-2016), with particular focus on version 1.55.0 (November 2013) which shows the highest spike.

{spike_info}

**Research Focus Areas:**

1. **Version 1.55.0 Specific Changes** (November 2013):
   - What major features, libraries, or improvements were introduced in Boost 1.55.0?
   - Were there any breaking changes, deprecations, or migration requirements that might have caused a surge in repository updates?
   - What C++ standard features or compiler support was added/improved?
   - Were there any significant bug fixes or performance improvements that made upgrading attractive?

2. **Industry and Technology Context (2013-2016)**:
   - What major C++ industry trends occurred during 2013-2016 that might have driven Boost adoption?
   - Were there C++ standard releases (C++11, C++14) that increased Boost relevance?
   - Did major companies or projects announce Boost adoption or migration during this period?
   - Were there any significant Boost-related conferences, publications, or community events?

3. **Technical Factors**:
   - Compiler support improvements (GCC, Clang, MSVC) for C++11/14 features
   - Boost library maturity and stability improvements
   - Integration with popular build systems (CMake, etc.)
   - Package manager adoption (vcpkg, Conan, etc.)

4. **Usage Patterns**:
   - Was there a shift in how Boost was distributed or packaged?
   - Did GitHub or other platforms change how they track Boost usage?
   - Were there changes in Boost's licensing or distribution model?

5. **Comparison Analysis**:
   - Compare usage patterns before (1.50.0-1.52.0), during (1.53.0-1.61.0), and after (1.62.0+) the spike
   - Identify any correlation with C++ standard adoption timelines
   - Analyze if the spike represents new adoption or migration from older versions

**Report Requirements:**
- Provide a CONCISE, OBJECTIVE, and QUANTITATIVE report (max 1000 words)
- Focus on evidence-based explanations with specific dates, version numbers, and metrics
- Include citations for all claims using [N] format
- Use SHORT paragraphs (2-4 sentences max), bullet points, and tables
- Structure with clear sections: Executive Summary, Key Findings, Technical Analysis, Industry Context, Conclusion
- Do not use bold formatting and quotation marks within sentences

**Target Audience:** Client report for understanding Boost adoption trends and business implications."""

    return query


def run_research(query: str, thread_id: str = "boost_spike", recursion_limit: int = 15):
    """
    Run deep research for the spike query using shared main process.
    """
    console.print(
        "\n[bold cyan]Starting Boost Usage Spike Investigation...[/bold cyan]"
    )
    console.print(f"[dim]Query: {query[:100]}...[/dim]\n")

    report_path, summary_path = execute_main_process(
        query,
        output_path=OUTPUT_PATH,
        report_prefix="boost_spike_analysis",
        task_name="investigate_boost_spike",
        report_title="Boost C++ Library Usage Spike Analysis (2013-2016)",
        thread_id=thread_id,
        recursion_limit=recursion_limit,
    )

    return {"report_path": report_path, "summary_path": summary_path}


def main():
    """Main entry point for Boost spike investigation."""
    console.print(
        Panel(
            "[bold cyan]Boost C++ Library Usage Spike Investigation[/bold cyan]\n\n"
            "This will investigate the reasons for the usage spike during\n"
            "versions 1.53.0-1.61.0 (2013-2016), focusing on version 1.55.0.",
            title="[bold]Research Task[/bold]",
            border_style="cyan",
        )
    )

    distribution_data = read_boost_distribution_data()
    query = create_research_query(distribution_data)

    # Run research
    try:
        result_paths = run_research(query)

        # Display summary
        console.print("\n[bold green]✓ Research completed successfully![/bold green]")
        console.print(
            f"[green]Report saved to: {result_paths.get('report_path')}[/green]"
        )
        if result_paths.get("summary_path"):
            console.print(
                f"[green]Summary saved to: {result_paths.get('summary_path')}[/green]"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Research interrupted by user.[/yellow]")
        sys.exit(1)
    except RuntimeError as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            console.print(
                Panel(
                    error_msg + "\n\n"
                    "[yellow]To resolve this issue:[/yellow]\n"
                    "1. Check your OpenAI account usage: https://platform.openai.com/usage\n"
                    "2. Verify your billing information is set up\n"
                    "3. Consider upgrading your plan if you've hit usage limits",
                    title="[bold red]API Quota Error[/bold red]",
                    border_style="red",
                )
            )
        elif "api key" in error_msg.lower() or "401" in error_msg:
            console.print(
                Panel(
                    error_msg + "\n\n"
                    "[yellow]To resolve this issue:[/yellow]\n"
                    "1. Verify your OPENAI_API_KEY in your .env file\n"
                    "2. Make sure the key is correct and not expired",
                    title="[bold red]API Key Error[/bold red]",
                    border_style="red",
                )
            )
        else:
            console.print(
                Panel(
                    error_msg,
                    title="[bold red]Runtime Error[/bold red]",
                    border_style="red",
                )
            )
        sys.exit(1)
    except Exception as e:
        console.print(
            Panel(
                f"[bold red]Unexpected error:[/bold red]\n{str(e)}\n\n"
                "If this is an API error, check your API keys and quota limits.",
                title="[bold red]Fatal Error[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
