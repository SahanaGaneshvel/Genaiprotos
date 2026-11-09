# Web frontend (Next.js)

Animated frontend for the Multi-Agent AI Research Assistant. It talks to the Python API in
`../api/server.py`, which runs the same LangGraph workflow as the Streamlit app.

```bash
# from the project root, in one terminal
python -m uvicorn api.server:app --port 8000

# in this folder, in another terminal
npm install
npm run build && npx next start -p 3000   # or: npm run dev
```

Set `NEXT_PUBLIC_API_URL` if the API is not on `http://localhost:8000`.

| Path | Purpose |
|---|---|
| `src/app/page.tsx` | Dashboard: run research, live agent pipeline, results tabs |
| `src/app/architecture/page.tsx` | Animated, clickable architecture diagram + every step in order |
| `src/app/about/page.tsx` | What the project and each agent do |
| `src/components/run-provider.tsx` | Run state in the root layout, so a run survives page navigation |
| `src/lib/api.ts` | API client; reads the Server-Sent Events stream with `fetch` |
| `src/lib/pipeline.ts` | Step-by-step description of the pipeline (mirrors the Python code) |

Stack: Next.js 16 (App Router, Cache Components), React 19, Tailwind CSS v4, Motion, react-markdown, lucide-react.
