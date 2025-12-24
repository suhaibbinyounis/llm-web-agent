"""
Context Manager - Load and manage document context.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

from llm_web_agent.context.loaders.base import (
    IContextLoader,
    LoadedDocument,
    DocumentType,
    TextLoader,
    JSONLoader,
    CSVLoader,
)

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manage document context for automation tasks.
    
    Provides a unified interface for loading documents,
    managing context, and injecting into prompts.
    
    Example:
        >>> manager = ContextManager()
        >>> await manager.load_document("data.csv")
        >>> await manager.load_document("instructions.txt")
        >>> context = manager.get_context_for_prompt(max_tokens=2000)
    """
    
    def __init__(self):
        """Initialize the context manager."""
        self._loaders: Dict[str, IContextLoader] = {}
        self._documents: Dict[str, LoadedDocument] = {}
        self._variables: Dict[str, Any] = {}
        
        # Register default loaders
        self._register_default_loaders()
    
    def _register_default_loaders(self) -> None:
        """Register built-in loaders."""
        for loader in [TextLoader(), JSONLoader(), CSVLoader()]:
            for ext in loader.supported_extensions:
                self._loaders[ext] = loader
    
    def register_loader(self, loader: IContextLoader) -> None:
        """
        Register a custom loader.
        
        Args:
            loader: Loader to register
        """
        for ext in loader.supported_extensions:
            self._loaders[ext] = loader
    
    async def load_document(
        self,
        source: Union[str, Path],
        name: Optional[str] = None,
        **options: Any,
    ) -> LoadedDocument:
        """
        Load a document into context.
        
        Args:
            source: File path or URL
            name: Optional name for the document
            **options: Loader-specific options
            
        Returns:
            Loaded document
        """
        path = Path(source) if isinstance(source, str) else source
        ext = path.suffix.lower()
        
        loader = self._loaders.get(ext)
        if not loader:
            raise ValueError(f"No loader registered for extension: {ext}")
        
        doc = await loader.load(path, **options)
        doc_name = name or path.stem
        self._documents[doc_name] = doc
        
        logger.info(f"Loaded document '{doc_name}' ({doc.token_estimate} tokens)")
        return doc
    
    def set_variable(self, name: str, value: Any) -> None:
        """
        Set a context variable for template substitution.
        
        Args:
            name: Variable name
            value: Variable value
        """
        self._variables[name] = value
    
    def get_variable(self, name: str) -> Optional[Any]:
        """Get a context variable."""
        return self._variables.get(name)
    
    def get_document(self, name: str) -> Optional[LoadedDocument]:
        """Get a loaded document by name."""
        return self._documents.get(name)
    
    def get_context_for_prompt(
        self,
        max_tokens: int = 4000,
        include_docs: Optional[List[str]] = None,
    ) -> str:
        """
        Get combined context for LLM prompt.
        
        Args:
            max_tokens: Maximum tokens to include
            include_docs: Specific documents to include (all if None)
            
        Returns:
            Combined context string
        """
        parts = []
        remaining_tokens = max_tokens
        
        docs = include_docs or list(self._documents.keys())
        
        for doc_name in docs:
            doc = self._documents.get(doc_name)
            if not doc:
                continue
            
            # Check if fits
            if doc.token_estimate > remaining_tokens:
                # Truncate content
                chars_available = remaining_tokens * 4
                content = doc.content[:chars_available]
                parts.append(f"## {doc_name} (truncated)\n{content}")
                break
            else:
                parts.append(f"## {doc_name}\n{doc.content}")
                remaining_tokens -= doc.token_estimate
        
        return "\n\n".join(parts)
    
    def resolve_template(self, template: str) -> str:
        """
        Resolve variables in a template string.
        
        Replaces {{variable}} patterns with values from
        context variables and document data.
        
        Args:
            template: Template string with {{variable}} patterns
            
        Returns:
            Resolved string
        """
        import re
        
        def replacer(match):
            var_path = match.group(1).strip()
            parts = var_path.split(".")
            
            # Try variables first
            if parts[0] in self._variables:
                value = self._variables[parts[0]]
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part, "")
                    else:
                        value = getattr(value, part, "")
                return str(value)
            
            # Try documents
            if parts[0] in self._documents:
                doc = self._documents[parts[0]]
                if doc.data and len(parts) > 1:
                    value = doc.data
                    for part in parts[1:]:
                        if isinstance(value, dict):
                            value = value.get(part, "")
                        elif isinstance(value, list) and part.isdigit():
                            value = value[int(part)] if int(part) < len(value) else ""
                        else:
                            value = ""
                    return str(value)
            
            return match.group(0)  # Keep original if not found
        
        return re.sub(r'\{\{([^}]+)\}\}', replacer, template)
    
    def list_documents(self) -> List[str]:
        """List loaded document names."""
        return list(self._documents.keys())
    
    def clear(self) -> None:
        """Clear all loaded documents and variables."""
        self._documents.clear()
        self._variables.clear()
