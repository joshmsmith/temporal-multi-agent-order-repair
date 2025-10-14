import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows import RepairAgentWorkflowProactive, RepairAgentWorkflowMonolith
from dotenv import load_dotenv

import argparse
parser = argparse.ArgumentParser(description="Run the repair agent workflow.")
parser.add_argument(
    "--emails-only",
    action="store_true",
    help="Only use email data.",
)
args = parser.parse_args() 

async def main(emails_only: bool) -> None:
    """Run the monolith repair agent workflow. It's like the proactive repair agent, but a monolith agent.
    Used to demonstrate that monolith agents are not a good design pattern.
    Use the --emails-only flag to only use email data."""

    # Load environment variables
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    # Create client connected to server at the given address
    client = await get_temporal_client()

    # Start the workflow with an initial prompt
    start_msg = {
        "prompt": "Analyze and repair the orders in the order system.",
        "metadata": {
            "user": user,  
            "system": "temporal-repair-agent",
        },
        # Add this to enable the callback for a workflow
        # "callback": {
        #     "type": "signal-workflow",
        #     "name": "add_external_message",
        #     "task_queue": "agent-task-queue",
        #     "workflow_id": "agent-workflow",
        #     "args": "message: Union[str, Dict[str, Any]]"
        # },
        # Uncomment this to enable email notifications (requires email setup)
        # "callback": {
        #     "type": "email",
        #     "name": "email_callback",
        #     "subject": "Repair Agent Notification",
        #     "email": "repair-notify@yourcompany.com",
        #     "args": "message: Union[str, Dict[str, Any]]""
        # },
    }
    
    handle = await client.start_workflow(
        RepairAgentWorkflowMonolith.run,
        start_msg,
        id=f"monolith-agent-for-{user}",
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    print(f"{user}'s Repair Workflow started with ID: {handle.id}")

    # monitor the workflow as it's always running
    while True:
        repairs_complete = False
        while not repairs_complete:
            try:
                status = await handle.query("GetRepairStatus")
                if status == "REPORT-COMPLETED" or status == "NO-REPAIRS-NEEDED" or status == "REPAIR-COMPLETED":
                    repairs_complete = True
                    break
                elif status == "REPAIR-FAILED":
                    print("Repair failed. Exiting workflow.")
                    break
                print(f"Current repair status: {status}")
            except Exception as e:
                print(f"Error querying repair status: {e}")
            await asyncio.sleep(5)  # Wait before checking the status again
        
        
        try:
            repair_report : dict = await handle.query("GetRepairReport")
            report_summary = repair_report.get("report_summary", "No summary available")
            print(f"*** Repair complete*** \n Summary: {report_summary}")
        except Exception as e:
            print(f"Error querying repair report: {e}")
            repair_report = "No report available yet."


if __name__ == "__main__":
    asyncio.run(main(args.emails_only))
