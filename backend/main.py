import os
import json
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
import polars as pl
import numpy as np
import xgboost as xgb
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="EdNet AI Coaching Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to hold data and models
df_features = None
xgb_model = None

# Model features expected by XGBoost
MODEL_FEATURES = [
    'feat_question_difficulty', 'feat_current_part_accuracy', 'feat_answer_changes', 
    'feat_overall_accuracy', 'feat_reading_accuracy', 'feat_recent_accuracy', 
    'feat_is_rapid_guess', 'part', 'feat_total_attempts', 'feat_listening_accuracy', 
    'feat_explanation_ratio'
]

@app.on_event("startup")
async def startup_event():
    global df_features, xgb_model
    logging.info("Loading dataset...")
    try:
        # Load the features parquet file
        df_features = pl.read_parquet("data/kt4_features_1.parquet")
        # Ensure timestamp is numeric
        df_features = df_features.with_columns(pl.col('timestamp').cast(pl.Float64, strict=False))
        # Sort by user_id and timestamp for easier processing
        df_features = df_features.sort(['user_id', 'timestamp'])
        logging.info(f"Loaded dataset with {len(df_features)} rows.")
    except Exception as e:
        logging.error(f"Failed to load dataset: {e}")

    logging.info("Loading XGBoost model...")
    try:
        xgb_model = xgb.Booster()
        xgb_model.load_model("models/xgboost_final_model.json")
        logging.info("XGBoost model loaded successfully.")
    except Exception as e:
        logging.error(f"Failed to load model: {e}")

    # Configure Groq
    api_key = os.getenv("GROQ_API_KEY")
    if api_key and api_key != "your_api_key_here":
        logging.info("Groq API key configured.")
    else:
        logging.warning("GROQ_API_KEY not set or invalid. AI features might fail if key is not in environment.")


def generate_mock_history(user_data):
    # If the user has data, we map it into 14 days of history
    # For a real app, we'd aggregate timestamps. Here, we'll map the latest 14 days or mock using their base stats
    # For simplicity and to match the visualizer, we generate DayData based on their actual overall performance
    
    # We will compute the last 14 days based on the current date, spreading their attempts.
    # Since the dataset timestamps might be very old (e.g. 2019), we just simulate recent dates based on their aggregate stats.
    
    total_q = len(user_data)
    correct_q = int(user_data['target_is_correct'].sum())
    overall_acc = user_data['feat_overall_accuracy'].iloc[-1] if 'feat_overall_accuracy' in user_data else (correct_q/total_q if total_q else 0)
    
    history = []
    last_timestamp = float(user_data['timestamp'].iloc[-1]) if 'timestamp' in user_data else datetime.now().timestamp() * 1000
    base_date = datetime.fromtimestamp(last_timestamp / 1000.0) + timedelta(days=1)
    focus_date = base_date.strftime("%A, %B %d")
    
    # Parts config
    parts_config = {
        1: {"name": "Part 1", "label": "Photographs", "color": "#4ade80"},
        2: {"name": "Part 2", "label": "Q-Response", "color": "#60a5fa"},
        3: {"name": "Part 3", "label": "Conversations", "color": "#a78bfa"},
        4: {"name": "Part 4", "label": "Short Talks", "color": "#34d399"},
        5: {"name": "Part 5", "label": "Grammar", "color": "#f59e0b"},
        6: {"name": "Part 6", "label": "Text Completion", "color": "#fb923c"},
        7: {"name": "Part 7", "label": "Reading Comp.", "color": "#f87171"},
    }

    # Distribute attempts over 14 days
    import random
    random.seed(int(user_data.iloc[0]['user_id'])) # fixed seed per user
    
    for i in range(14):
        days_ago = 13 - i
        d = base_date - timedelta(days=days_ago)
        
        # simulated daily accuracy around their overall accuracy
        daily_acc = min(0.96, max(0.1, overall_acc + (random.random() - 0.5) * 0.2))
        q_count = random.randint(10, 30)
        daily_correct = int(q_count * daily_acc)
        
        parts_studied = random.sample([1,2,3,4,5,6,7], k=random.randint(2, 4))
        parts_data = {}
        for p in parts_studied:
            p_n = random.randint(4, 10)
            p_acc = min(0.96, max(0.1, daily_acc + (random.random() - 0.5) * 0.1))
            parts_data[p] = {"n": p_n, "correct": int(p_n * p_acc), "pct": int(p_acc * 100)}
            
        history.append({
            "idx": i,
            "daysAgo": days_ago,
            "date": f"{d.day}/{d.month}",
            "fullDate": d.strftime("%a, %d %b"),
            "accuracy": int(daily_acc * 100),
            "totalQ": q_count,
            "totalCorrect": daily_correct,
            "parts": parts_data,
            "studiedIds": parts_studied,
            "tookNotes": random.random() > 0.4,
            "watchedLecture": random.random() > 0.5,
            "reviewedWrong": random.random() > 0.4,
            "readExplanation": random.random() > 0.3,
            "anxietySignals": random.randint(0, 3) if sum(parts_studied) > 10 else 0
        })
    return history, focus_date


