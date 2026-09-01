import React, { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import ExecutiveSummary from './components/ExecutiveSummary';
import AgentBrainLearning from './components/AgentBrainLearning';
import LiveSignals from './components/LiveSignals';
import AgentWarRoom from './components/AgentWarRoom';
import ForensicScreener from './components/ForensicScreener';
import PortfolioView from './components/PortfolioView';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [status, setStatus] = useState(null);
  const [signals, setSignals] = useState([]);
  const [agents, setAgents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [portfolio, setPortfolio] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState('PLTR');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const wsRef = useRef(null);

  // Fetch initial data
  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 6000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket Connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;

    const connectWs = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'NEW_SIGNAL') {
              setSignals(prev => [msg.data, ...prev]);
            } else if (msg.type === 'PORTFOLIO_UPDATE') {
              setPortfolio(prev => ({ ...(prev || {}), summary: msg.data }));
            } else if (msg.type === 'TRADE_EXECUTED') {
              fetchPortfolio();
              fetchStatus();
            } else if (msg.type === 'AGENT_LOG') {
              setLogs(prev => [msg.data, ...prev.slice(0, 300)]);
            } else if (msg.type === 'AGENT_STATUS_UPDATE') {
              fetchAgents();
            }
          } catch (e) {
            console.error('Error handling WebSocket message', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch (e) {
        console.error('WebSocket connection failed', e);
      }
    };

    connectWs();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const fetchAllData = async () => {
    await Promise.all([
      fetchStatus(),
      fetchSignals(),
      fetchAgents(),
      fetchLogs(),
      fetchPortfolio()
    ]);
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) setStatus(await res.json());
    } catch (e) {}
  };

  const fetchSignals = async () => {
    try {
      const res = await fetch('/api/signals?limit=100');
      if (res.ok) setSignals(await res.json());
    } catch (e) {}
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/agents');
      if (res.ok) setAgents(await res.json());
    } catch (e) {}
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/agent-logs?limit=150');
      if (res.ok) setLogs(await res.json());
    } catch (e) {}
  };

  const fetchPortfolio = async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (res.ok) setPortfolio(await res.json());
    } catch (e) {}
  };

  const handleSelectTicker = (ticker) => {
    setSelectedTicker(ticker);
    setActiveTab('screener');
  };

  const handleTriggerAgent = async (agentName) => {
    await fetch(`/api/agents/${agentName}/trigger`, { method: 'POST' });
    setTimeout(fetchAllData, 1000);
  };

  const handleExecuteOrder = async (orderData) => {
    const res = await fetch('/api/portfolio/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Trade execution failed');
    }
    const data = await res.json();
    fetchPortfolio();
    fetchStatus();
    return data;
  };

  const handleClosePosition = async (symbol) => {
    await fetch(`/api/portfolio/position/${symbol}`, { method: 'DELETE' });
    fetchPortfolio();
    fetchStatus();
  };

  const handleResetPortfolio = async () => {
    await fetch('/api/portfolio/reset', { method: 'POST' });
    fetchPortfolio();
    fetchStatus();
  };

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status={status}
        wsConnected={wsConnected}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'overview' && (
          <ExecutiveSummary
            portfolio={portfolio}
            status={status}
            onClosePosition={handleClosePosition}
            onNavigateToTab={setActiveTab}
          />
        )}

        {activeTab === 'learning' && (
          <AgentBrainLearning />
        )}

        {activeTab === 'signals' && (
          <LiveSignals
            signals={signals}
            onSelectTicker={handleSelectTicker}
            onExecuteOrder={handleExecuteOrder}
          />
        )}

        {activeTab === 'screener' && (
          <ForensicScreener
            initialTicker={selectedTicker}
            onExecuteOrder={handleExecuteOrder}
          />
        )}

        {activeTab === 'portfolio' && (
          <PortfolioView
            portfolio={portfolio}
            onClosePosition={handleClosePosition}
            onExecuteOrder={handleExecuteOrder}
            onResetPortfolio={handleResetPortfolio}
          />
        )}

        {activeTab === 'warroom' && (
          <AgentWarRoom
            agents={agents}
            logs={logs}
            onTriggerAgent={handleTriggerAgent}
          />
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-[#070b12] py-4 text-center text-xs font-mono text-slate-400">
        AlphaForge Multi-Agent Quant Engine &bull; Adaptive Learning &bull; Public Feeds &bull; Production Mode
      </footer>

    </div>
  );
}
