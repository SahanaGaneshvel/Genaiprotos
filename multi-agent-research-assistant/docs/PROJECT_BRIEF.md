# Project Brief — Multi-Agent AI Research Assistant

> Saved verbatim (formatting only converted to Markdown) as the source of truth for this POC.
> Context: Junior AI Engineer internship assessment.

---

## 0. Original concept (from the co-founder)

**Concept:** An AI research team that independently investigates a topic and produces a structured research report.

**Example:** "Research the latest open-source multimodal models suitable for on-prem deployment."

**Multiple agents:**
- **Report Agent** – creates a final technical report.
- **Evaluation Agent** – identifies benchmarks and limitations.
- **Comparison Agent** – compares models, capabilities and licensing.
- **Research Agent** – searches papers, GitHub and documentation.

---

## Project description

Build an AI research team consisting of four specialised agents that independently perform different research responsibilities and collaborate to generate a structured technical research report.

Example user query:
"Research the latest open-source multimodal models suitable for on-premise deployment. Compare their capabilities, benchmarks, hardware requirements, licensing and limitations."

IMPORTANT: This is a proof of concept (POC) for a Junior AI Engineer internship assessment. Demonstrate understanding of multi-agent architecture, LLM integration, research automation, orchestration, source retrieval and evaluation.

Do NOT build a full-fledged enterprise platform. Keep the project small, clean, functional and easy to explain.

---

## 1. Required technology stack

- Python 3.11+
- Streamlit for frontend.
- LangGraph for multi-agent orchestration.
- Ollama for local LLM inference.
- Qwen3.5 4B as the default local model, configurable through environment variables.
- DuckDuckGo search for web discovery.
- arXiv API for research paper discovery.
- GitHub REST API for repository discovery.
- Requests and BeautifulSoup for public webpage retrieval.
- Pydantic for structured outputs and data validation.
- SQLite or JSON for lightweight storage.
- Markdown for final report generation.

**Model requirements:**
- Use only free, locally runnable open-weight models through Ollama.
- Default: `qwen3.5:4b`
- Allow changing the model through: `OLLAMA_MODEL=qwen3.5:4b`
- Do not use: OpenAI API, Anthropic API, Gemini API, Groq API, paid model endpoints, any service requiring paid credits.
- The application itself must use Ollama.
- If the default model is unsuitable for the available hardware, document how to select a smaller compatible model. Never silently use a paid API.
- Clearly distinguish open-weight models from models with fully open-source licences when researching them.

---

## 2. Multi-agent architecture

### Agent 1: Research Agent
Responsibilities:
- Understand the user's research query.
- Search the internet for relevant information.
- Search arXiv for academic papers.
- Search GitHub for relevant repositories.
- Retrieve official documentation and model cards.
- Extract relevant facts and technical information.
- Collect source URLs and publication dates.
- Identify relevant models, tools and technologies.

Output: a structured collection of research findings. Each finding includes:
Source ID, Title, Summary, Source URL, Source type, Publication or update date if available, Key findings, Limitations.

### Agent 2: Comparison Agent
Responsibilities:
- Consume the Research Agent's findings.
- Identify the models and technologies discovered.
- Compare capabilities and supported modalities.
- Compare parameter sizes where documented.
- Compare context windows where documented.
- Compare deployment methods.
- Compare hardware and memory requirements.
- Examine licensing and usage restrictions.
- Explain the differences between the models.

Output: a structured comparison table.

### Agent 3: Evaluation Agent
Responsibilities:
- Examine available benchmark results.
- Identify benchmark datasets and metrics.
- Identify reported scores with supporting sources.
- Evaluate model limitations.
- Assess suitability for on-premise deployment.
- Examine memory and inference requirements.
- Identify quantisation options.
- Identify trade-offs and missing evidence.

Important:
- Never fabricate benchmark values.
- Never claim that a benchmark was executed unless the application actually ran it.
- Clearly distinguish official results, third-party results and qualitative assessments.
- Flag missing evidence.

Output: structured evaluation results, benchmark evidence and recommendations.

### Agent 4: Report Agent
Responsibilities:
- Consume all previous agents' outputs.
- Consolidate their findings.
- Remove unnecessary duplication.
- Produce a coherent technical report.
- Preserve source references.
- Clearly distinguish facts, estimates and recommendations.

The final report must contain:
1. Executive Summary
2. Research Objective
3. Research Methodology
4. Models and Technologies Identified
5. Comparative Analysis
6. Benchmark Evaluation
7. On-Premise Deployment Considerations
8. Limitations and Risks
9. Recommendations
10. References

The report should be available as a downloadable Markdown file.

---

## 3. Orchestration workflow

Use LangGraph to coordinate the agents through an explicit workflow.

```
User Query
    |
    v
Orchestrator
    |
    v
Research Agent
    |
    v
Shared Research State
    |
    +---------------------+
    |                     |
    v                     v
Comparison Agent     Evaluation Agent
    |                     |
    +----------+----------+
               |
               v
         Report Agent
               |
               v
       Final Research Report
```

Implementation requirements:
- Define a shared state using TypedDict or an equivalent structured schema.
- Each agent must have a dedicated function.
- Each agent must have its own system prompt.
- Pass structured outputs through the shared state.
- Comparison and Evaluation must use the Research Agent's actual findings.
- Report Agent must use all three preceding outputs.
- Track each agent's execution status.
- Record errors and execution time.
- Use a fixed execution sequence.
- Do not allow unlimited agent-to-agent loops.
- For simplicity, Comparison and Evaluation can execute sequentially.
- Do not make four agents that simply repeat the same LLM prompt. Each must perform its own responsibility.

---

## 4. Source retrieval and research

