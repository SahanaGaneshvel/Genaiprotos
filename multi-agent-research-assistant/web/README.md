# Web frontend (Next.js)

A single page that shows the Multi-Agent AI Research Assistant working **behind the scenes**: a flow
diagram (Question → Check → Research → Compare → Evaluate → Write → Report, with the four kinds of
sources above Research and the local AI model below) lights up step by step, a "What's happening now"
panel explains the current step in plain words, and clicking any box shows what that step produced.

**Deployed:** [research-agents-blush.vercel.app](https://research-agents-blush.vercel.app/) (Replay mode).

It has two modes, which render identically:

| Mode | Where it works | What it shows |
|---|---|---|
| **Replay** | anywhere, including a hosted deployment | a real recorded run ([`public/recorded-run.json`](public/recorded-run.json)) played back with its real timings, sped up 10×, 30× or 100× |
| **Live** | only when the page is opened on `localhost` and the API is running | a new run streamed from the Python API as Server-Sent Events |

## Run it

```bash
# terminal 1, from the project root: the API that runs the LangGraph workflow
python -m uvicorn api.server:app --port 8000

# terminal 2, in this folder (Node.js 20+)
npm install
npm run build && npx next start -p 3000   # or: npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_URL` if the API is not on `http://localhost:8000`.
Without the API the page still works in Replay mode.

Shareable links: `?replay=play` starts the replay at once, `?replay=end` opens it finished, and
`?open=compare` (or any box id) opens that box's details.

## Files

| Path | Purpose |
|---|---|
| `src/app/page.tsx` | The page: question, replay controls, flow diagram, panels, final report |
| `src/components/flow/flow-diagram.tsx` | The diagram: SVG on wide screens, a vertical list on phones and tablets |
| `src/components/flow/panels.tsx` | "What's happening now" panel and the details card for a clicked box |
| `src/components/flow/report-view.tsx` | The final Markdown report with its citation audit |
| `src/lib/use-flow-run.ts` | Drives Replay and Live mode |
| `src/lib/flow.ts` | Turns raw agent events into steps |
| `src/lib/layers.ts` | Turns steps into the plain-language state of each box |
| `src/lib/api.ts` | API client; reads the Server-Sent Events stream with `fetch` |
| `src/lib/types.ts` | TypeScript types mirroring the Python schemas |

To refresh the replay with a newer run, from the project root:

```bash
python -m orchestration.workflow                                  # records outputs/run_<timestamp>.json
python scripts/export_replay.py outputs/run_<timestamp>.json      # writes public/recorded-run.json
```

Stack: Next.js 16 (App Router), React 19, Tailwind CSS v4, Motion, react-markdown.
