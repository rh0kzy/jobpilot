# Privacy

CVs are handled locally and not stored by default (in-memory for MVP). The CV is only sent to the AI provider the user explicitly chose. For a fully local mode, use Ollama. Optional SQLite in v1.1 stores saved profile and seen jobs on the user's machine.

AI/search keys are stored locally with mode `0600` when written via the Settings screen (saved settings override `.env`). The API key is only sent to the provider the user chose.