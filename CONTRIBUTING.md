# Contributing to LLM Web Agent

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/llm-web-agent.git
   cd llm-web-agent
   ```
3. **Set up the development environment**:
   ```bash
   make install-dev
   playwright install chromium
   ```

## Development Workflow

### Branch Naming

- `feat/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions/changes

### Making Changes

1. Create a new branch from `main`
2. Make your changes
3. Run tests: `make test`
4. Run linter: `make lint`
5. Format code: `make format`
6. Commit with a descriptive message

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new browser action
fix: resolve element selector issue
docs: update README with examples
refactor: simplify DOM parser logic
test: add unit tests for planner
```

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Request a review from maintainers

## Code Style

- Use **Black** for Python formatting
- Use **Ruff** for linting
- Use **mypy** for type checking
- Follow PEP 8 guidelines
- Add docstrings to all public functions/classes

## Architecture Guidelines

- Follow the existing modular architecture
- Use abstract interfaces for new components
- Register new components with the `ComponentRegistry`
- Keep configuration externalized (no hardcoding)

## Adding New Components

### New Browser Engine

```python
from llm_web_agent.interfaces.browser import IBrowser
from llm_web_agent.registry import register_browser

@register_browser("my_browser")
class MyBrowser(IBrowser):
    # Implement all abstract methods
    ...
```

### New LLM Provider

```python
from llm_web_agent.interfaces.llm import ILLMProvider
from llm_web_agent.registry import register_llm

@register_llm("my_provider")
class MyProvider(ILLMProvider):
    # Implement all abstract methods
    ...
```

## Questions?

Feel free to open an issue for any questions or discussions.
