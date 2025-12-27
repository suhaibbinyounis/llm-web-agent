"""
Engine Module - Core execution engine for NL-to-actions pipeline.

This is the heart of the agent, handling:
- Run context and memory management
- Instruction parsing and task graphs
- Batch execution of actions
- Target resolution across multiple layers

NEW: Adaptive Engine with LLM-first planning and learning.
"""

from llm_web_agent.engine.run_context import RunContext
from llm_web_agent.engine.task_graph import TaskGraph, TaskStep, StepStatus, StepIntent
from llm_web_agent.engine.instruction_parser import InstructionParser
from llm_web_agent.engine.target_resolver import TargetResolver, ResolvedTarget
from llm_web_agent.engine.batch_executor import BatchExecutor, BatchResult
from llm_web_agent.engine.state_manager import StateManager
from llm_web_agent.engine.engine import Engine, EngineResult

# NEW: Adaptive engine components
from llm_web_agent.engine.adaptive_engine import AdaptiveEngine, AdaptiveEngineResult
from llm_web_agent.engine.task_planner import TaskPlanner, ExecutionPlan, PlannedStep
from llm_web_agent.engine.site_profiler import SiteProfiler, SiteProfile, get_site_profiler
from llm_web_agent.engine.accessibility_resolver import AccessibilityResolver, get_accessibility_resolver
from llm_web_agent.engine.selector_pattern_tracker import SelectorPatternTracker, get_pattern_tracker

__all__ = [
    # Main engine (legacy)
    "Engine",
    "EngineResult",
    # NEW: Adaptive engine
    "AdaptiveEngine",
    "AdaptiveEngineResult",
    # NEW: Task planning
    "TaskPlanner",
    "ExecutionPlan",
    "PlannedStep",
    # NEW: Site profiling
    "SiteProfiler",
    "SiteProfile",
    "get_site_profiler",
    # NEW: Accessibility resolution
    "AccessibilityResolver",
    "get_accessibility_resolver",
    # NEW: Pattern learning
    "SelectorPatternTracker",
    "get_pattern_tracker",
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