Lightweight research tools:
- A. DuckDuckGo: search for relevant web pages.
- B. arXiv: search for academic papers relevant to the topic.
- C. GitHub: search for relevant repositories and project documentation.
- D. Public webpages: fetch relevant content using Requests and BeautifulSoup.

Keep retrieval limited to approximately 3–5 useful sources per category.

Requirements:
- Preserve original URLs.
- Extract titles and available dates.
- Handle failed webpage requests.
- Handle empty results.
- Handle rate limits.
- Avoid fabricated source information.
- Respect website terms and access restrictions.
- Use official documentation and model cards where possible.
- Cache results locally where useful.

GitHub API: use unauthenticated public search by default. Support an optional `GITHUB_TOKEN` through environment variables. Do not expose credentials.

---

## 5. LLM integration

Reusable Ollama client:
- Connect to the local Ollama server.
- Use the configured model.
- Support system and user prompts.
- Support structured JSON responses where possible.
- Validate results using Pydantic.
- Handle malformed responses.
- Handle model-not-found errors.
- Handle connection failures.
- Keep generation settings configurable.

Use conservative temperature settings for research and report generation.

Each agent must receive:
1. Its role.
2. Its responsibility.
3. The research context it needs.
4. The expected output schema.
5. Instructions not to fabricate facts or references.

Use only source URLs collected by the retrieval tools for citations.

---

## 6. Frontend (Streamlit)

Title: **Multi-Agent AI Research Assistant**

- **Header:** project name, short description, local model currently configured.
- **Input:** research topic text area; research depth selector (Basic / Detailed); Start Research button.
- **Agent execution section:** four agent cards (Research, Comparison, Evaluation, Report) showing Pending / Running / Completed / Failed — actual execution states, not fake animations.
- **Results tabs:**
  - Tab 1 Research Findings — findings, source titles and clickable URLs.
  - Tab 2 Model Comparison — comparison table, important differences.
  - Tab 3 Evaluation — benchmarks, metrics, limitations, deployment considerations.
  - Tab 4 Final Report — rendered Markdown report, download button.
- Small section showing number of sources retrieved and total execution time.
- Design: professional AI research dashboard, clean layout, minimal colours, good spacing, desktop-responsive, no unnecessary animations.

---

## 7. Error handling

Handle: Ollama server unavailable; model not downloaded; internet unavailable; no research results found; invalid research topic; rate limits; invalid LLM output; missing citations; webpage retrieval failures; agent execution failures.

- The application must not crash when one source is unavailable.
- Display meaningful error messages.
- Do not produce a final report that falsely claims successful research when all source retrieval failed.

---

## 8. Testing

Test: Pydantic schema validation; research finding validation; URL validation; agent output parsing; workflow execution order; shared state updates; missing Ollama model handling; report generation; citation consistency.

Mock external API and LLM calls for unit tests. Tests must not require paid APIs or internet access.

---

## 9. Project structure (suggested)

```
multi-agent-research-assistant/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── agents/        research_agent.py, comparison_agent.py, evaluation_agent.py, report_agent.py
├── orchestration/ workflow.py, state.py
├── services/      ollama_client.py, web_search.py, arxiv_search.py, github_search.py, document_fetcher.py
├── schemas/       research.py, comparison.py, evaluation.py, report.py
├── utils/         citations.py, helpers.py
├── tests/         test_schemas.py, test_workflow.py, test_citations.py
└── outputs/
```

May be adjusted with a clear reason, but keep it simple.

---

## 10. Development process

Before writing code: inspect project directory; check Python and dependencies; check Ollama; check hardware; explain architecture; create step-by-step plan.

Stages:
1. Project setup and Ollama integration
2. Research retrieval tools
3. Research Agent
4. Comparison Agent
5. Evaluation Agent
6. Report Agent
7. LangGraph orchestration
8. Streamlit frontend
9. Testing and debugging
10. README and example report

After each stage: run relevant tests, fix errors, explain what was implemented, show files changed, explain important technical decisions.

- Do not generate the entire project in one enormous file.
- Do not overwrite unrelated existing files without asking.
- Do not claim tests passed unless they were actually executed.

---

## 11. Final deliverables

1. A fully working local MVP.
2. Four clearly separated agents.
3. Actual research retrieval from external sources.
4. A shared state and orchestrator.
5. A structured comparison and evaluation.
6. A final report with real source references.
7. Markdown report download.
8. Clean, readable source code.
9. A requirements.txt.
10. A .env.example.
11. A comprehensive README.
12. A Mermaid architecture diagram.
13. One example research query and generated report.
14. Test suite and actual test results.
15. A list of limitations and possible future improvements.

---

## 12. Acceptance criteria

- I can launch the application locally.
- I can enter a research topic.
- The Research Agent retrieves actual sources.
- The Comparison Agent analyses the research findings.
- The Evaluation Agent identifies benchmark evidence and limitations.
- The Report Agent creates the final structured report.
- All agents share information through the orchestrator.
- Source references point to actual retrieved URLs.
- I can download the report.
- The interface displays actual agent execution status.
- Failures are handled gracefully.
- The project has a working README and tests.

---

## 13. Engineering principles

- Keep it a POC, not a production platform.
- Prefer readable and maintainable Python.
- Avoid unnecessary abstractions.
- Do not hallucinate research findings.
- Do not fabricate citations.
- Do not fabricate benchmark numbers.
- Make the workflow transparent.
- Keep all LLM inference local.
- Do not introduce paid APIs.
- Clearly document limitations.
- Ensure every major component can be explained during a technical demonstration.

---

## Additional instruction from the developer

This project is mainly to check whether the developer understands the concepts. Every stage must be explained so the developer understands the process — not just the code.
