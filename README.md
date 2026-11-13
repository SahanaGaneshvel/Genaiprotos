# Multi-Agent AI Research Assistant

A proof of concept built for a Junior AI Engineer internship assessment. The project lives in
[`multi-agent-research-assistant/`](multi-agent-research-assistant/).

**[▶ Live demo](https://research-agents-blush.vercel.app/)** (replays a real run, step by step) ·
**[→ Full documentation](multi-agent-research-assistant/README.md)**

An AI research team of four agents that investigates a technical topic and writes a structured,
cited research report. Every model call runs **locally through Ollama**: no paid APIs, no API keys.

```
Question → Orchestrator → Research → Comparison → Evaluation → Report → Markdown report
                            ↑
            web · Hugging Face model cards · arXiv · GitHub
```

| Agent | What it does |
|---|---|
| **Research** | Plans searches, retrieves sources from the web, Hugging Face, arXiv and GitHub, numbers them S1…Sn and extracts the facts in each |
| **Comparison** | Builds a model-by-model table (modalities, size, context window, deployment, hardware, licence) with code-set citations |
| **Evaluation** | Keeps only benchmark scores that appear in the cited source, assesses on-premise suitability, estimates memory needs |
| **Report** | Writes a 10-section technical report; references are built by code from the sources actually retrieved |

| | |
|---|---|
| Live demo | [research-agents-blush.vercel.app](https://research-agents-blush.vercel.app/) |
| Example report (real run) | [`outputs/example_report.md`](multi-agent-research-assistant/outputs/example_report.md) |
| Original brief | [`docs/PROJECT_BRIEF.md`](multi-agent-research-assistant/docs/PROJECT_BRIEF.md) |
| Architecture | [README, section 2](multi-agent-research-assistant/README.md#2-architecture) |
| How hallucinations are contained | [README, section 3](multi-agent-research-assistant/README.md#3-how-hallucinations-are-contained) |
| Tests (139 passed, offline) | [`docs/test_results.txt`](multi-agent-research-assistant/docs/test_results.txt) |

**Stack:** Python 3.11+, LangGraph, Ollama (`qwen3.5:4b` by default), Pydantic, Streamlit,
DuckDuckGo search, Hugging Face Hub API, arXiv API, GitHub REST API, Requests + BeautifulSoup,
FastAPI, and Next.js for the behind-the-scenes page.

### Quick start

```bash
cd multi-agent-research-assistant
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3.5:4b            # or qwen3.5:2b on machines with less than 6 GB free RAM
cp .env.example .env              # Windows: copy .env.example .env
streamlit run app.py
```

Setup details, the web page, tests and limitations are in the
[project README](multi-agent-research-assistant/README.md).
