# AtlasGuard

A guarded multi-agent finance copilot for international students (Topic C: Cross-border & Student Finance).
All accounts are a **sandbox simulation**. No real money, bank or payment network is touched.

## Quick start

```bash
# from the folder that CONTAINS the atlasguard/ directory
python -m venv .venv
# Windows:  .venv\Scripts\activate      Mac/Linux:  source .venv/bin/activate
pip install -r atlasguard/requirements.txt

# create .env in this same parent folder (next to atlasguard/), one line:
#   ANTHROPIC_API_KEY=sk-ant-...
python -m pytest atlasguard/tests -q      # works WITHOUT a key
python -m atlasguard.cli                  # needs the key
```

Try: `I need to pay 3000 EUR tuition by 5 Nov. Compare routes and draft the best one.`

## Layout and who owns what

| Folder | Purpose | Owner |
|---|---|---|
| `agents/` | Planner + Executor (Claude tool-use loop) | Ali |
| `tools/` | FX, routes, forecast, documents, transfers | Ali |
| `sandbox/` | SQLite sandbox bank, audit log | Ali |
| `guardian/` | Permission tiers and fraud rules | Fakhar |
| `tests/` | Unit tests + attack tests | Fakhar |
| `ui/` | Streamlit app (create this folder) | Hajira |
| `docs/` | Documentation, security report, deck | shared |

## Interface contract for the UI (Hajira)

```python
from atlasguard.sandbox.db import init_db
from atlasguard.agents.agent import AtlasGuardAgent   # one instance per session
from atlasguard.tools import transfers

init_db()
agent = AtlasGuardAgent()
answer = agent.ask("user message")      # returns the final text
agent.trace                             # list of steps: {"step":"plan"|"tool", ...} -> show in the trace panel

# Pending drafts come back inside agent.trace as tool outputs with
# status == "pending_human_confirmation" and a pending_id.
token = transfers.get_confirmation_token(pending_id)   # show to the HUMAN only
transfers.confirm_transfer(pending_id, user_typed_token)
```

Rules: never pass the token to the model; never add an execute tool for the agent.
The UI can be built and tested without an API key by calling the tools directly
(`tools.routes.compare_routes`, `tools.forecast.forecast_budget`, `tools.transfers`).

## Team workflow (parallel work)

1. Ali creates a **private** GitHub repo, pushes this folder, adds Hajira and Fakhar as collaborators.
2. Each person works on their own branch: `git checkout -b hajira-ui` / `fakhar-guardian` / `ali-agent`.
3. Stay inside your own folders (table above). Ask before changing someone else's file.
4. Commit small and often; open a pull request into `main`; Ali merges.
5. `git pull origin main` at least every few hours.
6. Before every merge run `python -m pytest atlasguard/tests -q`. Never merge failing tests.
7. `.env` is git-ignored. Never commit keys.

## Honesty notes (put these in the documentation too)

- FX mid-market rates are fetched live; the source (LIVE / CACHED / OFFLINE) is always shown.
- Provider fees, margins and delivery times are **assumed parameters** for a simulated market, not real quotes.
- Guardian rules are deterministic code; they reduce risk but are not a guarantee.
- Not financial advice.


## v2 additions (read this first)

Run from the folder that CONTAINS `atlasguard` (for example `C:\Fintech`).

    python -m pytest atlasguard\tests -q                 # 38 tests
    python -m atlasguard.cli --reset                      # terminal agent (needs API key + credit)
    streamlit run atlasguard\ui\app.py                   # screen, real AI
    set AG_MOCK=1 && streamlit run atlasguard\ui\app.py  # screen, demo mode, no key (Windows cmd)
    python -m atlasguard.evaluate                         # writes evidence\evaluation_results.md

After updating from v1, delete `atlasguard.db` (or run the CLI once with `--reset`) so the new tables exist.

New: payment memory (green/amber/red), look-alike account detection, money reserve alert,
deadline-safe route advice, tamper-evident action log, Attack Lab, sample fee letters,
Streamlit screen (5 pages). UI people edit only `atlasguard/ui/` and talk only to `atlasguard/api.py`.
Known gap (reported honestly): obfuscated injection wording (attack A20) is not caught by the fixed rules.
