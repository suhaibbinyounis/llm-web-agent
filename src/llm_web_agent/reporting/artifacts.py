"""
Artifact Manager - Manage run artifacts (files, data, exports).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil


class ArtifactType(Enum):
    """Types of artifacts."""
    SCREENSHOT = "screenshot"
    VIDEO = "video"
    LOG = "log"
    REPORT = "report"
    DATA = "data"
    OTHER = "other"


@dataclass
class Artifact:
    """
    A run artifact.
    
    Attributes:
        name: Artifact name
        artifact_type: Type of artifact
        path: File path
        created_at: Creation timestamp
        metadata: Additional metadata
    """
    name: str
    artifact_type: ArtifactType
    path: Path
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArtifactManager:
    """
    Manage artifacts for a run.
    
    Example:
        >>> manager = ArtifactManager(output_dir="./output", run_id="run_123")
        >>> manager.save_data("extracted_data", {"key": "value"})
        >>> manager.copy_file("/path/to/file.pdf", "uploaded_doc.pdf")
    """
    
    def __init__(self, output_dir: str | Path, run_id: str):
        """
        Initialize the artifact manager.
        
        Args:
            output_dir: Base output directory
            run_id: Unique run identifier
        """
        self.output_dir = Path(output_dir) / run_id
        self.run_id = run_id
        self._artifacts: List[Artifact] = []
        
        # Create directory structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "screenshots").mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)
        (self.output_dir / "data").mkdir(exist_ok=True)
    
    def save_data(
        self,
        name: str,
        data: Any,
        format: str = "json",
    ) -> Artifact:
        """
        Save data as an artifact.
        
        Args:
            name: Artifact name
            data: Data to save
            format: Output format (json, txt)
            
        Returns:
            Created artifact
        """
        filename = f"{name}.{format}"
        path = self.output_dir / "data" / filename
        
        if format == "json":
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        else:
            with open(path, "w") as f:
                f.write(str(data))
        
        artifact = Artifact(
            name=name,
            artifact_type=ArtifactType.DATA,
            path=path,
        )
        self._artifacts.append(artifact)
        return artifact
    
    def copy_file(
        self,
        source: str | Path,
        name: Optional[str] = None,
        artifact_type: ArtifactType = ArtifactType.OTHER,
    ) -> Artifact:
        """
        Copy a file as an artifact.
        
        Args:
            source: Source file path
            name: Target filename (uses source name if not provided)
            artifact_type: Type of artifact
            
        Returns:
            Created artifact
        """
        source = Path(source)
        target_name = name or source.name
        target = self.output_dir / target_name
        
        shutil.copy2(source, target)
        
        artifact = Artifact(
            name=target_name,
            artifact_type=artifact_type,
            path=target,
        )
        self._artifacts.append(artifact)
        return artifact
    
    def get_artifacts(
        self,
        artifact_type: Optional[ArtifactType] = None,
    ) -> List[Artifact]:
        """
        Get artifacts, optionally filtered by type.
        
        Args:
            artifact_type: Filter by type (None for all)
            
        Returns:
            List of artifacts
        """
        if artifact_type is None:
            return self._artifacts.copy()
        return [a for a in self._artifacts if a.artifact_type == artifact_type]
    
    def cleanup(self) -> None:
        """Remove all artifacts and the run directory."""
        shutil.rmtree(self.output_dir, ignore_errors=True)
        self._artifacts.clear()
