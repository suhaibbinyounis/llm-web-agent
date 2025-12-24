"""
Run Report - Generate comprehensive reports for agent runs.

Provides HTML, PDF, and JSON export capabilities for run documentation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


class RunStatus(Enum):
    """Status of a run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepSummary:
    """Summary of a single step in a run."""
    step_number: int
    action: str
    description: str
    status: str
    duration_ms: float
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RunSummary:
    """
    Summary of an agent run.
    
    Attributes:
        run_id: Unique identifier for the run
        task: Original task description
        status: Final status of the run
        started_at: When the run started
        completed_at: When the run completed
        total_steps: Number of steps executed
        successful_steps: Number of successful steps
        failed_steps: Number of failed steps
        duration_seconds: Total run duration
        final_url: URL at end of run
        steps: List of step summaries
        metadata: Additional run metadata
    """
    run_id: str
    task: str
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    duration_seconds: float = 0.0
    final_url: Optional[str] = None
    steps: List[StepSummary] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "task": self.task,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "duration_seconds": self.duration_seconds,
            "final_url": self.final_url,
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "description": s.description,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "metadata": self.metadata,
        }


class RunReport:
    """
    Generate and export run reports.
    
    Example:
        >>> report = RunReport(run_summary)
        >>> report.export_html("report.html")
        >>> report.export_json("report.json")
    """
    
    def __init__(self, summary: RunSummary):
        """
        Initialize the report generator.
        
        Args:
            summary: Run summary to generate report from
        """
        self.summary = summary
    
    def export_json(self, path: Path | str) -> None:
        """
        Export report as JSON.
        
        Args:
            path: Output file path
        """
        path = Path(path)
        with open(path, "w") as f:
            json.dump(self.summary.to_dict(), f, indent=2)
    
    def export_html(self, path: Path | str) -> None:
        """
        Export report as HTML.
        
        Args:
            path: Output file path
        """
        # TODO: Implement HTML template rendering
        raise NotImplementedError("HTML export not yet implemented")
    
    def export_pdf(self, path: Path | str) -> None:
        """
        Export report as PDF.
        
        Args:
            path: Output file path
        """
        # TODO: Implement PDF generation
        raise NotImplementedError("PDF export not yet implemented")
