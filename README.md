# AgenticCloudDiscovery

Minimal authentication slice for the Agentic Cloud Discovery MVP.

## Running locally
1. Copy `.env.example` to `.env` and fill Cosmos/secret values.
2. Backend (FastAPI):
   - `python -m venv .venv && .venv\\Scripts\\activate`
   - `pip install -r agent-orchestrator/requirements.txt`
   - `uvicorn main:app --app-dir agent-orchestrator --reload --port 8000`
3. Frontend (React + Vite):
   - `cd client-ui`
   - `npm install`
   - `npm run dev`
4. Visit http://localhost:5173 to use the login screen.

## OAuth setup (Google / Microsoft)
- Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` to match your Google OAuth app.
- Set `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_REDIRECT_URI` to match your Microsoft app (consumer-friendly tenant).
- Ensure redirect URIs in provider consoles match the callback endpoints exposed by the backend (e.g., `http://localhost:8000/auth/oauth/google/callback`).
