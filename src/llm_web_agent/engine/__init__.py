"""
Engine Module - Core execution engine for NL-to-actions pipeline.

This is the heart of the agent, handling:
- Run context and memory management
- Instruction parsing and task graphs
- Batch execution of actions
- Target resolution across multiple layers
"""

from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.task_graph import TaskGraph, TaskStep, StepStatus, StepIntent
from llm_web_agent.engine.instruction_parser import InstructionParser
from llm_web_agent.engine.target_resolver import TargetResolver, ResolvedTarget
from llm_web_agent.engine.batch_executor import BatchExecutor, BatchResult
from llm_web_agent.engine.state_manager import StateManager
from llm_web_agent.engine.engine import Engine, EngineResult

__all__ = [
    # Main engine
    "Engine",
    "EngineResult",
    # Context
    "RunContext",
    # Task graph
    "TaskGraph",
    "TaskStep",
    "StepStatus",
    "StepIntent",
    # Parsing
    "InstructionParser",
    # Resolution
    "TargetResolver",
    "ResolvedTarget",
    # Execution
    "BatchExecutor",
    "BatchResult",
    # State
    "StateManager",
]
