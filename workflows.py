import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from activities import analyze, detect, plan_repair, repair, report


def _parse_due_date(due: str) -> datetime:
    if due.endswith("Z"):
        due = due[:-1] + "+00:00"
    return datetime.fromisoformat(due)



# todo: add workflow for analyze/repair/report 
# todo: just an activity (+workflow to run it)
# todo: run once as a tool and report results
# todo run as a long-running tool with a loop
# todo: run as a long-running tool with a signal to callback
# todo add workflow starters for various types
# todo hook up to MCP server

#TODO: add a workflow that runs a single tool as an update operation to repair one order's problems

#TODO: add a workflow that runs daily and detects problems in the system, analyzes them, optionally repairs - use schedules

#TODO: add a workflow that runs all the time and sleeps for a day, then  detects problems in the system, analyzes them, optionally repairs

#TODO: add a workflow that is an agent itself, with a goal and tools, does tool planning

#TODO: explain automation agents vs conversational (assistive) agents, and how they can be used together

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
        self.planned: bool = False
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
    async def IsRepairPlanned(self) -> bool:
        if self.planned is None:
            raise ApplicationError("Repair approval status is not set yet.")
        return self.planned
    
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
    
    @workflow.query
    async def GetRepairPlanningResult(self) -> dict:
        if "planning_result" not in self.context:
            raise ApplicationError("Planning result is not available yet.")
        return self.context["planning_result"]

    @workflow.query
    async def GetRepairToolResults(self) -> str:
        if "repair_result" not in self.context:
            raise ApplicationError("Repair Tool Execution results are not available yet.")
        return self.context["repair_result"]
    
    @workflow.query
    async def GetRepairReport(self) -> str:
        if "report_result" not in self.context:
            raise ApplicationError("Repair results are not available yet.")
        return self.context["report_result"]

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        workflow.logger.debug(f"Starting repair workflow with inputs: {inputs}")

        # Execute the detection agent
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
        workflow.logger.debug(f"Detection result: {self.context["detection_result"]}")

        detection_confidence_score = self.context["detection_result"].get("confidence_score", 0.0)
        if detection_confidence_score < 0.5:
            analysis_notes = self.context["detection_result"].get("additional_notes", "")
            workflow.logger.info(f"Low confidence score from detection: {detection_confidence_score} ({analysis_notes}). No repair needed.")
            self.status = "NO-REPAIR-NEEDED"
            return f"No repair needed based on detection result: confidence score for repair: {detection_confidence_score} ({analysis_notes})"
        
        #execute the analysis agent
        self.status = "ANALYZING-PROBLEMS"                
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
        workflow.logger.debug(f"Analysis result: {self.context["analysis_result"]}")

        # If the analysis result indicates a need for repair, proceed with planning
        self.context["problems_to_repair"] = self.context["analysis_result"]
        
        # Execute the planning agent
        self.status = "PLANNING-REPAIR"                
        self.context["planning_result"] = await workflow.execute_activity(
            plan_repair,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),  
            ),
            heartbeat_timeout=timedelta(seconds=30),
        )
        workflow.logger.debug(f"Planning result: {self.context["planning_result"]}")
        self.planned = True

        # Wait for the approval or reject signal
        self.status = "PENDING-APPROVAL"
        workflow.logger.info(f"Waiting for approval for repair")
        await workflow.wait_condition(
            lambda: self.approved is not False or self.rejected is not False,
            timeout=timedelta(days=5),
        )

        if self.rejected:
            workflow.logger.info(f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}")
            self.status = "REJECTED"
            return f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}"
        
        self.status = "APPROVED"
        workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")

        # Proceed with the repair agent
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
        workflow.logger.debug(f"Repair result: {self.context["repair_result"]}")

        # Proceed with the report agent
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
        self.status = "REPORT-COMPLETED"
        workflow.logger.debug(f"Report result: {self.context["report_result"]}")   
        report_summary = self.context["report_result"].get("report_summary", "No summary available")
        
        return f"Repair workflow completed with status: {self.status}. Report Summary: {report_summary}"
