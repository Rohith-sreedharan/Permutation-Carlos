import React, { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const LandingPage: React.FC<{ onLaunch: () => void }> = ({ onLaunch }) => {
  const [email, setEmail] = useState('');
  const [founderCount, setFounderCount] = useState(243);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [referralCode, setReferralCode] = useState('');

  useEffect(() => {
    // Load founder count from backend
    fetch(`${API_BASE_URL}/api/waitlist/count`)
      .then(res => res.json())
      .then(data => setFounderCount(data.count || 243))
      .catch(() => setFounderCount(243));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/waitlist/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, referral_code: referralCode })
      });

      if (response.ok) {
        const data = await response.json();
        setReferralCode(data.referral_code);
        setIsSubmitted(true);
        setFounderCount(prev => Math.min(prev + 1, 300));
      }
    } catch (error) {
      console.error('Waitlist signup failed:', error);
    }
  };

  const founderPercentage = (founderCount / 300) * 100;
  const spotsRemaining = 300 - founderCount;

  return (
    <div className="min-h-screen bg-dark-navy text-white overflow-hidden">
      {/* Hero Section */}
      <div className="relative min-h-screen flex flex-col items-center justify-center px-4">
        {/* Animated Background Grid */}
        <div className="absolute inset-0 opacity-20">
          <div className="absolute inset-0" style={{
            backgroundImage: 'linear-gradient(rgba(212, 166, 74, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(212, 166, 74, 0.1) 1px, transparent 1px)',
            backgroundSize: '50px 50px'
          }}></div>
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-4xl text-center">
          {/* Logo */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-linear-to-br from-gold to-light-gold rounded-lg flex items-center justify-center">
                <svg className="w-8 h-8 text-dark-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h1 className="text-5xl font-bold text-gold font-teko">BEATVEGAS</h1>
            </div>
            <p className="text-muted-text text-sm tracking-widest uppercase">Institutional-Grade Intelligence</p>
          </div>

          {/* Hero Headline */}
          <h2 className="text-6xl md:text-7xl font-bold mb-6 font-teko leading-tight">
            <span className="text-white">The House Always Wins.</span>
            <br />
            <span className="text-gold">Until Now.</span>
          </h2>

          <p className="text-xl md:text-2xl text-muted-text mb-12 max-w-2xl mx-auto leading-relaxed">
            Monte Carlo simulations running <span className="text-light-gold font-bold">100,000 iterations</span> to
            expose market inefficiencies. Access institutional-grade forecasting before the public.
          </p>

          {/* Founder Counter */}
          <div className="bg-linear-to-br from-card-gray to-charcoal border border-gold/30 rounded-2xl p-8 mb-8">
            <div className="flex items-center justify-between mb-4">
              <div className="text-left">
                <div className="text-4xl font-bold text-gold font-teko">{founderCount} / 300</div>
                <div className="text-sm text-muted-text uppercase tracking-wide">Founder Spots Taken</div>
              </div>
              <div className="text-right">
                <div className="text-4xl font-bold text-deep-red font-teko">{spotsRemaining}</div>
                <div className="text-sm text-muted-text uppercase tracking-wide">Spots Remaining</div>
              </div>
            </div>
            
            {/* Progress Bar */}
            <div className="w-full h-3 bg-charcoal rounded-full overflow-hidden">
              <div 
                className="h-full bg-linear-to-r from-gold to-light-gold transition-all duration-1000"
                style={{ width: `${founderPercentage}%` }}
              ></div>
            </div>
          </div>

          {/* Waitlist Form or Success State */}
          {!isSubmitted ? (
            <form onSubmit={handleSubmit} className="max-w-md mx-auto">
              <div className="flex flex-col sm:flex-row gap-3 mb-6">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  required
                  className="flex-1 px-6 py-4 bg-card-gray border border-border-gray rounded-lg text-white placeholder-muted-text focus:outline-none focus:border-gold transition-colors"
                />
                <button
                  type="submit"
                  className="px-8 py-4 bg-linear-to-r from-gold to-light-gold text-dark-navy font-bold rounded-lg hover:shadow-lg hover:shadow-gold/50 transition-all transform hover:scale-105 whitespace-nowrap"
                >
                  Join Waitlist
                </button>
              </div>
              <p className="text-sm text-muted-text">
                🔥 Refer 3 friends to unlock <span className="text-gold font-semibold">Early Access</span>
              </p>
            </form>
          ) : (
            <div className="max-w-md mx-auto bg-linear-to-br from-gold/10 to-light-gold/10 border border-gold/50 rounded-2xl p-6">
              <div className="text-6xl mb-4">✓</div>
              <h3 className="text-2xl font-bold text-gold mb-3">You're In!</h3>
              <p className="text-muted-text mb-6">
                Share your referral code to skip the line:
              </p>
              <div className="bg-charcoal rounded-lg p-4 mb-4">
                <code className="text-gold text-lg font-mono">beatvegas.ai/ref/{referralCode}</code>
              </div>
              <p className="text-sm text-muted-text">
                Refer 3 friends = <span className="text-neon-green font-bold">Instant Access</span>
              </p>
            </div>
          )}

          {/* Trust Indicators */}
          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
            <div className="bg-card-gray/50 border border-border-gray rounded-xl p-6">
              <div className="text-3xl mb-2">🔒</div>
              <h3 className="text-gold font-bold mb-2">Institutional Quality</h3>
              <p className="text-sm text-muted-text">Same compute power used by Wall Street quant funds</p>
            </div>
            <div className="bg-card-gray/50 border border-border-gray rounded-xl p-6">
              <div className="text-3xl mb-2">⚡</div>
              <h3 className="text-gold font-bold mb-2">Real-Time Edge</h3>
              <p className="text-sm text-muted-text">Line movement alerts before public consensus shifts</p>
            </div>
            <div className="bg-card-gray/50 border border-border-gray rounded-xl p-6">
              <div className="text-3xl mb-2">📊</div>
              <h3 className="text-gold font-bold mb-2">Transparent Tracking</h3>
              <p className="text-sm text-muted-text">Public accuracy ledger. Every forecast verified.</p>
            </div>
          </div>

          {/* CTA for Existing Users */}
          {founderCount >= 300 && (
            <div className="mt-12">
              <button
                onClick={onLaunch}
                className="px-8 py-4 bg-deep-red text-white font-bold rounded-lg hover:bg-light-red transition-colors"
              >
                Already a Member? Login →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Distribution Curve Visualization Section */}
      <div className="relative py-20 px-4 border-t border-border-gray">
        <div className="max-w-6xl mx-auto text-center">
          <h3 className="text-4xl font-bold text-white mb-6 font-teko">
            See What The House <span className="text-gold">Can't Hide</span>
          </h3>
          <p className="text-xl text-muted-text mb-12 max-w-2xl mx-auto">
            Every outcome simulated 100,000 times. Discover the distribution the sportsbooks don't want you to see.
          </p>
          
          {/* Placeholder for animated distribution curve */}
          <div className="bg-linear-to-br from-card-gray to-charcoal border border-gold/30 rounded-2xl p-12">
            <div className="h-64 flex items-end justify-center gap-1">
              {Array.from({ length: 50 }).map((_, i) => {
                const height = Math.exp(-Math.pow((i - 25) / 10, 2)) * 100;
                return (
                  <div
                    key={i}
                    className="w-full bg-linear-to-t from-gold to-light-gold rounded-t-sm transition-all duration-300 hover:from-light-gold hover:to-gold"
                    style={{ height: `${height}%` }}
                  ></div>
                );
              })}
            </div>
            <div className="mt-6 text-sm text-muted-text">
              Monte Carlo Distribution Curve • 100,000 Simulations
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
