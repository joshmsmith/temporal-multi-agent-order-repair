from asyncio import sleep
from datetime import datetime
import os
import random
import json
from pathlib import Path
from temporalio import activity
from dotenv import load_dotenv

from litellm import completion
from temporalio.exceptions import ApplicationError

load_dotenv(override=True)


"""
This defines the activities for the repair agent workflow.
Activities are static methods that implement automated helper agents as tools.
They can be used to detect, analyze, repair, and report on the system.
"""


@activity.defn
async def single_tool_repair(self, input: dict) -> str:
    activity.logger.info(f"Running single_tool_repair with input: {input}")
    analysis = await self.analyze(input)
    activity.logger.info(f"Analysis result: {analysis}")
    activity.heartbeat("Analysis completed, proceeding to repair...")
    repairs = await self.repair(input)
    activity.heartbeat("Repair completed, proceeding to report...")
    activity.logger.info(f"Repair result: {repairs}")
    
    report = await report(input)

    return report
'''These activities demonstrate the detect, analyze, repair, and report steps of the repair agent workflow.
They can be used to detect, analyze, repair, and report on a system.
They simply call the corresponding functions to perform the actions.'''
@activity.defn
async def detect(input: dict) -> dict:
    return await detect_some_stuff(input)

@activity.defn
async def analyze(input: dict) -> dict:
    return await analyze_some_stuff(input)

@activity.defn
async def plan_repair(input: dict) -> dict:
    return await plan_to_repair_some_stuff(input)

@activity.defn
async def repair(input: dict) -> str:
    return await repair_some_stuff(input)

@activity.defn
async def report(input: dict) -> str:
    return await report_some_stuff(input)

'''These are the individual functions that implement the automated helper agents.
They can be used to detect, analyze, repair, and report on repairs for a system.'''

async def detect_some_stuff(input: dict) -> dict:
    """
    This  is a an automated helper agent that detects problems.
    It uses a Large Language Model (LLM) to analyze orders and determine if there are issues.
    It heartbeats the activity to indicate progress 
    It returns a dict response with the detection results: primarily a confidence_score.
    """
    # Load the orders data (from a JSON file)
    orders_of_interest: dict = input.get("orders_of_interest", [])
    orders_to_detect_json = load_orders_data(orders_of_interest)

    activity.heartbeat("Orders Loaded, detection in progress...")
    
    # Use the LLM to detect issues in the orders
    # Get the LLM model and key from environment variables
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    llm_key = os.environ.get("LLM_KEY")
    if not llm_model or not llm_key:
        exception_message = f"LLM model or key not found in environment variables."
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)

    
    # This is a context instruction for the LLM to understand its task
    context_instructions = "You are a helpful assistant that detects if there are problems in orders. " \
    "Your task is to analyze the provided orders and detect if there are any issues or anomalies. " \
    "You will receive a list of orders in JSON format, " \
    "each containing an 'order_id', 'order_date', 'status', 'items', and 'quantities'. " \
    "Look for common problems such as orders needing approval, orders stuck or delayed for various reasons for more than two weeks, " \
    "or other anomalies. " \
    "Ensure your response is valid JSON and does not contain any markdown formatting. " \
    "The response should be a JSON object with a confidence_score of how " \
    "sure you are that there are issues. " \
    "Feel free to include additional notes in 'additional_notes' if necessary. " \
    "If there are no issues, note that in additional_notes. " \
    "The list of orders to analyze is as follows: " \
    + json.dumps(orders_to_detect_json, indent=2)
    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + datetime.now().strftime("%B %d, %Y"),
        },
        # {
        #     "role": "user",
        #     "content": input.prompt,
        # },
    ]

    try:
        completion_kwargs = {
            "model": llm_model,
            "messages": messages,
            "api_key": llm_key,
        }

        response = completion(**completion_kwargs)

        response_content = response.choices[0].message.content
        #activity.logger.info(f"Raw LLM response: {repr(response_content)}")
        #activity.logger.info(f"LLM response content: {response_content}")
        #activity.logger.info(f"LLM response type: {type(response_content)}")
        
        # Sanitize the response to ensure it is valid JSON
        response_content = sanitize_json_response(response_content)
        activity.logger.info(f"Sanitized response: {repr(response_content)}")
        detection_json_response: dict = parse_json_response(response_content)

        if "confidence_score" not in detection_json_response:
            exception_message = "Detection response does not contain 'confidence_score'."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        
        confidence_score = detection_json_response.get("confidence_score", 0.0)
        activity.logger.info(f"Detection confidence score: {confidence_score}")
        return detection_json_response
    
    except Exception as e:
        print(f"Error in LLM completion: {str(e)}")
        raise
    
