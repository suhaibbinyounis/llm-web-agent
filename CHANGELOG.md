# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-12-24

### Added

- **Core Architecture**
  - Agent, Planner, Executor core components
  - Abstract interfaces (IBrowser, ILLMProvider, IAction, IDataExtractor)
  - Component registry with decorator-based registration
  - Pydantic configuration with YAML and environment variable support

- **Browser Support**
  - Playwright browser implementation (complete)
  - Selenium browser stub (planned)

- **LLM Providers**
  - OpenAI provider with vision and tool calling
  - Anthropic provider stub
  - GitHub Copilot API Gateway provider

- **Interaction Modes**
  - Natural Language mode - describe tasks in plain English
  - Record & Replay mode - capture and replay user actions
  - Guided mode - natural language + explicit selectors

- **Intelligence Module**
  - DOM parser and simplifier
  - Selector generator
  - Intent parser and entity extractor
  - Task decomposer and action mapper

- **Reporting**
  - Run reports with HTML/PDF/JSON export
  - Step-by-step logging
  - Screenshot and artifact management

- **Control Center**
  - Policy engine for domain/action restrictions
  - Credential vault with pluggable backends
  - Sensitive data detector and redactor

- **Context Management**
  - Document loaders for Text, JSON, CSV
  - Context manager with template variable resolution

- **GUI**
  - FastAPI-based web server
  - API routes for agent control, config, and runs

### Infrastructure

- Project structure with pyproject.toml
- Makefile for common development tasks
- Pytest configuration with fixtures
- Type hints and mypy configuration
- Ruff and Black for linting/formatting
