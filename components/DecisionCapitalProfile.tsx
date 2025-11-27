import React, { useState, useEffect } from 'react';
import type { RiskProfile } from '../types';
import LoadingSpinner from './LoadingSpinner';

interface DecisionCapitalProfileProps {
  onAuthError: () => void;
}

const DecisionCapitalProfile: React.FC<DecisionCapitalProfileProps> = ({ onAuthError }) => {
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);

  // Form state
  const [startingCapital, setStartingCapital] = useState<number>(1000);
  const [unitStrategy, setUnitStrategy] = useState<'fixed' | 'percentage'>('percentage');
  const [unitSize, setUnitSize] = useState<number>(2);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      
      // Initialize with default profile for new users
      const defaultProfile: RiskProfile = {
        user_id: 'current_user',
        starting_capital: 1000,
        unit_strategy: 'percentage',
        unit_size: 2,
        risk_classification: 'balanced',
        suggested_exposure_per_decision: 20,
        volatility_tolerance: 0.15,
        max_daily_exposure: 100,
        total_decisions: 0,
        winning_decisions: 0,
        roi: 0,
        sharpe_ratio: 0,
      };
      
      setProfile(defaultProfile);
      setStartingCapital(defaultProfile.starting_capital);
      setUnitStrategy(defaultProfile.unit_strategy);
      setUnitSize(defaultProfile.unit_size);
    } catch (err: any) {
      if (err.message?.includes('401') || err.message?.includes('Session expired')) {
        onAuthError();
      }
      console.error('Failed to load risk profile:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      // Calculate risk classification based on unit size
      let riskClassification: 'conservative' | 'balanced' | 'aggressive' = 'balanced';
      if (unitStrategy === 'percentage') {
        if (unitSize <= 1) riskClassification = 'conservative';
        else if (unitSize >= 3) riskClassification = 'aggressive';
      } else {
        const percentOfCapital = (unitSize / startingCapital) * 100;
        if (percentOfCapital <= 1) riskClassification = 'conservative';
        else if (percentOfCapital >= 3) riskClassification = 'aggressive';
      }

      const updatedProfile: RiskProfile = {
        ...profile!,
        starting_capital: startingCapital,
        unit_strategy: unitStrategy,
        unit_size: unitSize,
        risk_classification: riskClassification,
        suggested_exposure_per_decision: unitStrategy === 'percentage' 
          ? (startingCapital * unitSize) / 100 
          : unitSize,
        max_daily_exposure: unitStrategy === 'percentage'
          ? (startingCapital * unitSize * 5) / 100
          : unitSize * 5,
      };

      // TODO: Replace with actual API call
      // await updateRiskProfile(updatedProfile);
      setProfile(updatedProfile);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save risk profile:', err);
    }
  };

  const getRiskColor = (classification: string) => {
    switch (classification) {
      case 'conservative': return 'text-electric-blue';
      case 'balanced': return 'text-vibrant-yellow';
      case 'aggressive': return 'text-bold-red';
      default: return 'text-white';
    }
  };

  const getRiskBadgeColor = (classification: string) => {
    switch (classification) {
      case 'conservative': return 'bg-electric-blue/20 text-electric-blue';
      case 'balanced': return 'bg-vibrant-yellow/20 text-vibrant-yellow';
      case 'aggressive': return 'bg-bold-red/20 text-bold-red';
      default: return 'bg-navy text-white';
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!profile) {
    return (
      <div className="text-center text-light-gray p-8">
        Failed to load risk profile. Please try again.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-electric-blue/20 to-navy/30 rounded-lg p-6 border border-electric-blue/30">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-3xl font-bold text-white font-teko">Decision Capital Profile</h2>
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="px-4 py-2 bg-electric-blue text-white rounded-lg font-semibold hover:bg-electric-blue/80 transition-colors text-sm"
          >
            {isEditing ? 'Cancel' : 'Edit Profile'}
          </button>
        </div>
        <p className="text-sm text-light-gray">
          Define your personal risk framework and exposure preferences to guide disciplined decision-making.
        </p>
      </div>

      {/* Risk Classification Badge */}
      <div className="text-center">
        <div className={`inline-flex items-center space-x-2 px-6 py-3 rounded-full text-lg font-bold ${getRiskBadgeColor(profile.risk_classification)}`}>
          <span>RISK PROFILE:</span>
          <span className="uppercase">{profile.risk_classification}</span>
        </div>
      </div>

      {/* Configuration Form (if editing) */}
      {isEditing && (
        <div className="bg-charcoal rounded-lg border border-navy p-6 space-y-6">
          <h3 className="text-xl font-bold text-white font-teko mb-4">Configure Your Risk Framework</h3>

          {/* Starting Capital */}
          <div>
            <label className="block text-sm font-semibold text-light-gray mb-2">
              Starting Capital
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-light-gray">$</span>
              <input
                type="number"
                value={startingCapital}
                onChange={(e) => setStartingCapital(Number(e.target.value))}
                className="w-full bg-navy border border-electric-blue/30 rounded-lg px-10 py-3 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
                placeholder="1000"
              />
            </div>
            <p className="text-xs text-light-gray mt-1 italic">
              This represents your total decision capital for analytical tracking purposes.
            </p>
          </div>

          {/* Unit Strategy */}
          <div>
            <label className="block text-sm font-semibold text-light-gray mb-2">
              Unit Strategy
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setUnitStrategy('percentage')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  unitStrategy === 'percentage'
                    ? 'border-electric-blue bg-electric-blue/10 text-white'
                    : 'border-navy bg-charcoal text-light-gray hover:border-electric-blue/50'
                }`}
              >
                <div className="text-sm font-semibold mb-1">Percentage-Based</div>
                <div className="text-xs">% of capital per decision</div>
              </button>
              <button
                onClick={() => setUnitStrategy('fixed')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  unitStrategy === 'fixed'
                    ? 'border-electric-blue bg-electric-blue/10 text-white'
                    : 'border-navy bg-charcoal text-light-gray hover:border-electric-blue/50'
                }`}
              >
                <div className="text-sm font-semibold mb-1">Fixed Amount</div>
                <div className="text-xs">Same $ amount each time</div>
              </button>
            </div>
          </div>

          {/* Unit Size */}
          <div>
            <label className="block text-sm font-semibold text-light-gray mb-2">
              {unitStrategy === 'percentage' ? 'Unit Size (%)' : 'Unit Size ($)'}
            </label>
            <input
              type="number"
              value={unitSize}
              onChange={(e) => setUnitSize(Number(e.target.value))}
              step={unitStrategy === 'percentage' ? 0.5 : 10}
              className="w-full bg-navy border border-electric-blue/30 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
              placeholder={unitStrategy === 'percentage' ? '2' : '20'}
            />
            <p className="text-xs text-light-gray mt-1 italic">
              {unitStrategy === 'percentage' 
                ? 'Recommended: 1-2% (Conservative), 2-3% (Balanced), 3-5% (Aggressive)'
                : 'Fixed dollar amount per standard decision'}
            </p>
          </div>

          {/* Save Button */}
          <button
            onClick={handleSave}
            className="w-full bg-electric-blue text-white font-bold py-3 rounded-lg hover:bg-electric-blue/80 transition-colors"
          >
            Save Configuration
          </button>
        </div>
      )}

      {/* Current Settings Display */}
      {!isEditing && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Starting Capital */}
          <div className="bg-charcoal rounded-lg border border-navy p-5">
            <p className="text-xs text-light-gray font-semibold mb-2">STARTING CAPITAL</p>
            <p className="text-3xl font-bold text-white font-teko">
              ${profile.starting_capital.toLocaleString()}
            </p>
          </div>

          {/* Unit Strategy */}
          <div className="bg-charcoal rounded-lg border border-navy p-5">
            <p className="text-xs text-light-gray font-semibold mb-2">UNIT STRATEGY</p>
            <p className="text-xl font-bold text-white capitalize">
              {profile.unit_strategy === 'percentage' ? `${profile.unit_size}% Per Decision` : `$${profile.unit_size} Fixed`}
            </p>
          </div>

          {/* Suggested Exposure */}
          <div className="bg-charcoal rounded-lg border border-navy p-5">
            <p className="text-xs text-light-gray font-semibold mb-2">SUGGESTED EXPOSURE</p>
            <p className="text-3xl font-bold text-white font-teko">
              ${profile.suggested_exposure_per_decision?.toFixed(0)}
            </p>
            <p className="text-xs text-light-gray mt-1">per standard decision</p>
          </div>
        </div>
      )}

      {/* Risk Metrics */}
      <div className="bg-charcoal rounded-lg border border-navy p-6">
        <h3 className="text-xl font-bold text-white font-teko mb-4">Risk Framework Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-xs text-light-gray mb-1">VOLATILITY TOLERANCE</p>
            <p className="text-2xl font-bold text-white">
              {profile.volatility_tolerance ? `${(profile.volatility_tolerance * 100).toFixed(0)}%` : 'N/A'}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-light-gray mb-1">MAX DAILY EXPOSURE</p>
            <p className="text-2xl font-bold text-white">
              ${profile.max_daily_exposure?.toFixed(0) || 'N/A'}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-light-gray mb-1">TOTAL DECISIONS</p>
            <p className="text-2xl font-bold text-white">
              {profile.total_decisions || 0}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-light-gray mb-1">SHARPE RATIO</p>
            <p className="text-2xl font-bold text-white">
              {profile.sharpe_ratio?.toFixed(2) || 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Performance Tracking */}
      {profile.total_decisions && profile.total_decisions > 0 && (
        <div className="bg-charcoal rounded-lg border border-navy p-6">
          <h3 className="text-xl font-bold text-white font-teko mb-4">Performance vs Risk Style</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Win Rate */}
            <div>
              <p className="text-xs text-light-gray font-semibold mb-2">WIN RATE</p>
              <div className="flex items-center space-x-3">
                <div className="flex-1 bg-navy rounded-full h-4 overflow-hidden">
                  <div
                    className="bg-neon-green h-4 rounded-full transition-all duration-500"
                    style={{ width: `${((profile.winning_decisions || 0) / profile.total_decisions) * 100}%` }}
                  ></div>
                </div>
                <span className="text-lg font-bold text-white">
                  {(((profile.winning_decisions || 0) / profile.total_decisions) * 100).toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-light-gray mt-1">
                {profile.winning_decisions} / {profile.total_decisions} decisions
              </p>
            </div>

            {/* ROI */}
            <div>
              <p className="text-xs text-light-gray font-semibold mb-2">RETURN ON INTELLIGENCE</p>
              <p className={`text-4xl font-bold font-teko ${profile.roi && profile.roi >= 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                {profile.roi ? `${profile.roi >= 0 ? '+' : ''}${profile.roi.toFixed(1)}%` : 'N/A'}
              </p>
            </div>

            {/* Classification Alignment */}
            <div>
              <p className="text-xs text-light-gray font-semibold mb-2">RISK CLASSIFICATION</p>
              <p className={`text-2xl font-bold uppercase ${getRiskColor(profile.risk_classification)}`}>
                {profile.risk_classification}
              </p>
              <p className="text-xs text-light-gray mt-1">
                Based on unit sizing strategy
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Decision Discipline Notice */}
      <div className="bg-navy/30 rounded-lg border border-electric-blue/30 p-6">
        <h3 className="text-lg font-bold text-white mb-3 flex items-center space-x-2">
          <svg className="w-5 h-5 text-electric-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Decision Discipline Framework</span>
        </h3>
        <p className="text-sm text-light-gray leading-relaxed">
          All forecasts provided by BeatVegas are analytical insights designed to inform your decision-making process. 
          Your exposure settings help visualize risk tolerance and understand variance over time. 
          This framework encourages disciplined, sustainable decision strategies based on quantified confidence levels.
        </p>
        <div className="mt-4 pt-4 border-t border-navy/50">
          <p className="text-xs text-light-gray italic">
            <strong>Remember:</strong> Past performance does not guarantee future results. 
            Manage your exposure responsibly and align decisions with your personal risk tolerance.
          </p>
        </div>
      </div>

      {/* Confidence Weight Tiers (Educational) */}
      <div className="bg-charcoal rounded-lg border border-navy p-6">
        <h3 className="text-xl font-bold text-white font-teko mb-4">Suggested Confidence Weight Tiers</h3>
        <p className="text-sm text-light-gray mb-4">
          Use these guidelines to scale exposure based on forecast confidence levels:
        </p>
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-navy/30 rounded-lg">
            <div>
              <p className="font-semibold text-white">High Confidence (65%+)</p>
              <p className="text-xs text-light-gray">Strong model alignment</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-neon-green">2-3 Units</p>
            </div>
          </div>
          <div className="flex items-center justify-between p-3 bg-navy/30 rounded-lg">
            <div>
              <p className="font-semibold text-white">Medium Confidence (58-64%)</p>
              <p className="text-xs text-light-gray">Moderate edge detected</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-vibrant-yellow">1-2 Units</p>
            </div>
          </div>
          <div className="flex items-center justify-between p-3 bg-navy/30 rounded-lg">
            <div>
              <p className="font-semibold text-white">Standard Confidence (52-57%)</p>
              <p className="text-xs text-light-gray">Slight edge, exploratory</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-electric-blue">0.5-1 Unit</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DecisionCapitalProfile;
