# ADR-001: AI-Assisted Documentation-First Workflow

## Status
Accepted

## Context
The repo began as a generated documentation set. Implementation work needs a reliable source of truth so agents and engineers do not invent scope.

## Decision
Use an AI-assisted documentation-first workflow. Product, architecture, design, database, testing, and implementation docs must be refined before Figma and code generation.

## Alternatives Considered
- Start coding from generated placeholder docs.
- Design directly in Figma without traceable requirements.

## Consequences
- More up-front documentation work.
- Lower risk of building unsupported scope.
- Requirements can be traced to screens, APIs, entities, and tests.
