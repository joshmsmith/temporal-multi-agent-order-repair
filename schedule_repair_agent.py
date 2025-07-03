import asyncio
from datetime import timedelta
import os

from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client

from workflows import RepairAgentWorkflow
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleState,
    ScheduleAsyncIterator,
)
from workflows import RepairAgentWorkflow
from dotenv import load_dotenv

import argparse
from temporalio.client import WorkflowExecutionAsyncIterator

SCHEDULE_ID = "Repair-Agent-Daily-Schedule"
parser = argparse.ArgumentParser(description="Schedule a repair agent workflow.")
parser.add_argument(
    "--operation",
    type=str,
    default="create",
    help="Optional operations to perform related to schedules.",
)
args = parser.parse_args() 

async def main(operation: str) -> None:
    """Schedule the repair agent workflow to run daily."""
    # Load environment variables
    load_dotenv(override=True)
    user = os.environ.get("USER_NAME", "Harry.Potter") 
    print(f"Using user: {user}")
    # Create client connected to server at the given address
    client: Client = await get_temporal_client()

    workflow_id = f"scheduled-repair-{user}"
    
    
    if operation == "list":
        await list_schedules(client)
    elif operation == "delete":
        await delete_schedule(client, SCHEDULE_ID)
    elif operation == "describe":
        await describe_schedule(client, SCHEDULE_ID)
    elif operation == "trigger":
        await trigger_schedule(user, client)
    elif operation == "upsert":
        await upsert_schedule(user, client, workflow_id, SCHEDULE_ID)
    elif operation == "create":
        await create_schedule(user, client, workflow_id, SCHEDULE_ID)
    else:
        await create_schedule(user, client, workflow_id, SCHEDULE_ID) # for now create is the default operation

async def trigger_schedule(user, client):
    handle = client.get_schedule_handle(SCHEDULE_ID)
    await handle.trigger()
    print(f"Triggered schedule {SCHEDULE_ID} for user {user}.")

async def upsert_schedule(user, client, workflow_id, schedule_id=SCHEDULE_ID):

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.describe()
        print(f"Schedule {schedule_id} already exists.")
        # If the schedule exists, we can update it, for now i leave as is
    except Exception as e:
        print(f"Schedule {schedule_id} does not exist. Creating a new one.")

        await create_schedule(user, client, workflow_id, schedule_id)

async def create_schedule(user, client, workflow_id, schedule_id=SCHEDULE_ID):
    start_msg = {
        "prompt": "Analyze and repair the orders in the order system.",
        "metadata": {
            "user": user,  
            "system": "temporal-repair-agent",
        },
    }

    await client.create_schedule(
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                RepairAgentWorkflow.run,
                start_msg,
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(days=1))]
            ),
            state=ScheduleState(note="Daily repair agent workflow scheduled by user " + user),
        ),
    )
    print(f"Schedule created with ID: {schedule_id} for user {user}.")

async def list_schedules(client: Client):
    """List all schedules in our namespace."""
    await client.list_schedules()
    async for schedule in await client.list_schedules():
        print(f"List Schedule Info: {schedule.info}.")


async def delete_schedule(client: Client, schedule_id: str):
    """Delete a schedule by ID."""
    handle = client.get_schedule_handle(
        schedule_id,
    )
    await handle.delete()
    print(f"Schedule {schedule_id} deleted.")

async def describe_schedule(client: Client, schedule_id: str):
    """Describe a schedule by ID."""
    handle = client.get_schedule_handle(
        schedule_id
    )
    desc = await handle.describe()
    print(f"Schedule Description: {desc.info}.")

if __name__ == "__main__":
    asyncio.run(main(args.operation))
