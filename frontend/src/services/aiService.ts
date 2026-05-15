import { AICoachingData, DayData, LiveTestPayload, LiveTestResponse, TaskItem } from '../types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export interface DashboardData {
  history: DayData[];
  coaching: AICoachingData;
  todayFocusTasks: TaskItem[];
  focusDate: string;
  weeklyDifficulty?: {
    easy: number;
    medium: number;
    hard: number;
    total: number;
  };
  behaviorCounts?: {
    rapidGuesses: number;
    sessionFatigue: number;
  };
}

export async function getDashboardData(userId: number): Promise<DashboardData> {
  try {
    const response = await fetch(`${API_BASE}/dashboard/${userId}`);
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(errorBody?.detail ?? `HTTP ${response.status}`);
    }
    const data = await response.json();
    return data as DashboardData;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

export interface DailyChallengeModelInfo {
  id: string;
  ready: boolean;
  loadError?: string | null;
  isDefault: boolean;
}

export interface DailyChallengeResult {
  expectedCorrect: number;
  n: number;
  perQuestionProbs: number[];
}

export interface DailyChallengeResponse {
  plan: Record<number, number>;
  questionsParts: number[];
  results: Record<string, DailyChallengeResult>;
  errors: Record<string, string>;
  notes: {
    recentAccuracyWindow: number;
    softProbabilityFeedback: boolean;
    excludedModels: string[];
  };
}

export async function getDailyChallengeModels(): Promise<{ models: DailyChallengeModelInfo[] }> {
  const r = await fetch(`${API_BASE}/daily-challenge/models`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function runDailyChallenge(
  userId: number,
  body: {
    totalN?: number;
    perPart?: Record<number, number>;
    models: string[];
    seed?: number;
  },
): Promise<DailyChallengeResponse> {
  const r = await fetch(`${API_BASE}/daily-challenge/${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err?.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export async function submitLiveTest(userId: number, payload: LiveTestPayload): Promise<LiveTestResponse> {
  try {
    const response = await fetch(`${API_BASE}/live-test/${userId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(errorBody?.detail ?? `HTTP ${response.status}`);
    }
    return await response.json() as LiveTestResponse;
  } catch (error) {
    console.error('API Error in Live Test:', error);
    throw error;
  }
}
