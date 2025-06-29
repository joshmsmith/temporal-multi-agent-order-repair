# temporal-multi-agent
Examples showing how to do different styles of multi-agents with Temporal

### Prerequisites:

- Python3+
- `uv` (curl -LsSf https://astral.sh/uv/install.sh | sh)
- Temporal [Local Setup Guide](https://learn.temporal.io/getting_started/?_gl=1*1bxho70*_gcl_au*MjE1OTM5MzU5LjE3NDUyNjc4Nzk.*_ga*MjY3ODg1NzM5LjE2ODc0NTcxOTA.*_ga_R90Q9SJD3D*czE3NDc0MDg0NTIkbzk0NyRnMCR0MTc0NzQwODQ1MiRqMCRsMCRoMA..)
- [Claude for Desktop](https://claude.ai/download)


## 1. Setup

```bash
uv venv
source .venv/bin/activate
# uv pip install temporalio fastmcp

poetry install
```

## 2. Launch Temporal locally

```bash
temporal server start-dev
```

## 3. Start the worker

```bash
poetry run python run_worker.py
```

## 4. Start Various Workflows
```bash
poetry run python run_repair_agent.py
```

#todo: mention install mcp
#todo: mention add various workflows
## 5. Results

### What's Cool About This:

#todo talk about the ingredients (detect, analyze, Action, Report)
#todo talk about the styles: single activity, multiple activities, proactive/scheduled, proactive/looping, supervised