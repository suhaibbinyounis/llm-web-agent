# LLM Web Agent

A universal browser automation agent powered by large language models. Transform natural language instructions into precise browser actions — from navigation and form-filling to complex multi-step workflows.

## ✨ Features

- 🗣️ **Natural Language Interface** - Describe tasks in plain English
- 🎥 **Record & Replay** - Perform actions once, replay them automatically
- 🎯 **Guided Mode** - Combine natural language with explicit selectors for accuracy
- 🔄 **Model Agnostic** - Works with OpenAI, Anthropic, GitHub Copilot, and more
- 🌐 **Browser Agnostic** - Supports Playwright (default) and Selenium
- ⚙️ **Fully Configurable** - YAML configs, environment variables, CLI args
- 🔌 **Plugin Architecture** - Easy to extend with new browsers, LLMs, and actions
- 📊 **Comprehensive Reporting** - Run logs, screenshots, video recording
- 🔒 **Enterprise Control Center** - Policies, credential vault, PII detection
- 📄 **Document Context** - Load PDFs, CSVs, JSONs as automation context

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/suhaibbinyounis/llm-web-agent.git
cd llm-web-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e ".[all]"

# Install Playwright browsers
playwright install chromium
```

## 📖 Quick Start

### Mode 1: Natural Language

```python
import asyncio
from llm_web_agent import Agent

async def main():
    agent = Agent()
    async with agent:
        result = await agent.run("Go to google.com and search for Python tutorials")
        print(f"Success: {result.success}")

asyncio.run(main())
```

### Mode 2: Record & Replay

```python
from llm_web_agent.modes import RecordReplayMode

# Record user actions
mode = RecordReplayMode()
await mode.start(page, config)
await mode.start_recording()
# ... user performs actions manually ...
recording = await mode.stop_recording()
mode.save_recording(recording, "my_workflow.json")

# Replay later
await mode.execute("my_workflow.json")
```

### Mode 3: Guided (NL + Selectors)

```python
from llm_web_agent.modes import GuidedMode, GuidedTaskInput, LocatorHint

task = GuidedTaskInput(
    task="Login to the application",
    hints=[
        LocatorHint(name="email", selector="#email"),
        LocatorHint(name="password", selector="#password"),
        LocatorHint(name="submit", selector="button[type='submit']"),
    ],
    data={
        "email": "user@example.com",
        "password": "secret123",
    },
)
result = await guided_mode.execute(task)
```

## ⚙️ Configuration

### Environment Variables

```bash
# LLM Provider
OPENAI_API_KEY=sk-your-key-here
LLM_WEB_AGENT__LLM__PROVIDER=openai
LLM_WEB_AGENT__LLM__MODEL=gpt-4o

# Browser
LLM_WEB_AGENT__BROWSER__HEADLESS=true
```

### YAML Config

```yaml
browser:
  engine: playwright
  headless: true

llm:
  provider: openai
  model: gpt-4o
  temperature: 0.3

agent:
  max_steps: 20
  verbose: true
```

## 🏗️ Architecture

### How It Works

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER INSTRUCTION                                 │
│        "Go to amazon.com, search for laptops, copy the first price"         │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          INSTRUCTION PARSER                                   │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │ Pattern Match   │────▶│ Split Clauses   │────▶│  Build Graph    │        │
│  │ (Fast, No LLM)  │     │                 │     │                 │        │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘        │
│           │                                              │                   │
│           │ (unmatched)                                  ▼                   │
│           └──────────────▶ LLM Fallback ──────▶   TaskGraph                 │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              TASK GRAPH                                       │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐                │
│  │ Step 1  │────▶│ Step 2  │────▶│ Step 3  │────▶│ Step 4  │                │
│  │navigate │     │  fill   │     │  click  │     │ extract │                │
│  │amazon   │     │ search  │     │ result  │     │  price  │                │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘                │
│                                                                              │
│  Batching: [Step 1] → [Step 2,3] → [Step 4]                                 │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           BATCH EXECUTOR                                      │
│                                                                              │
│  For each batch:                                                             │
│   1. Parse DOM once (cached)                                                 │
│   2. Resolve all targets upfront                                             │
│   3. Execute actions sequentially                                            │
│   4. Batch form fills via JavaScript (fast!)                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    TARGET RESOLVER                                  │     │
│  │  Layer 1: Exact Match   (#id, [data-testid], [name])   ─────┐      │     │
│  │  Layer 2: Text Match    (button:has-text("Login"))     ─────┤      │     │
│  │  Layer 3: Fuzzy Match   (similarity scoring)           ─────┼──▶ ✓ │     │
│  │  Layer 4: LLM Fallback  (send DOM, ask LLM)            ─────┘      │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                             RUN CONTEXT                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  clipboard: { "price": "$299.99" }     ◀── extracted data           │    │
│  │  variables: { "search_term": "laptops" }                            │    │
│  │  history: [action1 ✓, action2 ✓, ...]                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Template Resolution: "Price is {{price}}" → "Price is $299.99"             │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              RESULT                                           │
│  {                                                                           │
│    success: true,                                                            │
│    steps_completed: 4,                                                       │
│    extracted_data: { "price": "$299.99" },                                   │
│    duration_seconds: 3.2                                                     │
│  }                                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

| Principle | How We Achieve It |
|-----------|-------------------|
| **Speed First** | Pattern matching before LLM, batch DOM operations, JS form fills |
| **LLM as Fallback** | 4-layer target resolution uses LLM only when heuristics fail |
| **Memory/Clipboard** | `RunContext` stores extracted data for cross-step references |
| **Batch Operations** | Multiple fills on same page execute in one JS call |
| **Smart Grouping** | Steps auto-grouped by page context, dependencies respected |

### Module Structure

```
src/llm_web_agent/
├── engine/         # 🧠 Core execution (NEW)
│   ├── engine.py           # Main orchestrator
│   ├── run_context.py      # Memory/clipboard
│   ├── task_graph.py       # Step dependencies
│   ├── instruction_parser.py  # NL → steps
│   ├── target_resolver.py  # Element finding
│   ├── batch_executor.py   # Optimized execution
│   └── state_manager.py    # Page transitions
├── core/           # Agent, Planner, Executor
├── interfaces/     # Abstract base classes
├── browsers/       # Playwright, Selenium
├── llm/            # OpenAI, Anthropic, Copilot
├── actions/        # Click, Fill, Navigate, etc.
├── modes/          # NL, Record/Replay, Guided
├── intelligence/   # DOM parsing, NLP
├── reporting/      # Run reports, screenshots
├── control/        # Policies, security
├── context/        # Document loaders
├── gui/            # Web-based control UI
├── config/         # Settings management
├── registry/       # Plugin registration
└── utils/          # Logging, retry, helpers
```

## 🛠️ Development

```bash
# Install dev dependencies
make install-dev

# Run tests
make test

# Run linter
make lint

# Format code
make format
```

## 📦 Project Stats

- **82+ Python files**
- **27 directories**
- **14 modules**

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

