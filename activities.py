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
    
@activity.defn
async def detect(input: dict) -> dict:
    return await detect_some_stuff(input)

@activity.defn
async def analyze(input: dict) -> str:
    return await analyze_some_stuff(input)

@activity.defn
async def repair(input: dict) -> str:
    return await repair_some_stuff(input)

@activity.defn
async def report(input: dict) -> str:
    return await report_some_stuff(input)

'''These are the individual activities that implement the automated helper agents.
They can be used to detect, analyze, repair, and report on the system.'''
async def detect_some_stuff(input: dict) -> dict:
    """
    This  is a an automated helper agent that detects problems.
    """
    # Load the orders data from a JSON file
    orders_file_path = (
        Path(__file__).resolve().parent / "data" / "orders.json"
    )
    if not orders_file_path.exists():
        exception_message = f"Orders data file not found at {orders_file_path}"
        activity.logger.error(exception_message)
        print(exception_message)
        raise ApplicationError(exception_message)

    with open(orders_file_path, "r") as orders_file:
        order_data = json.load(orders_file)

    
        orders_of_interest = input.get("orders_of_interest", [])
        if orders_of_interest:
            # Filter the order data based on the orders of interest
            orders_to_detect_json = [
                order for order in order_data if order["order_id"] in orders_of_interest
            ]
        if not orders_of_interest:
            orders_to_detect_json = order_data

        activity.heartbeat("Orders Loaded, detection in progress...")
        
        llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
        llm_key = os.environ.get("LLM_KEY")
        if not llm_model or not llm_key:
            return {"error": "LLM model or key not found in environment variables."}
    
        # Define the messages for the LLM completion
        context_instructions = "You are a helpful assistant that detects problems in orders. " \
        "Your task is to analyze the provided orders and identify any issues or anomalies. " \
        "You will receive a list of orders in JSON format, " \
        "each containing an 'order_id', 'items', and 'quantities'. " \
        "Look for common problems such as orders needing approval, orders stuck or delayed for various reasons for more than two weeks, " \
        "or other anomalies. " \
        "Ensure your response is valid JSON and does not contain any markdown formatting. " \
        "The response should be a JSON object with a key 'issues' that contains a list of detected issues. " \
        "If there are no issues, return an empty list. " \
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
            activity.logger.info(f"Raw LLM response: {repr(response_content)}")
            activity.logger.info(f"LLM response content: {response_content}")
            activity.logger.info(f"LLM response type: {type(response_content)}")
            activity.logger.info(
                f"LLM response length: {len(response_content) if response_content else 'None'}"
            )

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

async def analyze_some_stuff(input: dict) -> str:
    """
    This is an automated helper agent that analyzes problems.
    """
    #todo call some llm here to analyze for problems
    await sleep(2)  # Simulate a 2-second delay
    activity.heartbeat("Analysis in progress...")
    
    # Return a success message
    return "Analysis completed successfully, recommend repairing 75 problems."

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