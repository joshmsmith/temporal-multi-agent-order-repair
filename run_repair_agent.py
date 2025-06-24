import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows import RepairAgentWorkflow
from dotenv import load_dotenv

import argparse
parser = argparse.ArgumentParser(description="Run the repair agent workflow.")
parser.add_argument(
    "--auto-approve",
    action="store_true",
    help="Automatically approve the repair workflow without user input.",
)
args = parser.parse_args() 

#todo change main to accept auto-approve as an argument

async def main(auto_approve: bool) -> None:
    # Load environment variables
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    # Create client connected to server at the given address
    client = await get_temporal_client()

    # Start the workflow with an initial prompt
    start_msg = {
        "prompt": "Analyze and repair the system.",
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
    print(f"{user}'s Workflow started with ID: {handle.id}")

    if(auto_approve):
        print("Auto-approving the repair workflow")
        await handle.signal("ApproveRepair", user)

    # Wait for the workflow to complete
    result = await handle.result()
    print(f"Workflow completed with result: {result}")


if __name__ == "__main__":
    asyncio.run(main(args.auto_approve))
