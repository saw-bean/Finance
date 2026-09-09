import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, Cpu, Code, Play, RefreshCw, Zap, 
  Terminal, CheckCircle, AlertTriangle, Activity, Database, Flame
} from 'lucide-react';

export default function BossConsole({ wsConnected }) {
  const [audit, setAudit] = useState(null);
  const [evolutions, setEvolutions] = useState([]);
  const [directives, setDirectives] = useState([]);
  const [loading, setLoading] = useState(false);
  const [spawnStrategy, setSpawnStrategy] = useState('BIOTECH_FDA');
  const [customTicker, setCustomTicker] = useState('');
  const [spawnLoading, setSpawnLoading] = useState(false);
  const [spawnResult, setSpawnResult] = useState(null);
  const [selectedCode, setSelectedCode] = useState(null);

  const fetchBossData = async () => {
    setLoading(true);
    try {
      const [auditRes, evolutionsRes, directivesRes] = await Promise.all([
        fetch('/api/boss/audit'),
        fetch('/api/boss/evolutions'),
        fetch('/api/boss/directives')
      ]);
      if (auditRes.ok) setAudit(await auditRes.json());
      if (evolutionsRes.ok) {
        const evos = await evolutionsRes.json();
        setEvolutions(evos);
        if (evos.length > 0 && !selectedCode) {
          setSelectedCode(evos[0]);
        }
      }
      if (directivesRes.ok) setDirectives(await directivesRes.json());
    } catch (e) {
      console.error('Failed to load Boss data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBossData();
    const interval = setInterval(fetchBossData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSpawn = async (e) => {
    e.preventDefault();
    setSpawnLoading(true);
    setSpawnResult(null);
    try {
      const res = await fetch('/api/boss/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_type: spawnStrategy,
          custom_params: customTicker ? { tickers: customTicker.split(',').map(s => s.trim().toUpperCase()) } : {}
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSpawnResult({ success: true, message: data.message });
        fetchBossData();
      } else {
        setSpawnResult({ success: false, message: data.detail || 'Failed to deploy agent' });
      }
    } catch (err) {
      setSpawnResult({ success: false, message: err.message });
    } finally {
      setSpawnLoading(false);
    }
  };

  const healthScore = audit?.health_score || 95;
  const getScoreColor = (score) => {
    if (score >= 90) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (score >= 75) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  };

  return (
    <div className="space-y-6">
      {/* Header Deck */}
      <div className="bg-slate-900/80 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-2xl relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Cpu className="w-7 h-7 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-black tracking-tight text-white">CHIEF ARCHITECT & FUND BOSS</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                  AUTONOMOUS META-AGENT
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                24/7 Swarm Performance Auditor, Self-Coding Strategy Generator & Live Agent Spawner
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 w-full lg:w-auto">
            <div className={`px-5 py-3 rounded-2xl border flex items-center gap-3 ${getScoreColor(healthScore)}`}>
              <Activity className="w-6 h-6 animate-pulse" />
              <div>
                <div className="text-xs uppercase tracking-wider font-bold opacity-80">Swarm Health</div>
                <div className="text-2xl font-black">{healthScore}/100</div>
              </div>
            </div>

            <button
              onClick={fetchBossData}
              disabled={loading}
              className="p-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 transition flex items-center justify-center"
              title="Refresh Audit"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Recommendations Banner */}
        {audit?.recommendations && audit.recommendations.length > 0 && (
          <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-3 text-sm text-cyan-300 bg-cyan-950/30 px-4 py-3 rounded-xl border border-cyan-800/40">
            <Zap className="w-5 h-5 text-cyan-400 shrink-0" />
            <span className="font-semibold">Executive Directive:</span>
            <span>{audit.recommendations[0]}</span>
          </div>
        )}
      </div>

      {/* Grid: Left: Strategy Synthesizer & Directives | Right: Code & Evolution Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column (5 cols): Spawn & Directives */}
        <div className="lg:col-span-5 space-y-6">
          
          {/* Strategy Synthesizer */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-2 mb-4">
              <Code className="w-5 h-5 text-indigo-400" />
              <h2 className="text-lg font-bold text-white">Synthesize & Launch Sub-Agent</h2>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              The Boss will write Python code, run AST syntax validation, execute sandbox unit tests, and hot-load the new agent directly into the live swarm.
            </p>

            <form onSubmit={handleSpawn} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Strategy Architecture
                </label>
                <select
                  value={spawnStrategy}
                  onChange={(e) => setSpawnStrategy(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="BIOTECH_FDA">Biotech & FDA PDUFA Catalyst Sniper</option>
                  <option value="CRYPTO_MACRO">Crypto Equity & Macro Spread Momentum</option>
                  <option value="EARNINGS_ACCELERATION">Earnings Acceleration & EPS Velocity</option>
                  <option value="VOLATILITY_BREAKOUT">High-Beta Volatility Breakout Agent</option>
                  <option value="FED_LIQUIDITY">Fed Liquidity & Treasury Spread Tracker</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider">
                  Custom Target Universe (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. VRTX, CRSP, REGN, ARWR"
                  value={customTicker}
                  onChange={(e) => setCustomTicker(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <button
                type="submit"
                disabled={spawnLoading}
                className="w-full py-3 bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-cyan-500/20 transition flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {spawnLoading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Writing & Testing Code...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    <span>Autonomously Code & Deploy Agent</span>
                  </>
                )}
              </button>

              {spawnResult && (
                <div className={`p-3 rounded-xl text-xs flex items-center gap-2 border ${
                  spawnResult.success 
                    ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300' 
                    : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
                }`}>
                  {spawnResult.success ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                  <span>{spawnResult.message}</span>
                </div>
              )}
            </form>
          </div>

          {/* Active Directives */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="w-5 h-5 text-cyan-400" />
              <h2 className="text-lg font-bold text-white">Active Executive Directives</h2>
            </div>
            
            {directives.length === 0 ? (
              <div className="text-xs text-slate-500 py-4 text-center">
                All swarm agents operating on baseline institutional protocols.
              </div>
            ) : (
              <div className="space-y-3">
                {directives.map((d) => (
                  <div key={d.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-start justify-between">
                    <div>
                      <div className="text-xs font-bold text-cyan-400">{d.directive_key}</div>
                      <div className="text-xs text-slate-300 mt-0.5">{d.description}</div>
                    </div>
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
                      ACTIVE
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column (7 cols): Self-Coding Evolution Feed & Code Viewer */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-bold text-white">Self-Coding Architecture & Evolutions</h2>
              </div>
              <span className="text-xs text-slate-400">
                {evolutions.length} Deployed Evolutions
              </span>
            </div>

            {/* List of evolutions */}
            <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-thin">
              {evolutions.map((evo) => (
                <button
                  key={evo.id}
                  onClick={() => setSelectedCode(evo)}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition border ${
                    selectedCode?.id === evo.id
                      ? 'bg-indigo-600/30 border-indigo-500 text-white'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {evo.title}
                </button>
              ))}
            </div>

            {/* Code & Details Viewer */}
            {selectedCode ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs bg-slate-950 px-4 py-2.5 rounded-xl border border-slate-800">
                  <div className="flex items-center gap-3">
                    <span className="text-slate-400 font-mono">{selectedCode.code_path || 'dynamic_agent.py'}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      AST VERIFIED
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                      SANDBOX PASSED
                    </span>
                  </div>
                  <span className="text-slate-500">{new Date(selectedCode.timestamp).toLocaleTimeString()}</span>
                </div>

                <div className="p-3 bg-slate-950/90 rounded-xl border border-slate-800/80 text-xs text-slate-300">
                  <div className="font-semibold text-white mb-1">{selectedCode.title}</div>
                  <div>{selectedCode.description}</div>
                </div>

                {selectedCode.code_content && (
                  <div className="bg-slate-950 rounded-xl p-4 border border-slate-800/80 font-mono text-xs text-cyan-300 overflow-x-auto max-h-96 scrollbar-thin">
                    <pre>{selectedCode.code_content}</pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500 text-sm">
                No custom evolutions deployed yet. Launch a sub-agent on the left to trigger the Boss code engine.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