@app.get("/api/dashboard/{user_id}")
async def get_user_dashboard(user_id: int):
    if df_features is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded")
        
    user_data_pl = df_features.filter(pl.col('user_id') == user_id)
    if len(user_data_pl) == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_data = user_data_pl.to_pandas()
        
    # Get history for the charts
    history, focus_date = generate_mock_history(user_data)
    
    # Calculate weakest part for Today's Focus
    part_accs = {}
    for p in range(1, 8):
        part_data = user_data[user_data['part'] == p]
        if len(part_data) > 0:
            part_accs[p] = part_data['target_is_correct'].mean()
    weakest_part = min(part_accs, key=part_accs.get) if part_accs else 5
    
    # Get questions for weakest part to suggest
    weak_questions = user_data[user_data['part'] == weakest_part]['item_id'].unique()
    suggested_q = weak_questions[0] if len(weak_questions) > 0 else f"q{weakest_part}001"
    
    parts_labels = {
        1: "Photographs", 2: "Q-Response", 3: "Conversations", 4: "Short Talks", 
        5: "Grammar", 6: "Text Completion", 7: "Reading Comp."
    }
    
    todayFocusTasks = [
        {
            "title": f"Practice Part {weakest_part} ({parts_labels.get(weakest_part, 'Grammar')})",
            "desc": f"Solve question {suggested_q} from your weak part.",
            "time": "09:00 AM",
            "iconType": "target",
            "active": True
        },
        {
            "title": "Review Concepts",
            "desc": f"Watch lecture l-{weakest_part}-01 on Part {weakest_part} strategies.",
            "time": "11:30 AM",
            "iconType": "brain",
            "active": False
        },
        {
            "title": "Review Mistakes",
            "desc": "Check explanations for all mistakes from your last session.",
            "time": "02:00 PM",
            "iconType": "history",
            "active": False
        }
    ]
    
    # Get latest state for prediction
    latest_row = user_data.iloc[-1:]
    
    # Prepare features for XGBoost
    # Fill NA to prevent XGBoost errors
    X = latest_row[MODEL_FEATURES].fillna(0)
    dmatrix = xgb.DMatrix(X)
    
    # Predict success probability
    if xgb_model:
        pred_prob = float(xgb_model.predict(dmatrix)[0])
    else:
        pred_prob = 0.5
        
    # Extract behavioral signals from the latest row
    # Example features that map to behavior
    explanation_ratio = float(latest_row['feat_explanation_ratio'].fillna(0).iloc[0])
    lecture_watches = float(latest_row['feat_lecture_watches'].fillna(0).iloc[0])
    rapid_guesses = float(latest_row['feat_is_rapid_guess'].fillna(0).iloc[0])
    session_fatigue = float(latest_row['feat_session_fatigue'].fillna(0).iloc[0])
    recent_acc = float(latest_row['feat_recent_accuracy'].fillna(0).iloc[0])
    overall_acc = float(latest_row['feat_overall_accuracy'].fillna(0).iloc[0])
    
    # Call Gemini for Coaching
    coaching = await generate_coaching(
        user_id=user_id, 
        pred_prob=pred_prob, 
        overall_acc=overall_acc, 
        recent_acc=recent_acc, 
        explanation_ratio=explanation_ratio, 
        lecture_watches=lecture_watches, 
        rapid_guesses=rapid_guesses, 
        session_fatigue=session_fatigue
    )
    
    return {
        "history": history,
        "coaching": coaching,
        "todayFocusTasks": todayFocusTasks,
        "focusDate": focus_date
    }

