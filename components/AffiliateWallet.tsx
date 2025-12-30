import React, { useState, useEffect } from 'react';
import LoadingSpinner from './LoadingSpinner';
import { getAffiliateEarnings } from '../services/api';

interface EarningsData {
  lifetimeEarnings: number;
  pendingPayout: number;
  nextPayoutDate: string;
  isConnected: boolean;
  payouts: Array<{
    id: string;
    date: string;
    amount: number;
    status: 'completed' | 'pending' | 'failed';
  }>;
}

const AffiliateWallet: React.FC = () => {
  const [earnings, setEarnings] = useState<EarningsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadEarnings = async () => {
      try {
        setLoading(true);
        const data = await getAffiliateEarnings();
        setEarnings(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load earnings');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadEarnings();
  }, []);

  const handleConnectBank = () => {
    // Redirect to Stripe Connect Onboarding
    window.location.href = '/api/stripe/connect/onboard';
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-bold text-white font-teko">Creator Earnings</h1>
        <span className="text-sm text-light-gray">Your marketplace revenue</span>
      </div>

      {/* Earnings Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-linear-to-br from-neon-green to-green-600 rounded-lg shadow-lg p-6">
          <p className="text-sm text-white/70 uppercase tracking-wider">Lifetime Earnings</p>
          <h2 className="text-4xl font-bold text-white mt-2">
            ${earnings?.lifetimeEarnings?.toFixed(2) || '0.00'}
          </h2>
          <p className="text-sm text-white/80 mt-1">Total revenue earned</p>
        </div>

        <div className="bg-linear-to-br from-electric-blue to-blue-600 rounded-lg shadow-lg p-6">
          <p className="text-sm text-white/70 uppercase tracking-wider">Pending Payout</p>
          <h2 className="text-4xl font-bold text-white mt-2">
            ${earnings?.pendingPayout?.toFixed(2) || '0.00'}
          </h2>
          <p className="text-sm text-white/80 mt-1">Ready for transfer</p>
        </div>

        <div className="bg-linear-to-br from-purple-500 to-purple-600 rounded-lg shadow-lg p-6">
          <p className="text-sm text-white/70 uppercase tracking-wider">Next Payout</p>
          <h2 className="text-2xl font-bold text-white mt-2">
            {earnings?.nextPayoutDate
              ? new Date(earnings.nextPayoutDate).toLocaleDateString()
              : 'Not scheduled'}
          </h2>
          <p className="text-sm text-white/80 mt-1">Automatic transfer</p>
        </div>
      </div>

      {/* Bank Connection */}
      {!earnings?.isConnected ? (
        <div className="bg-charcoal rounded-lg shadow-lg p-8 border-2 border-dashed border-electric-blue/30">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-electric-blue/20 rounded-full mb-4">
              <span className="text-3xl">🏦</span>
            </div>
            <h3 className="text-2xl font-bold text-white mb-2">Connect Your Bank Account</h3>
            <p className="text-light-gray mb-6">
              Set up direct deposit via Stripe Connect to receive your earnings automatically.
            </p>
            <button
              onClick={handleConnectBank}
              className="bg-electric-blue text-white font-semibold px-8 py-3 rounded-lg hover:bg-opacity-90 transition-colors"
            >
              Connect Bank Account
            </button>
            <p className="text-xs text-light-gray mt-4">
              Powered by Stripe • Secure • Encrypted
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-charcoal rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-white">Bank Account</h3>
            <span className="text-neon-green text-sm flex items-center">
              <span className="w-2 h-2 bg-neon-green rounded-full mr-2"></span>
              Connected
            </span>
          </div>
          <div className="bg-navy/50 p-4 rounded-lg">
            <p className="text-white font-semibold">Bank account connected via Stripe</p>
            <p className="text-sm text-light-gray">Payouts are processed automatically</p>
          </div>
        </div>
      )}

      {/* Payout History */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Payout History</h3>
        {earnings?.payouts && earnings.payouts.length > 0 ? (
          <div className="space-y-3">
            {earnings.payouts.map((payout) => (
              <div key={payout.id} className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
                <div className="flex items-center space-x-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    payout.status === 'completed'
                      ? 'bg-neon-green/20'
                      : payout.status === 'pending'
                      ? 'bg-electric-blue/20'
                      : 'bg-bold-red/20'
                  }`}>
                    <span className="text-xl">
                      {payout.status === 'completed'
                        ? '✓'
                        : payout.status === 'pending'
                        ? '⏱'
                        : '✗'}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-white capitalize">{payout.status}</p>
                    <p className="text-sm text-light-gray">
                      {new Date(payout.date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="text-lg font-bold text-white">
                  ${payout.amount.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-center text-light-gray py-8">No payouts yet</p>
        )}
      </div>

      {/* Revenue Split Info */}
      <div className="bg-navy/30 border border-electric-blue/30 rounded-lg p-4">
        <p className="text-sm text-light-gray">
          <span className="text-electric-blue font-semibold">💰 Revenue Split:</span> You earn 70% of all subscription and report sales. BeatVegas retains 30% for platform operations. Payouts are processed automatically on the 1st of each month.
        </p>
      </div>
    </div>
  );
};

export default AffiliateWallet;
