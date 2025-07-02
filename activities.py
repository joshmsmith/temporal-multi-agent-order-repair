from asyncio import sleep
from datetime import datetime
import os
import json
from pathlib import Path
from typing import Callable
from temporalio import activity
from dotenv import load_dotenv

from litellm import completion
from temporalio.exceptions import ApplicationError
from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client

load_dotenv(override=True)

# Define the date for analysis to be a useful date (June 28, 2025), relative to the static order dates
DATE_FOR_ANALYSIS = datetime(2025, 6, 28)

"""
This defines the activities for the repair agent workflow.
Activities are static methods that implement automated helper agents as tools.
They can be used to detect, analyze, repair, and report on the system.
"""

@activity.defn
async def single_tool_repair(self, input: dict) -> str:
    #TODO this needs to detect, move the results from analysis to orders_to_repair, plan repairs
    #TODO detect
    activity.logger.info(f"Running single_tool_repair with input: {input}")
    analysis = await self.analyze(input)
    activity.logger.info(f"Analysis result: {analysis}")
    activity.heartbeat("Analysis completed, proceeding to repair...")
    #TODO move the analysis results to the input for repair
    #TODO plan repairs
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
async def notify(input: dict) -> dict:
    return await notify_interested_parties(input)

@activity.defn
async def repair(input: dict) -> dict:
    return await repair_some_stuff(input)

