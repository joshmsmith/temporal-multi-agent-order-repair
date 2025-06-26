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
    print(f"{user}'s Repair Workflow started with ID: {handle.id}")

    proposed_tools : str = "No tools proposed yet."
    repairs_planned = False
    while not repairs_planned:
        try:
            repairs_planned = await handle.query("IsRepairPlanned")
            status = await handle.query("GetRepairStatus")
            print(f"Current repair status: {status}")
        except Exception as e:
            print(f"Error querying repair status: {e}")
        await asyncio.sleep(5)  # Wait before checking the status again
    
    print("Repair planning is complete.")
    try:
        proposed_tools = await handle.query("GetRepairPlanningResult")
    except Exception as e:
        print(f"Error querying repair planning result: {e}")
        proposed_tools = "No tools proposed yet."
    
    print(f"Proposed tools for repair: {proposed_tools}") #TODO replace this with a more structured output
    if not auto_approve:
        print("Waiting for user approval to proceed with repairs...")
        try:
            approved = await handle.query("IsRepairApproved")
            if approved:
                print("Repair has already been approved.")
            else:
                print("Repair has not been approved yet. Waiting for user input...")
                # Wait for user input to approve the repair
                while not approved:
                    user_input = input("Do you approve the repair? (yes/no): ").strip().lower()
                    if user_input == "yes":
                        await handle.signal("ApproveRepair", user)
                        approved = True
                        print("Repair approved by user.")
                    elif user_input == "no":
                        print("Repair not approved. Exiting workflow.")
                        return
                    else:
                        print("Invalid input. Please enter 'yes' or 'no'.")
        except Exception as e:
            print(f"Error querying repair approval status: {e}")
    else:
        print("Auto-approval is enabled. Proceeding with repair workflow.")
    if(auto_approve):
        print("Auto-approving the repair workflow")
        await handle.signal("ApproveRepair", user)

    repairs_complete = False
    while not repairs_complete:
        try:
            status = await handle.query("GetRepairStatus")
            if status == "REPORT-COMPLETED":
                repairs_complete = True
                break
            elif status == "REPAIR-FAILED":
                print("Repair failed. Exiting workflow.")
                break
            print(f"Current repair status: {status}")
        except Exception as e:
            print(f"Error querying repair status: {e}")
        await asyncio.sleep(5)  # Wait before checking the status again
    
    print("Repair planning is complete.")
    
    # Wait for the workflow to complete
    result = await handle.result()
    print(f"Workflow completed with result: {result}")


if __name__ == "__main__":
    asyncio.run(main(args.auto_approve))
