# API Standards

## Versioning
Use `/api/v1` for all launch endpoints.

## Request/Response
- Use JSON.
- Use explicit DTOs.
- Validate all incoming request bodies.
- Return consistent error shapes with code, message, and field errors where applicable.

## Errors
- 400 for validation failures.
- 404 for missing resources.
- 409 for future booking conflicts.
- 500 only for unexpected server errors.

## Naming
- Resource paths are plural nouns.
- Commands use POST where they create state or trigger workflow.
- Future booking/payment/OTP routes stay reserved until implemented.
