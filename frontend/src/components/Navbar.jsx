import React, { useState, useEffect } from 'react';
import { Home, Brain, Activity, Search, Briefcase, Cpu, Settings, TrendingUp, Clock } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, status, wsConnected, onOpenSettings }) {
  const account = status?.account || {};
  const totalEquity = account.total_equity || 100.0;
  const totalPnl = account.total_pnl || 0.0;
  const totalPnlPct = account.total_pnl_pct || 0.0;
  const isPositive = totalPnl >= 0;

  // Bulletproof persistent 24/7 start time using localStorage and database timestamp
  const [uptimeDisplay, setUptimeDisplay] = useState('Active');

  useEffect(() => {
    // 1. Initialize persistent start time in localStorage if not present
    let sessionStartMs = localStorage.getItem('alphaforge_247_start_time');
    
    if (status?.server_start_time) {
      sessionStartMs = new Date(status.server_start_time).getTime();
      localStorage.setItem('alphaforge_247_start_time', sessionStartMs);
    } else if (!sessionStartMs) {
      // Fallback to earliest agent activity or 2 days ago baseline
      const earliestAgent = status?.active_agents?.find(a => a.last_run)?.last_run;
      if (earliestAgent) {
        sessionStartMs = new Date(earliestAgent).getTime();
      } else {
        sessionStartMs = Date.now();
      }
      localStorage.setItem('alphaforge_247_start_time', sessionStartMs);
    }

    const startTimestamp = Number(sessionStartMs) || Date.now();

    const updateClock = () => {
      const now = Date.now();
      const totalSec = Math.max(0, Math.floor((now - startTimestamp) / 1000));
      
      const days = Math.floor(totalSec / 86400);
      const rem = totalSec % 86400;
      const hours = Math.floor(rem / 3600);
      const mins = Math.floor((rem % 3600) / 60);
      const secs = rem % 60;

      if (days > 0) {
        setUptimeDisplay(`${days}d ${hours}h ${mins}m ${secs}s`);
      } else if (hours > 0) {
        setUptimeDisplay(`${hours}h ${mins}m ${secs}s`);
      } else {
        setUptimeDisplay(`${mins}m ${secs}s`);
      }
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, [status?.server_start_time]);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Home },
    { id: 'learning', label: 'AI Brain & Learning', icon: Brain, badge: 'Adaptive' },
    { id: 'signals', label: 'Live Signals', icon: Activity, badge: status?.total_signals_detected },
    { id: 'screener', label: 'Stock Screener', icon: Search },
    { id: 'portfolio', label: 'Portfolio & Trades', icon: Briefcase, badge: account.open_positions_count },
    { id: 'warroom', label: 'War Room', icon: Cpu },
  ];

  return (
    <header className="bg-[#0b1120] border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Live 24/7 Uptime Badge */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2.5 cursor-pointer" onClick={() => setActiveTab('overview')}>
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-500 via-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <TrendingUp className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="text-lg font-black tracking-wider bg-gradient-to-r from-emerald-400 via-cyan-300 to-indigo-300 bg-clip-text text-transparent">
                  ALPHAFORGE
                </span>
                <div className="text-[10px] font-mono text-slate-400 tracking-tight leading-none">
                  ADAPTIVE QUANT ENGINE
                </div>
              </div>
            </div>

            {/* Live 24/7 Persistent Uptime Counter */}
            <div className="hidden sm:flex items-center space-x-2.5 px-3 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-xs shadow-sm">
              <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              <span className="font-mono text-[11px] text-slate-300 font-bold">
                24/7 ONLINE
              </span>
              <span className="text-slate-700">|</span>
              <span className="font-mono text-[11px] text-emerald-300 font-bold flex items-center gap-1.5" title="Persistent 24/7 system uptime (never resets on refresh)">
                <Clock className="w-3.5 h-3.5 text-emerald-400 animate-spin-slow" />
                <span>Uptime: {uptimeDisplay}</span>
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-indigo-950/80 text-indigo-300 border border-indigo-700/80 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && (
                    <span className="ml-1 px-1.5 py-0.2 rounded-full bg-slate-800 text-[10px] font-mono text-emerald-300">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Account Metrics Banner & Settings */}
          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex flex-col text-right">
              <div className="text-[10px] text-slate-400 uppercase font-mono tracking-wider">
                Simulated Balance
              </div>
              <div className="flex items-center space-x-2">
                <span className="font-mono text-sm font-bold text-slate-100">
                  ${totalEquity.toFixed(2)}
                </span>
                <span className={`font-mono text-xs font-semibold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isPositive ? '+' : ''}{totalPnlPct.toFixed(2)}%
                </span>
              </div>
            </div>

            <button
              onClick={onOpenSettings}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Configuration & Environment"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>

        </div>

        {/* Mobile Navigation Row & Uptime */}
        <div className="md:hidden flex items-center justify-between py-2 border-t border-slate-800 px-1">
          <div className="flex overflow-x-auto space-x-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs whitespace-nowrap font-medium ${
                    isActive ? 'bg-indigo-950 text-indigo-300 border border-indigo-800' : 'text-slate-400'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
          <span className="font-mono text-[10px] text-emerald-300 shrink-0 ml-2">
            ⏱️ {uptimeDisplay}
          </span>
        </div>

      </div>
    </header>
  );
}
