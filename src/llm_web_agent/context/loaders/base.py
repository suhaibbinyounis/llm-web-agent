"""
Base Loader - Abstract interface for context loaders.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DocumentType(Enum):
    """Types of loaded documents."""
    TEXT = "text"
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    IMAGE = "image"
    HTML = "html"
    UNKNOWN = "unknown"


@dataclass
class LoadedDocument:
    """
    A loaded document with extracted content.
    
    Attributes:
        source: Original file path or URL
        doc_type: Type of document
        content: Extracted text content
        metadata: Document metadata
        chunks: Content split into chunks for large docs
        data: Structured data (for JSON, CSV, Excel)
    """
    source: str
    doc_type: DocumentType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[str] = field(default_factory=list)
    data: Optional[Any] = None
    
    @property
    def token_estimate(self) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars)."""
        return len(self.content) // 4
    
    def get_chunk(self, index: int) -> Optional[str]:
        """Get a specific chunk."""
        if 0 <= index < len(self.chunks):
            return self.chunks[index]
        return None


class IContextLoader(ABC):
    """
    Abstract interface for document loaders.
    
    Implementations load specific file types and extract
    their content for use as context.
    """
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """List of supported file extensions (e.g., ['.pdf', '.PDF'])."""
        ...
    
    @property
    @abstractmethod
    def doc_type(self) -> DocumentType:
        """The document type this loader produces."""
        ...
    
    @abstractmethod
    async def load(
        self,
        source: Union[str, Path],
        **options: Any,
    ) -> LoadedDocument:
        """
        Load a document from a file or URL.
        
        Args:
            source: File path or URL
            **options: Loader-specific options
            
        Returns:
            Loaded document with content
        """
        ...
    
    @abstractmethod
    def can_load(self, source: Union[str, Path]) -> bool:
        """
        Check if this loader can handle the given source.
        
        Args:
            source: File path or URL
            
        Returns:
            True if this loader can handle the source
        """
        ...


class TextLoader(IContextLoader):
    """
    Loader for plain text files.
    
    Example:
        >>> loader = TextLoader()
        >>> doc = await loader.load("readme.txt")
        >>> print(doc.content)
    """
    
    @property
    def supported_extensions(self) -> List[str]:
        return [".txt", ".text", ".md", ".markdown", ".rst"]
    
    @property
    def doc_type(self) -> DocumentType:
        return DocumentType.TEXT
    
    def can_load(self, source: Union[str, Path]) -> bool:
        path = Path(source) if isinstance(source, str) else source
        return path.suffix.lower() in self.supported_extensions
    
    async def load(
        self,
        source: Union[str, Path],
        encoding: str = "utf-8",
        **options: Any,
    ) -> LoadedDocument:
        """Load a text file."""
        path = Path(source)
        
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
        
        return LoadedDocument(
            source=str(path),
            doc_type=self.doc_type,
            content=content,
            metadata={
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "encoding": encoding,
            },
        )


class JSONLoader(IContextLoader):
    """Loader for JSON files."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return [".json"]
    
    @property
    def doc_type(self) -> DocumentType:
        return DocumentType.JSON
    
    def can_load(self, source: Union[str, Path]) -> bool:
        path = Path(source) if isinstance(source, str) else source
        return path.suffix.lower() in self.supported_extensions
    
    async def load(
        self,
        source: Union[str, Path],
        **options: Any,
    ) -> LoadedDocument:
        """Load a JSON file."""
        import json
        path = Path(source)
        
        with open(path, "r") as f:
            data = json.load(f)
        
        # Convert to string representation for content
        content = json.dumps(data, indent=2)
        
        return LoadedDocument(
            source=str(path),
            doc_type=self.doc_type,
            content=content,
            data=data,
            metadata={"filename": path.name},
        )


class CSVLoader(IContextLoader):
    """Loader for CSV files."""
    
    @property
    def supported_extensions(self) -> List[str]:
        return [".csv"]
    
    @property
    def doc_type(self) -> DocumentType:
        return DocumentType.CSV
    
    def can_load(self, source: Union[str, Path]) -> bool:
        path = Path(source) if isinstance(source, str) else source
        return path.suffix.lower() in self.supported_extensions
    
    async def load(
        self,
        source: Union[str, Path],
        **options: Any,
    ) -> LoadedDocument:
        """Load a CSV file."""
        import csv
        path = Path(source)
        
        rows = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for row in reader:
                rows.append(row)
        
        # Convert to readable content
        content_lines = [", ".join(headers)]
        for row in rows[:100]:  # Limit for context window
            content_lines.append(", ".join(str(v) for v in row.values()))
        
        return LoadedDocument(
            source=str(path),
            doc_type=self.doc_type,
            content="\n".join(content_lines),
            data=rows,
            metadata={
                "filename": path.name,
                "headers": headers,
                "row_count": len(rows),
            },
        )
