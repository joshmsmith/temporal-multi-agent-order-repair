# temporal-multi-agent
Examples showing different styes of multi-agent architecture with Temporal.
These agents are automation agents who accomplish tasks intelligently and independently. 
They are _not_ conversational. These agents are exposed as tools (via MCP) so they can be used 
by an MCP client.

#TODO diagram of agents and tools and ODS
#TODO DAPRR explanation



## Prerequisites:

- Python3+
- `uv` (curl -LsSf https://astral.sh/uv/install.sh | sh)
- Temporal [Local Setup Guide](https://learn.temporal.io/getting_started/?_gl=1*1bxho70*_gcl_au*MjE1OTM5MzU5LjE3NDUyNjc4Nzk.*_ga*MjY3ODg1NzM5LjE2ODc0NTcxOTA.*_ga_R90Q9SJD3D*czE3NDc0MDg0NTIkbzk0NyRnMCR0MTc0NzQwODQ1MiRqMCRsMCRoMA..)
- [Claude for Desktop](https://claude.ai/download), [Goose](https://github.com/block/goose), or maybe [mcp inspector](https://github.com/modelcontextprotocol/inspector)


## 1. Setup

```bash
uv venv
source .venv/bin/activate
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
### Repair Agent
Repair Agent executes the detect/analyze/repair cycle once:
1. Detects problems
2. Analyzes problems
3. Proposes repairs
4. Waits for approval
5. Executes repairs
6. Reports on its actions
#TODO could make this a diagram
```bash
poetry run python run_repair_agent.py  --auto-approve
```
Optionally you can auto-approve the repairs:
```bash
poetry run python run_repair_agent_periodic.py --auto-approve
```
Or you can approve it using the Temporal UI or included script:
```bash
poetry run python ./approve_repair_for_agent.py --workflow-id "repair-Josh-49c94bb5-d7a6-4a25-a8a3-39f0bf800f91"
```

```none
poetry run python run_repair_agent.py --auto-approve
Client connection: [localhost:7233], Namespace: [default], Task Queue: [agent-repair-task-queue]
Josh's Repair Workflow started with ID: repair-Josh-0a75c9b7-cabe-4339-ba9c-5c8770dc88b0
Current repair status: DETECTING-PROBLEMS
Current repair status: PLANNING-REPAIR
Current repair status: PENDING-APPROVAL
Repair planning is complete.
Proposed Orders to repair:
  - ORD-001-HJP: 
    - request_payment_update_tool: confidence score 0.8 
      - additional_notes: Please deliver after 3 PM to avoid Dursleys
      - customer_id: CUST-HP-001
      - customer_name: Harry James Potter
      - order_id: ORD-001-HJP
      - original_payment_method: Gringotts Vault Transfer
  - ORD-002-HJG: 
    - order_inventory_tool: confidence score 0.95 
      - inventory_description: S.P.E.W. Badge Set
      - inventory_to_order: STP-ORG-001
      - order_id: ORD-002-HJG
      - quantity: 300
  - ORD-003-RBW: 
    - request_payment_update_tool: confidence score 0.9 
      - additional_notes: Maybe short on gold. Can you hold this for a week?
      - customer_id: CUST-RW-003
      - customer_name: Ronald Bilius Weasley
      - order_id: ORD-003-RBW
      - original_payment_method: Gringotts Vault Transfer
  - ORD-004-RHG: 
    - request_approval_tool: confidence score 0.95 
      - approval_request_contents: Request to Approve Order
      - approver: approve-orders@diagonalley.co.uk
      - order_id: ORD-004-RHG
Auto-approval is enabled. Proceeding with repair workflow.
Auto-approving the repair workflow
Current repair status: PENDING-REPAIR
Current repair status: PENDING-REPORT
Workflow completed with result: Repair workflow completed with status: REPORT-COMPLETED. Report Summary: The repair process was completed successfully for 4 issues, with no problems skipped. Each relevant order received the necessary corrections and updates.
```

You can also hook this up to an MCP Client using the included `mcp_server.py`. 
WSL config:
```JSON
    "order_repair_agent": {
      "disabled": false,
      "timeout": 60,
      "type": "stdio",
      "command": "wsl.exe",
      "args": [
        "--cd",
        "/path/to/temporal-multi-agent",
        "--",
        "poetry",
        "run",
        "python",
        "mcp_server.py"
      ]
    }
```
Here's how it looks with Claude:

<img src="./assets/claude-repair-success.png" width="50%" alt="Claude Success">

### Proactive Repair Agent
This proactive agent executes detection and analysis periodically, and notifies if it finds problems. 
It will wait for approval before proceeding with the repair. It _recommends_ repair actions but doesn't do it's own decision making
1. Detects problems
2. Analyzes problems
3. Proposes repairs
4. Notify that there are problems
5. Waits for approval 
 - Unless the confidence score is > .95, in which case it confidently self-approves
6. Executes repairs
7. Reports on its actions
8. Wait some time, start again from the top
#todo good to diagram

```none
poetry run python start_repair_agent_proactive.py 
Client connection: [localhost:7233], Namespace: [default], Task Queue: [agent-repair-task-queue]
Josh's Repair Workflow started with ID: always-be-repairin-for-Josh
Current repair status: DETECTING-PROBLEMS
Current repair status: PLANNING-REPAIR
Current repair status: PENDING-REPAIR
Current repair status: PENDING-REPORT
Repair planning is complete.
<snip just like above but the confidence score was high enough to self-approve>
*** Repair complete*** 
 Summary: The repair process was successful with a total of 3 problems repaired and none skipped. Key repairs involved sending payment update requests to Harry James Potter and Ronald Bilius Weasley. Additionally, an approval request was sent for Rubeus Hagrid's order.
Current repair status: WAITING-FOR-NEXT-CYCLE, waiting for a minute before checking again.
```

## 5. Results
#todo talk about the ingredients (detect, analyze, Action, Report)
#todo talk about the styles: single activity, multiple activities, proactive/scheduled, proactive/looping, supervised

#TODO: explain automation agents vs conversational (assistive) agents, and how they can be used together

### What's Cool About This:
#todo talk about long running interactive agents, proactive agents, self-repairing workflows
