"""
Instruction Normalizer - Convert natural language to standard format.

Uses ONE LLM call to normalize all instructions upfront.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


# Prompt for normalizing instructions
NORMALIZE_PROMPT = '''You are an instruction normalizer for a browser automation system.

Convert these natural language instructions into our standard format.

**OUR FORMAT:**
- navigate: URL
- click: TARGET
- hover: TARGET  ← Use for dropdown menus that reveal on hover
- fill: TARGET with VALUE  ← Extract VALUE from the instruction!
- type: VALUE
- scroll: down/up
- wait: SECONDS
- press: KEY

**CRITICAL: EXTRACT VALUES FROM THE INSTRUCTIONS!**
- If instruction says "Enter username standard_user" → value is "standard_user"
- If instruction says "Fill first name with Bob" → value is "Bob"  
- If instruction says "Enter password secret123" → value is "secret123"
- NEVER invent or hardcode values - extract them from the original instruction!

**RULES FOR TARGETS:**
1. For form fields, use the EXACT field name that distinguishes it:
   - "first-name" NOT "input[type=text]"
   - "lastName" or "last-name" NOT "text input"
   - "postalCode" or "postal-code" or "zip" NOT just "input"
2. Each field MUST have a UNIQUE target

**GENERAL RULES:**
1. Skip meta-instructions like "Open browser" (already open)
2. For saucedemo.com, use known IDs: user-name, password, login-button, checkout, first-name, last-name, postal-code, continue, finish
3. When instruction says "Fill first name, last name, postal code" without specific values, use placeholder values like "TestFirst", "TestLast", "10001"

**INSTRUCTIONS TO CONVERT:**
{instructions}

**RESPOND WITH JSON ARRAY (extract actual values from instructions!):**
[
  {{"action": "navigate", "url": "<extracted URL>"}},
  {{"action": "fill", "target": "<field name>", "value": "<VALUE FROM INSTRUCTION>"}},
  {{"action": "click", "target": "<button/element>"}},
  ...
]

Only output the JSON array, nothing else.'''



async def normalize_instructions(
    instructions: List[str],
    llm_provider: "ILLMProvider",
    timeout_seconds: int = 30,
) -> List[dict]:
    """
    Normalize a list of natural language instructions into standard format.
    
    Args:
        instructions: List of natural language instructions
        llm_provider: LLM provider for normalization
        timeout_seconds: Timeout for LLM call
        
    Returns:
        List of normalized instruction dicts
    """
    import asyncio
    import json
    from llm_web_agent.interfaces.llm import Message
    
    # Format instructions for prompt
    instructions_text = "\n".join(f"{i}. {inst}" for i, inst in enumerate(instructions, 1))
    
    prompt = NORMALIZE_PROMPT.format(instructions=instructions_text)
    
    try:
        # Use complete() with Message objects
        messages = [Message.user(prompt)]
        
        response = await asyncio.wait_for(
            llm_provider.complete(messages, temperature=0.3),
            timeout=timeout_seconds,
        )
        
        # Extract content from LLMResponse
        response_text = response.content.strip()
        
        # Handle markdown code blocks
        if "```json" in response_text:
            start = response_text.index("```json") + 7
            end = response_text.index("```", start)
            response_text = response_text[start:end]
        elif "```" in response_text:
            start = response_text.index("```") + 3
            end = response_text.index("```", start)
            response_text = response_text[start:end]
        
        normalized = json.loads(response_text.strip())
        
        if not isinstance(normalized, list):
            logger.warning("LLM did not return a list")
            return []
        
        logger.info(f"Normalized {len(instructions)} instructions into {len(normalized)} actions")
        return normalized
        
    except asyncio.TimeoutError:
        logger.error(f"Instruction normalization timed out after {timeout_seconds}s")
        return []
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse normalized instructions: {e}")
        return []
        
    except Exception as e:
        logger.error(f"Instruction normalization failed: {e}")
        return []


def normalized_to_instruction(action: dict) -> str:
    """
    Convert a normalized action dict back to a simple instruction string.
    """
    action_type = action.get("action", "").lower()
    
    if action_type == "navigate":
        url = action.get("url", "")
        return f"go to {url}"
    
    elif action_type == "click":
        target = action.get("target", "")
        return f"click {target}"
    
    elif action_type == "fill":
        target = action.get("target", "")
        value = action.get("value", "")
        return f"enter {target} {value}"
    
    elif action_type == "type":
        value = action.get("value", "")
        return f'type "{value}"'
    
    elif action_type == "scroll":
        direction = action.get("direction", "down")
        return f"scroll {direction}"
    
    elif action_type == "wait":
        target = action.get("target") or action.get("seconds", "2")
        return f"wait for {target}"
    
    elif action_type == "press":
        key = action.get("key", "enter")
        return f"press {key}"
    
    elif action_type == "screenshot":
        return "take a screenshot"
    
    elif action_type == "hover":
        target = action.get("target", "")
        return f"hover {target}"
    
    else:
        return action.get("description", str(action))
