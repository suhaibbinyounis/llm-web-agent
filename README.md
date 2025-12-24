# LLM Web Agent

> A research-driven approach to browser automation combining pattern-based element resolution with LLM intelligence for robust, fast, and natural web interactions.

[![CI](https://github.com/suhaibbinyounis/llm-web-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/suhaibbinyounis/llm-web-agent/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🔬 Research Context

This project explores a critical question in AI-driven browser automation:

**How can we build web agents that are both fast AND robust, without relying entirely on expensive LLM calls for every interaction?**

### The Problem with Current Approaches

| Approach | Speed | Robustness | Cost | Limitation |
|----------|-------|------------|------|------------|
| **Pure LLM Agents** (GPT-4V, Claude) | Slow (5-20s/action) | High | $$$ | Every action requires LLM call |
| **Traditional Automation** (Selenium scripts) | Fast | Low | $ | Brittle selectors break easily |
| **Visual AI** (Computer Vision) | Medium | Medium | $$ | Needs screenshots, slow processing |

### Our Hypothesis

> **Pattern-based element resolution can handle 90%+ of web interactions at 10x the speed, with LLM as an intelligent fallback for edge cases.**

## 🎯 Key Research Contributions

### 1. Intelligent Resolution Architecture (v3 - DOMMap)

We implement a sophisticated **multi-layered resolution engine** that combines speed, adaptability, and robustness:

```mermaid
graph TD
    A["Request: 'Click Submit'"] --> B{"Layer 0: DOMMap"}
    B -->|O(1) Multi-Index| C["Fingerprint + Selector"]
    B -->|Miss| D{"Layer 1: Direct/Index"}
    D -->|Direct Selector| E["CSS/XPath Match"]
    D -->|Miss| F{"Layer 2: Parallel Race"}
    F -->|Simultaneous| G["Text First"]
    F -->|Simultaneous| H["Playwright"]
    F -->|Simultaneous| I["Smart Selectors"]
    F -->|All Fail| J{"Layer 3: Fallback"}
    J -->|Scoring| K["Fuzzy Search"]
    J -->|Async Match| L["Dynamic Wait"]
    
    style B fill:#9f9,stroke:#333
    style C fill:#9f9,stroke:#333
    style F fill:#bbf,stroke:#333
    style J fill:#f9f,stroke:#333
```

**Key Innovations:**

*   **DOMMap Real-Time Registry**: Persistent multi-index map (text, aria-label, role, data-testid, placeholder, fingerprint) with O(1) lookups. Built once per page, automatically refreshes on stale detection.
*   **Element Fingerprinting**: Stable 12-character hashes for elements that survive page refreshes and CSS-in-JS class changes. Uses multi-signal approach (text, aria, position, stable classes).
*   **Framework Hints**: Pattern library for MUI, Ant Design, Chakra, React-Select, Bootstrap, and Headless UI components.
*   **Spatial Grid Index**: Grid-based spatial index for relational queries like *"Click Submit near Email"*.
*   **O(1) Text Indexing**: Builds an inverted index of the page for instant lookups, treating the DOM like a database.
*   **Parallel Execution**: Races 3 different strategies simultaneously (Text, Playwright, Smart) instead of trying them sequentially.
*   **Spatial Resolution**: Understands layout queries like *"Click Submit near Email"* using the spatial index.
*   **Adaptive Learning**: Tracks success rates per-domain and auto-adjusts strategy ordering (e.g., learns that `TextFirst` works best on GitHub but `Playwright` works best on React sites).
*   **Exponential Backoff**: Adaptive waiting (100ms → 3s) for dynamic elements to appear.

### 2. Framework-Agnostic Design

Unlike approaches that require framework-specific knowledge, our agent works equally well on:
- Static HTML sites
- React/Next.js applications
- Angular applications
- Material UI components
- Any JavaScript framework

**Why it works**: We target rendered text and semantic HTML, not implementation details.

### 3. Intelligent Code Container Detection

Web pages often contain code samples that should NOT be clicked. Our `isCodeContainer()` heuristic automatically skips:
- `<textarea>`, `<pre>`, `<code>` elements
- Elements with classes containing "code", "editor", "syntax"
- `contenteditable` elements
- **Semantic patterns** like `import`, `function`, `=>`, JSX syntax.

This prevents the agent from mistakenly interacting with documentation code samples.

### 4. Dynamic Element Handling

Modern web apps use dropdowns, modals, and popovers that only appear after interaction. Our `DYNAMIC` strategy uses:
- **Exponential Backoff**: Adaptive waits (100ms, 300ms, 1s, 3s)
- **Action Context**: Tracks newly appeared elements after a click
- Playwright's `waitForSelector` for reliable visibility

This successfully handles dropdown options, modals, and popovers without explicit waits.

---

## 📊 Performance Benchmarks

### Speed Comparison (Action Execution Time)

| Site | Action | Before Optimization | After Optimization | Improvement |
|------|--------|---------------------|-------------------|-------------|
| GitHub | Click "Sign in" | Failed | 2.7s | ✅ Fixed |
| DuckDuckGo | Search | Failed | 1.4s | ✅ Fixed |
| Bing | Search + Enter | 71s | 3.7s | **19x faster** |
| MUI.com | 7-step navigation | - | 2.4s | ~0.3s/step |
| DemoQA | 11-field form fill | - | 33.4s | ~3s/step |

### Complex Task Performance

| Test Case | Steps | Success Rate | Duration |
|-----------|-------|--------------|----------|
| MUI docs navigation | 12 | 12/12 (100%) | 8.4s |
| Form filling (all field types) | 11 | 11/11 (100%) | 33.4s |
| React component interaction | 7 | 7/7 (100%) | 2.4s |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     USER INSTRUCTION                                 │
│       "Fill the form with name John, email test@example.com"        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INSTRUCTION PARSER                                │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐    │
│  │   Pattern   │───▶│  LLM Fallback │───▶│   Structured Steps   │    │
│  │   Matching  │    │  (if needed)  │    │                     │    │
│  └─────────────┘    └──────────────┘    └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TARGET RESOLVER                                  │
│                                                                      │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────┐ ┌─────────┐    │
│  │  DIRECT  │▶│TEXT_FIRST │▶│PLAYWRIGHT│▶│ SMART │▶│ DYNAMIC │    │
│  │  <1ms    │ │  ~50ms    │ │  ~100ms  │ │~200ms │ │ ~3000ms │    │
│  └──────────┘ └───────────┘ └──────────┘ └───────┘ └─────────┘    │
│                                                                      │
│  Innovation: 6-layer cascade with automatic fallback                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  
┌─────────────────────────────────────────────────────────────────────┐
│                     BATCH EXECUTOR                                   │
│  • Groups compatible actions for efficient execution                │
│  • Batches form fills via single JavaScript call                    │
│  • Implements retry logic with LLM-powered recovery                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Installation

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

### Basic Usage

```bash
# Run with natural language instruction
llm-web-agent run "go to google.com, search for Python tutorials"

# Run with visible browser (for debugging)
llm-web-agent run "go to github.com, click Sign in" --visible
```

### Python API

```python
import asyncio
from llm_web_agent import Agent

async def main():
    agent = Agent()
    async with agent:
        result = await agent.run(
            "Go to demoqa.com/automation-practice-form, "
            "type 'John' in First Name, "
            "type 'Doe' in Last Name, "
            "click Male, click Submit"
        )
        print(f"Success: {result.success}")
        print(f"Steps: {result.steps_completed}")

asyncio.run(main())
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# LLM Provider (required for instruction parsing)
OPENAI_API_KEY=sk-your-key-here
# Or use local endpoint
LLM_WEB_AGENT__LLM__BASE_URL=http://127.0.0.1:3030

# Browser settings
LLM_WEB_AGENT__BROWSER__HEADLESS=true
```

### Supported LLM Providers

| Provider | Configuration |
|----------|--------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| GitHub Copilot | Via [github-copilot-api-vscode](https://github.com/suhaibbinyounis/github-copilot-api-vscode) |
| Local LLMs | Any OpenAI-compatible endpoint |

---

## 🔄 How This Differs from Other Projects

### vs. browser-use / Playwright Codegen
- **browser-use**: Relies on LLM for every action → slower, costly
- **Our approach**: Pattern-first with LLM fallback → 10x faster for common cases

### vs. GPT-4V / Claude Vision
- **Vision models**: Screenshot → process → action (~5-20s per step)
- **Our approach**: DOM-based resolution (~0.1-0.5s per step)

### vs. Traditional Test Automation
- **Selenium/Cypress**: Hardcoded selectors that break easily
- **Our approach**: Natural language + multi-strategy resolution = robust

### Unique Contributions
1. **TEXT_FIRST strategy**: Human-like element finding via TreeWalker
2. **6-layer resolution cascade**: Automatic fallback with speed priority
3. **Code container detection**: Avoids clicking on documentation code samples
4. **Dynamic element waiting**: Handles React-Select, MUI components, modals

---

## 🧪 Current Status

### What Works Well
- ✅ Text input filling (by placeholder, label, name)
- ✅ Button/link clicking (by visible text)
- ✅ Radio buttons and checkboxes
- ✅ Form submission
- ✅ Multi-step navigation
- ✅ React/Angular/MUI components
- ✅ Scroll actions

### Known Limitations
- ⚠️ Complex dropdowns (React-Select) require exact option text
- ⚠️ Elements behind sticky headers may need scroll adjustment
- ⚠️ File uploads not fully implemented

### Roadmap
- [ ] Improved dropdown/select handling
- [ ] Vision-assisted fallback for complex layouts
- [ ] Recording and playback improvements
- [ ] Plugin system for custom actions

---

## 🛠️ Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter
ruff check .

# Format code
ruff format .
```

---

## 📚 Project Structure

```
src/llm_web_agent/
├── engine/           # Core execution engine
│   ├── engine.py          # Main orchestrator
│   ├── instruction_parser.py  # NL → structured steps
│   ├── target_resolver.py     # 7-layer element resolution
│   ├── dom_map.py             # Real-time DOM registry (O(1) lookups)
│   ├── fingerprint.py         # Stable element identification
│   ├── framework_hints.py     # UI framework patterns (MUI, Ant, etc.)
│   ├── text_index.py          # Inverted text index
│   ├── batch_executor.py      # Optimized action execution
│   └── state_manager.py       # Page state tracking
├── browsers/         # Browser adapters (Playwright, Selenium)
├── llm/              # LLM provider integrations
├── actions/          # Action implementations
├── modes/            # Execution modes (NL, Guided, Record)
└── cli/              # Command-line interface
```

---

## 📖 Citation

If you use this project in your research, please cite:

```bibtex
@software{llm_web_agent,
  author = {Suhaib Bin Younis},
  title = {LLM Web Agent: Pattern-First Browser Automation with LLM Intelligence},
  year = {2024},
  url = {https://github.com/suhaibbinyounis/llm-web-agent}
}
```

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

<p align="center">
  <sub>Built with ❤️ as part of ongoing research in AI-driven web automation</sub>
</p>
