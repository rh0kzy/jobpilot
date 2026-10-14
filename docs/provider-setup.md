# Provider setup

Free options: Google Gemini, Groq, Ollama (local). Each provider is implemented behind a single interface in `apps/api/app/providers`. SDKs are optional dependency groups; install only what you use. Set `AI_PROVIDER` and `AI_MODEL` plus the matching key in `.env`. The app should clearly tell the user when the AI key is missing or invalid (first-run check in docs only).