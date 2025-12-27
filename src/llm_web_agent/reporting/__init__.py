"""
Reporting module for llm-web-agent.

Provides tools for documenting and reporting on agent runs.
"""

from llm_web_agent.reporting.run_report import (
    RunStatus,
    StepSummary,
    RunSummary,
    RunReport,
)
from llm_web_agent.reporting.screenshot_manager import (
    Screenshot,
    ScreenshotManager,
)
from llm_web_agent.reporting.step_logger import (
    LogLevel,
    StepLog,
    StepLogger,
)
from llm_web_agent.reporting.execution_report import (
    StepDetail,
    ExecutionReport,
    ExecutionReportGenerator,
)

__all__ = [
    # Run Report
    "RunStatus",
    "StepSummary",
    "RunSummary",
    "RunReport",
    # Screenshots
    "Screenshot",
    "ScreenshotManager",
    # Logging
    "LogLevel",
    "StepLog",
    "StepLogger",
    # Execution Report (NEW)
    "StepDetail",
    "ExecutionReport",
    "ExecutionReportGenerator",
]
