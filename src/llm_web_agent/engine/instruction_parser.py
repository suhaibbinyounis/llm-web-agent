"""
Instruction Parser - Parse natural language into TaskGraph.

Uses pattern matching for common actions, falls back to LLM for complex instructions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import re
import logging

from llm_web_agent.engine.task_graph import TaskGraph, TaskStep, StepIntent

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ParsedClause:
    """A parsed instruction clause."""
    text: str
    intent: Optional[StepIntent] = None
    target: Optional[str] = None
    value: Optional[str] = None
    store_as: Optional[str] = None
    confidence: float = 0.0


class InstructionParser:
    """
    Parse natural language instructions into a TaskGraph.
    
    Uses a two-layer approach:
    1. Pattern matching for common actions (fast, no LLM)
    2. LLM parsing for complex/ambiguous instructions
    
    Example:
        >>> parser = InstructionParser()
        >>> graph = await parser.parse(
        ...     "Go to amazon.com, search for laptops, and click the first result"
        ... )
        >>> print(graph.to_summary())
    """
    
    # Clause separators
    CLAUSE_SEPARATORS = re.compile(
        r'[,;]|\s+(?:then|and then|after that|next|finally|and)\s+',
        re.IGNORECASE
    )
    
    # Pattern rules: (regex, intent, groups) 
    # Groups: 1=target, 2=value, or custom mapping
    PATTERNS: List[Tuple[re.Pattern, StepIntent, Dict[str, int]]] = [
        # Navigation
        (re.compile(r'^(?:go to|open|visit|navigate to)\s+(.+)$', re.I), 
         StepIntent.NAVIGATE, {"target": 1}),
        
        # Search
        (re.compile(r'^search\s+(?:for\s+)?["\']?(.+?)["\']?$', re.I),
         StepIntent.FILL, {"value": 1, "target": "search"}),
        
        (re.compile(r'^(?:search|look|find)\s+(.+?)\s+(?:on|in|at)\s+(.+)$', re.I),
         StepIntent.FILL, {"value": 1, "target": 2}),
        
        # PRESS KEY - MUST be before generic "press" click pattern!
        (re.compile(r'^press\s+(enter|return|tab|escape|esc|backspace|delete|space|up|down|left|right)(?:\s+key)?$', re.I),
         StepIntent.PRESS_KEY, {"value": 1}),
        
        (re.compile(r'^hit\s+(enter|return|tab|escape|esc)(?:\s+key)?$', re.I),
         StepIntent.PRESS_KEY, {"value": 1}),
        
        # Click
        (re.compile(r'^click\s+(?:on\s+)?(?:the\s+)?(.+)$', re.I),
         StepIntent.CLICK, {"target": 1}),
        
        (re.compile(r'^(?:tap|select|choose)\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.CLICK, {"target": 1}),
        
        # Only "press" on non-key things (like buttons)
        (re.compile(r'^press\s+(?:the\s+)?(.+?)\s+(?:button|link)$', re.I),
         StepIntent.CLICK, {"target": 1}),
        
        # Fill/Type
        (re.compile(r'^(?:type|enter|input)\s+["\']?(.+?)["\']?\s+(?:in(?:to)?|on)\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.FILL, {"value": 1, "target": 2}),
        
        (re.compile(r'^fill\s+(?:in\s+)?(?:the\s+)?(.+?)\s+(?:with|as)\s+["\']?(.+?)["\']?$', re.I),
         StepIntent.FILL, {"target": 1, "value": 2}),
        
        (re.compile(r'^(?:set|put)\s+["\']?(.+?)["\']?\s+(?:in(?:to)?|as)\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.FILL, {"value": 1, "target": 2}),
        
        # Extract/Copy
        (re.compile(r'^(?:copy|get|read|extract)\s+(?:the\s+)?(.+?)(?:\s+(?:and\s+)?(?:save|store|remember)\s+(?:it\s+)?as\s+(.+))?$', re.I),
         StepIntent.EXTRACT, {"target": 1, "store_as": 2}),
        
        (re.compile(r'^remember\s+(?:the\s+)?(.+?)\s+as\s+(.+)$', re.I),
         StepIntent.EXTRACT, {"target": 1, "store_as": 2}),
        
        # Paste
        (re.compile(r'^paste\s+(?:the\s+)?(?:\{\{)?(.+?)(?:\}\})?\s+(?:in(?:to)?|on)\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.FILL, {"value": "{{\\1}}", "target": 2}),
        
        # Select dropdown
        (re.compile(r'^select\s+["\']?(.+?)["\']?\s+(?:from|in)\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.SELECT, {"value": 1, "target": 2}),
        
        # Scroll
        (re.compile(r'^scroll\s+(up|down|to\s+(?:top|bottom))$', re.I),
         StepIntent.SCROLL, {"target": 1}),
        
        (re.compile(r'^scroll\s+to\s+(?:the\s+)?(.+)$', re.I),
         StepIntent.SCROLL, {"target": 1}),
        
        # Wait
        (re.compile(r'^wait\s+(?:for\s+)?(\d+)\s*(?:seconds?|s)$', re.I),
         StepIntent.WAIT, {"value": 1}),
        
        (re.compile(r'^wait\s+(?:for\s+)?(?:the\s+)?(.+?)(?:\s+to\s+(?:load|appear))?$', re.I),
         StepIntent.WAIT, {"target": 1}),
        
        # Submit
        (re.compile(r'^submit(?:\s+(?:the\s+)?(?:form|page))?$', re.I),
         StepIntent.SUBMIT, {}),
        
        # Hover
        (re.compile(r'^hover\s+(?:over\s+)?(?:the\s+)?(.+)$', re.I),
         StepIntent.HOVER, {"target": 1}),
    ]
    
    def __init__(self, llm_provider: Optional["ILLMProvider"] = None):
        """
        Initialize the parser.
        
        Args:
            llm_provider: Optional LLM for complex parsing
        """
        self._llm = llm_provider
    
    async def parse(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskGraph:
        """
        Parse an instruction into a TaskGraph.
        
        Args:
            instruction: Natural language instruction
            context: Optional context (current URL, available elements, etc.)
            
        Returns:
            TaskGraph with parsed steps
        """
        instruction = instruction.strip()
        
        if not instruction:
            return TaskGraph(original_instruction=instruction)
        
        # Step 1: Split into clauses
        clauses = self._split_clauses(instruction)
        logger.debug(f"Split into {len(clauses)} clauses: {clauses}")
        
        # Step 2: Try pattern matching first
        parsed_clauses: List[ParsedClause] = []
        unmatched: List[str] = []
        
        for clause in clauses:
            result = self._pattern_match(clause)
            if result and result.confidence > 0.5:
                parsed_clauses.append(result)
            else:
                unmatched.append(clause)
        
        logger.debug(f"Pattern matched: {len(parsed_clauses)}, Unmatched: {len(unmatched)}")
        
        # Step 3: Use LLM for unmatched clauses
        if unmatched and self._llm:
            llm_parsed = await self._llm_parse(unmatched, context)
            parsed_clauses.extend(llm_parsed)
        elif unmatched:
            # No LLM, try to handle as generic
            for clause in unmatched:
                parsed_clauses.append(ParsedClause(
                    text=clause,
                    intent=StepIntent.CUSTOM,
                    target=clause,
                    confidence=0.3,
                ))
        
        # Step 4: Build TaskGraph
        graph = self._build_graph(parsed_clauses, instruction)
        
        return graph
    
    def _split_clauses(self, instruction: str) -> List[str]:
        """Split instruction into individual action clauses."""
        # Split by separators
        parts = self.CLAUSE_SEPARATORS.split(instruction)
        
        # Clean up
        clauses = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 2:  # Skip very short fragments
                clauses.append(part)
        
        return clauses if clauses else [instruction]
    
    def _pattern_match(self, clause: str) -> Optional[ParsedClause]:
        """Try to match clause against known patterns."""
        clause = clause.strip()
        
        for pattern, intent, groups in self.PATTERNS:
            match = pattern.match(clause)
            if match:
                # Build ParsedClause from match groups
                parsed = ParsedClause(
                    text=clause,
                    intent=intent,
                    confidence=0.8,
                )
                
                for field, group_idx in groups.items():
                    if isinstance(group_idx, int):
                        try:
                            value = match.group(group_idx)
                            setattr(parsed, field, value)
                        except IndexError:
                            pass
                    elif isinstance(group_idx, str):
                        # Static value or template
                        if "\\1" in group_idx:
                            try:
                                value = group_idx.replace("\\1", match.group(1))
                                setattr(parsed, field, value)
                            except IndexError:
                                setattr(parsed, field, group_idx)
                        else:
                            setattr(parsed, field, group_idx)
                
                # Handle special case: search without explicit target
                if intent == StepIntent.FILL and parsed.target == "search":
                    parsed.metadata = {"is_search": True}
                
                return parsed
        
        return None
    
    async def _llm_parse(
        self,
        clauses: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ParsedClause]:
        """Parse clauses using LLM."""
        if not self._llm:
            return []
        
        from llm_web_agent.engine.llm.strategy import LLMStrategy
        from llm_web_agent.engine.llm.schemas import ParsedInstruction, StepIntent as LLMStepIntent
        
        # Create strategy and parse
        strategy = LLMStrategy(self._llm)
        
        # Combine clauses back for LLM
        combined = ". ".join(clauses)
        
        response = await strategy.parse_instruction(combined, context)
        
        if not response.success or not response.parsed:
            logger.warning(f"LLM parsing failed: {response.error}")
            return [
                ParsedClause(
                    text=clause,
                    intent=StepIntent.CUSTOM,
                    target=clause,
                    confidence=0.5,
                )
                for clause in clauses
            ]
        
        # Convert LLM output to ParsedClauses
        parsed_instruction: ParsedInstruction = response.parsed
        results = []
        
        for step in parsed_instruction.steps:
            # Map LLM intent to our StepIntent
            try:
                intent = StepIntent(step.intent)
            except ValueError:
                intent = StepIntent.CUSTOM
            
            results.append(ParsedClause(
                text=f"{step.intent}: {step.target or ''}",
                intent=intent,
                target=step.target,
                value=step.value,
                store_as=step.store_as,
                confidence=0.85,  # LLM-parsed confidence
            ))
        
        logger.info(f"LLM parsed {len(results)} steps from {len(clauses)} clauses")
        return results
    
    def _build_graph(
        self,
        clauses: List[ParsedClause],
        original: str,
    ) -> TaskGraph:
        """Build TaskGraph from parsed clauses."""
        graph = TaskGraph(original_instruction=original)
        
        prev_step: Optional[TaskStep] = None
        
        for clause in clauses:
            if clause.intent is None:
                continue
            
            # Create step
            step = graph.add_step(
                intent=clause.intent,
                target=clause.target,
                value=clause.value,
                store_as=clause.store_as,
                depends_on=[prev_step.id] if prev_step else [],
            )
            
            prev_step = step
        
        return graph
    
    def parse_sync(self, instruction: str) -> TaskGraph:
        """
        Synchronous parsing (pattern matching only).
        
        Does not use LLM, suitable for simple instructions.
        """
        import asyncio
        
        # Temporarily disable LLM
        llm = self._llm
        self._llm = None
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create new loop for sync call
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.parse(instruction))
                    return future.result()
            else:
                return loop.run_until_complete(self.parse(instruction))
        finally:
            self._llm = llm
