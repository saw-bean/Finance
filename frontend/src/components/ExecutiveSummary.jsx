import React, { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, TrendingDown, ShieldCheck, AlertCircle, HelpCircle, ArrowUpRight, ArrowDownRight, CheckCircle2, Lock, Sparkles } from 'lucide-react';

export default function ExecutiveSummary({ portfolio, status, onClosePosition, onNavigateToTab }) {
  const [holdings, setHoldings] = useState([]);
  const [loading, setLoading] = useState(true);

  const account = status?.account || {};
  const totalEquity = account.total_equity || 100.0;
  const initialCap = account.initial_capital || 100.0;
  const totalPnl = account.total_pnl || 0.0;
  const totalPnlPct = account.total_pnl_pct || 0.0;
  const cash = account.cash || 100.0;
  const investedVal = account.positions_value || 0.0;
  const isPositive = totalPnl >= 0;

  useEffect(() => {
    fetchHoldingsSummary();
    const interval = setInterval(fetchHoldingsSummary, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchHoldingsSummary = async () => {
    try {
      const res = await fetch('/api/portfolio/holdings-summary');
      if (res.ok) {
        setHoldings(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/60 p-6 rounded-2xl border border-slate-800 shadow-lg relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 font-bold mb-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              SYSTEM ACTIVE & MONITORING MARKETS
            </div>
            <h1 className="text-2xl font-black text-slate-100 tracking-tight">
              Executive Portfolio Overview
            </h1>
            <p className="text-xs text-slate-300 mt-1 max-w-2xl">
              Your multi-agent AI system scans official SEC filings, balance sheets, and market flow 24/7 to protect capital and seize asymmetric opportunities.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigateToTab('learning')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition shadow-lg shadow-indigo-600/30"
            >
              <Sparkles className="w-4 h-4" />
              <span>See How AI Learns</span>
            </button>
            <button
              onClick={() => onNavigateToTab('screener')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700 transition"
            >
              <span>Scan Any Stock</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 Big Simple Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Total Money */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-400">
            Total Account Value
          </div>
          <div className="text-3xl font-black font-mono text-slate-100 mt-1">
            ${totalEquity.toFixed(2)}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-2">
            Started with ${initialCap.toFixed(2)}
          </div>
        </div>

        {/* Total Profit / Loss */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-400">
            Total Net Return
          </div>
          <div className={`text-3xl font-black font-mono mt-1 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isPositive ? '+' : ''}${totalPnl.toFixed(2)}
          </div>
          <div className={`text-[11px] font-mono font-bold mt-2 flex items-center gap-1 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
            <span>{isPositive ? '+' : ''}{totalPnlPct.toFixed(2)}% total return</span>
          </div>
        </div>

        {/* Invested Money */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-400">
            Active Stock Holdings
          </div>
          <div className="text-3xl font-black font-mono text-indigo-300 mt-1">
            ${investedVal.toFixed(2)}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-2">
            {holdings.length} stocks currently owned
          </div>
        </div>

        {/* Cash Reserve */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="text-xs font-semibold text-slate-400">
            Available Cash Buffer
          </div>
          <div className="text-3xl font-black font-mono text-cyan-300 mt-1">
            ${cash.toFixed(2)}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-2">
            Ready for new catalysts
          </div>
        </div>

      </div>

      {/* What the AI is Holding Right Now (Plain-English Cards) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              What is the System Holding Right Now?
            </h2>
            <p className="text-xs text-slate-400">
              Plain-English breakdown of why each position was chosen, its current return, and automated safety exits.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {holdings.length} Active Positions
          </span>
        </div>

        {holdings.length === 0 ? (
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-8 text-center text-xs text-slate-400 font-mono">
            No active positions at this moment. The agents are waiting for new high-conviction catalysts.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            {holdings.map((pos) => (
              <div
                key={pos.symbol}
                className="bg-slate-950/90 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition flex flex-col justify-between space-y-4"
              >
                <div>
                  {/* Top Row: Symbol, Price & Return Badge */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-black font-mono text-slate-100">
                          ${pos.symbol}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          ({pos.shares.toFixed(3)} shares)
                        </span>
                      </div>
                      <div className="text-xs font-mono text-slate-300 mt-0.5">
                        Current Value: <span className="font-bold text-slate-100">${pos.market_value.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold ${
                        pos.is_profitable
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}>
                        {pos.gain_loss_text}
                      </span>
                    </div>
                  </div>

                  {/* Why We Bought This */}
                  <div className="bg-slate-900/90 p-3 rounded-lg border border-slate-800/80 text-xs mt-3">
                    <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase tracking-wider block mb-1">
                      💡 Why the AI Bought This:
                    </span>
                    <p className="text-slate-300 leading-relaxed">
                      {pos.why_we_bought}
                    </p>
                  </div>
                </div>

                {/* Safety Exits & Action */}
                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                  <div className="space-y-1 font-mono text-[11px]">
                    <div className="text-slate-400 flex items-center gap-1.5">
                      <Lock className="w-3 h-3 text-rose-400" />
                      <span>Safety Stop-Loss: <strong className="text-slate-200">{pos.safety_stop_loss}</strong></span>
                    </div>
                    <div className="text-slate-400 flex items-center gap-1.5">
                      <TrendingUp className="w-3 h-3 text-emerald-400" />
                      <span>Profit Target: <strong className="text-slate-200">{pos.profit_target}</strong></span>
                    </div>
                  </div>

                  <button
                    onClick={() => onClosePosition(pos.symbol)}
                    className="px-3 py-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs font-semibold transition"
                  >
                    Sell & Exit
                  </button>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
