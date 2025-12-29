"""
Schemas - Structured output definitions for LLM responses.

Uses Pydantic for validation and JSON schema generation.
These schemas ensure LLM responses are properly structured.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# INSTRUCTION PARSING SCHEMAS
# =============================================================================

class StepIntent(str, Enum):
    """Valid step intents for parsed instructions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    EXTRACT = "extract"
    HOVER = "hover"
    SCROLL = "scroll"
    WAIT = "wait"
    SUBMIT = "submit"
    PRESS_KEY = "press_key"
    SCREENSHOT = "screenshot"


class ParsedStep(BaseModel):
    """A single parsed step from LLM."""
    intent: StepIntent
    target: Optional[str] = None
    value: Optional[str] = None
    store_as: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class ParsedInstruction(BaseModel):
    """Complete parsed instruction from LLM."""
    steps: List[ParsedStep]
    
    @classmethod
    def from_json(cls, data: Union[List, Dict]) -> "ParsedInstruction":
        """Parse from JSON (handles both list and object formats)."""
        if isinstance(data, list):
            return cls(steps=[ParsedStep(**s) for s in data])
        elif isinstance(data, dict) and "steps" in data:
            return cls(steps=[ParsedStep(**s) for s in data["steps"]])
        else:
            raise ValueError(f"Invalid parsed instruction format: {type(data)}")


# =============================================================================
# ELEMENT FINDING SCHEMAS
# =============================================================================

class FoundElement(BaseModel):
    """Result of LLM element finding."""
    found: bool
    index: Optional[int] = None
    selector: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    
    @property
    def is_found(self) -> bool:
        return self.found and self.index is not None


class ElementCandidate(BaseModel):
    """A candidate element for matching."""
    index: int
    tag: str
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None
    selector: Optional[str] = None


# =============================================================================
# ACTION PLANNING SCHEMAS
# =============================================================================

class PlannedAction(BaseModel):
    """A single action in a plan."""
    step: int
    intent: StepIntent
    target: Optional[str] = None
    value: Optional[str] = None
    reason: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class ActionPlan(BaseModel):
    """Complete action plan from LLM."""
    plan: List[PlannedAction]
    variables_needed: List[str] = Field(default_factory=list)
    estimated_pages: int = 1
    
    @property
    def step_count(self) -> int:
        return len(self.plan)


# =============================================================================
# ERROR RECOVERY SCHEMAS
# =============================================================================

class RecoveryStep(BaseModel):
    """A recovery step suggested by LLM."""
    intent: StepIntent
    target: Optional[str] = None
    value: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class ErrorRecovery(BaseModel):
    """Error recovery suggestion from LLM."""
    diagnosis: str
    recovery_steps: List[RecoveryStep] = Field(default_factory=list)
    should_retry: bool = False
    alternative_approach: Optional[str] = None


# =============================================================================
# DOM EXTRACTION SCHEMAS
# =============================================================================

class ExtractedValue(BaseModel):
    """Extracted value from DOM."""
    found: bool
    value: Optional[str] = None
    element_index: Optional[int] = None
    confidence: float = 0.0


# =============================================================================
# GENERIC LLM RESPONSE
# =============================================================================

class LLMResponseStatus(str, Enum):
    """Status of LLM response."""
    SUCCESS = "success"
    PARSE_ERROR = "parse_error"
    INVALID_FORMAT = "invalid_format"
    EMPTY = "empty"
    ERROR = "error"


@dataclass
class LLMResponse:
    """
    Generic wrapper for LLM responses.
    
    Handles parsing, validation, and error cases.
    """
    status: LLMResponseStatus
    raw_text: str = ""
    parsed: Optional[Any] = None
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: float = 0
    
    @property
    def success(self) -> bool:
        return self.status == LLMResponseStatus.SUCCESS
    
    @classmethod
    def from_text(
        cls,
        text: str,
        schema_class: type,
        tokens: int = 0,
        latency: float = 0,
    ) -> "LLMResponse":
        """Parse LLM text response into structured format."""
        import json
        
        if not text or not text.strip():
            return cls(
                status=LLMResponseStatus.EMPTY,
                raw_text=text,
                error="Empty response",
            )
        
        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            json_text = text.strip()
            if "```json" in json_text:
                start = json_text.find("```json") + 7
                end = json_text.find("```", start)
                json_text = json_text[start:end].strip()
            elif "```" in json_text:
                start = json_text.find("```") + 3
                end = json_text.find("```", start)
                json_text = json_text[start:end].strip()
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Validate with schema
            if schema_class == ParsedInstruction:
                parsed = ParsedInstruction.from_json(data)
            else:
                parsed = schema_class(**data) if isinstance(data, dict) else schema_class(data)
            
            return cls(
                status=LLMResponseStatus.SUCCESS,
                raw_text=text,
                parsed=parsed,
                tokens_used=tokens,
                latency_ms=latency,
            )
        
        except json.JSONDecodeError as e:
            return cls(
                status=LLMResponseStatus.PARSE_ERROR,
                raw_text=text,
                error=f"JSON parse error: {e}",
                tokens_used=tokens,
                latency_ms=latency,
            )
        
        except Exception as e:
            return cls(
                status=LLMResponseStatus.INVALID_FORMAT,
                raw_text=text,
                error=f"Validation error: {e}",
                tokens_used=tokens,
                latency_ms=latency,
            )


# =============================================================================
# JSON SCHEMA GENERATION (for function calling)
# =============================================================================

def get_instruction_parse_schema() -> Dict[str, Any]:
    """Get JSON schema for instruction parsing."""
    return {
        "name": "parse_instruction",
        "description": "Parse a natural language instruction into executable steps",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "enum": [e.value for e in StepIntent],
                            },
                            "target": {"type": "string"},
                            "value": {"type": "string"},
                            "store_as": {"type": "string"},
                        },
                        "required": ["intent"],
                    },
                },
            },
            "required": ["steps"],
        },
    }


def get_element_find_schema() -> Dict[str, Any]:
    """Get JSON schema for element finding."""
    return {
        "name": "find_element",
        "description": "Find an element in the DOM matching a description",
        "parameters": {
            "type": "object",
            "properties": {
                "found": {"type": "boolean"},
                "index": {"type": "integer"},
                "selector": {"type": "string"},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"},
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["found"],
        },
    }


def get_action_plan_schema() -> Dict[str, Any]:
    """Get JSON schema for action planning."""
    return {
        "name": "create_plan",
        "description": "Create an action plan to achieve a goal",
        "parameters": {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "integer"},
                            "intent": {
                                "type": "string",
                                "enum": [e.value for e in StepIntent],
                            },
                            "target": {"type": "string"},
                            "value": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["step", "intent"],
                    },
                },
                "variables_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "estimated_pages": {"type": "integer"},
            },
            "required": ["plan"],
        },
    }
