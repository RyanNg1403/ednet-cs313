export interface Part {
  id: number;
  name: string;
  label: string;
  baseAcc: number;
  color: string;
}

export interface DayData {
  idx: number;
  daysAgo: number;
  date: string;
  fullDate: string;
  accuracy: number;
  totalQ: number;
  totalCorrect: number;
  parts: Record<number, { n: number; correct: number; pct: number }>;
  studiedIds: number[];
  tookNotes: boolean;
  watchedLecture: boolean;
  reviewedWrong: boolean;
  readExplanation: boolean;
  anxietySignals: number;
}

export interface AICoachingData {
  progressComment: string;
  praises: string[];
  weaknesses: string[];
  emotionalNote: string;
  tomorrowFocus: string;
  error?: boolean;
}
