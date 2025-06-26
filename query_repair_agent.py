import asyncio
import uuid
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows import RepairAgentWorkflow
from dotenv import load_dotenv

import argparse
parser = argparse.ArgumentParser(description="Query a repair agent workflow.")
parser.add_argument(
    "--auto-approve",
    action="store_true",
    help="Automatically approve the repair workflow without user input.",
)
parser.add_argument(
    "--workflow-id",
    type=str,
    default="repair-Josh-a736473c-61d9-44e7-98b4-ad5309a8579e",
    help="The ID of the workflow to query.",
)
args = parser.parse_args() 

async def main(auto_approve: bool, workflow_id: str) -> None:
    # Load environment variables
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    print(f"Using user: {user}")
    # Create client connected to server at the given address
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id=workflow_id)
    print(f"Workflow handle: {handle}")
    status = await handle.query("GetRepairStatus")
    print(f"Current repair status: {status}")
    try:
        proposed_tools = await handle.query("GetRepairPlanningResult")
    except Exception as e:
        print(f"Error querying repair planning result: {e}")
        proposed_tools = "No tools proposed yet."

    try: 
        # probably could do key/value for proposed tools
        for order in proposed_tools["proposed_tools"]:
            print(f"order: {order}")
            order_id = order.get("order_id", "Unknown Order ID")
            
            additional_notes = order.get("additional_notes", "No additional notes provided.")
            print(f"Additional Notes: {additional_notes}")
            print(f"Order ID: {order_id}")
            proposed_tools_for_order = order.get("proposed_tools", {})
            if not proposed_tools_for_order:
                print(f"No proposed tools found for order ID: {order_id}")
                continue
            if not isinstance(proposed_tools_for_order, list):
                print(f"Expected a list for proposed tools, got {type(proposed_tools_for_order)} for order ID {order_id}")
                continue
            for tool_for_order in proposed_tools_for_order:
                if not isinstance(tool_for_order, dict):
                    print(f"Unexpected tool data format for order ID {order_id}: {tool_for_order}")
                    continue
                tool_name = tool_for_order.get("tool_name", "Unknown Tool Name")
            
                confidence_score = tool_for_order.get("confidence_score", "Unknown Confidence Score")
            
                print(f"Tool Name: {tool_name}")
                print(f"- Confidence Score: {confidence_score}")
                tool_arguments = tool_for_order.get("tool_arguments", {})
                if not isinstance(tool_arguments, dict):
                    print(f"- Expected a dictionary for tool arguments, got {type(tool_arguments)} for order ID {order_id}")
                    continue
                if not tool_arguments:
                    print(f"- No arguments provided for tool {tool_name} in order ID {order_id}")
                    continue
                print(f"- Tool Arguments: ")
                for key, value in tool_arguments.items():
                    print(f"  - {key}: {value}")
            
            print("-" * 50)
    except Exception as e:
            print(f"Error printing proposed tools: {e}")


if __name__ == "__main__":
    asyncio.run(main(args.auto_approve, args.workflow_id))