@activity.defn
async def report(input: dict) -> dict:
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
    activity.logger.debug(f"Context instructions for LLM: {context_instructions}")

    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + DATE_FOR_ANALYSIS.strftime("%B %d, %Y"),
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
        activity.logger.debug(f"Raw LLM response: {repr(response_content)}")
        activity.logger.debug(f"LLM response content: {response_content}")
        activity.logger.debug(f"LLM response type: {type(response_content)}")
        
        # Sanitize the response to ensure it is valid JSON
        response_content = sanitize_json_response(response_content)
        activity.logger.debug(f"Sanitized response: {repr(response_content)}")
        detection_json_response: dict = parse_json_response(response_content)

        activity.logger.debug(f"Validating Detection Result: {detection_json_response}")
        if "confidence_score" not in detection_json_response:
            exception_message = "Detection response does not contain 'confidence_score'."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        
        confidence_score = detection_json_response.get("confidence_score", 0.0)
        activity.logger.info(f"Detection confidence score: {confidence_score}")
        return detection_json_response
    
    except Exception as e:
        activity.logger.error(f"Error in LLM completion: {str(e)}")
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
    # First, get the LLM model and key from environment variables
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    llm_key = os.environ.get("LLM_KEY")
    if not llm_model or not llm_key:
        exception_message = f"LLM model or key not found in environment variables."
        activity.logger.error(exception_message)
        raise ApplicationError(exception_message)

    # Define the messages for the LLM completion
    context_instructions = "You are a helpful assistant that detects and analyzes problems in orders. " \
    "Your task is to analyze the provided orders and identify any issues or anomalies. " \
    "You will receive a list of orders in JSON format, " \
    "each containing an 'order_id', 'order_date', 'status', 'items', and 'quantities'. " \
    "Look for common problems such as orders needing approval, orders stuck or delayed for various reasons for more than two weeks, " \
    "or other anomalies. " \
    "Ensure your response is valid JSON and does not contain any markdown formatting. " \
    "The response should be a JSON object with a key 'issues' that contains a list of detected issues, " \
    "each with an order_id, item with key 'issue' that describes the issue, and " \
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
            + DATE_FOR_ANALYSIS.strftime("%B %d, %Y"),
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
        activity.logger.debug(f"Raw LLM response: {repr(response_content)}")
        activity.logger.debug(f"LLM response content: {response_content}")
        activity.logger.debug(f"LLM response type: {type(response_content)}")
        activity.logger.debug(
            f"LLM response length: {len(response_content) if response_content else 'None'}"
        )
    
    except Exception as e:
        activity.logger.error(f"Error in LLM completion: {str(e)}")
        raise

    # Sanitize, parse, and validate the response to ensure it is valid JSON and a valid response in this context
    response_content = sanitize_json_response(response_content)
    activity.logger.debug(f"Sanitized response: {repr(response_content)}")
    parsed_response : dict = parse_json_response(response_content)
    activity.logger.debug(f"Validating Analysis Result: {parsed_response}")
    if not parsed_response:
        exception_message = "LLM response content is empty."
        activity.logger.error(exception_message)
        raise ApplicationError(exception_message)
    if not isinstance(parsed_response, dict):
        activity.logger.error(f"Expected a dictionary for response content, got {type(parsed_response)}")
        raise ApplicationError(f"Expected a dictionary for response content, got {type(parsed_response)}")
    else:
        activity.logger.debug(f"Response content type: {type(parsed_response)}")
        notes = parsed_response.get("additional_notes", "")
        activity.logger.debug(f"Additional Notes: {notes}")
        confidence_score = parsed_response.get("confidence_score", 0.0)
        activity.logger.debug(f"Analysis confidence score: {confidence_score}")
        issues = parsed_response.get("issues", [])
        if not issues:
            activity.logger.info("No issues detected in the orders.")
        else:
            activity.logger.debug(f"Detected issues: {issues}")
            if not isinstance(issues, list):
                activity.logger.error(f"Expected a list for issues, got {type(issues)}")
                raise ApplicationError(f"Expected a list for issues, got {type(issues)}")
            else:
                activity.logger.debug(f"Issues type: {type(issues)}")
                activity.logger.info(f"Number of issues detected: {len(issues)}")
                for order_issue in issues:
                    if not isinstance(order_issue, dict):
                        activity.logger.error(f"Expected a dictionary for issue, got {type(order_issue)}")
                        raise ApplicationError(f"Expected a dictionary for issue, got {type(order_issue)}")
                    else:
                        activity.logger.debug(f"Issue type: {type(order_issue)}")
                        issue_description = order_issue.get("issue", "No description provided.")
                        activity.logger.debug(f"Issue Description: {issue_description}")
                        order_issue_confidence_score = order_issue.get("confidence_score", 0.0)
                        activity.logger.debug(f"Issue Confidence Score: {order_issue_confidence_score}")
                        order_id = order_issue.get("order_id", "Unknown Order ID")
                        activity.logger.debug(f"Order ID: {order_id}")

    return parsed_response

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
        raise ApplicationError(exception_message)
    
    tool_list = get_order_tools()

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
    "a set of orders with key order_id. Orders should have one or more proposed tools to repair the order with key tool_name." \
    "Each tool entry should include tool_arguments for each tool, and " \
    "a confidence_score of how confident you are that the tool will solve the problem. " \
    "Feel free to include additional notes in 'additional_notes' if necessary. " \
    "If there are no proposed tools for repairs, note that in additional_notes. " \
    "Include an overall_confidence_score for the proposed tools indicating confidence that the repairs should be triggered, " \
    "The list of orders to analyze is as follows: " \
    + json.dumps(orders_to_detect_json, indent=2)
    context_instructions = context_instructions  + "\nThe list of issues to repair is as follows: " \
    + json.dumps(input.get("problems_to_repair", []), indent=2) 
    context_instructions = context_instructions  + "\nThe list of tools that can be used to repair the issues is as follows: " \
    + json.dumps(tool_list, indent=2)
    context_instructions = context_instructions  + "\nThe inventory data is as follows: " \
    + json.dumps(inventory_data_json, indent=2)
    activity.logger.debug(f"Context instructions for LLM: {context_instructions}")

    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + DATE_FOR_ANALYSIS.strftime("%B %d, %Y"),
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
        activity.logger.debug(f"Raw LLM response: {repr(response_content)}")
        activity.logger.debug(f"LLM response content: {response_content}")
        activity.logger.debug(f"LLM response type: {type(response_content)}")
        activity.logger.debug(
            f"LLM response length: {len(response_content) if response_content else 'None'}"
        )

        if not response_content:
            exception_message = "LLM response content is empty."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        
        activity.logger.debug(f"Sanitizing response content: {repr(response_content)}")
        response_content = sanitize_json_response(response_content)
        activity.logger.debug(f"Sanitized response: {repr(response_content)}")
        parsed_response: dict = parse_json_response(response_content)

        activity.logger.info(f"Validating Planning Result...")

        #Note: could put this into a data structure
        proposed_tools_for_all_orders = parsed_response.get("proposed_tools", {})
        if not proposed_tools_for_all_orders:
            activity.logger.info("No proposed tools found for repair.")
        else:
            activity.logger.debug(f"Proposed tools for all orders: {proposed_tools_for_all_orders}")
            activity.logger.info(f"Number of orders with proposed tools: {len(proposed_tools_for_all_orders)}")
            for order_id, order in proposed_tools_for_all_orders.items():
                if not isinstance(order, list):
                    activity.logger.error(f"Expected a dictionary for order {order_id}, got {type(list)}")
                    raise ApplicationError(f"Expected a dictionary for order {order_id}, got {type(list)}")
                for tool in order:
                    # confidence_score = tool.get("confidence_score", 0.0)
                    # additional_notes = tool.get("additional_notes", "No additional notes provided.")
                    tool_name = tool.get("tool_name", "Unknown Tool Name")
                    tool_arguments = tool.get("tool_arguments", {})
                    if not tool_name or tool_name == "Unknown Tool Name" or not tool_arguments:
                        activity.logger.error(f"Tool name or arguments missing for tool {tool_name} for order {order_id}: {tool}.")
                        raise ApplicationError(f"Tool name or arguments missing for tool {tool_name} for order {order_id}.")
                    if not isinstance(tool_arguments, dict):
                        activity.logger.error(f"Expected a dictionary for tool arguments for tool {tool_name} for order {order_id}, got {type(tool_arguments)} for {tool}")
                        raise ApplicationError(f"Expected a dictionary for tool arguments for tool {tool_name} for order {order_id}, got {type(tool_arguments)}")
                    activity.logger.debug(f"Tool arguments for tool {tool_name} for order {order_id}: {tool_arguments}")
                    
        activity.logger.info(f"...Planning results valid.")
        return parsed_response
    
    except Exception as e:
        activity.logger.error(f"Error in LLM completion: {str(e)}")
        raise   

