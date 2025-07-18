import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from activities import analyze, detect, plan_repair, notify, execute_repairs, report, single_tool_repair, process_order

ITERATIONS_BEFORE_CONTINUE_AS_NEW = 10  # Number of iterations before exiting the workflow

'''RepairAgentWorkflow: 
This is an agent implemented as a Temporal Workflow that orchestrates repairs.
Key logic is in the planning activity.
It will analyze the system, repair it, and report the results.
It will wait for approval before proceeding with the repair.
It will also allow for rejection of the repair.
Tools are static Activities that implement automated helper agents.
It can be used as a long-running interactive tool-agent via MCP or as a standalone workflow.'''
@workflow.defn
class RepairAgentWorkflow:
    def __init__(self) -> None:
        self.approved: bool = False
        self.rejected: bool = False
        self.planned: bool = False
        self.status: str = "INITIALIZING"
        self.context: dict = {}

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        workflow.logger.debug(f"Starting repair workflow with inputs: {inputs}")

        # Execute the detection agent
        self.problems_found_confidence_score = await self.perform_detection(self.context)

        # if confidence is low, no need to repair
        if self.problems_found_confidence_score < 0.5:
            analysis_notes = self.context["detection_result"].get("additional_notes", "")
            workflow.logger.info(f"Low confidence score from detection: {self.problems_found_confidence_score} ({analysis_notes}). No repair needed.")
            self.set_workflow_status("NO-REPAIR-NEEDED")
            return f"No repair needed based on detection result: confidence score for repair: {self.problems_found_confidence_score} ({analysis_notes})"
        
        #execute the analysis agent
        await self.analyze_problems(self.context)
        
        # Execute the planning for this agent
        await self.create_plan(self.context)

        # Wait for the approval or reject signal
        self.set_workflow_status("PENDING-APPROVAL")
        workflow.logger.info(f"Waiting for approval for repair")
        await workflow.wait_condition(
            lambda: self.approved is not False or self.rejected is not False,
            timeout=timedelta(hours=12),
        )

        if self.rejected:
            workflow.logger.info(f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}")
            self.set_workflow_status("REJECTED")
            return f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}"
        
        self.set_workflow_status("APPROVED")
        workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")

        # Proceed with the repair
        await self.execute_repair()

        # Create the report with the report agent
        report_summary = await self.generate_report()
        
        return f"Repair workflow completed with status: {self.status}. Report Summary: {report_summary}"


    # workflow helper functions
    def set_workflow_status(self, status: str) -> None: 
        """Set the current status of the workflow."""
        self.status = status
        # set workflow current details in Markdown format. Include status, iteration count, and timestamp.
        details: str = f"## Workflow Status \n\n" \
                    f"- **Phase:** {status}\n" 
        if hasattr(self, 'iteration_count'):
                details += f"- **Iteration:** {self.iteration_count}\n"
        details += f"- **Last Status Set:** {workflow.now().isoformat()}\n"
        if status == "REPORT-COMPLETED":
            details += f"- **Repairs Complete:** \n"
            details += f"- **Report Summary:** {self.context.get('report_result', {}).get('repairs_summary', 'No summary available')}\n"
            details += f"- See [Repairs Report](file://pathto/directory/tool_execution_report.md)\n"
        elif self.planned:
            details += f"- **Repair Planned:** {self.planned}\n"
            details += f"- See [Planned Repairs](file://pathto/directory/planning_report.md)\n"
        workflow.set_current_details(details)
        workflow.logger.debug(f"Workflow status set to: {status}")


    async def perform_detection(self, context: dict) -> float:
        """Detect problems in the system.
        This function executes the detect activity and updates the context with the detection result.
        It returns a confidence score indicating the likelihood of problems being present."""
        self.set_workflow_status("DETECTING-PROBLEMS")
        workflow.logger.info("Detecting problems in the system")
        context["detection_result"] = await workflow.execute_activity(
            detect,
            context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),  
            ),
            heartbeat_timeout=timedelta(seconds=20),
        )
        workflow.logger.debug(f"Detection result: {context["detection_result"]}")

        detection_confidence_score = context["detection_result"].get("confidence_score", 0.0)
        return detection_confidence_score

    async def analyze_problems(self: any, context: dict) -> None:
            """Analyze the problems detected in the system.
            This function executes the analyze activity and updates the context with the analysis result.
            """
            self.set_workflow_status( "ANALYZING-PROBLEMS")        
            
            context["analysis_result"] = await workflow.execute_activity(
                analyze,
                context,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=30),  
                ),
                heartbeat_timeout=timedelta(seconds=20),
            )
            workflow.logger.debug(f"Analysis result: {context["analysis_result"]}")

            # If the analysis result indicates a need for repair, proceed with planning
            context["problems_to_repair"] = context["analysis_result"]

    async def create_plan(self, context: dict) -> None:
            """Create a plan for repairing the detected problems. 
            This function executes the plan_repair activity and updates the context with the planning result.
            Once approved, planned repairs are executed in the repair step."""
            self.set_workflow_status("PLANNING-REPAIR")
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
            self.planning_confidence_score = self.context.get("planning_result", {}).get("overall_confidence_score", 0.0)

    async def execute_repair(self):
        """Execute the repair based on the planned repairs.
        These are approved in the workflow via a signal.
        This function executes the repair activity and updates the context with the repair result.
        """
        self.set_workflow_status("PENDING-REPAIR")
        self.context["repair_result"] = await workflow.execute_activity(
            execute_repairs,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
            ),
            heartbeat_timeout=timedelta(seconds=20),
        )
        workflow.logger.debug(f"Repair result: {self.context["repair_result"]}")

    async def generate_report(self):
        self.set_workflow_status("PENDING-REPORT")
        self.context["report_result"] = await workflow.execute_activity(
            report,
            self.context,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=30),
            ),
            heartbeat_timeout=timedelta(seconds=20),
        )
        self.set_workflow_status("REPORT-COMPLETED")
        workflow.logger.debug(f"Report result: {self.context["report_result"]}")   
        report_summary = self.context["report_result"].get("repairs_summary", "No summary available")
        return report_summary

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
    async def GetProblemsConfidenceScore(self) -> float:
        if self.problems_found_confidence_score is None:
            return 0.0
        return self.problems_found_confidence_score
    
    @workflow.query
    async def GetPlannedRepairConfidenceScore(self) -> float:
        if self.planning_confidence_score is None:
            return 0.0
        return self.planning_confidence_score
    
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


