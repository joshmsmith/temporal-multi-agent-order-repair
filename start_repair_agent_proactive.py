import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows import RepairAgentWorkflowProactive
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
    """Run the proactive repair agent workflow.
    This workflow runs periodically, analyzing and repairing orders in the order system.
    It will propose repairs and wait for user approval before executing them.
    After repairs & reporting, it will continue to run periodically to check for new issues.
    It will notify the user of any issues found and proposed repairs.
    Use the --auto-approve flag to skip user approval and proceed with repairs automatically (for the first one)."""

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
    }
    
    handle = await client.start_workflow(
        RepairAgentWorkflowProactive.run,
        start_msg,
        id=f"always-be-repairin-for-{user}",
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    print(f"{user}'s Repair Workflow started with ID: {handle.id}")

    # monitor the workflow as it's always running
    while True:
        # Check if repairs have been planned
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

        # get the proposed tools for repair
        try:
            planning_result : dict = await handle.query("GetRepairPlanningResult")
            proposed_tools_for_all_orders : dict = planning_result.get("proposed_tools", [])
            additional_notes = planning_result.get("additional_notes", "")

        except Exception as e:
            print(f"Error querying repair planning result: {e}")
            proposed_tools = "No tools proposed yet."
        
        if not proposed_tools_for_all_orders:
            print("No proposed tools found for repair.")
        else:
            print("Proposed Orders to repair:")
            for order_id, order in proposed_tools_for_all_orders.items():
                print(f"  - {order_id}: ")
                if not isinstance(order, list):
                    print(f"Expected a dictionary for order, got {type(list)}")
                for tool in order:
                    confidence_score = tool.get("confidence_score", 0.0)
                    additional_notes = tool.get("additional_notes", "")
                    if additional_notes:
                        additional_notes = f"({additional_notes})"
                    tool_name = tool.get("tool_name", "Unknown Tool Name")
                    if confidence_score < 0.5:
                        print(f"Low confidence score for repair: {confidence_score}. Tools with low confidence will not be executed.")
                    
                    print(f"    - {tool_name}: confidence score {confidence_score} {additional_notes}")
                    tool_arguments = tool.get("tool_arguments", {})
                    if not isinstance(tool_arguments, dict):
                        print(f"Expected a dictionary for tool arguments, got {type(tool_arguments)}")
                    for arg_name, arg_value in tool_arguments.items():
                        print(f"      - {arg_name}: {arg_value}")

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
            print("Auto-approving the repair workflow")
            await handle.signal("ApproveRepair", user)
     
        repairs_complete = False
        while not repairs_complete:
            try:
                status = await handle.query("GetRepairStatus")
                if status == "REPORT-COMPLETED" or status == "NO-REPAIRS-NEEDED" or status == "WAITING-FOR-NEXT-CYCLE":
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

        # while the report is waiting for its next cycle, we will monitor the status
        while True:
            # if the repair
            try:
                status = await handle.query("GetRepairStatus")
                if status == "REPORT-COMPLETED" or status == "WAITING-FOR-NEXT-CYCLE":
                    print(f"Current repair status: {status}, waiting for a minute before checking again.")
                    await asyncio.sleep(60)  # Wait before checking the status again
                    continue # Loop back to monitor the next repair planning stage
            except Exception as e:
                print(f"Error querying repair status: {e}")



if __name__ == "__main__":
    asyncio.run(main(args.auto_approve))
