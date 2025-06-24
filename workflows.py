from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

from activities import report, repair, analyze, detect


def _parse_due_date(due: str) -> datetime:
    if due.endswith("Z"):
        due = due[:-1] + "+00:00"
    return datetime.fromisoformat(due)



# todo: add workflow for analyze/repair/report 
#todo: just an activity (+workflow to run it)
# todo: run once as a tool and report results
# todo run as a long-running tool with a loop
# todo: run as a long-running tool with a signal to callback
#todo add workflow starters for various types
# todo hook up to MCP server
# todo make fake data for testing


'''RepairAgentWorkflow: 
This is a Temporal Workflow that orchestrates repairs.
It will analyze the system, repair it, and report the results.
It will wait for approval before proceeding with the repair.
It will also allow for rejection of the repair.
Tools are static Activities that implement automated helper agents.'''
@workflow.defn
class RepairAgentWorkflow:
    def __init__(self) -> None:
        self.approved: bool = False
        self.rejected: bool = False
        self.status: str = "INITIALIZING"
        self.context: dict = {}

    @workflow.signal
    async def ApproveRepair(self, approver: str) -> None:
        self.approved = True
        self.context["approved_by"] = approver

    @workflow.signal
    async def RejectRepair(self, rejecter: str) -> None:
        self.rejected = True
        self.context["rejected_by"] = rejecter

    @workflow.query
    async def IsRepairApproved(self) -> bool:
        if self.approved is None:
            raise ApplicationError("Repair approval status is not set yet.")
        return self.approved
    
    @workflow.query
    async def GetRepairStatus(self) -> str:
        return self.status
    
    @workflow.query
    async def GetRepairContext(self) -> dict:
        return self.context
    
    @workflow.query
    async def GetRepairContextValue(self, key: str) -> str:
        if key not in self.context:
            raise ApplicationError(f"Context key '{key}' not found.")
        return self.context[key]
    
    @workflow.query
    async def GetRepairContextKeys(self) -> List[str]:
        return list(self.context.keys())
    
    @workflow.query
    async def GetRepairAnalysisResult(self) -> str:
        if "analysis_result" not in self.context:
            raise ApplicationError("Analysis result is not available yet.")
        return self.context["analysis_result"]
    
    @workflow.query
    async def GetRepairDetectionResult(self) -> str:
        if "detection_result" not in self.context:
            raise ApplicationError("Detection result is not available yet.")
        return self.context["detection_result"]

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        workflow.logger.info(f"Starting repair workflow with inputs: {inputs}")

        #TODO detect any problems before analysis
        self.status = "DETECTING-PROBLEMS"
        workflow.logger.info("Detecting problems in the system")
        self.context["detection_result"] = await workflow.execute_activity(
            detect,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),  
            ),
            heartbeat_timeout=timedelta(seconds=10),
        )
        workflow.logger.info(f"Detection result: {self.context["detection_result"]}")


        self.status = "ANALYZING"
                
        self.context["analysis_result"] = await workflow.execute_activity(
            analyze,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),  
            ),
            heartbeat_timeout=timedelta(seconds=10),
        )
        workflow.logger.info(f"Analysis result: {self.context["analysis_result"]}")

        self.status = "PENDING-APPROVAL"
        workflow.logger.info(f"Waiting for approval for repair")
        # Wait for the approval or reject signal

        await workflow.wait_condition(
            lambda: self.approved is not False or self.rejected is not False,
            timeout=timedelta(days=5),
        )

        if self.rejected:
            workflow.logger.warning(f"REJECTED by user {self.context.get('rejected_by', 'unknown')}")
            self.status = "REJECTED"
            return f"REJECTED by user {self.context.get('rejected_by', 'unknown')}"
        
        self.status = "APPROVED"
        workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")

        # Proceed with the repair activity
        self.status = "PENDING-REPAIR"
        self.context["repair_result"] = await workflow.execute_activity(
            repair,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
            ),
            heartbeat_timeout=timedelta(seconds=10),
        )
        workflow.logger.info(f"Repair result: {self.context["repair_result"]}")

        # Proceed with the repair activity
        self.status = "PENDING-REPORT"
        self.context["report_result"] = await workflow.execute_activity(
            report,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
            ),
            heartbeat_timeout=timedelta(seconds=10),
        )
        workflow.logger.info(f"Report result: {self.context["report_result"]}")     

        
        return self.status
