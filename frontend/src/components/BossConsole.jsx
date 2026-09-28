import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw, Zap, Activity, AlertTriangle } from 'lucide-react';

export default function BossConsole() {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/boss/audit');
      if (res.ok) setAudit(await res.json());
    } catch (e) {
      console.error('Failed to load audit', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
    const interval = setInterval(fetchAudit, 10000);
    return () => clearInterval(interval);
  }, []);

  const healthScore = audit?.health_score;
  const getScoreColor = (score) => {
    if (score == null) return 'text-slate-300 border-slate-600 bg-slate-800/40';
    if (score >= 90) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (score >= 75) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  };
  const acc = audit?.account || {};
  const money = (v) => (v == null ? '—' : `$${Number(v).toFixed(2)}`);

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/80 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-2xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center">
              <Cpu className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white">FUND AUDITOR</h1>
              <p className="text-sm text-slate-400 mt-1">
                Account, win rate, catalyst record and agent errors, read directly from the trade database every minute.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 w-full lg:w-auto">
            <div className={`px-5 py-3 rounded-2xl border flex items-center gap-3 ${getScoreColor(healthScore)}`}>
              <Activity className="w-6 h-6" />
              <div>
                <div className="text-xs uppercase tracking-wider font-bold opacity-80">Health</div>
                <div className="text-2xl font-black">{healthScore == null ? '—' : `${healthScore}/100`}</div>
              </div>
            </div>
            <button
              onClick={fetchAudit}
              disabled={loading}
              className="p-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition"
              title="Refresh Audit"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {audit?.recommendations?.length > 0 && (
          <div className="mt-6 space-y-2">
            {audit.recommendations.map((r, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-cyan-300 bg-cyan-950/30 px-4 py-2.5 rounded-xl border border-cyan-800/40">
                <Zap className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>{r}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ['Total Equity', money(acc.total_equity)],
          ['Total P/L', acc.total_pnl == null ? '—' : `${money(acc.total_pnl)} (${acc.total_pnl_pct}%)`],
          ['Win Rate', audit?.win_rate == null ? 'No closed trades' : `${audit.win_rate}% of ${audit.closed_trades}`],
          ['Open Positions', acc.open_positions ?? '—'],
        ].map(([label, value]) => (
          <div key={label} className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4">
            <div className="text-xs uppercase tracking-wider text-slate-400 font-bold">{label}</div>
            <div className="text-lg font-black text-white mt-1">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6">
          <h2 className="text-lg font-bold text-white mb-4">Catalyst Record</h2>
          <div className="space-y-2 text-sm font-mono">
            {Object.entries(audit?.catalyst_ratings || {}).map(([cat, r]) => (
              <div key={cat} className="flex justify-between border-b border-slate-800 pb-1.5">
                <span className="text-slate-300">{cat}</span>
                <span className="text-slate-400">
                  {r.trades} trades · {r.win_rate == null ? '—' : `${r.win_rate}%`} · {r.weight}x
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6">
          <h2 className="text-lg font-bold text-white mb-4">Agents</h2>
          <div className="space-y-2 text-sm font-mono">
            {(audit?.agent_performance || []).map((a) => (
              <div key={a.name} className="flex justify-between border-b border-slate-800 pb-1.5">
                <span className="text-slate-300 flex items-center gap-2">
                  {a.status === 'ERROR' && <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />}
                  {a.display_name}
                </span>
                <span className="text-slate-400">{a.signals ?? 0} signals · {a.errors ?? 0} errors</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
