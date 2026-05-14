import { AICoachingData, DayData } from '../types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export interface DashboardData {
  history: DayData[];
  coaching: AICoachingData;
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
