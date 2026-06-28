# PostgreSQL Standards

- UUID primary keys (gen_random_uuid())
- timestamptz for all timestamps
- snake_case naming
- FK constraints mandatory
- CHECK constraints for enums where applicable
- JSONB only for flexible metadata
