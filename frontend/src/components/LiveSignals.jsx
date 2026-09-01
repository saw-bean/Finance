import React, { useState } from 'react';
import { Activity, ShieldCheck, AlertTriangle, FileText, Award, Zap, ChevronRight, ExternalLink, Play } from 'lucide-react';

export default function LiveSignals({ signals, onSelectTicker, onExecuteOrder }) {
  const [filterAction, setFilterAction] = useState('ALL');
  const [filterCatalyst, setFilterCatalyst] = useState('ALL');
  const [expandedId, setExpandedId] = useState(null);

  const getCatalystBadge = (type) => {
    switch (type) {
      case 'SEC_FORM4_CLUSTER_BUY':
        return { label: 'SEC Form 4 Insider Buy', color: 'bg-emerald-950/80 text-emerald-300 border-emerald-800/80', icon: ShieldCheck };
      case 'SEC_8K_MATERIAL_AGREEMENT':
        return { label: '8-K Material Agreement', color: 'bg-blue-950/80 text-blue-300 border-blue-800/80', icon: FileText };
      case 'GOV_CONTRACT_AWARD':
        return { label: 'Federal / Defense Contract', color: 'bg-amber-950/80 text-amber-300 border-amber-800/80', icon: Award };
      case 'SHORT_SQUEEZE_SETUP':
        return { label: 'FINRA Short Squeeze Alert', color: 'bg-purple-950/80 text-purple-300 border-purple-800/80', icon: Zap };
      case 'FORENSIC_HIGH_QUALITY':
        return { label: 'Forensic Quality Screen Passed', color: 'bg-teal-950/80 text-teal-300 border-teal-800/80', icon: ShieldCheck };
      case 'ACCOUNTING_RED_FLAG':
        return { label: 'Accounting Red Flag / Short', color: 'bg-rose-950/80 text-rose-300 border-rose-800/80', icon: AlertTriangle };
      default:
        return { label: type, color: 'bg-slate-800 text-slate-300 border-slate-700', icon: Activity };
    }
  };

  const filteredSignals = signals.filter((s) => {
    if (filterAction !== 'ALL' && s.action !== filterAction) return false;
    if (filterCatalyst !== 'ALL' && s.catalyst_type !== filterCatalyst) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      
      {/* Header & Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800 backdrop-blur-sm">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            Live Alpha Signal Stream
          </h2>
          <p className="text-xs text-slate-400">
            Real-time asymmetric catalysts ingested by autonomous sniper agents from free public feeds.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-2 text-xs">
          <button
            onClick={() => setFilterAction('ALL')}
            className={`px-3 py-1.5 rounded-lg border font-medium transition ${
              filterAction === 'ALL'
                ? 'bg-slate-800 border-slate-600 text-slate-100'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            All Signals ({signals.length})
          </button>
          <button
            onClick={() => setFilterAction('BUY')}
            className={`px-3 py-1.5 rounded-lg border font-medium transition ${
              filterAction === 'BUY'
                ? 'bg-emerald-950/80 border-emerald-700 text-emerald-300'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-emerald-300'
            }`}
          >
            BUY Only
          </button>
          <button
            onClick={() => setFilterAction('SELL')}
            className={`px-3 py-1.5 rounded-lg border font-medium transition ${
              filterAction === 'SELL'
                ? 'bg-rose-950/80 border-rose-700 text-rose-300'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-rose-300'
            }`}
          >
            SELL / Red Flags
          </button>
        </div>
      </div>

      {/* Signal Cards Grid */}
      {filteredSignals.length === 0 ? (
        <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-12 text-center">
          <Activity className="w-12 h-12 text-slate-600 mx-auto mb-3 animate-pulse" />
          <h3 className="text-sm font-semibold text-slate-300">Awaiting New Market Catalysts</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            Agents are continuously polling SEC EDGAR, USASpending, FINRA, and financial statements in the background. Signals will appear here in real-time.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {filteredSignals.map((signal) => {
            const badge = getCatalystBadge(signal.catalyst_type);
            const Icon = badge.icon;
            const isBuy = signal.action === 'BUY';
            const isExpanded = expandedId === signal.id;

            return (
              <div
                key={signal.id}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-xl p-4 transition-all shadow-sm group"
              >
                <div className="flex items-start justify-between gap-4">
                  
                  <div className="flex items-start space-x-3.5">
                    {/* Ticker Box */}
                    <div
                      onClick={() => onSelectTicker(signal.ticker)}
                      className="cursor-pointer px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 group-hover:border-emerald-500/50 transition text-center"
                      title="Inspect in Forensic Screener"
                    >
                      <span className="font-mono text-base font-black text-slate-100 block">
                        {signal.ticker}
                      </span>
                      <span className={`text-[10px] font-mono font-bold uppercase ${isBuy ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {signal.action}
                      </span>
                    </div>

                    {/* Content */}
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-1.5">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${badge.color}`}>
                          <Icon className="w-3 h-3" />
                          {badge.label}
                        </span>

                        <span className="text-[11px] font-mono text-slate-400">
                          {new Date(signal.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>

                        {signal.confidence && (
                          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700 text-[10px] font-mono text-slate-300">
                            <span>Conviction:</span>
                            <span className="font-bold text-emerald-400">{(signal.confidence * 100).toFixed(0)}%</span>
                          </div>
                        )}
                      </div>

                      <h3 className="text-sm font-semibold text-slate-100 group-hover:text-emerald-300 transition">
                        {signal.title}
                      </h3>
                      <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                        {signal.summary}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <button
                      onClick={() => onSelectTicker(signal.ticker)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-emerald-950 hover:text-emerald-300 border border-slate-700 hover:border-emerald-800 text-[11px] font-medium text-slate-200 transition"
                    >
                      <span>Deep Dive</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => setExpandedId(isExpanded ? null : signal.id)}
                      className="text-[11px] text-slate-400 hover:text-slate-200 underline"
                    >
                      {isExpanded ? 'Hide Details' : 'Metadata'}
                    </button>
                  </div>
                </div>

                {/* Metadata Accordion */}
                {isExpanded && signal.metadata && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80 bg-slate-950/60 p-3 rounded-lg text-xs font-mono text-slate-300">
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2 font-bold">
                      Extracted Metadata & Source Payload
                    </div>
                    <pre className="overflow-x-auto text-[11px] text-emerald-300/90 whitespace-pre-wrap">
                      {JSON.stringify(signal.metadata, null, 2)}
                    </pre>
                    {signal.metadata.filing_url && (
                      <a
                        href={signal.metadata.filing_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 mt-2 text-xs text-cyan-400 hover:underline"
                      >
                        <span>View Official SEC Filing</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
