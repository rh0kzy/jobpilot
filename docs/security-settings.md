# Writable settings security

Settings (AI/search provider + keys) can be edited at runtime via `/settings` when `SETTINGS_WRITABLE=true`.
- Validate the `Host` header against `JOBPILOT_ALLOWED_HOSTS`.
- Mutating requests require the custom header `X-JobPilot-Token` matching the local token.
- Saved values are stored in a local config file outside version control with file mode `0600`.
- Saved settings override `.env` defaults.
- `GET /settings` returns only a masked key; `PUT /settings` saves; `POST /settings/test-key` validates.
- `GET /settings/token` returns the local token to the web app at runtime (localhost only); alternatively set `JOBPILOT_SETTINGS_TOKEN` in the environment.
- Keys are never logged or returned in full.
- For local dev, bind the API to `127.0.0.1` and allow CORS only from the web app origin.
- For any non-local deployment, set `SETTINGS_WRITABLE=false`.