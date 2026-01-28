# Deep Research

Multi-agent research system using Self-Balancing Agentic AI for comprehensive research on complex topics.

## Features

- **Multi-Agent Research**: Supervisor coordinates specialized research agents
- **Red Team Evaluation**: Built-in adversarial evaluation for objectivity and bias assessment
- **Iterative Refinement**: Blue-red feedback loop improves report quality
- **Initial Report Enrichment**: Enhance user-provided reports with targeted research
- **Token Usage Tracking**: Comprehensive API usage monitoring

## Installation

### Prerequisites

- Python 3.11+
- pip or uv

### Setup

1. **Clone and install**:

   ```bash
   git clone <repository-url>
   cd Deep_Research
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Configure API keys**:

   ```bash
   cp env.example .env
   # Edit .env and add your API keys
   ```

   Required:
   - `OPENAI_API_KEY` - OpenAI API key
   - `TAVILY_API_KEY` - Tavily search API key

   Optional:
   - `USE_OPENROUTER` - Use OpenRouter instead of OpenAI
   - `OPENROUTER_API_KEY` - OpenRouter API key
   - `ENABLE_RED_TEAM_EVAL` - Enable red team evaluation (default: false)

3. **Verify**:

   ```bash
   python -c "import deep_research; print('OK')"
   ```

## Usage

### Research Tasks

Run predefined research tasks:

```bash
# Beast2 CI analysis
python -m tasks.investigate_beast2_ci

# Boost library competitors
python -m tasks.Investigate_competitors

# Boost usage spike investigation
python -m tasks.investigate_boost_spike

# RAGaaS platform analysis
python -m tasks.investigate_ragaas

# MIT research
python -m tasks.investigate_mit

# Cursor plans research
python -m tasks.investigate_cursor_plans
```

### Custom Research

Create a new task in `tasks/` following the pattern:

```python
from deep_research.main_process import execute_main_process

def main():
    query = "Your research question here"
    execute_main_process(
        query,
        output_path="report_output",
        report_prefix="research",
        task_name="custom_task"
    )
```

### Initial Report Enrichment

Provide an initial report file to enrich:

```python
with open("initial_report.md", "r", encoding="utf-8") as f:
    initial_report = f.read()

execute_main_process(
    query,
    initial_report=initial_report,
    output_path="report_output",
    report_prefix="enriched",
    task_name="enrichment_task"
)
```

## Project Structure

```
Deep_Research/
├── src/                    # Core source code
│   ├── research_agent_full.py      # Full research workflow
│   ├── research_agent_scope.py     # Scoping phase
│   ├── multi_agent_supervisor.py   # Supervisor coordination
│   ├── red_team_evaluator.py       # Red team evaluation
│   ├── main_process.py             # Main execution workflow
│   └── ...
├── tasks/                  # Research task scripts
├── report_*/               # Generated reports
├── requirements.txt        # Python dependencies
└── env.example            # Environment template
```

## Configuration

### Environment Variables

See `env.example` for all available options. Key variables:

- `OPENAI_API_KEY` (required) - OpenAI API key
- `TAVILY_API_KEY` (required) - Tavily search API key
- `ENABLE_RED_TEAM_EVAL` - Enable red team evaluation
- `MIN_OBJECTIVITY_SCORE` - Minimum score threshold (0.0-1.0, default: 0.75)
- `MAX_REFINEMENT_ITERATIONS` - Max refinement cycles (default: 3)

## How It Works

1. **Scoping**: User clarification and research brief generation
2. **Research**: Multi-agent supervisor coordinates parallel research
3. **Evaluation**: Red team assesses objectivity, bias, and source quality
4. **Refinement**: Iterative improvement based on feedback
5. **Generation**: Final report with citations and sources

## License

See [LICENSE](LICENSE) for details.
