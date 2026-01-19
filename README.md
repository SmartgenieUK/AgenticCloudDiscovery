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
