import React, { useState } from 'react';
import { Cpu, Play, CheckCircle2, AlertCircle, RefreshCw, Terminal, Clock, ShieldCheck, Zap, Award, Search, Filter } from 'lucide-react';

export default function AgentWarRoom({ agents, logs, onTriggerAgent }) {
  const [triggering, setTriggering] = useState({});
  const [logFilter, setLogFilter] = useState('ALL');
  const [logSearch, setLogSearch] = useState('');

  const handleTrigger = async (agentName) => {
    setTriggering(prev => ({ ...prev, [agentName]: true }));
    try {
      await onTriggerAgent(agentName);
    } finally {
      setTimeout(() => {
        setTriggering(prev => ({ ...prev, [agentName]: false }));
      }, 1200);
    }
  };

  const getAgentIcon = (name) => {
    switch (name) {
      case 'sec_edgar_agent': return ShieldCheck;
      case 'forensic_quant_agent': return Search;
      case 'contract_catalyst_agent': return Award;
      case 'flow_gamma_agent': return Zap;
      case 'cio_risk_agent': return Cpu;
      default: return Cpu;
    }
  };

  const filteredLogs = logs.filter(log => {
    if (logFilter !== 'ALL' && log.level !== logFilter) return false;
    if (logSearch && !log.message.toLowerCase().includes(logSearch.toLowerCase()) && !log.agent_name.toLowerCase().includes(logSearch.toLowerCase()) && !(log.ticker && log.ticker.toLowerCase().includes(logSearch.toLowerCase()))) {
      return false;
    }
    return true;
  });

  const getLogLevelStyle = (level) => {
    switch (level) {
      case 'ALPHA': return 'text-emerald-400 font-bold bg-emerald-950/60 border-emerald-800/80';
      case 'ACTION': return 'text-cyan-300 font-bold bg-cyan-950/60 border-cyan-800/80';
      case 'WARNING': return 'text-amber-400 font-semibold bg-amber-950/60 border-amber-800/80';
      case 'ERROR': return 'text-rose-400 font-bold bg-rose-950/60 border-rose-800/80';
      default: return 'text-slate-400 bg-slate-800/40 border-slate-700/60';
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header */}
      <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-indigo-400" />
          Autonomous Agent Swarm (War Room)
        </h2>
        <p className="text-xs text-slate-400">
          Independent worker agents running asynchronous continuous pipelines on zero-cost public feeds.
        </p>
      </div>

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => {
          const Icon = getAgentIcon(agent.name);
          const isTriggering = triggering[agent.name];
          const isRunning = agent.status === 'RUNNING' || agent.status === 'POLLING';

          return (
            <div
              key={agent.name}
              className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-xl p-5 flex flex-col justify-between transition shadow-sm"
            >
              <div>
                {/* Top Row: Icon, Name & Status */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center space-x-2.5">
                    <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-indigo-400">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-100">
                        {agent.display_name}
                      </h3>
                      <div className="text-[10px] font-mono text-slate-400">
                        {agent.name}
                      </div>
                    </div>
                  </div>

                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold border ${
                    isRunning
                      ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800/80'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                    {agent.status}
                  </span>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 mb-4 leading-relaxed">
                  {agent.description}
                </p>

                {/* Stats Row */}
                <div className="grid grid-cols-2 gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80 text-[11px] font-mono mb-4">
                  <div>
                    <span className="text-slate-400 block text-[10px]">SIGNALS GENERATED</span>
                    <span className="text-emerald-400 font-bold text-xs">{agent.signals_generated || 0}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">ERRORS / FAILS</span>
                    <span className={`font-bold text-xs ${agent.errors_count > 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                      {agent.errors_count || 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom Trigger Action */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-800/80">
                <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  <span>
                    Last: {agent.last_run ? new Date(agent.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Never'}
                  </span>
                </div>

                <button
                  onClick={() => handleTrigger(agent.name)}
                  disabled={isTriggering}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-950 hover:bg-indigo-900 border border-indigo-800 text-indigo-300 text-xs font-semibold transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isTriggering ? 'animate-spin' : ''}`} />
                  <span>{isTriggering ? 'Running...' : 'Force Run'}</span>
                </button>
              </div>

            </div>
          );
        })}
      </div>

      {/* Real-time Streaming Terminal Logs */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        
        {/* Terminal Header */}
        <div className="bg-slate-900/90 px-4 py-3 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono font-bold text-slate-200">
              AGENT EVENT LOG & EXECUTION STREAM
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-400">
              {filteredLogs.length} events
            </span>
          </div>

          {/* Search & Level Filter */}
          <div className="flex items-center space-x-2 text-xs">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
              <input
                type="text"
                placeholder="Search log messages..."
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
                className="pl-8 pr-3 py-1 rounded-md bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 w-48"
              />
            </div>

            <select
              value={logFilter}
              onChange={(e) => setLogFilter(e.target.value)}
              className="px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-slate-300 text-xs focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Levels</option>
              <option value="ALPHA">ALPHA Only</option>
              <option value="ACTION">ACTION Only</option>
              <option value="INFO">INFO Only</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
        </div>

        {/* Logs Console Box */}
        <div className="p-4 max-h-96 overflow-y-auto font-mono text-xs space-y-1.5 bg-[#070b12]">
          {filteredLogs.length === 0 ? (
            <div className="text-slate-600 italic py-4 text-center">
              No logs matching the current filter.
            </div>
          ) : (
            filteredLogs.map((l) => (
              <div key={l.id} className="flex items-start space-x-2 py-0.5 hover:bg-slate-900/40 rounded px-1.5 transition">
                <span className="text-slate-400 shrink-0 text-[11px]">
                  [{new Date(l.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]
                </span>
                
                <span className="text-indigo-400 shrink-0 font-semibold text-[11px]">
                  {l.agent_name}:
                </span>

                <span className={`px-1.5 py-0.2 rounded text-[10px] uppercase border ${getLogLevelStyle(l.level)}`}>
                  {l.level}
                </span>

                {l.ticker && (
                  <span className="text-emerald-400 font-bold px-1 rounded bg-emerald-950/40 border border-emerald-900/60 text-[10px]">
                    ${l.ticker}
                  </span>
                )}

                <span className="text-slate-300 flex-1 break-all text-[11px]">
                  {l.message}
                </span>
              </div>
            ))
          )}
        </div>

      </div>

    </div>
  );
}
