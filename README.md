# EdNet AI Tutor — Demo

A two-part web app for TOEIC learning analytics, AI coaching, and **autoregressive multi-model daily-challenge prediction**.

The backend loads the engineered-features parquet, scores users with **5 trained models** (XGBoost, RandomForest, LightGBM, LSTM-raw, 1D-CNN-raw), and asks an LLM (OpenAI by default, Groq as fallback) for personalized feedback. The frontend is a Vite + React dashboard.

## Features

- Personalized dashboard loaded by user ID
- Daily and weekly progress tracking
- Part-by-part skill matrix for TOEIC Parts 1–7
- AI-generated coaching feedback and study suggestions
- Live test submission flow with immediate feedback
- **Daily Challenge**: pick N questions for the day; the 5 models autoregressively predict your expected number correct, with click-to-expand per-part breakdown and per-question detail

## Project Layout

```
backend/
  main.py                       FastAPI app + endpoints
  challenge.py                  Daily Challenge: model loading + autoregressive loop
  scripts/download_models.py    One-shot fetch of all weights + parquet from Drive
  models/                       (gitignored) trained model files — see Setup
  data/                         (gitignored) kt4_features_1.parquet — see Setup
  .env                          (gitignored) your local OPENAI_API_KEY — see Setup
  .env.example                  template
  requirements.txt
frontend/
  src/App.tsx                   all UI (sidebar, dashboard tabs, Daily Challenge)
  src/services/aiService.ts     API client
  package.json
```

## Requirements

- Python 3.10+
- Node.js 18+, npm
- Disk: ~1.2 GB (parquet ≈ 955 MB, models ≈ 170 MB)
- An **OpenAI API key** for AI coaching (Groq is supported as fallback)

## Setup

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### Configure your API key

```bash
cp .env.example .env
# edit .env and paste your OPENAI_API_KEY
```

#### Download the model weights and dataset

The model weights and the engineered-features parquet are large and not in git. Run the included downloader — it pulls everything from the team's Google Drive into `backend/models/` and `backend/data/`:

```bash
python scripts/download_models.py
```

This is idempotent — files already present are skipped. Total download is ~1.2 GB.

If the downloader fails or you prefer to do it manually, the source folders are:

| File | Drive folder | Goes to |
|---|---|---|
| `xgboost_final_model.json` | [Phương](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) | `backend/models/` |
| `random_forest_final_model.pkl` | [Phương](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) | `backend/models/` |
| `kt4_features_1.parquet` | [Phương](https://drive.google.com/drive/folders/1-oz4zf1CzahKMH2GSeSEjsfT5JhMDGo_?usp=sharing) | `backend/data/` |
| `lightgbm_final_model.pkl` | [Nguyễn](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) | `backend/models/` |
| `ednet_lstm_11_features.keras` | [Nguyễn](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) | `backend/models/` |
| `ednet_lstm_raw.keras` | [Nguyễn](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) | `backend/models/` |
| `ednet_1d_cnn_raw.keras` | [Nguyễn](https://drive.google.com/drive/folders/1ykpN1phTtHSytuGXW65Sx3FMZCrBu397?usp=sharing) | `backend/models/` |

Filenames must match exactly — `challenge.py` looks them up by name in `backend/models/`. The 6th model (`ednet_lstm_11_features.keras`) is downloaded for completeness but **not used by the demo** — it's flagged broken (AUC ≈ 0.5011) in the master branch's modeling reports.

#### Start the API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

First start takes ~30–60 seconds: the parquet (~1 GB) is loaded into memory and all 5 models are loaded.

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

The app is at http://localhost:3000. The frontend defaults to `http://localhost:8000/api`; override with `VITE_API_URL` if needed.

## API Endpoints

### `GET /api/dashboard/{user_id}`
14 days of synthetic activity, AI coaching feedback, today's focus tasks, focus date label.

### `POST /api/live-test/{user_id}`
Body: `{ answers: [{questionId, isCorrect, timeTaken}] }`. Returns live accuracy, next-question prediction, short coaching message and correction.

### `GET /api/daily-challenge/models`
Returns the 5 supported models with `ready` flag and load errors. Use this to discover which models are available before calling the next endpoint.

### `POST /api/daily-challenge/{user_id}`
Body:
```json
{
  "totalN": 10,                     // OR perPart, not both
  "perPart": {"1": 3, "5": 5, "7": 2},
  "models": ["xgboost", "lightgbm"],
  "seed": 277461                    // optional; same seed = same simulated questions across models
}
```
Returns per-model `expectedCorrect` (sum of per-q probabilities) + `perQuestionProbs` array, plus the resolved part plan and any per-model errors.

The autoregressive loop:
1. Sample non-target features for question N (difficulty from the user's own historical part-conditional distribution; ambient features from their empirical pool; timestamps anchored on their last row + sampled inter-question deltas).
2. Predict P(correct) using the currently configured model.
3. Update the running aggregates (overall / part / recent / listening / reading accuracy, attempts count) using the predicted probability as a soft outcome.
4. For sequence models, also feed P(correct) back as the shifted-`is_correct` channel for question N+1.
5. Repeat for question N+1.

Output `expectedCorrect = Σ perQuestionProbs`.

## Notes

- The backend uses CORS permissively for local development.
- LSTM-raw and 1D-CNN-raw need TensorFlow (~600 MB install). The first `pip install` is slow; subsequent runs are fast.
- The demo intentionally excludes `lstm-11-features` from the Daily Challenge results — see master branch's `output/modeling/reports/cross_member_review.md` §4.

## Development Commands

```bash
# backend
uvicorn main:app --reload

# frontend
npm run dev
npm run build
npm run lint
```

## License

No license file is included in this repository.
