import React, { useState, useEffect } from 'react';
import { Search, ShieldAlert, ShieldCheck, CheckCircle2, XCircle, AlertTriangle, TrendingUp, DollarSign, ShoppingCart, RefreshCw, Sparkles, Check, Info } from 'lucide-react';

export default function ForensicScreener({ initialTicker, onExecuteOrder }) {
  const [tickerInput, setTickerInput] = useState(initialTicker || 'PLTR');
  const [analyzing, setAnalyzing] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  
  const [orderQty, setOrderQty] = useState(1);
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState(null);

  const quickWatchlist = ['PLTR', 'NVDA', 'AAPL', 'HIMS', 'SOUN', 'RKLB', 'SMCI', 'ASTS'];

  useEffect(() => {
    if (initialTicker) {
      setTickerInput(initialTicker);
      fetchAnalysis(initialTicker);
    } else {
      fetchAnalysis('PLTR');
    }
  }, [initialTicker]);

  const fetchAnalysis = async (sym) => {
    const cleanSym = (sym || tickerInput).trim().toUpperCase();
    if (!cleanSym) return;

    setAnalyzing(true);
    setError(null);
    setOrderSuccess(null);

    try {
      const res = await fetch(`/api/screener/analyze/${cleanSym}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to fetch forensic data');
      }
      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleOrder = async (side) => {
    if (!metrics || !metrics.current_price || orderQty <= 0) return;
    setOrderSubmitting(true);
    setOrderSuccess(null);
    try {
      const res = await onExecuteOrder({
        symbol: metrics.ticker,
        side: side,
        qty: parseFloat(orderQty),
        reason: `Forensic Screener execution (Verdict: ${metrics.recommendation})`
      });
      if (res && res.success) {
        setOrderSuccess(`Successfully submitted ${side} order for ${orderQty} shares of ${metrics.ticker} at ~$${metrics.current_price}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setOrderSubmitting(false);
    }
  };

  const getTrafficLight = (rec) => {
    if (rec === 'STRONG_BUY' || rec === 'BUY') {
      return {
        color: 'bg-emerald-950 text-emerald-300 border-emerald-600',
        dot: 'bg-emerald-400',
        label: '🟢 High Quality / Safe Fundamentals',
        description: 'This company demonstrates strong balance sheet health, positive cash flow, and low accounting manipulation risk.'
      };
    } else if (rec === 'AVOID/SHORT') {
      return {
        color: 'bg-rose-950 text-rose-300 border-rose-600',
        dot: 'bg-rose-400',
        label: '🔴 High Risk / Accounting Warning',
        description: 'Caution: Company exhibits deteriorating profit quality, negative operating cash flow, or elevated earnings manipulation metrics.'
      };
    } else {
      return {
        color: 'bg-amber-950 text-amber-300 border-amber-600',
        dot: 'bg-amber-400',
        label: '🟡 Neutral / Mixed Fundamentals',
        description: 'Moderate financial strength without immediate red flags or standout momentum.'
      };
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      
      {/* Search Header */}
      <div className="bg-slate-900/90 p-5 rounded-2xl border border-slate-800 shadow-md space-y-3">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          
          <div className="relative flex-1 w-full">
            <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search any stock ticker (e.g. PLTR, AAPL, NVDA, TSLA, SOUN)..."
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && fetchAnalysis(tickerInput)}
              className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 placeholder-slate-500 font-mono text-sm focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          <button
            onClick={() => fetchAnalysis(tickerInput)}
            disabled={analyzing}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold flex items-center justify-center gap-2 transition disabled:opacity-50 shadow-lg shadow-indigo-600/20"
          >
            <RefreshCw className={`w-4 h-4 ${analyzing ? 'animate-spin' : ''}`} />
            <span>{analyzing ? 'Scanning...' : 'Scan Stock'}</span>
          </button>
        </div>

        {/* Quick Tickers */}
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-slate-400 font-mono text-[11px]">Popular Stocks:</span>
          {quickWatchlist.map((sym) => (
            <button
              key={sym}
              onClick={() => {
                setTickerInput(sym);
                fetchAnalysis(sym);
              }}
              className={`px-2.5 py-1 rounded-lg font-mono text-xs border transition ${
                metrics?.ticker === sym
                  ? 'bg-indigo-950 text-indigo-300 border-indigo-700 font-bold'
                  : 'bg-slate-950/60 text-slate-400 border-slate-800 hover:border-slate-700'
              }`}
            >
              ${sym}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {orderSuccess && (
        <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-sm flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400" />
          <span>{orderSuccess}</span>
        </div>
      )}

      {metrics && !analyzing && (
        <div className="space-y-6">
          
          {/* Plain-English Traffic Light Verdict Card */}
          {(() => {
            const verdict = getTrafficLight(metrics.recommendation);
            return (
              <div className={`p-6 rounded-2xl border ${verdict.color} shadow-lg space-y-3`}>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="text-3xl font-black font-mono text-slate-100">
                        ${metrics.ticker}
                      </span>
                      <span className="text-base font-semibold text-slate-200">
                        {metrics.company_name}
                      </span>
                    </div>
                    <p className="text-sm mt-1 text-slate-300 font-medium">
                      {verdict.description}
                    </p>
                  </div>

                  <div className="text-right">
                    <span className="text-xs font-mono uppercase tracking-wider block text-slate-400 mb-1">
                      Current Share Price
                    </span>
                    <span className="text-2xl font-black font-mono text-slate-100">
                      ${metrics.current_price?.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Plain-English Takeaways */}
                <div className="bg-black/30 p-3.5 rounded-xl text-xs space-y-1.5 pt-3">
                  <div className="font-bold text-slate-200 flex items-center gap-1.5 mb-1">
                    <Sparkles className="w-4 h-4 text-indigo-300" />
                    Key Takeaways:
                  </div>
                  <div className="text-slate-300 flex items-start gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span><strong>Balance Sheet Health:</strong> Piotroski F-Score is {metrics.piotroski_f_score}/9 ({metrics.piotroski_f_score >= 7 ? 'Strong' : 'Weak'}).</span>
                  </div>
                  <div className="text-slate-300 flex items-start gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span><strong>Earnings Quality:</strong> {metrics.earnings_quality} (Beneish M-Score is {metrics.beneish_m_score}, {metrics.beneish_m_score < -1.78 ? 'low manipulation risk' : 'elevated manipulation risk'}).</span>
                  </div>
                  <div className="text-slate-300 flex items-start gap-2">
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span><strong>Solvency:</strong> Altman Z-Score is {metrics.altman_z_score} ({metrics.altman_zone} safety zone).</span>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Quick Buy/Sell Box */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <ShoppingCart className="w-4 h-4 text-emerald-400" />
                Simulated Paper Trade for ${metrics.ticker}
              </h4>
              <p className="text-xs text-slate-400">
                Execute a trial order directly using your simulated capital.
              </p>
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs font-mono">
                <span className="text-slate-400">Shares:</span>
                <input
                  type="number"
                  step="0.1"
                  min="0.01"
                  value={orderQty}
                  onChange={(e) => setOrderQty(e.target.value)}
                  className="w-16 bg-transparent text-slate-100 focus:outline-none text-right font-bold"
                />
              </div>

              <button
                onClick={() => handleOrder('BUY')}
                disabled={orderSubmitting}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition disabled:opacity-50 shadow-md shadow-emerald-600/20"
              >
                Buy {orderQty} Shares (~${((metrics.current_price || 0) * orderQty).toFixed(2)})
              </button>

              <button
                onClick={() => handleOrder('SELL')}
                disabled={orderSubmitting}
                className="px-4 py-2 rounded-xl bg-rose-700 hover:bg-rose-600 text-white font-bold text-xs transition disabled:opacity-50"
              >
                Sell {orderQty} Shares
              </button>
            </div>
          </div>

        </div>
      )}

    </div>
  );
}
