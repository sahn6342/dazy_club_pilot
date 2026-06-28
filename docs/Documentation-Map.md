# Documentation Map

| Phase | Primary Docs | Consumed By |
|---|---|---|
| Context | PROJECT_CONTEXT.md, Master-Index.md, Decision-Log.md | Everyone |
| Product | PRD, MVP Scope, Functional Requirements, Personas, Journeys, Screens, Acceptance Criteria | Figma, frontend, API, QA |
| Architecture | System, Frontend, Backend, API Catalog, Auth, Booking, Pricing, Security, Deployment | backend, frontend, infra |
| Database | Database README, ER, Constraints, Indexes, Migrations, Entity Specs | backend, QA |
| Design | Brand, Design Principles, Design System, Responsive, Motion, Tokens, Components, Wireframes | Figma, frontend |
| Figma | Figma pages and handoff notes | frontend, product review |
| Implementation | Coding Order, Feature Matrix, Milestones, Codegen Tasks | coding agents |
| Testing | Testing Strategy, Acceptance Criteria, Traceability Matrix | QA, CI |
| Release | Launch Checklist, Definition of Done, Required Files | release owner |

## Authoritative Reading Order
1. PROJECT_CONTEXT.md
2. docs/product/PRD.md
3. docs/product/MVP-Scope.md
4. docs/Decision-Log.md
5. docs/Traceability-Matrix.md
6. docs/foundation/Brand-Guidelines.md
7. docs/design-system/Tokens.md
8. docs/architecture/System-Architecture.md
9. docs/architecture/API-Catalog.md
10. docs/implementation/README.md

## Duplicate Or Placeholder Treatment
- Existing generated docs with only a heading or one sentence are placeholders.
- Placeholder docs should not override expanded source-of-truth docs.
- Before implementation, update the relevant source-of-truth doc and trace it to acceptance criteria.
