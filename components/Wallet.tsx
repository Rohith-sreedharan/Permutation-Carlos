import React, { useState, useEffect } from 'react';
import { getUserWallet } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

const Wallet: React.FC = () => {
  const [wallet, setWallet] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadWallet = async () => {
      try {
        setLoading(true);
        const data = await getUserWallet();
        setWallet(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load wallet');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadWallet();
  }, []);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  if (!wallet) {
    return <div className="text-center text-light-gray p-8">No wallet data available</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-white font-teko mb-6">My Wallet</h1>
      
      {/* Balance Card */}
      <div className="bg-gradient-to-br from-electric-blue to-purple-600 rounded-lg shadow-lg p-8">
        <p className="text-sm text-white/70 uppercase tracking-wider">Current Balance</p>
        <h2 className="text-5xl font-bold text-white mt-2">
          ${wallet.balance?.toFixed(2) || '0.00'} <span className="text-2xl font-normal">{wallet.currency || 'USD'}</span>
        </h2>
        <div className="flex space-x-4 mt-6">
          <button className="flex-1 bg-white text-electric-blue font-semibold py-3 rounded-lg hover:bg-opacity-90 transition-colors">
            Deposit
          </button>
          <button className="flex-1 bg-white/20 text-white font-semibold py-3 rounded-lg hover:bg-white/30 transition-colors backdrop-blur">
            Withdraw
          </button>
        </div>
      </div>

      {/* Transaction History */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Transaction History</h3>
        {wallet.transactions && wallet.transactions.length > 0 ? (
          <div className="space-y-3">
            {wallet.transactions.map((tx: any, index: number) => (
              <div key={tx.id || index} className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
                <div className="flex items-center space-x-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    tx.type === 'deposit' ? 'bg-neon-green/20' : 'bg-bold-red/20'
                  }`}>
                    <span className="text-xl">
                      {tx.type === 'deposit' ? '↓' : '↑'}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-white capitalize">{tx.type || 'Transaction'}</p>
                    <p className="text-sm text-light-gray">{tx.description || 'No description'}</p>
                    <p className="text-xs text-light-gray">{tx.timestamp ? new Date(tx.timestamp).toLocaleString() : 'N/A'}</p>
                  </div>
                </div>
                <div className={`text-lg font-bold ${
                  tx.amount >= 0 ? 'text-neon-green' : 'text-bold-red'
                }`}>
                  {tx.amount >= 0 ? '+' : ''}{tx.amount?.toFixed(2) || '0.00'} {wallet.currency || 'USD'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-center text-light-gray py-8">No transactions yet</p>
        )}
      </div>
    </div>
  );
};

export default Wallet;