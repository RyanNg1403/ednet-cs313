# EdNet AI Tutor

EdNet AI Tutor is a two-part web app for TOEIC learning analytics and AI coaching.

The backend loads historical learner features, scores the latest session with an XGBoost model, and asks an AI model for personalized feedback. The frontend presents the learner dashboard, skill breakdowns, and live coaching UI.

## Features

- Personalized dashboard loaded by user ID
- Daily and weekly progress tracking
- Part-by-part skill matrix for TOEIC Parts 1-7
- AI-generated coaching feedback and study suggestions
- Live test submission flow with immediate feedback

## Project Layout

- `backend/` FastAPI service, model loader, and API endpoints
- `frontend/` Vite + React dashboard UI
- `backend/models/xgboost_final_model.json` trained XGBoost model used by the API
- `backend/data/kt4_features_1.parquet` expected feature dataset for each learner

## Requirements

- Python 3.10+
- Node.js 18+
- npm
- A valid `GROQ_API_KEY` for AI coaching responses
- The dataset file `backend/data/kt4_features_1.parquet`

The backend can start without `GROQ_API_KEY`, but coaching responses will fall back to a simpler offline message.
The backend code also imports `groq`; if your environment does not already include it, install that package before starting the API.

## Setup

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local environment file or export the variable in your shell:

```bash
export GROQ_API_KEY="your_api_key_here"
```

Make sure the expected data file exists at:

```text
backend/data/kt4_features_1.parquet
```

Then run the API:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
```

The frontend defaults to `http://localhost:8000/api`, but you can override it with `VITE_API_URL` if needed:

```bash
export VITE_API_URL="http://localhost:8000/api"
```

Run the UI:

```bash
npm run dev
```

The app will be available at `http://localhost:3000`.

## API Endpoints

### `GET /api/dashboard/{user_id}`

Returns:

- 14 days of synthetic activity history derived from the user profile
- AI coaching feedback
- Today-focused study tasks
- A focus date label

### `POST /api/live-test/{user_id}`

Accepts a list of answer results and returns:

- Live accuracy
- Updated next-question prediction
- Short feedback message
- A concrete next-step correction

## Notes

- The backend uses CORS permissively for local development.
- The frontend uses the API base URL from `VITE_API_URL` when present.
- If you do not have the dataset file, the dashboard endpoint will return a dataset loading error.

## Development Commands

Backend:

```bash
uvicorn main:app --reload
```

Frontend:

```bash
npm run dev
npm run build
npm run lint
```

## License

No license file is included in this repository.