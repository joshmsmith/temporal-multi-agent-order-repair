import os
import uuid
from typing import Dict

from mcp.server.fastmcp import FastMCP, Context
from temporalio.client import Client

from workflows import RepairAgentWorkflow


async def _client() -> Client:
    return await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233")) #todo use getclient


mcp = FastMCP("repair_processor")

#todo don't we need some context?


@mcp.tool()
async def trigger(repair: Dict, ctx: Context) -> Dict[str, str]:
    await ctx.report_progress(progress=0.1, total=1.0)
    await ctx.info("Starting repair processing workflow")
    """Start the repairWorkflow with the given repair JSON."""
    workflow_id = f"repair-{uuid.uuid4()}"
    client = await _client()
    handle = await client.start_workflow(
        RepairAgentWorkflow.run,
        repair,
        id=workflow_id,
        task_queue="repair-task-queue",
    )
    await ctx.info("repair processing workflow started")
    
    desc = await handle.describe()
    status = await handle.query("GetRepairStatus")
    await ctx.report_progress(progress=1.0, total=1.0)
    await ctx.info(f"Repair processing workflow started with status {status}")
    
    
    return {"workflow_id": handle.id, "run_id": handle.result_run_id}


@mcp.tool()
async def approve(workflow_id: str, run_id: str) -> str:
    """Signal approval for the repair workflow."""
    client = await _client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    await handle.signal("ApproveRepair")
    return "APPROVED"


@mcp.tool()
async def reject(workflow_id: str, run_id: str) -> str:
    """Signal rejection for the repair workflow."""
    client = await _client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    await handle.signal("RejectRepair")
    return "REJECTED"


@mcp.tool()
async def status(workflow_id: str, run_id: str) -> str:
    """Return current status of the workflow."""
    client = await _client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    desc = await handle.describe()
    status = await handle.query("GetRepairStatus")
    return f"repair with ID {workflow_id} is currently {status}. " \
           f"Workflow status: {desc.status.name}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