async def analyze_some_stuff(input: dict) -> dict:
    """
    This is an automated helper agent that analyzes problems.
    It uses a Large Language Model (LLM) to analyze orders and define issues.
    It heartbeats the activity to indicate progress 
    It returns a dictionary response with the detection results: 
        - orders 
         - their problems
         - how sure it is via a confidence_score.
    """    
    # Load the orders data (from a JSON file)
    orders_of_interest: dict = input.get("orders_of_interest", [])
    orders_to_detect_json = load_orders_data(orders_of_interest)

    activity.heartbeat("Orders Loaded, analysis in progress...")
    
    # Use the LLM to analyze issues in the orders
    # Get the LLM model and key from environment variables
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    llm_key = os.environ.get("LLM_KEY")
    if not llm_model or not llm_key:
        exception_message = f"LLM model or key not found in environment variables."
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)

    # Define the messages for the LLM completion
    context_instructions = "You are a helpful assistant that detects and analyzes problems in orders. " \
    "Your task is to analyze the provided orders and identify any issues or anomalies. " \
    "You will receive a list of orders in JSON format, " \
    "each containing an 'order_id', 'order_date', 'status', 'items', and 'quantities'. " \
    "Look for common problems such as orders needing approval, orders stuck or delayed for various reasons for more than two weeks, " \
    "or other anomalies. " \
    "Ensure your response is valid JSON and does not contain any markdown formatting. " \
    "The response should be a JSON object with a key 'issues' that contains a list of detected issues and " \
    "a confidence_score of how sure you are there is a problem. " \
    "Feel free to include additional notes in 'additional_notes' if necessary. " \
    "If there are no issues, note that in additional_notes. " \
    "The list of orders to analyze is as follows: " \
    + json.dumps(orders_to_detect_json, indent=2)
    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + datetime.now().strftime("%B %d, %Y"),
        },
    ]

    try:
        completion_kwargs = {
            "model": llm_model,
            "messages": messages,
            "api_key": llm_key,
        }

        response = completion(**completion_kwargs)

        response_content = response.choices[0].message.content
        # activity.logger.info(f"Raw LLM response: {repr(response_content)}")
        # activity.logger.info(f"LLM response content: {response_content}")
        # activity.logger.info(f"LLM response type: {type(response_content)}")
        # activity.logger.info(
        #     f"LLM response length: {len(response_content) if response_content else 'None'}"
        # )

        # Use the new sanitize function
        response_content = sanitize_json_response(response_content)
        activity.logger.info(f"Sanitized response: {repr(response_content)}")
        return parse_json_response(response_content)
    
    except Exception as e:
        print(f"Error in LLM completion: {str(e)}")
        raise

async def plan_to_repair_some_stuff(input: dict) -> dict:
    """
    This is a an automated helper agent that plans repairs for problems.
    It uses a Large Language Model (LLM) to analyze orders and plan repairs.
    It heartbeats the activity to indicate progress
    It returns a dictionary response with the planned repairs:
        - issues
        - planned tools to repair them
        - how sure it is via a confidence_score.
    """    
    # Load the orders data 
    orders_of_interest: dict = input.get("orders_of_interest", [])
    orders_to_detect_json = load_orders_data(orders_of_interest)
    inventory_data_json = load_inventory_data([])

    activity.heartbeat("Orders and inventory loaded, planning in progress...")
    
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    llm_key = os.environ.get("LLM_KEY")
    if not llm_model or not llm_key:
        exception_message = f"LLM model or key not found in environment variables."
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)
    
    tool_list = [
        {
            "tool_name": "request_approval_tool",
            "description": "A tool that can request approvals.",
            "arguments": {
                "approver": "approver_email", "default": "approve-orders@diagonalley.co.uk",
                "approval_request_contents": "Request to Approve Order",
                "order_id": "order_id"
            }
        },
        {
            "tool_name": "order_inventory_tool",
            "description": "A tool that can request orders for more inventory.",
            "arguments": {
                "inventory_to_order": "item_id",
                "inventory_description": "inventory_description",
                "quantity": "quantity",
                "order_id": "order_id"
            }
        },        
        {
            "tool_name": "request_payment_update_tool",
            "description": "A tool that can request payment updates so an order can be paid.",
            "arguments": {
                "customer_name": "customer_name",
                "customer_id": "customer_id",
                "original_payment_method": "original_payment_method",
                "additional_notes": "additional_notes",
                "order_id": "order_id"
            }
        }, 
    ]

    # Define the messages for the LLM completion
    context_instructions = "You are a helpful assistant that proposes solutions to problems in orders. " \
    "Your task is to analyze the provided orders, their problems, and propose tools to repair them " \
    "using the provided tool_list. " \
    "You will receive a list of orders in JSON format, " \
    "each containing an 'order_id', 'order_date', 'status', 'items', and 'quantities'. " \
    "You will also receive a list of issues that need to be repaired. " \
    "You will also receive a list of tools that can be used to repair the issues. " \
    "Ensure your response is valid JSON and does not contain any markdown formatting. " \
    "The response should be a JSON object with a key 'proposed_tools' that contains " \
    "a list of orders, proposed tools to repair each order, tool arguments for each tool, and " \
    "a confidence_score of how sure that the tool will solve the problem. " \
    "Feel free to include additional notes in 'additional_notes' if necessary. " \
    "If there are no proposed tools for repairs, note that in additional_notes. " \
    "The list of orders to analyze is as follows: " \
    + json.dumps(orders_to_detect_json, indent=2)
    context_instructions = context_instructions  + "\nThe list of issues to repair is as follows: " \
    + json.dumps(input.get("problems_to_repair", []), indent=2) 
    context_instructions = context_instructions  + "\nThe list of tools that can be used to repair the issues is as follows: " \
    + json.dumps(tool_list, indent=2)
    context_instructions = context_instructions  + "\nThe inventory data is as follows: " \
    + json.dumps(inventory_data_json, indent=2)

    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + datetime.now().strftime("%B %d, %Y"),
        },
    ]

    try:
        completion_kwargs = {
            "model": llm_model,
            "messages": messages,
            "api_key": llm_key,
        }

        response = completion(**completion_kwargs)

        response_content = response.choices[0].message.content
        # activity.logger.info(f"Raw LLM response: {repr(response_content)}")
        # activity.logger.info(f"LLM response content: {response_content}")
        # activity.logger.info(f"LLM response type: {type(response_content)}")
        # activity.logger.info(
        #     f"LLM response length: {len(response_content) if response_content else 'None'}"
        # )

        # Use the new sanitize function
        response_content = sanitize_json_response(response_content)
        activity.logger.info(f"Sanitized response: {repr(response_content)}")
        return parse_json_response(response_content)
    
    except Exception as e:
        print(f"Error in LLM completion: {str(e)}")
        raise   

