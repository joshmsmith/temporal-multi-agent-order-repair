import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from dotenv import load_dotenv

import argparse
parser = argparse.ArgumentParser(description="Query a repair agent workflow.")
parser.add_argument(
    "--workflow-id",
    type=str,
    default="repair-Josh-a736473c-61d9-44e7-98b4-ad5309a8579e",
    help="The ID of the workflow to query.",
)
args = parser.parse_args() 

async def main(workflow_id: str) -> None:
    """Query the repair agent workflow for its status and results.
    Used to check the status of a repair workflow and get details about proposed repairs and results."""
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

    try:
        planning_result : dict = await handle.query("GetRepairPlanningResult")
        proposed_tools_for_all_orders : dict = planning_result.get("proposed_tools", [])
        additional_notes = planning_result.get("additional_notes", "")
   
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
    except Exception as e:
        print(f"Error querying repair planning result: {e}")
        proposed_tools = "No tools proposed yet."

    try:
        repair_result = await handle.query("GetRepairToolResults")
    except Exception as e:
        print(f"Error querying repair tool results: {e}")
        repair_result = "No repair results available yet."
        
    print("Repair Tool Execution results:")
    if not isinstance(repair_result, dict):
        print(f"Expected a dictionary for repair results, got {type(repair_result)}")
    else:
        for key, value in repair_result.items():
            if isinstance(value, list):
                print(f"  - {key}: (results ommitted for brevity, {len(value)} items)")
            else:
                print(f"  - {key}: {value}")

    
        try:
            repair_report = await handle.query("GetRepairReport")

            report_summary = repair_report.get("report_summary", "No summary available")
            print(f"*** Final Report: ***")
            print(f"{report_summary}")
        except Exception as e:
            print(f"Error querying repair report: {e}")
            report_result = "No repair report available yet."
    
    print(f"Repair status: {status}")


if __name__ == "__main__":
    asyncio.run(main(args.workflow_id))
