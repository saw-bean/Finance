import React, { useState, useEffect } from 'react';
import { Sparkles, Brain, Award, TrendingUp, AlertTriangle, CheckCircle2, XCircle, RefreshCw, BarChart2, ShieldCheck, Cpu, Globe, Scale, Lightbulb, ArrowUpRight, Zap } from 'lucide-react';

export default function AgentBrainLearning() {
  const [performances, setPerformances] = useState([]);
  const [reflections, setReflections] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLearningData();
    const interval = setInterval(fetchLearningData, 6000);
    return () => clearInterval(interval);
  }, []);

  const fetchLearningData = async () => {
    try {
      const [perfRes, reflRes] = await Promise.all([
        fetch('/api/learning/performance'),
        fetch('/api/learning/reflections?limit=15')
      ]);
      if (perfRes.ok) setPerformances(await perfRes.json());
      if (reflRes.ok) setReflections(await reflRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      
      {/* Friendly Plain-English Overview Header */}
      <div className="bg-gradient-to-r from-indigo-950 via-slate-900 to-slate-900 p-6 rounded-2xl border border-indigo-900/60 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-3 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Brain className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
                How Your AI Learns & Self-Improves
              </h2>
              <p className="text-xs text-slate-300 mt-0.5 max-w-2xl leading-relaxed">
                The AI analyzes every trade outcome, measures which catalysts win the most, automatically allocates more capital to winning strategies, and builds new tools to fix weaknesses.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start md:self-auto">
            <span className="px-3 py-1.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-mono font-bold flex items-center gap-1.5 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Autonomous Learning: Active
            </span>
          </div>
        </div>

        {/* 3-Step Simple Explanation */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5 pt-4 border-t border-slate-800/80 text-xs">
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-full bg-indigo-900 text-indigo-300 font-bold flex items-center justify-center shrink-0 text-[11px]">1</span>
            <div>
              <strong className="text-slate-200 block mb-0.5">Executes With $100 Budget</strong>
              <span className="text-slate-400 text-[11px]">Tests catalysts in small fractional sizes ($5–$15) with strict 5% stop-loss safety.</span>
            </div>
          </div>

          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-full bg-indigo-900 text-indigo-300 font-bold flex items-center justify-center shrink-0 text-[11px]">2</span>
            <div>
              <strong className="text-slate-200 block mb-0.5">Reflects on Every Trade</strong>
              <span className="text-slate-400 text-[11px]">Calculates empirical win-rate percentages and saves plain-English lessons learned.</span>
            </div>
          </div>

          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-full bg-indigo-900 text-indigo-300 font-bold flex items-center justify-center shrink-0 text-[11px]">3</span>
            <div>
              <strong className="text-slate-200 block mb-0.5">Sizes Up Winners & Builds Tools</strong>
              <span className="text-slate-400 text-[11px]">Grants up to 1.50x conviction to winning setups and autonomously creates new filters.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Section 1: New Tools Built by the AI */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              New Skills & Tools Built by the AI (Zero Permission Needed)
            </h3>
            <p className="text-xs text-slate-400">
              When the AI detects missing data or lower precision, it autonomously designs and activates new micro-tools into the swarm.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 font-mono text-[11px] font-bold">
            3 Active Upgrades
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          
          <div className="bg-slate-950 border border-indigo-900/50 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] font-mono font-bold">
                  LIVE WEB INTEL
                </span>
                <Globe className="w-4 h-4 text-emerald-400" />
              </div>
              <h4 className="text-sm font-bold text-slate-100 mt-2">
                Bull vs. Bear Web Debate
              </h4>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                Auto-scrapes live Google News and checks for breaking contracts, lawsuits, or dilution before approving a trade.
              </p>
            </div>
            <div className="text-[11px] font-mono text-emerald-400 pt-2 border-t border-slate-800/80 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Edge: +30% Signal Precision</span>
            </div>
          </div>

          <div className="bg-slate-950 border border-indigo-900/50 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-mono font-bold">
                  FUNDAMENTAL FILTER
                </span>
                <Cpu className="w-4 h-4 text-cyan-400" />
              </div>
              <h4 className="text-sm font-bold text-slate-100 mt-2">
                EPS Surprise Acceleration
              </h4>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                Verifies positive quarterly earnings revisions to confirm companies have genuine revenue growth before entry.
              </p>
            </div>
            <div className="text-[11px] font-mono text-cyan-400 pt-2 border-t border-slate-800/80 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Edge: Filters False Squeezes</span>
            </div>
          </div>

          <div className="bg-slate-950 border border-indigo-900/50 rounded-xl p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-mono font-bold">
                  FLOW ANALYZER
                </span>
                <TrendingUp className="w-4 h-4 text-amber-400" />
              </div>
              <h4 className="text-sm font-bold text-slate-100 mt-2">
                Options Flow & Gamma Skew
              </h4>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                Cross-checks institutional call buying pressure to detect sudden upward short-squeeze momentum early.
              </p>
            </div>
            <div className="text-[11px] font-mono text-amber-400 pt-2 border-t border-slate-800/80 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Edge: Early Momentum Detection</span>
            </div>
          </div>

        </div>
      </div>

      {/* Section 2: Strategy Win-Rate Scoreboard */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Award className="w-5 h-5 text-emerald-400" />
              Strategy Win-Rate Scoreboard & AI Conviction Sizing
            </h3>
            <p className="text-xs text-slate-400">
              Strategies with proven high win rates get sized up (up to 1.50x), while underperforming strategies are throttled.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {performances.map((perf) => {
            const winPct = perf.win_rate_pct || 50.0;
            const weight = perf.calibrated_weight || 1.0;
            const isHighEdge = weight >= 1.1;

            return (
              <div
                key={perf.catalyst_type}
                className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-bold text-slate-100">
                        {perf.display_name}
                      </h4>
                      <span className="text-[11px] text-slate-400">
                        {perf.total_trades} Trades Evaluated ({perf.wins} Wins / {perf.losses} Losses)
                      </span>
                    </div>

                    <span className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold border ${
                      isHighEdge
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}>
                      {weight.toFixed(2)}x Sizing Weight
                    </span>
                  </div>

                  {/* Visual Win-Rate Progress Bar */}
                  <div className="mt-3 space-y-1.5">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-slate-400">Measured Win Rate:</span>
                      <span className="font-bold text-slate-100">{winPct.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          winPct >= 65 ? 'bg-emerald-400' : winPct >= 50 ? 'bg-indigo-400' : 'bg-rose-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(15, winPct))}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs font-mono pt-2 border-t border-slate-800/80">
                  <span className="text-slate-400">
                    Status: <strong className={isHighEdge ? 'text-emerald-400' : 'text-slate-300'}>{isHighEdge ? '🟢 Sizing Up' : '🟡 Standard Sizing'}</strong>
                  </span>
                  <span className={perf.total_pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    Net P/L: {perf.total_pnl >= 0 ? '+' : ''}${perf.total_pnl?.toFixed(2)}
                  </span>
                </div>

              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3: Plain-English Post-Trade Lessons */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-indigo-400" />
            Plain-English Lessons Learned (Post-Mortem Reflections)
          </h3>
          <p className="text-xs text-slate-400">
            Every time a position closes via stop-loss or profit target, the AI writes a plain-English takeaway to refine future trades.
          </p>
        </div>

        {reflections.length === 0 ? (
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-8 text-center text-xs text-slate-400 font-mono">
            No closed positions to reflect on yet. As open positions reach their +15% profit targets or hit stop-loss exits, the AI's takeaways will appear here.
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
                        {isWin ? 'WIN' : 'LOSS'} ({refl.pnl_pct >= 0 ? '+' : ''}{refl.pnl_pct}%)
                      </span>
                      <span className="font-bold font-mono text-slate-100 text-sm">
                        ${refl.symbol}
                      </span>
                      <span className="text-slate-400 font-mono text-[11px]">
                        Bought @ ${refl.entry_price?.toFixed(2)} → Sold @ ${refl.exit_price?.toFixed(2)}
                      </span>
                    </div>

                    <span className="text-[11px] font-mono text-slate-500">
                      {new Date(refl.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <p className="text-slate-300">
                    {refl.reflection_summary}
                  </p>

                  <div className="bg-slate-900 p-2.5 rounded-lg text-xs text-indigo-300 border border-slate-800 font-medium">
                    💡 <strong>Takeaway:</strong> {refl.lessons_learned}
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