async def repair_some_stuff(input: dict) -> str:
    """
    This is a an automated helper agent that repairs problems.
    """
    #todo call some llm here to repair problems
    await sleep(2)  # Simulate a 2-second delay
    activity.heartbeat("Repair in progress...")
    

    return "Repair completed successfully: 75 problems repaired."

async def report_some_stuff(input: dict) -> str:
    """
    This is an automated helper agent that reports on the repair.
    """
    await sleep(2)  # Simulate a 2-second delay
    activity.heartbeat("Reporting in progress...")
    
    # Return a success message
    return "Report completed successfully: With a fix swift and grand, problems vanish like sand."

def sanitize_json_response(response_content: str) -> str:
        """
        Sanitizes the response content to ensure it's valid JSON.
        """
        # Remove any markdown code block markers
        response_content = response_content.replace("```json", "").replace("```", "")

        # Remove any leading/trailing whitespace
        response_content = response_content.strip()

        return response_content

def parse_json_response(response_content: str) -> dict:
        """
        Parses the JSON response content and returns it as a dictionary.
        """
        try:
            data = json.loads(response_content)
            return data
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            raise

def load_orders_data(orders_of_interest: dict) -> dict:
    """
    Loads the orders data from a JSON file.
    If `orders_of_interest` is provided, it filters the orders based on the given order IDs.
    If no `orders_of_interest` is provided, it returns all orders.
    Raises an ApplicationError if the orders data file is not found.
    """
    orders_file_path = (
        Path(__file__).resolve().parent / "data" / "orders.json"
    )
    if not orders_file_path.exists():
        exception_message = f"Orders data file not found at {orders_file_path}"
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)

    with open(orders_file_path, "r") as orders_file:
        order_data: dict = json.load(orders_file)
    
        if orders_of_interest:
            # Filter the order data based on the orders of interest
            orders_to_detect_json = [
                order for order in order_data if order["order_id"] in orders_of_interest
            ]
        if not orders_of_interest:
            orders_to_detect_json = order_data
        
        return orders_to_detect_json
    
def load_inventory_data(inventory_of_interest: dict) -> dict:
    """
    Loads the inventory data from a JSON file.
    If `inventory_of_interest` is provided, it filters the inventory based on the given item IDs.
    If no `inventory_of_interest` is provided, it returns all inventory items.
    Raises an ApplicationError if the inventory data file is not found.
    """
    inventory_file_path = (
        Path(__file__).resolve().parent / "data" / "inventory.json"
    )
    if not inventory_file_path.exists():
        exception_message = f"Inventory data file not found at {inventory_file_path}"
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)

    with open(inventory_file_path, "r") as inventory_file:
        inventory_data: dict = json.load(inventory_file)

        if inventory_of_interest:
            # Filter the inventory data based on the items of interest
            inventory_to_analyze_json = [
                item for item in inventory_data if item["item_id"] in inventory_of_interest
            ]
        if not inventory_of_interest:
            inventory_to_analyze_json = inventory_data

        return inventory_to_analyze_json