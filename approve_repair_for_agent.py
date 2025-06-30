import asyncio
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from temporalio.client import WorkflowExecutionAsyncIterator
from workflows import RepairAgentWorkflow
from dotenv import load_dotenv

import argparse
from temporalio.client import WorkflowExecutionAsyncIterator
parser = argparse.ArgumentParser(description="Approve repair for a repair agent workflow.")
parser.add_argument(
    "--workflow-id",
    type=str,
    default="repair-Josh-a736473c-61d9-44e7-98b4-ad5309a8579e",
    help="The ID of the workflow to query.",
)
args = parser.parse_args() 

async def main(workflow_id: str) -> None:
    """Approve the repair agent workflow for execution.
    Used to approve the repair workflow after it has proposed repairs and is ready for execution."""
    # Load environment variables
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    print(f"Using user: {user}")
    # Create client connected to server at the given address
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id)
    print(f"Workflow handle: {handle}")

    try:
        status = await handle.query("GetRepairStatus")
        print(f"Current repair status: {status}")
    except Exception as e:
        print(f"Error querying repair status: {e}")
        status = "Unknown"
        
    print("Approving the repair workflow")
    await handle.signal("ApproveRepair", user)


if __name__ == "__main__":
    asyncio.run(main(args.workflow_id))