async def notify_interested_parties(input: dict) -> dict:
    """ This is a function that notifies interested parties about the repair planning results.
    In a real application it could send notifications via email, SMS, or other channels.
    For this one it fake-emails and can send a signal.
    """
    #todo get callback info from inputs
    notification_info = input.get("notification_info")
    if not notification_info or not isinstance(notification_info, dict):
        activity.logger.warning("No notification info provided, skipping notification.")
        return {
            "notification_status": "Improper notification info provided.",
        }
    if notification_info.get("type", "") == "email":
        #todo fake send email here
        activity.logger.info(f"Sending email to {notification_info.get('email', 'unknown')} with subject: {notification_info.get('subject', 'No Subject')}")
    elif notification_info.get("type", "") == "signal-workflow":
        signal_wf_id = notification_info.get("workflow_id", "agent-workflow")
        signal_name = notification_info.get("name", "add_external_message")
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id=signal_wf_id)
        await handle.signal(signal_name, "REPAIR PLANNING STATUS: ready to review proposed tools for repair. " )
        
    else:
        activity.logger.warning("Unsupported notification type, skipping notification.")
        return {
            "notification_status": "Unsupported interested parties to notify.",
            "notification_details": "Unsupported notification type provided."
        }

    return {
        "notification_status": "Interested parties notified.",
        "notification_details": "This is a placeholder for notification details."
    }

