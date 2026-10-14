# AI Task Worker: an autonomous agent for company workflows

Give it a plain-English task. It plans, operates a browser and files, recovers from failures, and **verifies the outcome independently** before reporting success.

## Core loop
Goal → Plan → Pick tool → Execute → Observe → Adapt → Verify → Report

## Architecture
- `agent/loop.py`: LLM-driven loop. The model chooses every action via tool calling.
- `agent/tools.py`: generic tools (`list_files`, `read_file`, `browser_goto/fill/click/read`, `remember`, `ask_human`, `verify`). Nothing is task-specific.
- `agent/verifier.py`: checks the real database through the API, not the agent's own browser or claims.
- `agent/memory.py`: run state, JSON traces, and a lessons store.
- `mock_app/app.py`: a simulated finance system with a **flaky mode** (renamed buttons, one-time HTTP 500).
- `eval.py`: runs tasks and scores them with the independent verifier.

## Design decisions
- **Independent verification.** The agent can be wrong about its own success, so pass/fail comes from the database.
- **Approval gate.** Write actions (save, pay, delete...) ask the human first.
- **No blind retries on writes.** Reads retry automatically. Writes are never repeated, so a retry can't create a duplicate record. The agent sees the error and replans.
- **Model-agnostic.** Any OpenAI-compatible tool-calling LLM works through three env vars. Tested on Gemini (free tier).

## Setup
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python data/make_invoices.py
```
Set the model (PowerShell, one line each):
```
$env:LLM_API_KEY="your-key"
$env:LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
$env:LLM_MODEL="gemini-3.5-flash-lite"
```
Terminal 1: `python mock_app/app.py` (set `$env:FLAKY="2"` first for flaky mode)
Terminal 2:
```
python run.py "Find the latest invoice from Company X in data/invoices, extract the amount and due date, enter it in the finance system, and tell me when it is done."
python eval.py normal
```

## Results
| Run | Pass | Notes |
|---|---|---|
| Eval 1 | 2/3 | Agent clicked Mark Paid, which was never requested. The independent verifier caught it. (Auto-approve was on for the eval.) |
| Eval 2, after adding a scope rule | 3/3 | Same tasks, 9 / 8 / 6 steps |

Three different tasks (enter from a PDF, enter a second vendor, mark as paid) ran with zero code changes.

**Failure recovery:** in flaky mode the save button was renamed, the click timed out, the agent re-read the page, found the new button and saved. Trace: `docs/flaky_recovery_trace.json`.

## Found and fixed during development
- The approval gate's word list missed "Paid" and "Mark", so a write skipped approval. Fixed.
- Automatic retries could re-run a write action after a server error. Fixed: writes never auto-retry.
- Agent took an out-of-scope action. Fixed with a scope rule in the prompt.

## Limitations (honest)
- "Learning from failures" is implemented (a reflection step writes a lesson that is added to the next run's prompt), but in my test it did **not** reduce steps. The failure was a server error, not something a lesson about element ids could prevent.
- The flaky-mode eval was not run end to end because of free-tier rate limits (5 requests/minute).
- Narrow environment: one simulated app and PDF/text files. No desktop apps.
- Small eval set (3 tasks, single run each).

## Next steps
Larger task suite with repeated runs, per-step task-specific verification, a desktop/computer-use backend, and tuning the lesson injection.