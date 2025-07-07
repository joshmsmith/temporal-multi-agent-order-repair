import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from dotenv import load_dotenv

import os

import activities
from workflows import RepairAgentWorkflow, RepairAgentWorkflowProactive
from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client




async def main() -> None:
    
    # Load environment variables
    load_dotenv(override=True)

    # Print LLM configuration info
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4")
    print(f"Using LLM Model: {llm_model}")
    
    logging.basicConfig(level=logging.INFO)

    
    try:
        await run_worker()
    finally:
        # Cleanup MCP connections when worker shuts down
        # await mcp_client_manager.cleanup()
        print(f"Cleanup Placeholder")


async def run_worker() -> None:
    # Get a client and init the list of activities
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[RepairAgentWorkflow, RepairAgentWorkflowProactive],
        activities=[activities.single_tool_repair, 
                    activities.detect,
                    activities.analyze, 
                    activities.plan_repair,
                    activities.notify,
                    activities.execute_repairs, 
                    activities.report],
    )
    print(f"Starting worker...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