async def repair_some_stuff(input: dict) -> dict:
    """
    This is a an automated helper that repairs problems.
    Note: may want to non-retry some of the data structure errors here because if the data structure isn't right, there's no point in retrying.
    """
    activity.logger.debug(f"Running repair with input: {input}")

    results = {}
    results["repair_tool_details"] = []
    problems_repaired : int = 0
    problems_skipped : int = 0
    proposed_tools_for_all_orders = input.get("planning_result", {}).get("proposed_tools", [])
    if not proposed_tools_for_all_orders:
        activity.logger.info("No proposed tools found for repair.")
        return {"repair_summary": "No proposed tools found for repair."}
    for order_id, order in proposed_tools_for_all_orders.items():
        print(f"*** Repairing order: {order_id} ***")
        if not isinstance(order, list):
            activity.logger.error(f"Expected a dictionary for order, got {type(list)}")
            raise ApplicationError(f"Expected a dictionary for order, got {type(list)}")
        for tool in order:
            activity.heartbeat(f"Repair for order {order_id} in progress...") # heartbeat the activity per tool
            activity.logger.debug(f"Data for tool selected: {tool}")        
            confidence_score = tool.get("confidence_score", 0.0)
            activity.logger.debug(f"Confidence Score: {confidence_score}")
            additional_notes = tool.get("additional_notes", "")
            if additional_notes:
                additional_notes = f"({additional_notes})"
            activity.logger.debug(f"Additional Notes: {additional_notes}")
            tool_name = tool.get("tool_name", "Unknown Tool Name")
            activity.logger.debug(f"Using tool: {tool_name}")
            if confidence_score < 0.5:
                activity.logger.warning(f"Low confidence score for repair: {confidence_score}. Skipping repair for order {order_id}.")
                problems_skipped += 1
                continue
            else:
                print(f"- Executing {tool_name} with confidence score {confidence_score} {additional_notes}")
                tool_arguments = tool.get("tool_arguments", {})
                if not isinstance(tool_arguments, dict):
                    activity.logger.error(f"Expected a dictionary for tool arguments, got {type(tool_arguments)}")
                    raise ApplicationError(f"Expected a dictionary for tool arguments, got {type(tool_arguments)}")
                activity.logger.debug(f"Tool arguments: {tool_arguments}")
                
                tool_function = get_order_tool_function_by_name(tool_name)
                try:
                    tool_result = tool_function(tool_arguments)
                    activity.logger.debug(f"Tool {tool_name} executed with result: {tool_result}")

                except Exception as e:
                    activity.logger.error(f"Error executing tool {tool_name}: {e}")
                    raise ApplicationError(f"Error executing tool {tool_name}: {e}")

                print(f" - Tool {tool_name} executed successfully for order {order_id}!")
                problems_repaired += 1
                results["repair_tool_details"].append({
                    "order_id": order_id,
                    "tool_name": tool_name,
                    "confidence_score": confidence_score,
                    "additional_notes": additional_notes,
                    "tool_arguments": tool_arguments,
                    "tool_result": tool_result
                })

    results["problems_repaired"] = problems_repaired
    results["problems_skipped"] = problems_skipped
    results["repair_summary"] = f"Repair completed successfully: {problems_repaired} problems repaired (with {problems_skipped} skipped)."
    
    activity.logger.info(f"Repair Summary: {results["repair_summary"]}")
    activity.logger.debug(f"Repair details: {results["repair_tool_details"]}")    
    return results

