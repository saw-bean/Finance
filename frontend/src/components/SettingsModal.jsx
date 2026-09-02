import React, { useState, useEffect } from 'react';
import { X, Save, Key, ShieldCheck, Cpu, Bell, CheckCircle2, Send, AlertCircle } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState(null);
  
  const [form, setForm] = useState({
    sec_user_agent: '',
    alpaca_api_key: '',
    alpaca_secret_key: '',
    gemini_api_key: '',
    ollama_base_url: 'http://localhost:11434',
    discord_webhook_url: '',
    telegram_bot_token: '',
    telegram_chat_id: '',
    max_position_size_pct: 0.10,
    default_stop_loss_pct: 0.05,
    default_take_profit_pct: 0.15
  });

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
      setTelegramStatus(null);
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setForm(prev => ({
          ...prev,
          sec_user_agent: data.SEC_USER_AGENT || '',
          ollama_base_url: data.OLLAMA_BASE_URL || 'http://localhost:11434',
          telegram_chat_id: data.TELEGRAM_CHAT_ID || '',
          max_position_size_pct: data.MAX_POSITION_SIZE_PCT || 0.10,
          default_stop_loss_pct: data.DEFAULT_STOP_LOSS_PCT || 0.05,
          default_take_profit_pct: data.DEFAULT_TAKE_PROFIT_PCT || 0.15
        }));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSaved(false);
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    setTelegramStatus(null);
    try {
      const res = await fetch('/api/telegram/test', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setTelegramStatus({ success: true, message: data.message || 'Telegram test message delivered!' });
      } else {
        setTelegramStatus({ success: false, message: data.detail || 'Failed to send Telegram alert.' });
      }
    } catch (err) {
      setTelegramStatus({ success: false, message: err.message });
    } finally {
      setTestingTelegram(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Key className="w-5 h-5 text-emerald-400" />
              Settings & Telegram Push Notifications
            </h3>
            <p className="text-xs text-slate-400">
              Configure automated Telegram trade alerts, free public feeds, and risk rules.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {saved && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-950/80 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>Settings successfully saved and persisted to .env!</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6 mt-5 text-xs">
          
          {/* Telegram Alerts Box */}
          <div className="space-y-3 p-4 rounded-xl bg-slate-950/90 border border-indigo-900/60 shadow-sm">
            <div className="flex items-center justify-between">
              <label className="font-mono text-slate-200 font-bold flex items-center gap-1.5 text-xs">
                <Bell className="w-4 h-4 text-indigo-400" />
                Telegram Instant Trade & Reflection Alerts
              </label>
              
              <button
                type="button"
                onClick={handleTestTelegram}
                disabled={testingTelegram}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-700 text-[11px] font-bold transition disabled:opacity-50"
              >
                <Send className={`w-3 h-3 ${testingTelegram ? 'animate-pulse' : ''}`} />
                <span>{testingTelegram ? 'Sending...' : 'Test Telegram Alert'}</span>
              </button>
            </div>

            {telegramStatus && (
              <div className={`p-2.5 rounded-lg text-xs flex items-center gap-2 ${
                telegramStatus.success
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-rose-950 text-rose-300 border border-rose-800'
              }`}>
                {telegramStatus.success ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                <span>{telegramStatus.message}</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <span className="text-[11px] text-slate-400 block mb-1">Telegram Bot Token (from @BotFather)</span>
                <input
                  type="password"
                  value={form.telegram_bot_token}
                  onChange={(e) => setForm({ ...form, telegram_bot_token: e.target.value })}
                  placeholder="e.g. 7123456789:AAH..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block mb-1">Telegram Chat ID (from @userinfobot)</span>
                <input
                  type="text"
                  value={form.telegram_chat_id}
                  onChange={(e) => setForm({ ...form, telegram_chat_id: e.target.value })}
                  placeholder="e.g. 123456789"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Every single <strong>BUY</strong>, <strong>SELL</strong> (stop-loss / take-profit), and <strong>Autonomous Self-Upgrade</strong> will be pushed instantly to your phone.
            </p>
          </div>

          {/* SEC EDGAR */}
          <div className="space-y-2 pt-2">
            <label className="block font-mono text-slate-200 font-bold flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              SEC EDGAR User-Agent (Standard Format: Name email@domain.com)
            </label>
            <input
              type="text"
              value={form.sec_user_agent}
              onChange={(e) => setForm({ ...form, sec_user_agent: e.target.value })}
              placeholder="AlphaForgeTrader research@alphaforge.local"
              className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
              required
            />
          </div>

          {/* Alpaca Paper Trading */}
          <div className="space-y-3 pt-3 border-t border-slate-800">
            <label className="block font-mono text-slate-200 font-bold flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-emerald-400" />
              Optional Alpaca Paper Broker Integration (Free at app.alpaca.markets)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <span className="text-[11px] text-slate-400 block mb-1">API Key ID</span>
                <input
                  type="password"
                  value={form.alpaca_api_key}
                  onChange={(e) => setForm({ ...form, alpaca_api_key: e.target.value })}
                  placeholder="PK..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block mb-1">Secret Key</span>
                <input
                  type="password"
                  value={form.alpaca_secret_key}
                  onChange={(e) => setForm({ ...form, alpaca_secret_key: e.target.value })}
                  placeholder="Secret..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          </div>

          {/* Risk Management */}
          <div className="space-y-3 pt-3 border-t border-slate-800">
            <label className="block font-mono text-slate-200 font-bold">
              Autonomous Risk & Sizing Rules
            </label>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">MAX POSITION %</span>
                <input
                  type="number"
                  step="0.01"
                  value={form.max_position_size_pct}
                  onChange={(e) => setForm({ ...form, max_position_size_pct: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono font-bold"
                />
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">STOP LOSS %</span>
                <input
                  type="number"
                  step="0.01"
                  value={form.default_stop_loss_pct}
                  onChange={(e) => setForm({ ...form, default_stop_loss_pct: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono font-bold text-rose-400"
                />
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">TAKE PROFIT %</span>
                <input
                  type="number"
                  step="0.01"
                  value={form.default_take_profit_pct}
                  onChange={(e) => setForm({ ...form, default_take_profit_pct: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono font-bold text-emerald-400"
                />
              </div>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition disabled:opacity-50 shadow-md shadow-emerald-600/20"
            >
              <Save className="w-4 h-4" />
              <span>{loading ? 'Saving...' : 'Save Configuration'}</span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
}
