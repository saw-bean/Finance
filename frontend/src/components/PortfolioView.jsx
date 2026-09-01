import React, { useState } from 'react';
import { Briefcase, DollarSign, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, RefreshCw, XCircle, RotateCcw, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function PortfolioView({ portfolio, onClosePosition, onExecuteOrder, onResetPortfolio }) {
  const [manualSymbol, setManualSymbol] = useState('PLTR');
  const [manualSide, setManualSide] = useState('BUY');
  const [manualQty, setManualQty] = useState(25);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const summary = portfolio?.summary || {};
  const positions = portfolio?.positions || [];
  const trades = portfolio?.trades || [];
  const equityCurve = portfolio?.equity_curve || [];

  const totalEquity = summary.total_equity || 100000;
  const cash = summary.cash || 100000;
  const positionsVal = summary.positions_value || 0;
  const totalPnl = summary.total_pnl || 0;
  const totalPnlPct = summary.total_pnl_pct || 0;
  const isPositive = totalPnl >= 0;

  const handleManualOrder = async (e) => {
    e.preventDefault();
    if (!manualSymbol || manualQty <= 0) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onExecuteOrder({
        symbol: manualSymbol.toUpperCase(),
        side: manualSide,
        qty: parseFloat(manualQty),
        reason: 'Manual execution from portfolio dashboard'
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* 4 Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Total Equity */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-mono text-slate-400 uppercase font-semibold">
            Total Account Equity
          </div>
          <div className="text-2xl font-black font-mono text-slate-100 mt-1">
            ${totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="flex items-center gap-1.5 mt-2">
            <span className={`flex items-center text-xs font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
              {isPositive ? '+' : ''}${totalPnl.toFixed(2)} ({isPositive ? '+' : ''}{totalPnlPct.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* Free Cash */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-mono text-slate-400 uppercase font-semibold">
            Available Cash
          </div>
          <div className="text-2xl font-black font-mono text-cyan-300 mt-1">
            ${cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs font-mono text-slate-400 mt-2">
            {((cash / totalEquity) * 100).toFixed(1)}% Cash allocation
          </div>
        </div>

        {/* Invested Positions */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-mono text-slate-400 uppercase font-semibold">
            Invested Value
          </div>
          <div className="text-2xl font-black font-mono text-indigo-300 mt-1">
            ${positionsVal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs font-mono text-slate-400 mt-2">
            {positions.length} Active Positions
          </div>
        </div>

        {/* Capital Allocation */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="text-xs font-mono text-slate-400 uppercase font-semibold">
              Paper Mode Status
            </div>
            <div className="text-sm font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Slippage & PnL Engine Live
            </div>
          </div>
          <button
            onClick={() => {
              if (window.confirm('Are you sure you want to reset the paper portfolio back to $100,000 cash?')) {
                onResetPortfolio();
              }
            }}
            className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-rose-400 transition mt-2"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset to Initial $100k</span>
          </button>
        </div>

      </div>

      {/* Equity Curve Chart */}
      {equityCurve.length > 1 && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Portfolio Equity Curve (Mark-to-Market)
            </h3>
            <span className="text-xs font-mono text-slate-400">
              {equityCurve.length} snapshots recorded
            </span>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityCurve}>
                <defs>
                  <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  stroke="#475569"
                  fontSize={10}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  stroke="#475569"
                  fontSize={10}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0b1120', borderColor: '#334155', borderRadius: '8px', fontSize: '11px' }}
                  formatter={(val) => [`$${Number(val).toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Total Equity']}
                />
                <Area type="monotone" dataKey="total_equity" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorEquity)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Active Positions Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-emerald-400" />
            Active Open Positions ({positions.length})
          </h3>
        </div>

        {positions.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 font-mono">
            No active positions. Trigger an agent scan or execute a manual order.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3">SYMBOL</th>
                  <th className="px-4 py-3">SHARES</th>
                  <th className="px-4 py-3">AVG ENTRY</th>
                  <th className="px-4 py-3">CURRENT</th>
                  <th className="px-4 py-3">MARKET VAL</th>
                  <th className="px-4 py-3">UNREALIZED PnL</th>
                  <th className="px-4 py-3">TARGET / STOP</th>
                  <th className="px-4 py-3">CATALYST</th>
                  <th className="px-4 py-3 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {positions.map((p) => {
                  const pnlPos = p.unrealized_pnl >= 0;
                  return (
                    <tr key={p.symbol} className="hover:bg-slate-800/40 transition">
                      <td className="px-4 py-3.5 font-bold text-slate-100">
                        ${p.symbol}
                      </td>
                      <td className="px-4 py-3.5 text-slate-300">
                        {p.qty}
                      </td>
                      <td className="px-4 py-3.5 text-slate-300">
                        ${p.avg_entry_price?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3.5 font-bold text-slate-100">
                        ${p.current_price?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3.5 text-slate-200">
                        ${p.market_value?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`font-bold ${pnlPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {pnlPos ? '+' : ''}${p.unrealized_pnl?.toFixed(2)} ({pnlPos ? '+' : ''}{p.unrealized_pnl_pct?.toFixed(2)}%)
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-[11px] text-slate-400">
                        TP: ${p.take_profit?.toFixed(2)} | SL: ${p.stop_loss?.toFixed(2)}
                      </td>
                      <td className="px-4 py-3.5 text-slate-300 truncate max-w-[150px]" title={p.catalyst}>
                        {p.catalyst || 'Manual'}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          onClick={() => onClosePosition(p.symbol)}
                          className="px-2.5 py-1 rounded bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 text-[11px] font-semibold transition"
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Manual Order Execution Form */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
        <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-emerald-400" />
          Direct Order Execution Terminal
        </h3>

        {error && (
          <div className="p-3 mb-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleManualOrder} className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono">
            <span className="text-slate-400">Ticker:</span>
            <input
              type="text"
              value={manualSymbol}
              onChange={(e) => setManualSymbol(e.target.value.toUpperCase())}
              className="w-20 bg-transparent text-slate-100 font-bold focus:outline-none uppercase"
              placeholder="AAPL"
              required
            />
          </div>

          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono">
            <span className="text-slate-400">Side:</span>
            <select
              value={manualSide}
              onChange={(e) => setManualSide(e.target.value)}
              className="bg-transparent text-slate-100 font-bold focus:outline-none"
            >
              <option value="BUY" className="bg-slate-900 text-emerald-400">BUY</option>
              <option value="SELL" className="bg-slate-900 text-rose-400">SELL</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono">
            <span className="text-slate-400">Shares:</span>
            <input
              type="number"
              min="1"
              value={manualQty}
              onChange={(e) => setManualQty(e.target.value)}
              className="w-16 bg-transparent text-slate-100 font-bold focus:outline-none"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className={`px-5 py-2 rounded-lg font-bold text-xs text-white transition disabled:opacity-50 ${
              manualSide === 'BUY' ? 'bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-600/20' : 'bg-rose-700 hover:bg-rose-600'
            }`}
          >
            {isSubmitting ? 'Transacting...' : `Submit Market ${manualSide}`}
          </button>
        </form>
      </div>

      {/* Trade Execution Ledger */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="text-sm font-bold text-slate-100">
            Historical Execution Ledger ({trades.length} trades)
          </h3>
        </div>

        {trades.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 font-mono">
            No executed trades recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto max-h-80">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5">TIME</th>
                  <th className="px-4 py-2.5">SYMBOL</th>
                  <th className="px-4 py-2.5">SIDE</th>
                  <th className="px-4 py-2.5">SHARES</th>
                  <th className="px-4 py-2.5">FILL PRICE</th>
                  <th className="px-4 py-2.5">SLIPPAGE</th>
                  <th className="px-4 py-2.5">REALIZED PnL</th>
                  <th className="px-4 py-2.5">RATIONALE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {trades.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/40 transition">
                    <td className="px-4 py-2.5 text-slate-400">
                      {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="px-4 py-2.5 font-bold text-slate-100">
                      ${t.symbol}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        t.side === 'BUY' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-300">
                      {t.qty}
                    </td>
                    <td className="px-4 py-2.5 text-slate-200">
                      ${t.price?.toFixed(2)}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">
                      ${t.slippage?.toFixed(3)}
                    </td>
                    <td className="px-4 py-2.5">
                      {t.side === 'SELL' ? (
                        <span className={`font-bold ${t.realized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {t.realized_pnl >= 0 ? '+' : ''}${t.realized_pnl?.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 truncate max-w-[200px]" title={t.reason}>
                      {t.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
