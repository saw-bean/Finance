import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AlertTriangle, RefreshCw } from 'lucide-react';

// Categorical slots 1-2, validated against the #0b1120 dark surface (dataviz validator: all checks pass)
const SERIES = { fund: '#3987e5', benchmark: '#d95926' };

const pct = (v, d = 2) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`);
const num = (v, d = 2) => (v == null ? '—' : Number(v).toFixed(d));
const usd = (v, d = 2) => (v == null ? '—' : `${v < 0 ? '-' : ''}$${Math.abs(v).toFixed(d)}`);
const signedUsd = (v) => (v == null ? '—' : `${v >= 0 ? '+' : '-'}$${Math.abs(v).toFixed(2)}`);

function Tile({ label, value, hint }) {
  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
      <div className="text-lg font-black text-slate-100 mt-0.5 font-mono">{value}</div>
      {hint && <div className="text-[11px] text-slate-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5">
      <h2 className="text-sm font-bold text-slate-200 mb-3 uppercase tracking-wider">{title}</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{children}</div>
    </div>
  );
}

function EndLabel({ x, y, index, data, text, color }) {
  if (index !== data.length - 1 || x == null) return null;
  return (
    <g>
      <circle cx={x} cy={y} r={4} fill={color} stroke="#0b1120" strokeWidth={2} />
      <text x={x - 8} y={y - 10} textAnchor="end" fill="#cbd5e1" fontSize={11}>{text}</text>
    </g>
  );
}

function AttributionTable({ title, rows }) {
  const entries = Object.entries(rows || {});
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5">
      <h2 className="text-sm font-bold text-slate-200 mb-3 uppercase tracking-wider">{title}</h2>
      {entries.length === 0 ? (
        <div className="text-xs text-slate-500">No P&L yet.</div>
      ) : (
        <table className="w-full text-xs font-mono">
          <tbody>
            {entries.slice().reverse().map(([k, v]) => (
              <tr key={k} className="border-b border-slate-800/60">
                <td className="py-1.5 text-slate-300">{k}</td>
                <td className="py-1.5 text-right text-slate-100">{signedUsd(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function PerformanceView() {
  const [m, setM] = useState(null);
  const [regime, setRegime] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async (refresh = false) => {
    setLoading(true);
    try {
      const [mr, rr] = await Promise.all([fetch(`/api/metrics${refresh ? '?refresh=true' : ''}`), fetch('/api/regime')]);
      if (mr.ok) setM(await mr.json());
      if (rr.ok) setRegime(await rr.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  if (!m) return <div className="text-slate-400 text-sm">Loading metrics…</div>;
  const r = m.returns || {};
  const t = m.trading || {};
  const e = m.exposure || {};
  const c = m.costs || {};
  const curve = m.equity_curve || [];
  const last = curve[curve.length - 1];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white">Fund Performance</h1>
          <p className="text-xs text-slate-400">
            Paper long/short book vs {m.benchmark}. Risk-free rate {pct(m.risk_free_rate)} (13-week T-bill).
            {regime?.regime && <> Regime: <span className="text-slate-200 font-bold">{regime.regime}</span> (risk ×{regime.risk_multiplier}, target beta {regime.target_beta}).</>}
          </p>
        </div>
        <button onClick={() => load(true)} className="p-2.5 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700" title="Recompute">
          <RefreshCw className={`w-4 h-4 text-slate-300 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {m.warnings?.length > 0 && (
        <div className="space-y-2">
          {m.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-200 bg-amber-950/40 border border-amber-800/50 rounded-xl px-3 py-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" /> <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile label="Equity" value={usd(m.equity)} hint={`from ${usd(m.initial_capital)}`} />
        <Tile label="Total return" value={pct(r.total_return)} hint={`${m.benchmark} ${pct(r.benchmark_return)}`} />
        <Tile label="Sharpe" value={num(r.sharpe_ratio)} hint={`${r.days ?? 0} trading days`} />
        <Tile label="Max drawdown" value={pct(r.max_drawdown)} hint={`current ${pct(r.current_drawdown)}`} />
      </div>

      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5">
        <h2 className="text-sm font-bold text-slate-200 mb-1 uppercase tracking-wider">Equity vs {m.benchmark}</h2>
        <p className="text-[11px] text-slate-500 mb-3">{m.benchmark} rescaled to the fund's starting capital, end of each day.</p>
        {curve.length < 2 ? (
          <div className="text-xs text-slate-500 py-10 text-center">The curve appears after the second trading day.</div>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curve} margin={{ top: 20, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#1e293b" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} stroke="#334155" />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} stroke="#334155" domain={['auto', 'auto']} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#e2e8f0' }} itemStyle={{ color: '#cbd5e1' }}
                  formatter={(v, name) => [usd(v), name]}
                  cursor={{ stroke: '#475569', strokeWidth: 1 }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: '#cbd5e1' }} />
                <Line type="monotone" dataKey="equity" name="Fund" stroke={SERIES.fund} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: '#0b1120' }}
                  label={(p) => <EndLabel {...p} data={curve} color={SERIES.fund} text={`Fund ${usd(last?.equity)}`} />} isAnimationActive={false} />
                <Line type="monotone" dataKey="benchmark" name={m.benchmark} stroke={SERIES.benchmark} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: '#0b1120' }}
                  label={(p) => <EndLabel {...p} data={curve} color={SERIES.benchmark} text={`${m.benchmark} ${usd(last?.benchmark)}`} />} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <Section title="Returns & risk">
        <Tile label="Annualized return" value={pct(r.annualized_return)} hint="needs 20+ days" />
        <Tile label="Annualized volatility" value={pct(r.annualized_volatility)} />
        <Tile label="Sortino" value={num(r.sortino_ratio)} />
        <Tile label="Calmar" value={num(r.calmar_ratio)} />
        <Tile label="1-day VaR 95%" value={pct(r.var_95_1d)} hint={`CVaR ${pct(r.cvar_95_1d)}`} />
        <Tile label="Best / worst day" value={`${pct(r.best_day)} / ${pct(r.worst_day)}`} />
        <Tile label="Positive days" value={pct(r.positive_days_pct, 0)} />
        <Tile label="Longest drawdown" value={`${r.max_drawdown_duration_days ?? 0} days`} />
      </Section>

      <Section title={`Versus ${m.benchmark}`}>
        <Tile label="Beta" value={num(r.beta)} />
        <Tile label="Alpha (annualized)" value={pct(r.alpha_annualized)} />
        <Tile label="Correlation" value={num(r.correlation)} />
        <Tile label="Information ratio" value={num(r.information_ratio)} hint={`tracking error ${pct(r.tracking_error)}`} />
      </Section>

      <Section title="Trading">
        <Tile label="Closed trades" value={t.closed_trades ?? 0} hint={`${t.long_trades ?? 0} long · ${t.short_trades ?? 0} short`} />
        <Tile label="Win rate" value={pct(t.win_rate, 0)} hint={`long ${pct(t.long_win_rate, 0)} · short ${pct(t.short_win_rate, 0)}`} />
        <Tile label="Profit factor" value={num(t.profit_factor)} hint={`payoff ${num(t.payoff_ratio)}`} />
        <Tile label="Expectancy / trade" value={usd(t.expectancy_per_trade, 4)} hint={`avg hold ${num(t.average_holding_days, 1)} days`} />
      </Section>

      <Section title="Exposure">
        <Tile label="Gross" value={pct(e.gross, 0)} hint={`${e.long_positions ?? 0} long · ${e.short_positions ?? 0} short`} />
        <Tile label="Net" value={pct(e.net, 0)} />
        <Tile label="Long / short value" value={`${usd(e.long_value)} / ${usd(e.short_value)}`} />
        <Tile label="Cash" value={usd(e.cash)} />
      </Section>

      <Section title="Costs & turnover">
        <Tile label="Spread paid" value={usd(c.spread_paid, 4)} hint={`${c.live_quote_fills ?? 0} live-quote fills · ${c.modeled_spread_fills ?? 0} modeled`} />
        <Tile label="SEC + FINRA fees" value={usd(c.regulatory_fees, 2)} hint={`commissions ${usd(c.commissions, 2)}`} />
        <Tile label="Borrow fees" value={usd(c.borrow_fees, 4)} />
        <Tile label="Total costs" value={usd(c.total, 4)} hint={`${pct(c.total_pct_of_initial)} of capital · turnover ${num(m.turnover?.turnover_multiple)}×`} />
      </Section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <AttributionTable title="P&L by strategy" rows={m.attribution_by_catalyst} />
        <AttributionTable title="P&L by agent" rows={m.attribution_by_agent} />
      </div>
    </div>
  );
}
