import React, { useState, useEffect } from 'react';
import { getToken } from '../services/api';

interface TelegramStatus {
  linked: boolean;
  telegram_username: string | null;
  telegram_user_id: string | null;
  telegram_connected_at?: string | null;
  has_access: boolean;
  channels: string[];
  entitlements: {
    telegram_signals: boolean;
    telegram_premium: boolean;
    beatvegas_tier: string;
    beatvegas_subscription_active: boolean;
    telegram_only_subscription_active: boolean;
  };
}

export default function TelegramConnection() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [deepLink, setDeepLink] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [pollCount, setPollCount] = useState(0);

  const authHeader = () => ({ 'Authorization': `Bearer ${getToken()}` });

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/telegram/status', { headers: authHeader() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus(await res.json());
    } catch (e) {
      console.error('Telegram status fetch failed:', e);
      // Leave status as null — handled below
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Poll for connection confirmation after deep link is generated
  useEffect(() => {
    if (!deepLink) return;
    const id = setInterval(async () => {
      await fetchStatus();
      setPollCount(c => c + 1);
    }, 4000);
    return () => clearInterval(id);
  }, [deepLink]);

  // Stop polling once connected
  useEffect(() => {
    if (status?.linked && deepLink) setDeepLink(null);
  }, [status?.linked]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await fetch('/api/v1/telegram/connect', {
        method: 'POST',
        headers: { ...authHeader(), 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDeepLink(data.deep_link);
    } catch (e) {
      console.error('Telegram connect failed:', e);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Telegram? You will lose channel access until you reconnect.')) return;
    setDisconnecting(true);
    try {
      await fetch('/api/telegram/unlink', {
        method: 'DELETE',
        headers: authHeader(),
      });
      setDeepLink(null);
      await fetchStatus();
    } catch (e) {
      console.error('Telegram disconnect failed:', e);
    } finally {
      setDisconnecting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin h-8 w-8 border-4 border-electric-blue border-t-transparent rounded-full" />
      </div>
    );
  }

  // ── STATE 1 — Intelligence Preview: no telegram_access ─────────────────────
  // Show upgrade gate — NOT an error
  if (!status || !status.has_access) {
    return (
      <div className="space-y-6 max-w-lg">
        <div>
          <h2 className="text-2xl font-bold text-white">Telegram Syndicate Channel</h2>
          <p className="text-light-gray mt-1 text-sm">
            Intelligence signals delivered automatically to Telegram. Every EDGE and LEAN
            classification posted in real time.
          </p>
        </div>
        <div className="bg-charcoal border border-yellow-400/20 rounded-xl p-6 space-y-4">
          <p className="text-sm text-light-gray">
            Available on Syndicate and Platform plans.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <a
              href="https://beatvegas.app/upgrade"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center border border-yellow-400 text-yellow-400 font-bold py-3 rounded-lg hover:bg-yellow-400/10 transition-colors text-sm"
            >
              Join Syndicate — $39/month
            </a>
            <a
              href="https://beatvegas.app/upgrade"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center bg-yellow-400 text-[#0a0e1a] font-bold py-3 rounded-lg hover:bg-yellow-300 transition-colors text-sm"
            >
              Upgrade to Platform — $97/month
            </a>
          </div>
        </div>
      </div>
    );
  }

  // ── STATE 3 — Connected ─────────────────────────────────────────────────────
  if (status.linked) {
    return (
      <div className="space-y-6 max-w-lg">
        <div>
          <h2 className="text-2xl font-bold text-white">Telegram Connected</h2>
        </div>
        <div className="bg-charcoal border border-neon-green/30 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-neon-green inline-block" />
            <span className="text-neon-green font-semibold">
              Connected{status.telegram_username ? ` — @${status.telegram_username}` : ''}
            </span>
          </div>
          {status.telegram_connected_at && (
            <p className="text-xs text-light-gray/60">
              Connected {new Date(status.telegram_connected_at).toLocaleDateString()}
            </p>
          )}
          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <a
              href="https://t.me/beatvegas_syndicate_channel"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center bg-electric-blue text-white font-bold py-2.5 rounded-lg hover:bg-electric-blue/90 transition-colors text-sm"
            >
              View Syndicate Channel →
            </a>
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="flex-1 border border-border-gray text-light-gray font-semibold py-2.5 rounded-lg hover:border-light-gray/50 hover:text-white transition-colors text-sm disabled:opacity-50"
            >
              {disconnecting ? 'Disconnecting…' : 'Disconnect'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── STATE 2 — Subscriber, not yet connected ─────────────────────────────────
  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h2 className="text-2xl font-bold text-white">Connect Your Telegram Account</h2>
        <p className="text-light-gray mt-1 text-sm">
          Join the BeatVegas Syndicate channel to receive intelligence signals automatically.
        </p>
      </div>
      <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
        {!deepLink ? (
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full bg-electric-blue text-white font-bold py-3 rounded-lg hover:bg-electric-blue/90 transition-colors disabled:opacity-50"
          >
            {connecting ? 'Generating link…' : 'Connect Telegram →'}
          </button>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-light-gray">
              Tap the button below to open Telegram and complete the connection. The link
              expires in 15 minutes.
            </p>
            <a
              href={deepLink}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-electric-blue text-white font-bold py-3 rounded-lg hover:bg-electric-blue/90 transition-colors"
            >
              Open Telegram — Complete Connection
            </a>
            <p className="text-xs text-light-gray/50 text-center">
              {pollCount > 0 ? 'Waiting for confirmation…' : 'Page will update automatically once connected.'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


interface TelegramStatus {
  linked: boolean;
  telegram_username: string | null;
  telegram_user_id: string | null;
  telegram_connected_at?: string | null;
  has_access: boolean;
  channels: string[];
  entitlements: {
    telegram_signals: boolean;
    telegram_premium: boolean;
    beatvegas_tier: string;
    beatvegas_subscription_active: boolean;
    telegram_only_subscription_active: boolean;
  };
}

interface LinkTokenResponse {
  link_token: string;
  expires_in: number;
  instructions: string;
}


