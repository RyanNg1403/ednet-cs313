import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  BarChart3, 
  Calendar, 
  Target, 
  Brain, 
  Settings, 
  Search, 
  Bell, 
  ChevronRight,
  TrendingUp,
  BookOpen,
  MessageSquare,
  History,
  AlertCircle,
  Zap,
  CheckCircle2,
  Clock,
  LayoutDashboard
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { PARTS } from './data';
import { DayData, AICoachingData, TaskItem, LiveTestResponse } from './types';
import { getDashboardData, submitLiveTest } from './services/aiService';
import { cn } from './lib/utils';

export default function App() {
  const [userId, setUserId] = useState<string>('');
  const [history, setHistory] = useState<DayData[] | null>(null);
  const [activeTab, setActiveTab] = useState<'today' | 'progress' | 'skills' | 'coaching'>('today');
  const [coaching, setCoaching] = useState<AICoachingData | null>(null);
  const [focusTasks, setFocusTasks] = useState<TaskItem[]>([]);
  const [focusDate, setFocusDate] = useState<string>('');
  const [showLiveTest, setShowLiveTest] = useState(false);
  const [liveTestResult, setLiveTestResult] = useState<LiveTestResponse | null>(null);
  const [submittingTest, setSubmittingTest] = useState(false);
  const [loadingAI, setLoadingAI] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const IconMap: Record<string, React.ReactNode> = {
    target: <Target size={18} className="text-status-danger" />,
    history: <History size={18} className="text-status-warning" />,
    brain: <Brain size={18} className="text-brand-primary" />
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;
    setLoadingAI(true);
    setErrorMsg('');
    try {
      const data = await getDashboardData(parseInt(userId));
      setHistory(data.history);
      setCoaching(data.coaching);
      setFocusTasks(data.todayFocusTasks);
      setFocusDate(data.focusDate);
    } catch (err: any) {
      setErrorMsg(err.message || 'Lỗi khi tải dữ liệu');
    } finally {
      setLoadingAI(false);
    }
  };

  // Derived values and memoized computations must be declared unconditionally
  // so the Hooks call order stays stable between renders.
  const recent7 = history ? history.slice(-7) : [] as DayData[];
  const today = history ? history[history.length - 1] : null as DayData | null;

  const partStats = useMemo(() => {
    if (!recent7.length) return [] as any[];
    return PARTS.map(p => {
      const rows = recent7.filter(d => d.parts[p.id]).map(d => d.parts[p.id]);
      if (!rows.length) return null;
      const avgPct = Math.round(rows.reduce((s, r) => s + r.pct, 0) / rows.length);
      const totalQ = rows.reduce((s, r) => s + r.n, 0);
      const totalCorrect = rows.reduce((s, r) => s + r.correct, 0);
      return { ...p, avgPct, sessions: rows.length, totalQ, totalCorrect };
    }).filter(Boolean);
  }, [recent7]);

  const weakParts = useMemo(() => {
    return [...(partStats as any[])].sort((a, b) => a.avgPct - b.avgPct);
  }, [partStats]);

  const behaviors = useMemo(() => ({
    notes: recent7.filter(d => d.tookNotes).length,
    lectures: recent7.filter(d => d.watchedLecture).length,
    reviewed: recent7.filter(d => d.reviewedWrong).length,
    explained: recent7.filter(d => d.readExplanation).length,
    anxiety: recent7.reduce((s, d) => s + d.anxietySignals, 0),
  }), [recent7]);

  const weekOverWeekDelta = useMemo(() => {
    if (!history || history.length < 14) return 0;
    const w1 = history.slice(0, 7).reduce((s, d) => s + d.accuracy, 0) / 7;
    const w2 = history.slice(7).reduce((s, d) => s + d.accuracy, 0) / 7;
    return Math.round(w2 - w1);
  }, [history]);

  if (!history) {
    return (
      <div className="flex h-screen bg-bg-secondary items-center justify-center font-sans">
        <form onSubmit={handleLogin} className="bento-card p-8 flex flex-col items-center max-w-sm w-full space-y-6">
          <div className="w-16 h-16 bg-brand-primary rounded-2xl flex items-center justify-center">
            <Brain className="text-white w-8 h-8" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-2">EdNet AI</h1>
            <p className="text-text-secondary text-sm">Enter your User ID to load personalized coaching</p>
          </div>
          <input
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="User ID (e.g. 1)"
            className="w-full px-4 py-3 rounded-xl border border-border-primary bg-bg-tertiary focus:outline-none focus:ring-2 focus:ring-brand-primary"
            required
          />
          {errorMsg && <p className="text-status-danger text-sm">{errorMsg}</p>}
          <button 
            type="submit" 
            disabled={loadingAI}
            className="w-full bg-brand-primary text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-brand-primary/90 transition-colors disabled:opacity-70"
          >
            {loadingAI ? 'Loading...' : 'Start Session'}
          </button>
        </form>
      </div>
    );
  }

  const handleRunCoaching = async () => {
    setLoadingAI(true);
    try {
      const data = await getDashboardData(parseInt(userId));
      setHistory(data.history);
      setCoaching(data.coaching);
      setFocusTasks(data.todayFocusTasks);
      setFocusDate(data.focusDate);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingAI(false);
    }
  };

  return (
    <div className="flex h-screen bg-bg-secondary overflow-hidden font-sans">
      {/* Sidebar - Desktop */}
      <aside className="w-64 border-r border-border-primary bg-white flex flex-col hidden lg:flex">
        <div className="p-6">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-brand-primary rounded-lg flex items-center justify-center">
              <Brain className="text-white w-5 h-5" />
            </div>
            <span className="font-bold text-xl tracking-tight">EdNet AI</span>
          </div>

          <nav className="space-y-1">
            <SidebarItem 
              icon={<LayoutDashboard size={20} />} 
              label="Overview" 
              active={activeTab === 'today'} 
              onClick={() => setActiveTab('today')} 
            />
            <SidebarItem 
              icon={<BarChart3 size={20} />} 
              label="Analytics" 
              active={activeTab === 'progress'} 
              onClick={() => setActiveTab('progress')} 
            />
            <SidebarItem 
              icon={<Target size={20} />} 
              label="Skill Matrix" 
              active={activeTab === 'skills'} 
              onClick={() => setActiveTab('skills')} 
            />
            <SidebarItem 
              icon={<MessageSquare size={20} />} 
              label="AI Tutor" 
              active={activeTab === 'coaching'} 
              onClick={() => setActiveTab('coaching')} 
            />
          </nav>
        </div>

        <div className="mt-auto p-6 border-t border-border-primary">
          <div className="flex items-center gap-3 p-3 rounded-xl bg-bg-tertiary">
            <div className="w-10 h-10 rounded-full bg-brand-secondary flex items-center justify-center text-white font-bold">
              MA
            </div>
            <div className="overflow-hidden">
              <p className="text-sm font-medium truncate">User #{userId}</p>
              <p className="text-xs text-text-tertiary">TOEIC 850 Goal</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Header */}
        <header className="h-16 border-b border-border-primary bg-white/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-10">
          <h1 className="text-lg font-semibold capitalize">{activeTab}</h1>
          <div className="flex items-center gap-4">
            <button className="p-2 text-text-secondary hover:bg-bg-tertiary rounded-full transition-colors">
              <Search size={20} />
            </button>
            <button className="p-2 text-text-secondary hover:bg-bg-tertiary rounded-full transition-colors relative">
              <Bell size={20} />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-brand-primary rounded-full border-2 border-white"></span>
            </button>
          </div>
        </header>

        {/* Scrollable Area */}
        <div className="flex-1 overflow-y-auto no-scrollbar p-8">
          <AnimatePresence mode="wait">
            {activeTab === 'today' && (
              <motion.div 
                key="today"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                {/* Stats Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  <StatCard 
                    label="Daily Accuracy" 
                    value={`${today.accuracy}%`} 
                    trend={`${today.totalCorrect}/${today.totalQ} correct`}
                    icon={<TrendingUp className="text-brand-primary" size={20} />}
                  />
                  <StatCard 
                    label="Weekly Improvement" 
                    value={`${weekOverWeekDelta >= 0 ? '+' : ''}${weekOverWeekDelta}%`} 
                    trend="vs last 7 days"
                    icon={<Zap className="text-status-warning" size={20} />}
                    status={weekOverWeekDelta >= 0 ? 'success' : 'danger'}
                  />
                  <StatCard 
                    label="Notes Taken" 
                    value={`${behaviors.notes}/7`} 
                    trend="Active learning"
                    icon={<BookOpen className="text-status-info" size={20} />}
                  />
                  <StatCard 
                    label="Total Sessions" 
                    value="14" 
                    trend="Consistent streak"
                    icon={<Calendar className="text-brand-secondary" size={20} />}
                  />
                </div>

                {/* Main Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  {/* Left Column: Schedule & Status */}
                  <div className="lg:col-span-2 space-y-8">
                    <section>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold">Today's Focus</h2>
                        <span className="text-xs font-medium text-text-tertiary">{focusDate}</span>
                      </div>
                      <div className="space-y-4">
                        {focusTasks.map((t, idx) => (
                          <FocusTask 
                            key={idx}
                            title={t.title}
                            desc={t.desc}
                            time={t.time}
                            icon={IconMap[t.iconType] || IconMap['target']}
                            active={t.active}
                          />
                        ))}
                      </div>
                    </section>

                    <section className="bento-card bg-gradient-to-br from-brand-primary to-brand-secondary text-white border-none">
                      <div className="flex flex-col md:flex-row items-center gap-6">
                        <div className="flex-1">
                          <h3 className="text-xl font-bold mb-2">Ready for a quick sprint?</h3>
                          <p className="text-white/80 text-sm mb-4">You have 10 minutes. Our AI recommends a Part 6 texture completion dash to boost your reading speed.</p>
                          <button onClick={() => setShowLiveTest(true)} className="bg-white text-brand-primary px-6 py-2 rounded-full font-semibold text-sm hover:bg-white/90 transition-colors shadow-lg">
                            Start Sprint
                          </button>
                        </div>
                        <div className="hidden md:block">
                          <Zap size={80} className="text-white/20" />
                        </div>
                      </div>
                    </section>
                  </div>

                  {/* Right Column: Weekly Progress Mini-Chart */}
                  <div className="space-y-8">
                    <section className="bento-card h-full">
                      <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
                        <TrendingUp size={18} className="text-brand-primary" />
                        Weekly Trend
                      </h2>
                      <div className="h-[240px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={recent7}>
                            <defs>
                              <linearGradient id="colorAcc" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis 
                              dataKey="date" 
                              tick={{ fontSize: 10, fill: '#94a3b8' }} 
                              axisLine={false} 
                              tickLine={false} 
                            />
                            <YAxis hide domain={[30, 100]} />
                            <Tooltip 
                              contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                              cursor={{ stroke: '#6366f1', strokeWidth: 2 }}
                            />
                            <Area 
                              type="monotone" 
                              dataKey="accuracy" 
                              stroke="#6366f1" 
                              strokeWidth={3}
                              fillOpacity={1} 
                              fill="url(#colorAcc)" 
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="mt-6 pt-6 border-t border-border-primary space-y-4">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-text-secondary">Completion Rate</span>
                          <span className="font-semibold">84%</span>
                        </div>
                        <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
                          <div className="h-full bg-brand-primary w-[84%] rounded-full"></div>
                        </div>
                      </div>
                    </section>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'progress' && (
              <motion.div 
                key="progress"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="space-y-8"
              >
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <section className="bento-card">
                    <h2 className="text-xl font-bold mb-6">Detailed Accuracy Log</h2>
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={history}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                          <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                          <Tooltip 
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          />
                          <Line 
                            type="monotone" 
                            dataKey="accuracy" 
                            stroke="#6366f1" 
                            strokeWidth={4} 
                            dot={{ r: 6, fill: '#6366f1', strokeWidth: 3, stroke: '#fff' }}
                            activeDot={{ r: 8, strokeWidth: 0 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  <section className="bento-card">
                    <h2 className="text-xl font-bold mb-6">Behavioral Engagement</h2>
                    <div className="space-y-6">
                      <BehaviorItem icon={<BookOpen size={18} />} label="Active Notes" value={behaviors.notes} total={7} color="bg-status-warning" />
                      <BehaviorItem icon={<Calendar size={18} />} label="Lectures Attended" value={behaviors.lectures} total={7} color="bg-brand-primary" />
                      <BehaviorItem icon={<History size={18} />} label="Mistake Remediation" value={behaviors.reviewed} total={7} color="bg-status-success" />
                      <BehaviorItem icon={<AlertCircle size={18} />} label="Stress Signals" value={behaviors.anxiety} total={10} color="bg-status-danger" />
                    </div>
                  </section>
                </div>
              </motion.div>
            )}

            {activeTab === 'skills' && (
              <motion.div 
                key="skills"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
              >
                {partStats.map((p: any) => (
                  <div key={p.id} className="bento-card flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ backgroundColor: `${p.color}20`, color: p.color }}>
                      <span className="font-bold text-lg">{p.name.split(' ')[1]}</span>
                    </div>
                    <h3 className="font-bold mb-1">{p.name}</h3>
                    <p className="text-sm text-text-tertiary mb-4">{p.label}</p>
                    <div className="w-full flex items-center justify-between mb-2">
                       <span className="text-xs font-semibold text-text-secondary">Efficiency</span>
                       <span className="text-xs font-bold" style={{ color: p.color }}>{p.avgPct}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${p.avgPct}%`, backgroundColor: p.color }}></div>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}

            {activeTab === 'coaching' && (
              <motion.div 
                key="coaching"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="max-w-4xl mx-auto"
              >
                {!coaching ? (
                  <div className="bento-card flex flex-col items-center justify-center py-20 bg-gradient-to-b from-white to-bg-tertiary">
                    <div className="w-20 h-20 bg-brand-primary/10 rounded-3xl flex items-center justify-center mb-6">
                      <Brain className="text-brand-primary" size={40} />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Unlock AI Insights</h2>
                    <p className="text-text-secondary text-center max-w-md mb-8">
                      Our advanced Gemini model will analyze your 14-day study data to pinpoint precisely where you need to focus.
                    </p>
                    <button 
                      onClick={handleRunCoaching}
                      disabled={loadingAI}
                      className={cn(
                        "bg-brand-primary text-white px-8 py-3 rounded-2xl font-bold flex items-center gap-2 transition-all hover:scale-105 active:scale-95 shadow-lg",
                        loadingAI && "opacity-70 cursor-not-allowed"
                      )}
                    >
                      {loadingAI ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Zap size={20} />
                          Generate My Coaching Plan
                        </>
                      )}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="flex items-center justify-between mb-2">
                      <h2 className="text-2xl font-bold">Personalized Coaching</h2>
                      <button onClick={handleRunCoaching} className="text-brand-primary text-sm font-medium hover:underline flex items-center gap-1">
                        <History size={14} /> Re-analyze
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bento-card border-brand-primary/10 bg-brand-primary/[0.02] col-span-1 md:col-span-2">
                        <p className="text-brand-primary font-bold text-sm uppercase tracking-wider mb-3">Overall Progress</p>
                        <p className="text-lg leading-relaxed">{coaching.progressComment}</p>
                      </div>
                      
                      <div className="bento-card border-status-success/10 bg-status-success/[0.02]">
                        <p className="text-status-success font-bold text-sm uppercase tracking-wider mb-4 flex items-center gap-2">
                          <CheckCircle2 size={16} /> Key Strengths
                        </p>
                        <ul className="space-y-3">
                          {coaching.praises.map((p, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-status-success shrink-0"></span>
                              {p}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="bento-card border-status-warning/10 bg-status-warning/[0.02]">
                        <p className="text-status-warning font-bold text-sm uppercase tracking-wider mb-4 flex items-center gap-2">
                          <AlertCircle size={16} /> Growth Areas
                        </p>
                        <ul className="space-y-3">
                          {coaching.weaknesses.map((w, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-status-warning shrink-0"></span>
                              {w}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="bento-card col-span-1 md:col-span-2 border-brand-secondary/20 bg-gradient-to-br from-brand-secondary/5 to-transparent">
                         <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div>
                                <p className="text-brand-secondary font-bold text-sm uppercase tracking-wider mb-2">Action Item: Tomorrow</p>
                                <p className="text-xl font-bold">{coaching.tomorrowFocus}</p>
                            </div>
                            <div className="bg-brand-secondary text-white p-4 rounded-2xl flex items-center gap-3">
                                <Clock size={24} />
                                <div>
                                  <p className="text-[10px] uppercase font-bold text-white/70">Estimated Session</p>
                                  <p className="font-bold text-sm">45 Minutes</p>
                                </div>
                            </div>
                         </div>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {/* Mobile Nav */}
      <footer className="lg:hidden fixed bottom-0 left-0 right-0 h-16 bg-white border-t border-border-primary px-6 flex items-center justify-between z-20">
        <MobileNavItem icon={<LayoutDashboard size={20} />} active={activeTab === 'today'} onClick={() => setActiveTab('today')} />
        <MobileNavItem icon={<BarChart3 size={20} />} active={activeTab === 'progress'} onClick={() => setActiveTab('progress')} />
        <MobileNavItem icon={<Target size={20} />} active={activeTab === 'skills'} onClick={() => setActiveTab('skills')} />
        <MobileNavItem icon={<MessageSquare size={20} />} active={activeTab === 'coaching'} onClick={() => setActiveTab('coaching')} />
      </footer>

      {/* Live Test Modal */}
      {showLiveTest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl p-8 max-w-lg w-full shadow-2xl relative">
            <button onClick={() => {setShowLiveTest(false); setLiveTestResult(null);}} className="absolute top-4 right-4 text-text-tertiary hover:text-text-primary">
              ✕
            </button>
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2"><Zap className="text-brand-primary" /> Live Sprint Test</h2>
            
            {!liveTestResult ? (
              <div className="space-y-6">
                <p className="text-text-secondary text-sm">Answer these 3 quick questions to gauge your current state. We'll provide real-time AI feedback.</p>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-bg-tertiary border border-border-primary">
                    <p className="font-semibold mb-3">1. The new software update will be _____ next Monday.</p>
                    <div className="flex gap-2">
                      <button className="flex-1 py-2 rounded-lg bg-white border border-border-primary hover:bg-brand-primary hover:text-white transition-colors text-sm font-medium">installing</button>
                      <button className="flex-1 py-2 rounded-lg bg-brand-primary text-white font-medium text-sm">installed</button>
                    </div>
                  </div>
                </div>
                <button 
                  disabled={submittingTest}
                  onClick={async () => {
                    setSubmittingTest(true);
                    try {
                      const payload = {
                        answers: [
                          { questionId: 'q1', isCorrect: true, timeTaken: 12 },
                          { questionId: 'q2', isCorrect: false, timeTaken: 8 },
                          { questionId: 'q3', isCorrect: true, timeTaken: 15 }
                        ]
                      };
                      const res = await submitLiveTest(parseInt(userId), payload);
                      setLiveTestResult(res);
                    } catch (e) {
                      console.error(e);
                    } finally {
                      setSubmittingTest(false);
                    }
                  }}
                  className="w-full py-3 rounded-xl bg-brand-primary text-white font-bold disabled:opacity-70 flex justify-center items-center gap-2"
                >
                  {submittingTest ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> : 'Submit Test'}
                </button>
              </div>
            ) : (
              <div className="space-y-6 animate-in fade-in zoom-in duration-300">
                <div className="flex justify-between items-center mb-4">
                  <div className="text-center p-4 bg-brand-primary/10 rounded-2xl flex-1 mr-2">
                    <p className="text-xs font-bold text-text-tertiary uppercase">Live Score</p>
                    <p className="text-3xl font-bold text-brand-primary">{(liveTestResult.liveAccuracy * 100).toFixed(0)}%</p>
                  </div>
                  <div className="text-center p-4 bg-status-success/10 rounded-2xl flex-1 ml-2">
                    <p className="text-xs font-bold text-text-tertiary uppercase">Next Q Predict</p>
                    <p className="text-3xl font-bold text-status-success">{(liveTestResult.nextPrediction * 100).toFixed(0)}%</p>
                  </div>
                </div>
                <div className="bg-bg-tertiary p-5 rounded-2xl">
                  <p className="text-text-primary text-sm leading-relaxed mb-4">
                    <strong className="text-brand-primary block mb-1">AI Coach Says:</strong>
                    {liveTestResult.message}
                  </p>
                  <p className="text-text-primary text-sm leading-relaxed">
                    <strong className="text-status-warning block mb-1">Immediate Correction:</strong>
                    {liveTestResult.nextCorrection}
                  </p>
                </div>
                <button onClick={() => setShowLiveTest(false)} className="w-full py-3 rounded-xl bg-bg-tertiary text-text-primary font-bold hover:bg-border-primary transition-colors">
                  Close & Continue
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Components ─────────────────────────────────────────────────────────────

function SidebarItem({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all group",
        active 
          ? "bg-brand-primary text-white shadow-lg shadow-brand-primary/20" 
          : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
      )}
    >
      <span className={cn("transition-transform group-active:scale-90", active ? "text-white" : "text-text-tertiary group-hover:text-brand-primary")}>
        {icon}
      </span>
      {label}
    </button>
  );
}

function MobileNavItem({ icon, active, onClick }: { icon: React.ReactNode, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "p-2 rounded-xl transition-all",
        active ? "text-brand-primary bg-brand-primary/10" : "text-text-tertiary"
      )}
    >
      {React.cloneElement(icon as React.ReactElement, { size: 24 })}
    </button>
  );
}

function StatCard({ label, value, trend, icon, status = 'default' }: { label: string, value: string, trend: string, icon: React.ReactNode, status?: 'default' | 'success' | 'danger' }) {
  const statusColors = {
    default: "text-text-tertiary",
    success: "text-status-success",
    danger: "text-status-danger"
  };

  return (
    <div className="bento-card">
      <div className="flex justify-between items-start mb-4">
        <div className="p-2 bg-bg-secondary rounded-lg">
          {icon}
        </div>
      </div>
      <div>
        <h3 className="text-3xl font-bold mb-1 tracking-tight">{value}</h3>
        <p className="text-text-secondary text-xs font-medium mb-1">{label}</p>
        <p className={cn("text-[10px] font-bold uppercase tracking-wider", statusColors[status])}>{trend}</p>
      </div>
    </div>
  );
}

function FocusTask({ title, desc, time, icon, active = false }: { title: string, desc: string, time: string, icon: React.ReactNode, active?: boolean }) {
  return (
    <div className={cn(
      "flex items-start gap-4 p-4 rounded-2xl border transition-all hover:bg-white group",
      active ? "bg-white border-brand-primary/30 shadow-sm" : "bg-bg-tertiary/50 border-transparent text-text-tertiary"
    )}>
      <div className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors",
        active ? "bg-bg-secondary" : "bg-bg-tertiary"
      )}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="flex justify-between items-center mb-0.5">
          <h4 className={cn("font-bold text-sm", active ? "text-text-primary" : "text-text-secondary")}>{title}</h4>
          <span className="text-[10px] font-bold opacity-60 flex items-center gap-1">
            <Clock size={10} /> {time}
          </span>
        </div>
        <p className="text-xs leading-relaxed">{desc}</p>
      </div>
      <div className="self-center">
        <ChevronRight size={16} className={cn("transition-transform group-hover:translate-x-1", active ? "text-brand-primary" : "text-text-tertiary opacity-0")} />
      </div>
    </div>
  );
}

function BehaviorItem({ icon, label, value, total, color }: { icon: React.ReactNode, label: string, value: number, total: number, color: string }) {
  const pct = Math.min(100, (value / total) * 100);
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className={cn("flex items-center justify-center w-8 h-8 rounded-lg", color.replace('bg-', 'bg-opacity-10 text-').replace('status-', 'text-status-'))}>
            {icon}
          </span>
          {label}
        </div>
        <span className="text-sm font-bold">{value}/{total}</span>
      </div>
      <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          className={cn("h-full rounded-full", color)}
        />
      </div>
    </div>
  );
}
