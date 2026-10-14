# How to add a connector

1. Create a new module under `apps/api/app/connectors/`.
2. Implement `BaseConnector` from `base.py`: set `name`, implement `fetch`.
3. Add tests under `apps/api/tests/` using anonymized fixtures.
4. Document the source in `docs/sources-and-terms.md` including attribution and rate limits.