async def report_some_stuff(input: dict) -> dict:
    """
    This is an automated helper agent that reports on the repair.
    
    It uses a Large Language Model (LLM) to prepare a summary of repairs.
    It heartbeats the activity to indicate progress
    It uses input["repair_result"] to get the results of the repair.
    It returns a dictionary response with the report of the repairs:
        - orders repaired and their issues and current status
        - any additional notes
    """    

    # Load the orders data 
    orders_of_interest: dict = input.get("orders_of_interest", [])
    orders_to_detect_json = load_orders_data(orders_of_interest)
    inventory_data_json = load_inventory_data([])

    activity.heartbeat("Orders, repairs, and inventory loaded, reporting in progress...")
    
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    llm_key = os.environ.get("LLM_KEY")
    if not llm_model or not llm_key:
        exception_message = f"LLM model or key not found in environment variables."
        activity.logger.error(exception_message)
        raise ApplicationError(exception_message)
    
    tool_list = get_order_tools()

    # Define the messages for the LLM completion
    context_instructions = "You are a helpful assistant that reports on repairs to orders. " \
    "The orders have been repaired using the tools mentioned in the input. " \
    "Your task is to analyze the provided repair notes, orders, and inventory and create a summary " \
    "of the repairs and their status. " \
    "You will receive a list of orders in JSON format, " \
    "each containing an 'order_id', 'order_date', 'status', 'items', and 'quantities'. " \
    "You will also receive a list of repair notes that detail the repairs made to each order. " \
    "Ensure your response is valid JSON and does not contain any markdown formatting. " \
    "The response should be a JSON object with a key 'repair_report' that contains " \
    "a summary of the repairs made as 'report_summary', " \
    "a summary of order health as 'order_summary', and " \
    "a repairs_sufficient_confidence_score of how confident you are that repairs are sufficient and orders are in a good status. " \
    "Feel free to include additional notes in 'additional_notes' if necessary. " \
    "The list of orders to analyze is as follows: " \
    + json.dumps(orders_to_detect_json, indent=2)
    context_instructions = context_instructions  + "\nThe results of repairs are as follows: " \
    + json.dumps(input.get("repair_result", []), indent=2) 
    context_instructions = context_instructions  + "\nThe inventory data is as follows: " \
    + json.dumps(inventory_data_json, indent=2)
    activity.logger.debug(f"Context instructions for LLM: {context_instructions}")

    messages = [
        {
            "role": "system",
            "content": context_instructions
            + ". The current date is "
            + DATE_FOR_ANALYSIS.strftime("%B %d, %Y"),
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
        activity.logger.debug(f"Raw LLM response: {repr(response_content)}")
        activity.logger.debug(f"LLM response content: {response_content}")
        activity.logger.debug(f"LLM response type: {type(response_content)}")
        activity.logger.debug(
            f"LLM response length: {len(response_content) if response_content else 'None'}"
        )

        if not response_content:
            exception_message = "LLM response content is empty."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        
        activity.logger.debug(f"Sanitizing response content: {repr(response_content)}")
        response_content = sanitize_json_response(response_content)
        activity.logger.debug(f"Sanitized response: {repr(response_content)}")
        parsed_response: dict = parse_json_response(response_content)

        activity.logger.info(f"Validating Reporting Result...")

        #Note: could put this into a data structure
        report_results = parsed_response.get("repair_report", {})
        if not report_results:
            activity.logger.info("No repair report found.")
            return {"report": "No repair report found."}
        activity.logger.debug(f"Repair report results: {report_results}")
        activity.logger.info(f"Number of orders in repair report: {len(report_results)}")
        if not isinstance(report_results, dict):
            activity.logger.error(f"Expected a dictionary for repair report results, got {type(report_results)}")
            raise ApplicationError(f"Expected a dictionary for repair report results, got {type(report_results)}")
        else:
            activity.logger.debug(f"Repair report results type: {type(report_results)}")
        report_summary = report_results.get("report_summary", "No summary provided.")
        activity.logger.debug(f"Report Summary: {report_summary}")
        order_summary = report_results.get("order_summary", {})
        if not order_summary:
            activity.logger.info("No order summary found in repair report.")
        else:
            activity.logger.debug(f"Order summary: {order_summary}")
            if not isinstance(order_summary, dict):
                activity.logger.error(f"Expected a dictionary for order summary, got {type(order_summary)}")
                raise ApplicationError(f"Expected a dictionary for order summary, got {type(order_summary)}")
            else:
                activity.logger.debug(f"Order summary type: {type(order_summary)}")
        repairs_sufficient_confidence_score = report_results.get("repairs_sufficient_confidence_score", 0.0)
        activity.logger.debug(f"Repairs sufficient confidence score: {repairs_sufficient_confidence_score}")
        additional_notes = report_results.get("additional_notes", "")
        if additional_notes:
            additional_notes = f"({additional_notes})"
        activity.logger.debug(f"Additional Notes: {additional_notes}")

        activity.logger.info(f"...Reporting results valid.")
        return report_results
    
    except Exception as e:
        activity.logger.error(f"Error in LLM completion: {str(e)}")
        raise   

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
    
def get_order_tools() -> dict:
    """
    Returns a registry of available tools for the repair agent.
    This can be used to dynamically load tools based on the context.
    """
    # Define the tools
    # Note: could load these from a config file, build them from a registry, or use MCP
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
    return tool_list

def get_order_tool_function_map() -> dict:
    """
    Returns a mapping of tool names to their corresponding functions.
    This can be used to dynamically call tools based on the context.
    """
    return {
        "request_approval_tool": request_approval_tool,
        "order_inventory_tool": order_inventory_tool,
        "request_payment_update_tool": request_payment_update_tool,
    }

def get_order_tool_function_by_name(tool_name: str) -> Callable[[dict], dict]:
    """
    Returns the function corresponding to the given tool name.
    Raises an ApplicationError if the tool name is not found.
    """
    tool_function_map = get_order_tool_function_map()
    if tool_name not in tool_function_map:
        exception_message = f"Tool {tool_name} not found in tool function map."
        activity.logger.error(exception_message)
        raise ApplicationError(exception_message)
    
    return tool_function_map[tool_name]

def request_approval_tool(inputs: dict) -> dict:
    """
    Mock tool to request approval for an order.
    This simulates the process of requesting approval for an order.
    """
    approver = inputs.get("approver")
    approval_request_contents = inputs.get("approval_request_contents", "Please approve this order.")
    order_id = inputs.get("order_id", "unknown_order_id")
    print(f"Requesting approval from [{approver}] for order [{order_id}]:")
    
    # Simulate a successful approval request
    print(f"Sent Approval Request:")
    print(f" - To: {approver}")
    print(f" - Subject Approval Request for order {order_id}")
    print(f" - Contents: {approval_request_contents}")

    print(f"### MAGICAL APPROVER AUTOWAND ENGAGED ###")
    print(f"### RESPOONSE: APPROVER AUTOWAND APPROVED ###")
    with open(Path(__file__).resolve().parent / "data" / "orders.json", "r") as orders_file:
        orders_data = json.load(orders_file)
        orders = orders_data.get("orders", [])
        if not orders:
            exception_message = "No orders found in orders data."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        # Find the order to update
        for order in orders:
            if order["order_id"] == order_id:
                order["status"] = "approved-preparing-shipment"
                break
    with open(Path(__file__).resolve().parent / "data" / "orders.json", "w") as orders_file:
        json.dump(orders_data, orders_file, indent=2)
    
    return {"status": "success", "message": f"Approval request sent to {approver} for order {order_id}."}

def order_inventory_tool(inputs: dict) -> dict:
    """
    Mock tool to order more inventory.
    This simulates the process of ordering more inventory for an order.
    Could make it idempotent to add reliability, or just leave it as is for funny magical effects.
    It will update the inventory in the inventory.json file.
    """
    inventory_to_order: str = inputs.get("inventory_to_order", "unknown_item_id")
    inventory_description: str = inputs.get("inventory_description", "No description provided.")
    quantity: int = inputs.get("quantity", 1)
    order_id: str = inputs.get("order_id", "unknown_order_id")
    print(f"Ordering more inventory for order [{order_id}]:")
    print(f" - Item: {inventory_to_order}")
    print(f" - Description: {inventory_description}")
    print(f" - Quantity: {quantity}")
    
    # Simulate a delay for the inventory ordering process
    print("### INSTY-WIZ HIPPOGRIFF RESTOCK DELIVERY SERVICE ENGAGED ###")

    inventory_file_path = Path(__file__).resolve().parent / "data" / "inventory.json"
    if not inventory_file_path.exists():
        exception_message = f"Inventory data file not found at {inventory_file_path}"
        activity.logger.error(exception_message)
        raise ApplicationError(exception_message)
    with open(inventory_file_path, "r") as inventory_file:
        inventory_data = json.load(inventory_file)
        inventory = inventory_data.get("inventory", [])
        # Find the inventory item to update
        for item in inventory:
            if item["item_id"] == inventory_to_order:
                # Update the inventory quantity
                item["current_stock"] += quantity
                item["available_stock"] += quantity
                item["last_ordered"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f" - Updated inventory for item {inventory_to_order}: {item['current_stock']} in stock.")
                break
    
    print("### INSTY-WIZ HIPPOGRIFF RESTOCK COMPLETED! ###")

    # Write the updated inventory data back to the file
    with open(inventory_file_path, "w") as inventory_file:
        json.dump(inventory_data, inventory_file, indent=2)

    print(f"### WIZZO-SHIP RUSH ORDER OWL DELIVERY ENGAGED  ###")
    print(f"### WIZZO-SHIP OWL COMPLETED DELIVERY ###")
    with open(Path(__file__).resolve().parent / "data" / "orders.json", "r") as orders_file:
        orders_data = json.load(orders_file)        
        orders = orders_data.get("orders", [])
        if not orders:
            exception_message = "No orders found in orders data."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        for order in orders:
            if order["order_id"] == order_id:
                order["status"] = "completed"
                break
    with open(Path(__file__).resolve().parent / "data" / "orders.json", "w") as orders_file:
        json.dump(orders_data, orders_file, indent=2)
    
    return {"status": "success", "message": f"Inventory ordered and order completed successfully for order {order_id}."}

def request_payment_update_tool(inputs: dict) -> dict:
    """
    Mock tool to request payment update for an order.
    This simulates the process of requesting a payment update for an order.
    """
    customer_name: str = inputs.get("customer_name", "Unknown Customer")
    customer_id: str = inputs.get("customer_id", "unknown_customer_id")
    original_payment_method: str = inputs.get("original_payment_method", "Unknown Payment Method")
    additional_notes: str = inputs.get("additional_notes", "No additional notes provided.")
    order_id: str = inputs.get("order_id", "unknown_order_id")
    
    print(f"Requesting payment update for order [{order_id}]:")
    print(f" - Customer Name: {customer_name}")
    print(f" - Customer ID: {customer_id}")
    print(f" - Original Payment Method: {original_payment_method}")
    print(f" - Additional Notes: {additional_notes}")

    
    # Simulate a successful payment update request
    print(f"Sent Payment Update Request:")
    print(f" - To: {customer_name} ({customer_id})")
    print(f" - Subject: Payment Update Request for Order {order_id}")
    print(f" - Contents: Please update your payment method for order {order_id}.")

    print(f"### MAGICAL PAYMENT UPDATE REQUEST ENGAGED ###")
    print(f"### RESPOONSE: PAYMENT UPDATE REQUEST SENT ###")

    with open(Path(__file__).resolve().parent / "data" / "orders.json", "r") as orders_file:
        orders_data = json.load(orders_file)
        orders = orders_data.get("orders", [])
        if not orders:
            exception_message = "No orders found in orders data."
            activity.logger.error(exception_message)
            raise ApplicationError(exception_message)
        for order in orders:
            if order["order_id"] == order_id:
                order["status"] = "payment_update_requested"
                break
    with open(Path(__file__).resolve().parent / "data" / "orders.json", "w") as orders_file:
        json.dump(orders_data, orders_file, indent=2)
    
    return {"status": "success", "message": f"Payment update request sent to {customer_name} for order {order_id}."}