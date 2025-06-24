from asyncio import sleep
import os
import random
from temporalio import activity
from dotenv import load_dotenv
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
async def detect(input: dict) -> str:
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
async def detect_some_stuff(input: dict) -> str:
    """
    This  is a an automated helper agent that detects problems.
    """
    #llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    #llm_key = os.environ.get("LLM_KEY")


    
    activity.heartbeat("Detection in progress...")
    
    return "Detection completed successfully: found 75 problems."

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