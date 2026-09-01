import React, { useState, useEffect } from 'react';
import { Sparkles, Brain, Award, TrendingUp, AlertTriangle, CheckCircle2, XCircle, RefreshCw, BarChart2, ShieldCheck, Cpu, Globe, Scale } from 'lucide-react';

export default function AgentBrainLearning() {
  const [performances, setPerformances] = useState([]);
  const [reflections, setReflections] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLearningData();
    const interval = setInterval(fetchLearningData, 8000);
    return () => clearInterval(interval);
  }, []);

  const fetchLearningData = async () => {
    try {
      const [perfRes, reflRes, logRes] = await Promise.all([
        fetch('/api/learning/performance'),
        fetch('/api/learning/reflections?limit=25'),
        fetch('/api/agent-logs?limit=50')
      ]);
      if (perfRes.ok) setPerformances(await perfRes.json());
      if (reflRes.ok) setReflections(await reflRes.json());
      if (logRes.ok) setLogs(await logRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const autonomousUpgrades = logs.filter(l => l.message.includes('AUTONOMOUS UPGRADE') || l.message.includes('Bull Debate'));

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-950/80 via-slate-900 to-slate-900 p-6 rounded-2xl border border-indigo-900/50 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Brain className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
                Autonomous Learning, Web Intel & Self-Evolution
              </h2>
              <p className="text-xs text-slate-400">
                The AI tracks real-world win rates, conducts live Bull vs. Bear web investigations, and autonomously builds new tools when accuracy gaps are detected.
              </p>
            </div>
          </div>
          <span className="px-3 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-mono font-bold flex items-center gap-1.5 self-start md:self-auto">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Self-Evolution: Active
          </span>
        </div>
      </div>

      {/* Autonomous Innovations & Upgrades Feed */}
      <div className="bg-slate-900/80 border border-indigo-900/40 rounded-2xl p-6 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            Autonomous System Upgrades & Tool Deployments (Zero-Permission Needed)
          </h3>
          <span className="text-[11px] font-mono text-slate-400">Instant Notification Feed</span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          <div className="p-3.5 rounded-xl bg-slate-950/90 border border-slate-800 text-xs space-y-1.5">
            <div className="flex items-center justify-between font-mono">
              <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                Live Web Intel & Bull/Bear Debate Engine
              </span>
              <span className="text-slate-400 text-[10px]">Active</span>
            </div>
            <p className="text-slate-300">
              Auto-conducts live web searches and tests Bull vs. Bear thesis before submitting orders to the CIO.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/90 border border-slate-800 text-xs space-y-1.5">
            <div className="flex items-center justify-between font-mono">
              <span className="text-cyan-400 font-bold flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" />
                EPS Surprise & Revision Acceleration
              </span>
              <span className="text-slate-400 text-[10px]">Active</span>
            </div>
            <p className="text-slate-300">
              Cross-checks positive quarterly earnings acceleration on all candidate balance sheets.
            </p>
          </div>
        </div>
      </div>

      {/* Catalyst Win Rate & Weight Calibration Grid */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Award className="w-5 h-5 text-emerald-400" />
              Catalyst Win-Rate & Dynamic Weight Calibration
            </h3>
            <p className="text-xs text-slate-400">
              Higher win rates grant higher AI conviction multipliers (up to 1.50x), while underperforming catalysts are automatically throttled.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {performances.length} Strategies Tracked
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          {performances.map((perf) => {
            const winPct = perf.win_rate_pct || 50.0;
            const weight = perf.calibrated_weight || 1.0;
            const isHighEdge = weight >= 1.1;

            return (
              <div
                key={perf.catalyst_type}
                className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-100">
                      {perf.display_name}
                    </h4>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                      isHighEdge
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}>
                      {weight.toFixed(2)}x Conviction Multiplier
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="mt-3 space-y-1">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-slate-400">Empirical Win Rate:</span>
                      <span className="font-bold text-slate-200">{winPct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          winPct >= 60 ? 'bg-emerald-400' : winPct >= 45 ? 'bg-indigo-400' : 'bg-rose-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(10, winPct))}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800/60">
                  <span>Trades: {perf.total_trades} (W: {perf.wins} / L: {perf.losses})</span>
                  <span className={perf.total_pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    Net PnL: {perf.total_pnl >= 0 ? '+' : ''}${perf.total_pnl?.toFixed(2)}
                  </span>
                </div>

              </div>
            );
          })}
        </div>
      </div>

      {/* Post-Mortem Reflections Feed */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Brain className="w-5 h-5 text-indigo-400" />
            Recent Post-Trade Reflections & Lessons Learned
          </h3>
          <p className="text-xs text-slate-400">
            Autonomous post-mortem analysis performed on every closed position to refine future execution.
          </p>
        </div>

        {reflections.length === 0 ? (
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-8 text-center text-xs text-slate-400 font-mono">
            No closed trades to reflect upon yet. As positions exit via stop-loss or take-profit, reflections will appear here.
          </div>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {reflections.map((refl) => {
              const isWin = refl.outcome === 'WIN';
              return (
                <div
                  key={refl.id}
                  className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-black ${
                        isWin ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}>
                        {refl.outcome} ({refl.pnl_pct >= 0 ? '+' : ''}{refl.pnl_pct}%)
                      </span>
                      <span className="font-bold font-mono text-slate-100">
                        ${refl.symbol}
                      </span>
                      <span className="text-slate-500 font-mono text-[11px]">
                        Entry: ${refl.entry_price?.toFixed(2)} → Exit: ${refl.exit_price?.toFixed(2)}
                      </span>
                    </div>

                    <span className="text-[11px] font-mono text-slate-500">
                      {new Date(refl.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <p className="text-slate-300 font-medium">
                    {refl.reflection_summary}
                  </p>

                  <div className="bg-slate-900/80 p-2.5 rounded-lg text-[11px] text-indigo-300 border border-slate-800 font-mono">
                    <strong>Lesson:</strong> {refl.lessons_learned}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