async def generate_coaching(user_id, pred_prob, overall_acc, recent_acc, explanation_ratio, lecture_watches, rapid_guesses, session_fatigue):
    # Provide a fallback in case Gemini isn't configured
    fallback = {
        "progressComment": f"Bạn đang duy trì tỷ lệ đúng {overall_acc*100:.1f}%. Dự đoán khả năng làm đúng câu tiếp theo là {pred_prob*100:.1f}%.",
        "praises": ["Tích cực luyện tập."] if lecture_watches > 0 else [],
        "weaknesses": ["Dấu hiệu mệt mỏi."] if session_fatigue > 10 else [],
        "emotionalNote": "Cố gắng lên nhé!",
        "tomorrowFocus": "Tiếp tục cải thiện điểm số.",
        "error": False
    }
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        fallback["error"] = True
        return fallback

    prompt = f"""
    You are an AI English Tutor for a TOEIC student.
    Based on the following behavioral data of User {user_id}, generate a JSON response with coaching feedback.
    
    Data:
    - Predicted success probability for next question (XGBoost): {pred_prob:.2f} (If < 0.5, performance is bad, if > 0.7, good).
    - Overall Accuracy: {overall_acc:.2f}
    - Recent Accuracy: {recent_acc:.2f}
    - Explanation Ratio (How much they read explanations): {explanation_ratio:.2f}
    - Lecture Watches: {lecture_watches}
    - Rapid Guesses (sign of anxiety/guessing): {rapid_guesses}
    - Session Fatigue: {session_fatigue}

    Please act as a helpful and encouraging tutor. 
    Analyze the behaviors:
    - ALWAYS include a compliment in the `praises` array. Even if lecture_watches is 0 or they haven't read explanations, praise them for their effort, for trying to take notes, or for just showing up to practice. Make sure they feel encouraged!
    - If rapid_guesses > 0 or session_fatigue is high, note this as an anxiety/fatigue weakness and recommend rest.
    - If pred_prob is low, suggest going back to basics.
    
    Output strictly in the following JSON format:
    {{
        "progressComment": "A 2-sentence summary of their current progress and predicted state.",
        "praises": ["Praise 1", "Praise 2"],
        "weaknesses": ["Weakness 1", "Weakness 2"],
        "emotionalNote": "A short, empathetic note to motivate the user.",
        "tomorrowFocus": "A concrete action item for tomorrow's study session."
    }}
    """
    
    try:
        client = Groq()
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
              {
                "role": "user",
                "content": prompt
              }
            ],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            response_format={"type": "json_object"},
            stream=False,
        )
        response_text = completion.choices[0].message.content
        data = json.loads(response_text)
        data["error"] = False
        return data
    except Exception as e:
        logging.error(f"Groq API Error: {e}")
        fallback["error"] = True
        return fallback

class LiveTestSubmission(BaseModel):
    answers: List[dict]

@app.post("/api/live-test/{user_id}")
async def submit_live_test(user_id: int, payload: LiveTestSubmission):
    if df_features is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded")
    
    total = len(payload.answers)
    correct = sum(1 for a in payload.answers if a.get("isCorrect", False))
    live_acc = correct / total if total > 0 else 0
    
    user_data_pl = df_features.filter(pl.col('user_id') == user_id)
    if len(user_data_pl) == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_data = user_data_pl.to_pandas()
    latest_row = user_data.tail(1).copy()
    
    latest_row['feat_recent_accuracy'] = live_acc
    latest_row['feat_session_fatigue'] = float(latest_row['feat_session_fatigue'].iloc[0]) + total
    
    X = latest_row[MODEL_FEATURES].fillna(0)
    dmatrix = xgb.DMatrix(X)
    
    if xgb_model:
        pred_prob = float(xgb_model.predict(dmatrix)[0])
    else:
        pred_prob = 0.5
        
    prompt = f"""
    You are an AI English Tutor. User {user_id} just completed a live test of {total} questions.
    They got {correct} correct (Accuracy: {live_acc*100:.1f}%).
    The XGBoost model now predicts a {pred_prob*100:.1f}% chance of answering the next question correctly.
    
    Provide immediate real-time feedback.
    
    Output strictly in JSON:
    {{
        "liveAccuracy": {live_acc},
        "nextPrediction": {pred_prob},
        "message": "A short encouraging message about their live test performance.",
        "nextCorrection": "One concrete action they should take right now based on the test."
    }}
    """
    
    try:
        client = Groq()
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
              {
                "role": "user",
                "content": prompt
              }
            ],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            response_format={"type": "json_object"},
            stream=False,
        )
        response_text = completion.choices[0].message.content
        data = json.loads(response_text)
        return data
    except Exception as e:
        logging.error(f"Groq API Error in Live Test: {e}")
        return {
            "liveAccuracy": live_acc,
            "nextPrediction": pred_prob,
            "message": "Great effort on the live test! The AI is currently resting, but keep up the good work.",
            "nextCorrection": "Review the questions you just missed."
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
