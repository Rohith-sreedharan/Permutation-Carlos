import React, { useState } from 'react';
import LoadingSpinner from './LoadingSpinner';

interface OnboardingData {
  bankroll: number;
  unit_size: number;
  unit_strategy: 'fixed' | 'percentage';
  risk_profile: 'grinder' | 'gunslinger';
  preferred_sports: string[];
  preferred_markets: string[];
}

interface OnboardingWizardProps {
  onComplete: () => void;
  onSkip: () => void;
}

const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ onComplete, onSkip }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<OnboardingData>({
    bankroll: 1000,
    unit_size: 50,
    unit_strategy: 'fixed',
    risk_profile: 'grinder',
    preferred_sports: [],
    preferred_markets: []
  });

  const handleBankrollChange = (value: number) => {
    setFormData(prev => ({ ...prev, bankroll: value }));
    
    // Auto-calculate conservative unit size (1% of bankroll)
    if (formData.unit_strategy === 'percentage') {
      setFormData(prev => ({ ...prev, unit_size: Math.round(value * 0.01) }));
    }
  };

  const handleUnitStrategyChange = (strategy: 'fixed' | 'percentage') => {
    setFormData(prev => ({ 
      ...prev, 
      unit_strategy: strategy,
      unit_size: strategy === 'percentage' ? Math.round(prev.bankroll * 0.01) : 50
    }));
  };

  const toggleSport = (sport: string) => {
    setFormData(prev => ({
      ...prev,
      preferred_sports: prev.preferred_sports.includes(sport)
        ? prev.preferred_sports.filter(s => s !== sport)
        : [...prev.preferred_sports, sport]
    }));
  };

  const toggleMarket = (market: string) => {
    setFormData(prev => ({
      ...prev,
      preferred_markets: prev.preferred_markets.includes(market)
        ? prev.preferred_markets.filter(m => m !== market)
        : [...prev.preferred_markets, market]
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:8000/api/user/profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        throw new Error('Failed to save profile');
      }

      // Mark onboarding as complete
      localStorage.setItem('onboarding_complete', 'true');
      
      // Trigger completion callback
      onComplete();
    } catch (err: any) {
      setError(err.message || 'Failed to save profile. Please try again.');
      setLoading(false);
    }
  };

  const nextStep = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const canProceed = () => {
    if (currentStep === 1) {
      return formData.bankroll > 0 && formData.unit_size > 0;
    }
    if (currentStep === 2) {
      return formData.risk_profile !== null;
    }
    if (currentStep === 3) {
      return formData.preferred_sports.length > 0 && formData.preferred_markets.length > 0;
    }
    return true;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-navy flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-navy flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-black text-white font-teko mb-2">
            STRATEGY WIZARD
          </h1>
          <p className="text-light-gray text-lg">
            Let's personalize your AI betting experience
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-light-gray">Step {currentStep} of 3</span>
            <span className="text-sm text-electric-blue">{Math.round((currentStep / 3) * 100)}% Complete</span>
          </div>
          <div className="h-2 bg-charcoal rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-electric-blue to-purple-600 transition-all duration-300"
              style={{ width: `${(currentStep / 3) * 100}%` }}
            />
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-charcoal rounded-2xl p-8 border border-navy">
          {/* Step 1: The Bankroll */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div className="text-center mb-6">
                <div className="text-5xl mb-3">💰</div>
                <h2 className="text-3xl font-bold text-white font-teko mb-2">THE BANKROLL</h2>
                <p className="text-light-gray">Set your starting capital and unit size</p>
              </div>

              {/* Starting Bankroll */}
              <div>
                <label className="block text-white font-semibold mb-2">
                  Starting Bankroll
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-light-gray text-xl">$</span>
                  <input
                    type="number"
                    value={formData.bankroll}
                    onChange={(e) => handleBankrollChange(parseInt(e.target.value) || 0)}
                    className="w-full bg-dark-navy border border-navy rounded-lg px-4 py-3 pl-8 text-white text-xl focus:ring-2 focus:ring-electric-blue focus:outline-none"
                    placeholder="1000"
                  />
                </div>
                <p className="text-xs text-light-gray mt-1">
                  💡 Only bet what you can afford to lose
                </p>
              </div>

              {/* Unit Strategy */}
              <div>
                <label className="block text-white font-semibold mb-3">
                  Unit Size Strategy
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => handleUnitStrategyChange('fixed')}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      formData.unit_strategy === 'fixed'
                        ? 'border-electric-blue bg-electric-blue/10'
                        : 'border-navy hover:border-light-gray'
                    }`}
                  >
                    <div className="text-2xl mb-2">🎯</div>
                    <div className="text-white font-semibold mb-1">Fixed</div>
                    <div className="text-sm text-light-gray">Same bet every time</div>
                  </button>
                  
                  <button
                    onClick={() => handleUnitStrategyChange('percentage')}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      formData.unit_strategy === 'percentage'
                        ? 'border-electric-blue bg-electric-blue/10'
                        : 'border-navy hover:border-light-gray'
                    }`}
                  >
                    <div className="text-2xl mb-2">📊</div>
                    <div className="text-white font-semibold mb-1">Percentage</div>
                    <div className="text-sm text-light-gray">1% of bankroll</div>
                  </button>
                </div>
              </div>

              {/* Unit Size */}
              <div>
                <label className="block text-white font-semibold mb-2">
                  Typical Unit Size
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-light-gray text-xl">$</span>
                  <input
                    type="number"
                    value={formData.unit_size}
                    onChange={(e) => setFormData(prev => ({ ...prev, unit_size: parseInt(e.target.value) || 0 }))}
                    disabled={formData.unit_strategy === 'percentage'}
                    className={`w-full bg-dark-navy border border-navy rounded-lg px-4 py-3 pl-8 text-white text-xl focus:ring-2 focus:ring-electric-blue focus:outline-none ${
                      formData.unit_strategy === 'percentage' ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                    placeholder="50"
                  />
                </div>
                <p className="text-xs text-light-gray mt-1">
                  {formData.unit_strategy === 'percentage' 
                    ? `Auto-calculated: ${((formData.unit_size / formData.bankroll) * 100).toFixed(1)}% of bankroll`
                    : `Recommended: $${Math.round(formData.bankroll * 0.01)} - $${Math.round(formData.bankroll * 0.05)}`
                  }
                </p>
              </div>

              {/* Risk Warning */}
              <div className="bg-bold-red/10 border border-bold-red/30 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <span className="text-2xl">⚠️</span>
                  <div>
                    <div className="text-bold-red font-semibold mb-1">Responsible Gaming</div>
                    <div className="text-sm text-light-gray">
                      Never bet more than you can afford to lose. The AI can predict edges, but variance is real.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Risk Profile */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div className="text-center mb-6">
                <div className="text-5xl mb-3">🎲</div>
                <h2 className="text-3xl font-bold text-white font-teko mb-2">THE RISK PROFILE</h2>
                <p className="text-light-gray">Choose your betting personality</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Grinder */}
                <button
                  onClick={() => setFormData(prev => ({ ...prev, risk_profile: 'grinder' }))}
                  className={`p-6 rounded-xl border-2 text-left transition-all ${
                    formData.risk_profile === 'grinder'
                      ? 'border-neon-green bg-neon-green/10'
                      : 'border-navy hover:border-light-gray'
                  }`}
                >
                  <div className="text-4xl mb-3">📊</div>
                  <h3 className="text-2xl font-bold text-white font-teko mb-2">GRINDER</h3>
                  <p className="text-light-gray text-sm mb-4">
                    Low risk, high win rate. Focus on consistent profits over flashy wins.
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center space-x-2">
                      <span className="text-neon-green">✓</span>
                      <span className="text-white">Low volatility picks</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-neon-green">✓</span>
                      <span className="text-white">High confidence (75%+)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-neon-green">✓</span>
                      <span className="text-white">Steady bankroll growth</span>
                    </div>
                  </div>
                  {formData.risk_profile === 'grinder' && (
                    <div className="mt-4 text-neon-green font-semibold flex items-center space-x-2">
                      <span>✓</span>
                      <span>SELECTED</span>
                    </div>
                  )}
                </button>

                {/* Gunslinger */}
                <button
                  onClick={() => setFormData(prev => ({ ...prev, risk_profile: 'gunslinger' }))}
                  className={`p-6 rounded-xl border-2 text-left transition-all ${
                    formData.risk_profile === 'gunslinger'
                      ? 'border-bold-red bg-bold-red/10'
                      : 'border-navy hover:border-light-gray'
                  }`}
                >
                  <div className="text-4xl mb-3">🔥</div>
                  <h3 className="text-2xl font-bold text-white font-teko mb-2">GUNSLINGER</h3>
                  <p className="text-light-gray text-sm mb-4">
                    High risk, high reward. Swing for the fences with volatile picks.
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center space-x-2">
                      <span className="text-bold-red">✓</span>
                      <span className="text-white">High volatility tolerance</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-bold-red">✓</span>
                      <span className="text-white">High EV upside (10%+)</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-bold-red">✓</span>
                      <span className="text-white">Big win potential</span>
                    </div>
                  </div>
                  {formData.risk_profile === 'gunslinger' && (
                    <div className="mt-4 text-bold-red font-semibold flex items-center space-x-2">
                      <span>✓</span>
                      <span>SELECTED</span>
                    </div>
                  )}
                </button>
              </div>

              {/* Explanation */}
              <div className="bg-navy/50 rounded-lg p-4">
                <div className="text-sm text-light-gray">
                  <strong className="text-white">What does this affect?</strong><br/>
                  The AI's Risk Agent will filter picks based on your profile. Grinders see low-variance plays, Gunslingers see high-upside bets.
                </div>
              </div>
            </div>
          )}

          {/* Step 3: The Focus */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="text-center mb-6">
                <div className="text-5xl mb-3">🎯</div>
                <h2 className="text-3xl font-bold text-white font-teko mb-2">THE FOCUS</h2>
                <p className="text-light-gray">Choose your favorite sports and markets</p>
              </div>

              {/* Preferred Sports */}
              <div>
                <label className="block text-white font-semibold mb-3">
                  Favorite Sports
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {['NBA', 'NFL', 'MLB', 'NHL', 'CFB', 'CBB'].map(sport => (
                    <button
                      key={sport}
                      onClick={() => toggleSport(sport)}
                      className={`py-3 px-4 rounded-lg border-2 font-semibold transition-all ${
                        formData.preferred_sports.includes(sport)
                          ? 'border-electric-blue bg-electric-blue/10 text-electric-blue'
                          : 'border-navy text-light-gray hover:border-light-gray'
                      }`}
                    >
                      {sport}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-light-gray mt-2">
                  Select at least one sport
                </p>
              </div>

              {/* Preferred Markets */}
              <div>
                <label className="block text-white font-semibold mb-3">
                  Preferred Markets
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'spreads', label: 'Spreads', icon: '📊' },
                    { key: 'totals', label: 'Totals (O/U)', icon: '⚡' },
                    { key: 'moneyline', label: 'Moneyline', icon: '💰' },
                    { key: 'player_props', label: 'Player Props', icon: '🏀' },
                    { key: 'parlays', label: 'Parlays', icon: '🎯' },
                    { key: 'live', label: 'Live Betting', icon: '🔴' }
                  ].map(market => (
                    <button
                      key={market.key}
                      onClick={() => toggleMarket(market.key)}
                      className={`py-3 px-4 rounded-lg border-2 font-semibold transition-all text-left ${
                        formData.preferred_markets.includes(market.key)
                          ? 'border-purple-600 bg-purple-600/10 text-purple-400'
                          : 'border-navy text-light-gray hover:border-light-gray'
                      }`}
                    >
                      <span className="mr-2">{market.icon}</span>
                      {market.label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-light-gray mt-2">
                  Select at least one market type
                </p>
              </div>

              {/* Summary */}
              <div className="bg-navy/50 rounded-lg p-4">
                <div className="text-sm text-light-gray">
                  <strong className="text-white">Personalized Dashboard Ready</strong><br/>
                  The AI will prioritize {formData.preferred_sports.join(', ')} games with {formData.preferred_markets.join(', ')} opportunities that match your {formData.risk_profile} profile.
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-6 bg-bold-red/10 border border-bold-red rounded-lg p-4">
              <div className="flex items-center space-x-2">
                <span className="text-bold-red text-xl">❌</span>
                <span className="text-bold-red">{error}</span>
              </div>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-navy">
            <button
              onClick={prevStep}
              disabled={currentStep === 1}
              className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                currentStep === 1
                  ? 'bg-charcoal text-light-gray cursor-not-allowed'
                  : 'bg-navy text-white hover:bg-navy/80'
              }`}
            >
              ← Back
            </button>

            <button
              onClick={nextStep}
              disabled={!canProceed()}
              className={`px-8 py-3 rounded-lg font-semibold transition-all ${
                canProceed()
                  ? 'bg-gradient-to-r from-electric-blue to-purple-600 text-white hover:shadow-lg hover:shadow-electric-blue/50'
                  : 'bg-charcoal text-light-gray cursor-not-allowed'
              }`}
            >
              {currentStep === 3 ? '🚀 Launch Dashboard' : 'Next →'}
            </button>
          </div>
        </div>

        {/* Skip Link */}
        <div className="text-center mt-6">
          <button
            onClick={onSkip}
            className="text-light-gray text-sm hover:text-white transition-colors"
          >
            Skip for now (not recommended)
          </button>
        </div>
      </div>
    </div>
  );
};

export default OnboardingWizard;
