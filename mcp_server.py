import os
import uuid
from typing import Dict

from mcp.server.fastmcp import FastMCP, Context
import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows import RepairAgentWorkflow
from dotenv import load_dotenv


mcp = FastMCP(name="Order Repair Agent",
              description="A repair agent for order management systems.",
              version="0.1.0",
              author="Josh Smith",
              instructions="""
This agent is designed to analyze and repair issues in order management systems.
It can detect problems, plan repairs, and execute them based on user approval."""
                )

@mcp.tool(description="Trigger a repair workflow to start that will detect order problems and propose repairs. " \
          "Upon Approval, the workflow will continue with the repairs and eventually report its results.",
          #tags={"repair", "order management", "workflow", "start workflow"},
          )
async def initiate_repair_processing() -> Dict[str, str]:
    """Start the repair Workflow to detect and repair problems."""
    
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()

    start_msg = {
        "prompt": "Analyze and repair the orders in the order system.",
        "metadata": {
            "user": user,  
            "system": "temporal-repair-agent",
        },
    }
    
    handle = await client.start_workflow(
        RepairAgentWorkflow.run,
        start_msg,
        id=f"repair-{user}-{uuid.uuid4()}",
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    
    desc : str= await handle.describe()
    status : str = await handle.query("GetRepairStatus")    
    
    return {"workflow_id": handle.id, "run_id": handle.result_run_id, "status": status, "description": desc.status.name}


@mcp.tool(description="Approve the repairs proposed by the repair agent workflow. Upon Approval, " \
        "the Workflow will continue with the repairs and eventually report its results.",
          #tags={"repair", "order management", "workflow", "approve workflow"},
          )
async def approve_proposed_repairs(workflow_id: str, run_id: str) -> str:
    """Signal approval for the repair workflow."""
    
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    await handle.signal("ApproveRepair", user)
    
    status : str = await handle.query("GetRepairStatus")    
    return status


@mcp.tool(description="Reject the repairs proposed by the repair agent workflow. Upon Rejection, " \
        "the Workflow will end and not continue with the repairs.",
          #tags={"repair", "order management", "workflow", "reject workflow"},
          )
async def reject_proposed_repairs(workflow_id: str, run_id: str) -> str:
    """Signal rejection for the repair workflow."""
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    await handle.signal("RejectRepair", user)
    status : str = await handle.query("GetRepairStatus")    
    return status


@mcp.tool(description="Get the current status of the repair workflow.",
          #tags={"repair", "order management", "workflow", "status"},
          )
async def status(workflow_id: str, run_id: str) -> Dict[str, str]:
    """Return current status of the workflow."""
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    desc = await handle.describe()
    status = await handle.query("GetRepairStatus")
    return {
        "status": status,
        "description": desc.status.name
    }


#todo add mcp more tools like getting proposed tools, getting repair tool results, and the final report
@mcp.tool(description="Get the proposed tools for the repair workflow.",
          #tags={"repair", "order management", "workflow", "proposed tools"},
          )
async def get_proposed_tools(workflow_id: str, run_id: str) -> Dict[str, str]:
    """Return the proposed tools for the repair workflow. This is the result of the planning step. 
    This should not be confused with the tools that are actually executed.
    This won't have results before the planning step is complete."""
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    
    try:
        planning_result: dict = await handle.query("GetRepairPlanningResult")
        proposed_tools_for_all_orders: dict = planning_result.get("proposed_tools", [])
        additional_notes = planning_result.get("additional_notes", "")
    except Exception as e:
        print(f"Error querying repair planning result: {e}")
        proposed_tools_for_all_orders = "No tools proposed yet."
    
    return {
        "proposed_tools": proposed_tools_for_all_orders,
        "additional_notes": additional_notes
    }

@mcp.tool(description="Get the results of the repair tools executed by the workflow.",
          #tags={"repair", "order management", "workflow", "repair results"},
          )
async def get_repair_tool_results(workflow_id: str, run_id: str) -> Dict[str, str]:
    """Return the results of the repair tools executed by the workflow.
    This won't have results before the repair step is complete."""
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    
    try:
        repair_result = await handle.query("GetRepairToolResults")
    except Exception as e:
        print(f"Error querying repair tool results: {e}")
        repair_result = "No repair results available yet."
    
    return {
        "repair_results": repair_result
    }

@mcp.tool(description="Get the final report of the repair workflow.",
          #tags={"repair", "order management", "workflow", "report"},
          )
async def get_repair_report(workflow_id: str, run_id: str) -> Dict[str, str]:
    """Return the final report of the repair workflow. This is the result of the report step.
    This won't have results before the report step is complete."""
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id, run_id=run_id)
    
    try:
        report_result = await handle.query("GetRepairReport")
    except Exception as e:
        print(f"Error querying repair report: {e}")
        report_result = "No repair report available yet."
    
    return {
        "report": report_result
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
