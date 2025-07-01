import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from activities import analyze, detect, plan_repair, notify, repair, report




ITERATIONS_BEFORE_CONTINUE_AS_NEW = 10  # Number of iterations before exiting the workflow

#TODO: add a workflow that runs a single tool as an update operation to repair one order's problems
#TODO: add a workflow that runs daily and detects problems in the system, analyzes them, optionally repairs - use schedules


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
        if approver is None or approver == "":
            approver = self.context.get("metadata", {}).get("user", "unknown")
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
    async def GetRepairAnalysisResult(self) -> dict:
        if "analysis_result" not in self.context:
            raise ApplicationError("Analysis result is not available yet.")
        return self.context["analysis_result"]
    
    @workflow.query
    async def GetRepairDetectionResult(self) -> dict:
        if "detection_result" not in self.context:
            raise ApplicationError("Detection result is not available yet.")
        return self.context["detection_result"]
    
    @workflow.query
    async def GetRepairPlanningResult(self) -> dict:
        if "planning_result" not in self.context:
            raise ApplicationError("Planning result is not available yet.")
        return self.context["planning_result"]

    @workflow.query
    async def GetRepairToolResults(self) -> dict:
        if "repair_result" not in self.context:
            raise ApplicationError("Repair Tool Execution results are not available yet.")
        return self.context["repair_result"]
    
    @workflow.query
    async def GetRepairReport(self) -> dict:
        if "report_result" not in self.context:
            raise ApplicationError("Repair results are not available yet.")
        return self.context["report_result"]

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        workflow.logger.debug(f"Starting repair workflow with inputs: {inputs}")

        # Execute the detection agent
        set_workflow_status(self, "DETECTING-PROBLEMS")
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
            set_workflow_status(self, "NO-REPAIR-NEEDED")
            return f"No repair needed based on detection result: confidence score for repair: {detection_confidence_score} ({analysis_notes})"
        
        #execute the analysis agent
        set_workflow_status(self, "ANALYZING-PROBLEMS")
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
        set_workflow_status(self, "PLANNING-REPAIR")
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
        set_workflow_status(self, "PENDING-APPROVAL")
        workflow.logger.info(f"Waiting for approval for repair")
        await workflow.wait_condition(
            lambda: self.approved is not False or self.rejected is not False,
            timeout=timedelta(days=5),
        )

        if self.rejected:
            workflow.logger.info(f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}")
            set_workflow_status(self, "REJECTED")
            return f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}"
        
        set_workflow_status(self, "APPROVED")
        workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")

        # Proceed with the repair agent
        set_workflow_status(self, "PENDING-REPAIR")
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
        set_workflow_status(self, "PENDING-REPORT")
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
        set_workflow_status(self, "REPORT-COMPLETED")
        workflow.logger.debug(f"Report result: {self.context["report_result"]}")   
        report_summary = self.context["report_result"].get("report_summary", "No summary available")
        
        return f"Repair workflow completed with status: {self.status}. Report Summary: {report_summary}"