'''RepairAgentWorkflowProactive: 
This is an agent implemented as a Temporal Workflow that orchestrates repairs.
It's much like RepairAgentWorkflow, but it is designed to run proactively.
It's intended to be always running:
 - detecting problems repairing problems in the system
 - optionally without waiting for user approval if confidence is high enough.
 - waiting for some time (or a signal) before the next iteration.
Tools are static Activities that implement automated helper agents.'''
@workflow.defn
class RepairAgentWorkflowProactive(RepairAgentWorkflow):
    def __init__(self) -> None:
        RepairAgentWorkflow.__init__(self)
        self.exit_requested: bool = False
        self.continue_as_new_requested: bool = False
        self.iteration_count: int = 0
        self.stop_waiting: bool = False

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["prompt"] = inputs.get("prompt", {})
        self.context["metadata"] = inputs.get("metadata", {})
        self.context["notification_info"] = inputs.get("callback", None)
        workflow.logger.debug(f"Starting repair workflow with inputs: {inputs}")

        while not self.exit_requested and not self.continue_as_new_requested and self.iteration_count < ITERATIONS_BEFORE_CONTINUE_AS_NEW:
            self.iteration_count += 1
            self.approved = False
            self.stop_waiting = False
            
            self.set_workflow_status("WAITING-FOR-NEXT-CYCLE")
            await workflow.wait_condition(
                lambda: self.exit_requested is True or 
                        self.continue_as_new_requested is True or
                        self.stop_waiting is True,
                timeout=timedelta(days=1), # Wait a day for the next detect->analysis->repair cycle. 
                                        # Could make this a dynamic timer if you wanted to always run at a certain time            
            )                           
            if self.continue_as_new_requested or self.exit_requested:
                workflow.logger.info("Continuing as new or exit requested. Skipping analysis for this iteration.")
            else:
                # Execute the detection agent
                self.problems_found_confidence_score = await self.perform_detection(self.context)

                self.problems_found_confidence_score = self.context["detection_result"].get("confidence_score", 0.0)
                if self.problems_found_confidence_score < 0.5:
                    analysis_notes = self.context["detection_result"].get("additional_notes", "")
                    workflow.logger.info(f"Low confidence score from detection: {self.problems_found_confidence_score} ({analysis_notes}). No repair needed at this time.")
                    self.set_workflow_status("NO-REPAIR-NEEDED")
                    continue  # Skip to the next iteration if no repair is needed
                
                #execute the analysis agent      
                await self.analyze_problems(self.context)
                
                # Execute the planning for this agent
                await self.create_plan(self.context)

                # for low planning confidence scores, we will notify the user and wait for approval
                if self.planning_confidence_score <= 0.95:
                    # Notify the user about the planned repairs
                    await self.execute_notification()

                    # Wait for the approval or reject signal
                    self.set_workflow_status("PENDING-APPROVAL")
                    workflow.logger.info(f"Waiting for approval for repair")
                    await workflow.wait_condition(
                        lambda: self.approved is not False or self.rejected is not False,
                        timeout=timedelta(hours=20),  # Wait for up to 24 hours for approval
                    )

                    if self.rejected:
                        workflow.logger.info(f"Repair REJECTED by user {self.context.get('rejected_by', 'unknown')}. No repair needed at this time - will check again later.")
                        self.set_workflow_status("REJECTED")
                        continue # Skip to the next iteration if repair is rejected
                    
                    self.set_workflow_status("APPROVED")
                    workflow.logger.info(f"Repair approved by user {self.context.get('approved_by', 'unknown')}")
                else:
                    # If the planning confidence score is high enough, we can proceed without waiting for approval
                    self.approved = True
                    self.context["approved_by"] = f"Agentically Approved with confidence score {self.context['planning_result'].get('overall_confidence_score', 0.0)}"
                    self.set_workflow_status("APPROVED")
                    workflow.logger.info("Planning confidence score is high enough. Proceeding with repair without waiting for approval.")

                # Proceed with the repair
                await self.execute_repair()

                # Create the report with the report agent
                report_summary = await self.generate_report()
                workflow.logger.info(f"Repair completed with status: {self.status}. Report Summary: {report_summary}") 
            
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

    async def execute_notification(self):
        """Inform the user about the planned repairs.
        Notification information is passed in the context."""
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

