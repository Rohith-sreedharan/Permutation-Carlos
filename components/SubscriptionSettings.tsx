import React, { useState, useEffect } from 'react';
import LoadingSpinner from './LoadingSpinner';
import { getSubscriptionStatus } from '../services/api';

interface SubscriptionData {
  tier: string;
  renewalDate: string;
  paymentMethod?: {
    last4: string;
    brand: string;
  };
  status: 'active' | 'canceled' | 'past_due';
}

const SubscriptionSettings: React.FC = () => {
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSubscription = async () => {
      try {
        setLoading(true);
        const data = await getSubscriptionStatus();
        setSubscription(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load subscription');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadSubscription();
  }, []);

  const handleManageSubscription = () => {
    // Redirect to Stripe Customer Portal
    window.location.href = '/api/stripe/customer-portal';
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  const tierInfo = {
    starter: { name: 'Starter', color: 'from-gray-500 to-gray-600', price: 'Free' },
    core: { name: 'Core', color: 'from-blue-500 to-blue-600', price: '$29/mo' },
    pro: { name: 'Pro', color: 'from-purple-500 to-purple-600', price: '$49/mo' },
    elite: { name: 'Elite', color: 'from-gold-500 to-gold-600', price: '$89/mo' },
    founder: { name: 'Founder', color: 'from-gold-600 to-yellow-500', price: 'Lifetime' }
  };

  const currentTier = (subscription?.tier || 'starter').toLowerCase();
  const tierConfig = tierInfo[currentTier as keyof typeof tierInfo] || tierInfo.starter;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-bold text-white font-teko">Billing & Subscription</h1>
        <span className="text-sm text-light-gray">Manage your plan and payment methods</span>
      </div>

      {/* Current Plan Card */}
      <div className={`bg-gradient-to-br ${tierConfig.color} rounded-lg shadow-lg p-8`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-white/70 uppercase tracking-wider">Current Plan</p>
            <h2 className="text-4xl font-bold text-white mt-2">{tierConfig.name}</h2>
            <p className="text-xl text-white/90 mt-1">{tierConfig.price}</p>
            
            {subscription?.renewalDate && currentTier !== 'starter' && (
              <p className="text-sm text-white/70 mt-4">
                Renews on {new Date(subscription.renewalDate).toLocaleDateString()}
              </p>
            )}
            
            {subscription?.status === 'past_due' && (
              <div className="mt-4 bg-bold-red/20 border border-bold-red text-white px-4 py-2 rounded">
                ⚠️ Payment failed. Please update your payment method.
              </div>
            )}
          </div>
          
          <div className="flex flex-col space-y-2">
            <button
              onClick={handleManageSubscription}
              className="bg-white text-navy font-semibold px-6 py-3 rounded-lg hover:bg-opacity-90 transition-colors"
            >
              Manage Subscription
            </button>
            {currentTier === 'starter' && (
              <button
                onClick={() => window.location.href = '/upgrade'}
                className="bg-electric-blue text-white font-semibold px-6 py-3 rounded-lg hover:bg-opacity-90 transition-colors"
              >
                Upgrade Plan
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Payment Method */}
      {subscription?.paymentMethod && (
        <div className="bg-charcoal rounded-lg shadow-lg p-6">
          <h3 className="text-xl font-bold text-white mb-4">Payment Method</h3>
          <div className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-8 bg-white rounded flex items-center justify-center">
                <span className="text-xs font-bold text-navy uppercase">
                  {subscription.paymentMethod.brand}
                </span>
              </div>
              <div>
                <p className="font-semibold text-white">•••• •••• •••• {subscription.paymentMethod.last4}</p>
                <p className="text-sm text-light-gray">Primary payment method</p>
              </div>
            </div>
            <button
              onClick={handleManageSubscription}
              className="text-electric-blue hover:underline font-semibold"
            >
              Update
            </button>
          </div>
        </div>
      )}

      {/* Plan Features */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Your Plan Includes</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {currentTier === 'starter' && (
            <>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Unlimited Simulations</p>
                  <p className="text-sm text-light-gray">10,000 iterations per analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Basic Analytics</p>
                  <p className="text-sm text-light-gray">Win probability & spread distribution</p>
                </div>
              </div>
            </>
          )}
          {currentTier === 'core' && (
            <>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Unlimited Simulations</p>
                  <p className="text-sm text-light-gray">25,000 iterations per analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Advanced Analytics</p>
                  <p className="text-sm text-light-gray">Volatility scoring & prop analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Creator Marketplace Access</p>
                  <p className="text-sm text-light-gray">Follow expert analysts</p>
                </div>
              </div>
            </>
          )}
          {currentTier === 'pro' && (
            <>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Unlimited Simulations</p>
                  <p className="text-sm text-light-gray">50,000 iterations per analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Premium Analytics</p>
                  <p className="text-sm text-light-gray">Full decision command center</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Parlay Correlation Engine</p>
                  <p className="text-sm text-light-gray">Cross-sport analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Priority Support</p>
                  <p className="text-sm text-light-gray">24/7 email support</p>
                </div>
              </div>
            </>
          )}
          {currentTier === 'elite' && (
            <>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Unlimited Simulations</p>
                  <p className="text-sm text-light-gray">100,000 iterations per analysis</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">Elite Analytics Suite</p>
                  <p className="text-sm text-light-gray">Real-time model performance tracking</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">API Access</p>
                  <p className="text-sm text-light-gray">Programmatic simulation access</p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-neon-green text-xl">✓</span>
                <div>
                  <p className="text-white font-semibold">White Glove Support</p>
                  <p className="text-sm text-light-gray">Dedicated account manager</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Compliance Notice */}
      <div className="bg-navy/30 border border-electric-blue/30 rounded-lg p-4">
        <p className="text-sm text-light-gray">
          <span className="text-electric-blue font-semibold">📊 Analysis Platform:</span> BeatVegas provides sports analytics and intelligence. We do not accept wagers or hold funds for betting purposes. All payments are for subscription access only.
        </p>
      </div>
    </div>
  );
};

export default SubscriptionSettings;
