import React, { useState, useEffect } from 'react';

interface TelegramStatus {
  linked: boolean;
  telegram_username: string | null;
  telegram_user_id: string | null;
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
      const data = await response.json();
      setNotifications(data.filter((n: AccessNotification) => !n.is_read).slice(0, 3));
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
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
        <div className="animate-spin h-8 w-8 border-4 border-amber-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!status) {
    return (
      <div className="bg-red-500/10 border border-red-500 rounded-lg p-4">
        <p className="text-red-400">Failed to load Telegram status</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-2">Telegram Integration</h2>
        <p className="text-gray-400">
          Connect your Telegram account to receive real-time qualified signals
        </p>
      </div>

      {/* Notifications */}
      {notifications.length > 0 && (
        <div className="space-y-2">
          {notifications.map(notification => (
            <div
              key={notification.event_id}
              className={`p-4 rounded-lg border ${
                notification.event_type === 'telegram_granted'
                  ? 'bg-green-500/10 border-green-500'
                  : 'bg-amber-500/10 border-amber-500'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-semibold text-white mb-1">
                    {notification.title}
                  </h3>
                  <p className="text-sm text-gray-300 mb-2">
                    {notification.message}
                  </p>
                  {notification.cta_url && notification.cta_text && (
                    <a
                      href={notification.cta_url}
                      className="inline-flex items-center text-sm font-medium text-amber-400 hover:text-amber-300"
                    >
                      {notification.cta_text} →
                    </a>
                  )}
                </div>
                <button
                  onClick={() => markNotificationRead(notification.event_id)}
                  className="text-gray-400 hover:text-white ml-4"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Connection Status */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center text-2xl">
              📱
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">
                {status.linked ? 'Connected' : 'Not Connected'}
              </h3>
              {status.linked && status.telegram_username && (
                <p className="text-gray-400">@{status.telegram_username}</p>
              )}
            </div>
          </div>
          
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
            status.linked
              ? 'bg-green-500/20 text-green-400'
              : 'bg-gray-700 text-gray-400'
          }`}>
            {status.linked ? '✓ Linked' : 'Not Linked'}
          </div>
        </div>

        {/* Access Status */}
        <div className="border-t border-gray-700 pt-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Telegram Signals Access</span>
            <span className={`font-semibold ${
              status.has_access ? 'text-green-400' : 'text-gray-500'
            }`}>
              {status.has_access ? 'Enabled' : 'Disabled'}
            </span>
          </div>

          {status.has_access && status.channels.length > 0 && (
            <div>
              <p className="text-sm text-gray-400 mb-2">Active Channels:</p>
              <div className="flex flex-wrap gap-2">
                {status.channels.map(channel => (
                  <span
                    key={channel}
                    className="px-3 py-1 bg-amber-500/20 text-amber-400 rounded-full text-sm font-medium"
                  >
                    #{channel}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Subscription Info */}
          <div className="bg-gray-900 rounded p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">BeatVegas Tier</span>
              <span className="text-white font-medium">
                {status.entitlements.beatvegas_tier.toUpperCase()}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Platform Subscription</span>
              <span className={`font-medium ${
                status.entitlements.beatvegas_subscription_active
                  ? 'text-green-400'
                  : 'text-gray-500'
              }`}>
                {status.entitlements.beatvegas_subscription_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Telegram-Only Subscription</span>
              <span className={`font-medium ${
                status.entitlements.telegram_only_subscription_active
                  ? 'text-green-400'
                  : 'text-gray-500'
              }`}>
                {status.entitlements.telegram_only_subscription_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          {!status.linked ? (
            <button
              onClick={handleGenerateLinkToken}
              className="flex-1 bg-amber-500 hover:bg-amber-600 text-black font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              Link Telegram Account
            </button>
          ) : (
            <button
              onClick={handleUnlink}
              disabled={unlinking}
              className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50"
            >
              {unlinking ? 'Unlinking...' : 'Unlink Account'}
            </button>
          )}
        </div>
      </div>

      {/* Link Instructions */}
      {showInstructions && linkToken && (
        <div className="bg-amber-500/10 border border-amber-500 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            Link Your Telegram Account
          </h3>
          
          <div className="bg-gray-900 rounded-lg p-4 mb-4">
            <p className="text-sm text-gray-400 mb-2">Your Link Code:</p>
            <div className="flex items-center justify-between bg-black rounded p-4">
              <span className="text-3xl font-mono font-bold text-amber-400 tracking-wider">
                {linkToken}
              </span>
              <button
                onClick={() => navigator.clipboard.writeText(linkToken)}
                className="text-gray-400 hover:text-white text-sm"
              >
                Copy
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">Expires in 1 hour</p>
          </div>

          <div className="space-y-3 text-sm text-gray-300">
            <p className="font-semibold text-white">Instructions:</p>
            {instructions?.split('\n').map((line, i) => (
              <p key={i} className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">{i + 1}.</span>
                <span>{line.replace(/^\d+\.\s*/, '')}</span>
              </p>
            ))}
          </div>

          <div className="mt-4 flex items-center gap-2 text-xs text-gray-400">
            <span>💡</span>
            <span>
              The bot will confirm once your account is linked. You can then request to join signal channels.
            </span>
          </div>
        </div>
      )}

      {/* Eligibility Notice */}
      {status.linked && !status.has_access && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-3">
            Telegram Access Not Included
          </h3>
          <p className="text-gray-400 mb-4">
            You're currently on the {status.entitlements.beatvegas_tier.toUpperCase()} plan.
            Telegram signal delivery requires the <strong>100k plan</strong> ($49.99/month) or higher.
          </p>
          <div className="flex gap-3">
            <a
              href="/billing/upgrade"
              className="bg-amber-500 hover:bg-amber-600 text-black font-semibold py-2 px-6 rounded-lg transition-colors"
            >
              Upgrade to 100k Plan
            </a>
            <a
              href="/billing/telegram-only"
              className="bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 px-6 rounded-lg transition-colors"
            >
              Get Telegram Only ($39)
            </a>
          </div>
        </div>
      )}

      {/* Success State */}
      {status.linked && status.has_access && (
        <div className="bg-green-500/10 border border-green-500 rounded-lg p-6">
          <div className="flex items-start gap-4">
            <span className="text-3xl">✅</span>
            <div>
              <h3 className="text-lg font-semibold text-white mb-2">
                You're All Set!
              </h3>
              <p className="text-gray-300 mb-3">
                You'll receive QUALIFIED signals in Telegram as they're generated.
                Make sure you've joined the signal channels.
              </p>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>• Max 3 qualified signals per day</li>
                <li>• Signals posted when edge ≥ 7 pts and win prob ≥ 56%</li>
                <li>• "Simulations: 100,000" displayed on all signals</li>
                <li>• Sharp side action shown for spread markets</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