'''RepairAgentWorkflow: 
This is a Temporal Workflow that orchestrates repairs.
It runs periodically to detect and repair problems in the system.
It will analyze the system, repair it, and report the results.
It will wait for approval before proceeding with the repair.
It will also allow for rejection of the repair.
Tools are static Activities that implement automated helper agents.'''
@workflow.defn
class RepairAgentWorkflowProactive:
    def __init__(self) -> None:
        self.approved: bool = False
        self.rejected: bool = False
        self.planned: bool = False
        self.status: str = "INITIALIZING"
        self.context: dict = {}
        self.exit_requested: bool = False
        self.continue_as_new_requested: bool = False
        self.iteration_count: int = 0
        self.stop_waiting: bool = False

    @workflow.signal
    async def ApproveRepair(self, approver: str) -> None:
        self.approved = True
        self.context["approved_by"] = approver

    @workflow.signal
    async def RequestExit(self) -> None:
        self.exit_requested = True

    @workflow.signal
    async def StopWaiting(self) -> None:
        self.stop_waiting = True

    @workflow.query
    async def GetIterationCount(self) -> int:
        return self.iteration_count
    
    @workflow.signal
    async def RequestContinueAsNew(self) -> None:
        self.continue_as_new_requested = True

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
    async def GetRepairAnalysisResult(self) -> dict:
        if "analysis_result" not in self.context:
            raise ApplicationError("Analysis result is not available yet.")
        return self.context["analysis_result"]
    
    @workflow.query
    async def GetRepairDetectionResult(self) -> dict:
        if "detection_result" not in self.context:
            raise ApplicationError("Detection result is not available yet.")
        return self.context["detection_result"]
    
    @workflow.query
    async def GetRepairPlanningResult(self) -> dict:
        if "planning_result" not in self.context:
            raise ApplicationError("Planning result is not available yet.")
        return self.context["planning_result"]

    @workflow.query
    async def GetRepairToolResults(self) -> dict:
        if "repair_result" not in self.context:
            raise ApplicationError("Repair Tool Execution results are not available yet.")
        return self.context["repair_result"]
    
    @workflow.query
    async def GetRepairReport(self) -> dict:
        if "report_result" not in self.context:
            raise ApplicationError("Repair results are not available yet.")
        return self.context["report_result"]

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        self.context["notification_info"] = inputs.get("callback", None)
        workflow.logger.debug(f"Starting repair workflow with inputs: {inputs}")

        while not self.exit_requested and not self.continue_as_new_requested and self.iteration_count < ITERATIONS_BEFORE_CONTINUE_AS_NEW:
            self.iteration_count += 1
            # Execute the detection agent
            self.approved = False
            
            set_workflow_status(self, "DETECTING-PROBLEMS")
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
                set_workflow_status(self, "NO-REPAIR-NEEDED")
                return f"No repair needed based on detection result: confidence score for repair: {detection_confidence_score} ({analysis_notes})"
            
            #execute the analysis agent
            set_workflow_status(self, "ANALYZING-PROBLEMS")           
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
            set_workflow_status(self, "PLANNING-REPAIR")
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

            # Notify the user about the planned repairs
            await workflow.execute_activity(
                notify, 
                self.context,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),  
                ),
                heartbeat_timeout=timedelta(seconds=30),
            )

            # Wait for the approval or reject signal
            set_workflow_status(self, "PENDING-APPROVAL")
            workflow.logger.info(f"Waiting for approval for repair")
            await workflow.wait_condition(
                lambda: self.approved is not False or self.rejected is not False,
                timeout=timedelta(hours=24),  # Wait for up to 24 hours for approval
            )

            if self.rejected:
                workflow.logger.info(f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}")
                set_workflow_status(self, "REJECTED")
                return f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}"
            
            set_workflow_status(self, "APPROVED")
            workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")

            # Proceed with the repair agent
            set_workflow_status(self, "PENDING-REPAIR")
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
            set_workflow_status(self, "PENDING-REPORT")
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
            set_workflow_status(self, "REPORT-COMPLETED")
            workflow.logger.debug(f"Report result: {self.context["report_result"]}")   
            report_summary = self.context["report_result"].get("report_summary", "No summary available")
            workflow.logger.info(f"Repair completed with status: {self.status}. Report Summary: {report_summary}") 
            
            set_workflow_status(self, "WAITING-FOR-NEXT-CYCLE")
            await workflow.wait_condition(
                lambda: self.exit_requested is True or 
                        self.continue_as_new_requested is True or
                        self.stop_waiting is True,
                timeout=timedelta(days=1), # Wait a day for the next detect->analysis->repair cycle. 
                                           # Could make this a dynamic timer if you wanted to always run at a certain time
            )
            self.stop_waiting = False
            
        if self.exit_requested:
            workflow.logger.info("Exit requested. Ending workflow.")
            return "Repair workflow exited as requested."
        
        if self.continue_as_new_requested or self.iteration_count >= ITERATIONS_BEFORE_CONTINUE_AS_NEW:
            workflow.logger.info("Continuing as new-")
            # Continue as new workflow
            workflow.continue_as_new(
                inputs,
            )
            await workflow.wait_condition(lambda: workflow.all_handlers_finished())
        return "Repair workflow continued as new with status: WAITING-FOR-NEXT-CYCLE."

# workflow helper functions
def set_workflow_status(self, status: str) -> None: 
    """Set the current status of the workflow."""
    self.status = status
    details : str
    # set workflow current details in Markdown format. Include status, iteration count, and timestamp.
    details = f"## Workflow Status \n\n" \
              f"- **Phase:** {status}\n" \
              f"- **Iteration:** {self.iteration_count}\n" \
              f"- **Last Status Set:** {workflow.now().isoformat()}\n"
    workflow.set_current_details(details)
    workflow.logger.debug(f"Workflow status set to: {status}")