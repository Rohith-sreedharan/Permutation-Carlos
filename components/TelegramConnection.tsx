import React, { useState, useEffect } from 'react';
import { TELEGRAM_CONNECTION_COPY } from '../uiCopy/products';

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

interface AccessNotification {
  event_id: string;
  event_type: string;
  title: string;
  message: string;
  cta_url: string | null;
  cta_text: string | null;
  created_at: string;
  is_read: boolean;
}

export default function TelegramConnection() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [instructions, setInstructions] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [unlinking, setUnlinking] = useState(false);
  const [notifications, setNotifications] = useState<AccessNotification[]>([]);
  const [showInstructions, setShowInstructions] = useState(false);

  useEffect(() => {
    fetchStatus();
    fetchNotifications();
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/telegram/status', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch Telegram status:', error);
      setLoading(false);
    }
  };

  const fetchNotifications = async () => {
    try {
      const response = await fetch('/api/telegram/notifications', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (Array.isArray(data)) {
        setNotifications(data.filter((n: AccessNotification) => !n.is_read).slice(0, 3));
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
      setNotifications([]);
    }
  };

  const handleGenerateLinkToken = async () => {
    try {
      const response = await fetch('/api/telegram/link', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });
      const data: LinkTokenResponse = await response.json();
      setLinkToken(data.link_token);
      setInstructions(data.instructions);
      setShowInstructions(true);
    } catch (error) {
      console.error('Failed to generate link token:', error);
    }
  };

  const handleUnlink = async () => {
    if (!confirm('Are you sure you want to unlink your Telegram account? You will lose access to signal channels.')) {
      return;
    }

    setUnlinking(true);
    try {
      await fetch('/api/telegram/unlink', {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      await fetchStatus();
      setLinkToken(null);
      setShowInstructions(false);
    } catch (error) {
      console.error('Failed to unlink Telegram:', error);
    } finally {
      setUnlinking(false);
    }
  };

  const markNotificationRead = async (eventId: string) => {
    try {
      await fetch(`/api/telegram/notifications/${eventId}/read`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      setNotifications(notifications.filter(n => n.event_id !== eventId));
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin h-8 w-8 border-4 border-electric-blue border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!status) {
    return (
      <div className="bg-bold-red/10 border border-bold-red rounded-lg p-4">
        <p className="text-bold-red">Failed to load Telegram status.</p>
      </div>
    );
  }

  const connected = TELEGRAM_CONNECTION_COPY.CONNECTED;
  const notConnected = TELEGRAM_CONNECTION_COPY.NOT_CONNECTED;

  // ─── Connected state ───────────────────────────────────────────────────────
  if (status.linked && status.has_access) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white">{connected.pageTitle}</h2>
        </div>

        {/* Status card */}
        <div className="bg-charcoal border border-neon-green/30 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-neon-green text-lg font-semibold">{connected.statusLabel}</span>
          </div>

          <div className="space-y-2 text-sm">
            {status.telegram_username && (
              <div className="flex justify-between">
                <span className="text-light-gray">{connected.usernameLabel}</span>
                <span className="text-white font-medium">@{status.telegram_username}</span>
              </div>
            )}
            {status.telegram_connected_at && (
              <div className="flex justify-between">
                <span className="text-light-gray">{connected.connectedLabel}</span>
                <span className="text-white font-medium">
                  {new Date(status.telegram_connected_at).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>

          <div className="border-t border-navy pt-4">
            <p className="text-xs font-semibold text-white uppercase tracking-wide mb-2">Receiving</p>
            <ul className="space-y-1">
              {connected.receiving.map((item) => (
                <li key={item} className="text-sm text-light-gray flex items-center gap-2">
                  <span className="text-neon-green">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Notifications */}
        {notifications.length > 0 && (
          <div className="space-y-2">
            {notifications.map((notification) => (
              <div
                key={notification.event_id}
                className={`p-4 rounded-lg border ${
                  notification.event_type === 'telegram_granted'
                    ? 'bg-neon-green/10 border-neon-green/40'
                    : 'bg-navy/40 border-navy'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-white mb-1">{notification.title}</h3>
                    <p className="text-sm text-light-gray mb-2">{notification.message}</p>
                    {notification.cta_url && notification.cta_text && (
                      <a
                        href={notification.cta_url}
                        className="inline-flex items-center text-sm font-medium text-electric-blue hover:underline"
                      >
                        {notification.cta_text} →
                      </a>
                    )}
                  </div>
                  <button
                    onClick={() => markNotificationRead(notification.event_id)}
                    className="text-light-gray/50 hover:text-white ml-4"
                    aria-label="Dismiss"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleUnlink}
            disabled={unlinking}
            className="py-2 px-4 rounded-lg text-sm font-semibold border border-navy text-light-gray hover:text-white hover:border-light-gray/50 transition-all disabled:opacity-50"
          >
            {unlinking ? 'Disconnecting...' : connected.ctaDisconnect}
          </button>
        </div>
      </div>
    );
  }

  // ─── Not connected / instructions state ───────────────────────────────────
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">{notConnected.pageTitle}</h2>
        <p className="text-light-gray mt-1">{notConnected.subheadline}</p>
      </div>

      {/* Notifications */}
      {notifications.length > 0 && (
        <div className="space-y-2">
          {notifications.map((notification) => (
            <div
              key={notification.event_id}
              className="p-4 rounded-lg border bg-navy/40 border-navy"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-semibold text-white mb-1">{notification.title}</h3>
                  <p className="text-sm text-light-gray">{notification.message}</p>
                </div>
                <button
                  onClick={() => markNotificationRead(notification.event_id)}
                  className="text-light-gray/50 hover:text-white ml-4"
                  aria-label="Dismiss"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Connect instructions */}
      {!showInstructions ? (
        <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
          <ol className="space-y-3">
            {notConnected.instructions.map((step, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-light-gray">
                <span className="text-electric-blue font-bold shrink-0">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>

          <button
            onClick={handleGenerateLinkToken}
            className="w-full py-3 rounded-lg font-bold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
          >
            Generate Verification Code
          </button>
        </div>
      ) : (
        <div className="bg-charcoal border border-electric-blue/40 rounded-xl p-6 space-y-4">
          <ol className="space-y-3">
            {notConnected.instructions.map((step, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-light-gray">
                <span className="text-electric-blue font-bold shrink-0">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>

          {linkToken && (
            <div className="bg-navy rounded-lg p-4 space-y-2">
              <p className="text-xs text-light-gray">{notConnected.codeLabel}</p>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-mono font-bold text-electric-blue tracking-widest">
                  {linkToken}
                </span>
                <button
                  onClick={() => navigator.clipboard.writeText(linkToken)}
                  className="text-xs text-light-gray/60 hover:text-white transition-all"
                >
                  Copy
                </button>
              </div>
              <p className="text-xs text-light-gray/50">
                {notConnected.expiryLabel} ~60 minutes
              </p>
            </div>
          )}

          <p className="text-xs text-light-gray/50 text-center">{notConnected.statusWaiting}</p>

          <button
            onClick={() => window.open('https://t.me/BeatVegasBot', '_blank')}
            className="text-xs text-electric-blue hover:underline"
          >
            {notConnected.guideCta}
          </button>
        </div>
      )}
    </div>
  );
}