'''OrderWorkflow:
This is a Temporal Workflow that orchestrates the order management process.
It's just a simple demo workflow to demonstrate order repairs
'''
@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str = "INITIALIZING"
        self.context: dict = {}

    @workflow.run
    async def run(self, inputs: dict) -> str:
        self.context["metadata"] = inputs.get("metadata", {})
        self.context["order_details"] = inputs.get("order_details", {})
        self.order_id = inputs.get("order_id", "unknown")
        workflow.logger.debug(f"Order ID: {self.order_id}")
        workflow.logger.debug(f"Order details: {self.context['order_details']}")
        self.set_workflow_status("INITIALIZING")
        workflow.logger.debug(f"Starting order workflow with inputs: {inputs}")
        order_result = "pending"

        # Execute the order management steps
        while self.status not in ["ORDER-COMPLETED", "ORDER-FAILED"]:
            self.set_workflow_status("PROCESSING-ORDER")
            # try to process the order
            try:
                process_order_status = await workflow.execute_activity(
                    process_order,
                    self.context,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=30),  
                    ),
                    heartbeat_timeout=timedelta(seconds=20),
                )
                workflow.logger.debug(f"Process order result: {process_order_status}")
                order_result = process_order_status
            except ActivityError as e:
                # Handle activity errors
                workflow.logger.error(f"Activity error while processing order: {e}")
                self.set_workflow_status("ORDER-FAILED")
                return f"Order processing failed with error: {e}"
            
            if process_order_status not in ["pending", "in-progress", "completed", "approved-preparing-shipment"]:
                workflow.logger.warning(f"Order processing returned stuck: {process_order_status}. Initiating troubleshooting.")
                # If the order processing fails or returns an unexpected status, initiate troubleshooting
                self.set_workflow_status("ORDER-TROUBLESHOOTING")
                
                try:
                    repair_result = await workflow.execute_activity(
                        single_tool_repair,
                        self.context,
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(
                            initial_interval=timedelta(seconds=1),
                            maximum_interval=timedelta(seconds=30),  
                        ),
                        heartbeat_timeout=timedelta(seconds=20),
                    )
                    workflow.logger.debug(f"Repair result: {repair_result}")
                except ActivityError as e:
                    # if repair fails, mark the order as failed
                    self.set_workflow_status("ORDER-FAILED")
                    return f"Order processing failed with error: {str(e)}"
            elif process_order_status in ["pending", "in-progress", "approved-preparing-shipment"]:
                #wait a bit for the order to be processed
                workflow.logger.info(f"Order is still in progress: {process_order_status}. Waiting for processing.")
                await workflow.wait_condition(
                    lambda: self.status in ["ORDER-COMPLETED", "ORDER-FAILED"],
                    timeout=timedelta(days=1), 
                )
            elif process_order_status == "completed":
                # If the order is completed, we can finalize the workflow
                workflow.logger.info(f"Order processing completed successfully: {process_order_status}.")
                self.set_workflow_status("ORDER-COMPLETED")
                order_result = "Order completed successfully"
                break

        # Finalize the workflow
        return f"Order workflow completed with status: {self.status}. Order Result: {order_result}"
    
    # workflow helper functions
    def set_workflow_status(self, status: str) -> None: 
        """Set the current status of the workflow."""
        self.status = status
        # set workflow current details in Markdown format. Include status, iteration count, and timestamp.
        details: str = f"## Workflow Status \n\n" \
                    f"- **Phase:** {status}\n" 
        details += f"- **Last Status Set:** {workflow.now().isoformat()}\n"
        workflow.set_current_details(details)
        workflow.logger.debug(f"Workflow status set to: {status}")