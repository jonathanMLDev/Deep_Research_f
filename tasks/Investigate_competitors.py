"""
Library Competitor Investigation Module

Simplified to delegate the full research workflow to main_process.execute_main_process.
Each library contributes only its query; the shared runner handles execution, pricing,
logging, and report generation.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

from deep_research.main_process import execute_main_process

LIBRARY_FILE = "boost_library.json"
OUTPUT_PATH = "report_by_library"


def load_libraries() -> List[Dict]:
    path = Path(LIBRARY_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Library file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("libraries", [])


def create_research_query(library: Dict) -> str:
    name = library.get("name", "")
    description = library.get("description", "").strip()
    cpp_version = library.get("c++_version", "")

    query = f"""Research top 5-6 C++ library competitors for Boost.{name} ({cpp_version}).

Library: {name}
Purpose: {description}

Provide a CONCISE, OBJECTIVE, and QUANTITATIVE report (max 800 words) with SHORT paragraphs (2-4 sentences max).

**CRITICAL: CONCISENESS REQUIREMENTS:**
- Keep paragraphs SHORT (2-4 sentences maximum)
- Use bullet points and tables liberally for better readability
- Avoid long, dense paragraphs - break information into digestible chunks
- Prioritize key insights over exhaustive detail
- Remove redundant information
- Do not use bold formatting and quotation marks within a sentence.

1. **Top 5-6 Competitors** (use bullet points, keep each competitor to 3-4 bullet points):
   For each competitor, provide:
   - Name, GitHub URL, 1-sentence description
   - Main advantage vs Boost {name}
   - Main disadvantage vs Boost {name}
   - GitHub stars, last update date, C++ standard requirement (if available)

2. **Quantitative Metric Comparison Table**:
   Create a concise comparison table with these metrics for Boost.{name} and each competitor:
   - **Performance**: Runtime speed, memory usage, build time impact
   - **Code Quality**: Lines of code (approx), test coverage (%), static analysis findings
   - **Ecosystem**: GitHub stars, contributor count, issue resolution time
   - **Standards & Portability**: C++ standard compliance, platform support
   - **Usability**: API ergonomics (1-5 rating), documentation quality (1-5 rating)

   Use actual numbers when available, or "—" if not available. Be objective and data-driven.

3. **Summary Comparison Table**:
   Create a concise table with columns:
   | Library | Main Advantage vs Boost.{name} | Main Disadvantage vs Boost.{name} | When to Prefer | C++ Standard |

   Include Boost.{name} in the table for reference.

4. **Recent Trends (2023-2025)** - Brief summary (2-3 short paragraphs max):
   - Adoption trends (growing/stable/declining) with evidence
   - Major updates or releases
   - Community activity level

5. **Conclusion** - Objective assessment (2-3 short paragraphs max):
   - When to use Boost {name} vs alternatives
   - Key trade-offs based on quantitative metrics

Focus on objective, quantitative data. Include specific numbers, dates, and metrics when available. Keep the report concise and scannable."""
    return query


def sanitize_prefix(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_").lower() or "library"


def run_for_library(library: Dict, thread_id_prefix: str = "library") -> None:
    name = library.get("name", "unknown")
    query = create_research_query(library)
    prefix = sanitize_prefix(name)
    thread_id = f"{thread_id_prefix}_{prefix}"
    print(f"Thread ID: {thread_id}")

    report_path, summary_path = execute_main_process(
        query,
        output_path=OUTPUT_PATH,
        report_prefix=prefix,
        task_name=f"investigate_competitor_{prefix}",
        report_title=f"Competitor Analysis: {name}",
        preface_lines=[
            f"Library: {name}",
            f"C++ Version: {library.get('c++_version', 'N/A')}",
            f"Description: {library.get('description', 'N/A')}",
            f"URL: {library.get('name_link', 'N/A')}",
        ],
        thread_id=thread_id,
        recursion_limit=15,
    )

    print(f"[✓] {name} -> {report_path}")
    if summary_path:
        print(f"[✓] Summary -> {summary_path}")


def main():
    libraries = load_libraries()
    # Optional CLI args: start_index max_libraries
    start_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    max_libraries = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if max_libraries is not None:
        libraries = libraries[start_index : start_index + max_libraries]
    else:
        libraries = libraries[start_index:]

    for lib in libraries[73:74]:
        print(f"Processing {lib['name']}...")
        run_for_library(lib)


if __name__ == "__main__":
    main()
