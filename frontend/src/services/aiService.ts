import { AICoachingData, DayData, TaskItem } from '../types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export interface DashboardData {
  history: DayData[];
  coaching: AICoachingData;
  todayFocusTasks: TaskItem[];
  focusDate: string;
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

export async function submitLiveTest(userId: number, payload: any): Promise<any> {
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
    return await response.json();
  } catch (error) {
    console.error('API Error in Live Test:', error);
    throw error;
  }
}
