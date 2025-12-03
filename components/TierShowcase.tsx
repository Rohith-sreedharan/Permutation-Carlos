/**
 * TIER SHOWCASE - Visual demonstration of all tier badges
 * Remove this file after reviewing - it's just for demo purposes
 */
import React from 'react';
import SimulationBadge from './SimulationBadge';
import ConfidenceGauge from './ConfidenceGauge';

export default function TierShowcase() {
  return (
    <div className="bg-[#0a0e1a] p-8 space-y-8">
      <h1 className="text-3xl font-bold text-white mb-6">Tier System Visual Preview</h1>
      
      {/* Simulation Badges */}
      <div className="space-y-4">
        <h2 className="text-xl text-gold font-semibold">Simulation Power Badges</h2>
        <div className="flex flex-wrap gap-4">
          <SimulationBadge tier="free" showUpgradeHint={true} />
          <SimulationBadge tier="starter" />
          <SimulationBadge tier="pro" />
          <SimulationBadge tier="elite" />
          <SimulationBadge tier="admin" />
        </div>
      </div>

      {/* Confidence Gauges */}
      <div className="space-y-4">
        <h2 className="text-xl text-gold font-semibold">Confidence Gauges</h2>
        <div className="flex gap-8 items-end">
          <ConfidenceGauge confidence={95} size="sm" />
          <ConfidenceGauge confidence={78} size="md" />
          <ConfidenceGauge confidence={52} size="lg" showLabel={true} />
          <ConfidenceGauge confidence={38} size="md" animated={false} />
        </div>
      </div>

      {/* Combined View (Game Detail Style) */}
      <div className="space-y-4">
        <h2 className="text-xl text-gold font-semibold">Combined View (Game Detail)</h2>
        <div className="bg-charcoal rounded-xl p-6 border border-navy animate-fade-in">
          <div className="flex items-center justify-between mb-6">
            <SimulationBadge tier="pro" />
            <ConfidenceGauge confidence={82} size="md" animated={true} />
          </div>
          <div className="bg-navy rounded-lg p-6 animate-pulse-glow">
            <div className="text-center">
              <div className="text-4xl font-bold text-neon-green mb-2">
                OVER 118.5
              </div>
              <div className="text-gold text-lg">
                82% Win Probability
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tier Comparison */}
      <div className="space-y-4">
        <h2 className="text-xl text-gold font-semibold">Tier Upgrade Path</h2>
        <div className="grid grid-cols-4 gap-4">
          {[
            { tier: 'free', sims: '10K', price: 'Free', color: 'bg-gray-700' },
            { tier: 'starter', sims: '25K', price: '$19.99/mo', color: 'bg-blue-700' },
            { tier: 'pro', sims: '50K', price: '$39.99/mo', color: 'bg-purple-700' },
            { tier: 'elite', sims: '75K', price: '$89/mo', color: 'bg-amber-700' },
          ].map(({ tier, sims, price, color }) => (
            <div key={tier} className={`${color} rounded-lg p-4 text-center border border-white/20`}>
              <div className="text-3xl font-bold text-white mb-1">{sims}</div>
              <div className="text-xs text-white/80 uppercase mb-2">{tier}</div>
              <div className="text-sm text-white font-semibold">{price}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Animation Demo */}
      <div className="space-y-4">
        <h2 className="text-xl text-gold font-semibold">Animation Effects</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-navy p-6 rounded-lg animate-fade-in">
            <p className="text-white text-center">Fade In (0.3s)</p>
          </div>
          <div className="bg-navy p-6 rounded-lg animate-slide-up">
            <p className="text-white text-center">Slide Up (0.3s)</p>
          </div>
          <div className="bg-navy p-6 rounded-lg animate-pulse-glow">
            <p className="text-white text-center">Pulse Glow (2s loop)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
