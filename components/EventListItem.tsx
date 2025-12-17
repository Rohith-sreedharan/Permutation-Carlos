import React from 'react';
import type { EventWithPrediction } from '../types';

interface EventListItemProps {
  event: EventWithPrediction;
  isRecalculated?: boolean;
  onClick?: () => void;
}

const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.75) return 'bg-neon-green';
    if (confidence >= 0.5) return 'bg-vibrant-yellow';
    return 'bg-bold-red';
}

// UI TRUST LAYER: Suppress extreme certainty for non-PICK states
const shouldSuppressDisplay = (event: EventWithPrediction): boolean => {
  const pickState = (event as any).pick_state;
  const confidence = event.prediction?.confidence || 0;
  
  return pickState !== 'PICK' || confidence < 0.20;
};

const EventListItem: React.FC<EventListItemProps> = ({ event, isRecalculated = false, onClick }) => {
  const { home_team, away_team, commence_time, top_prop_bet, prediction, sport_key } = event;
  const gameTime = new Date(commence_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).replace(' ', ' ') + ' EST';

  const confidencePercentage = prediction ? Math.round(prediction.confidence * 100) : 0;
  const suppressCertainty = shouldSuppressDisplay(event);
  
  return (
    <div 
      onClick={onClick}
      className={`bg-charcoal rounded-lg shadow-lg p-4 flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0 md:space-x-4 transition-all duration-300 border relative ${
        isRecalculated ? 'border-neon-green shadow-neon-green/50 animate-pulse' : 'border-transparent hover:border-electric-blue'
      } ${onClick ? 'cursor-pointer hover:scale-[1.01]' : ''}`}
    >
      {/* AI Recalculated Badge */}
      {isRecalculated && (
        <div className="absolute top-2 left-2 bg-neon-green text-charcoal text-xs font-bold px-3 py-1 rounded-full flex items-center space-x-1 animate-bounce z-10">
          <span>🤖</span>
          <span>AI RECALCULATED</span>
        </div>
      )}
      
      <div className="flex items-center gap-4 w-full md:w-1/3">
        <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{sport_key}</span>
        <div>
          <h3 className="font-bold text-white">{home_team} vs. {away_team}</h3>
          <p className="text-sm text-light-gray">{gameTime}</p>
        </div>
      </div>
      
      <div className="w-full md:w-1/3">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-xs text-light-gray font-semibold">MODEL MISPRICING (NOT A BETTING PICK)</p>
          <span className="cursor-help text-light-gray/60 hover:text-white text-xs" title="BeatVegas identifies statistical deviations between our simulation output and sportsbook odds. This is NOT a list of recommended bets.">ⓘ</span>
        </div>
        <p className="text-sm font-bold text-white">{top_prop_bet}</p>
        <p className="text-[10px] text-gray-500 italic mt-1">MODEL MISPRICING — NOT a betting recommendation.</p>
      </div>
      
      {prediction && (
        <div className="w-full md:w-1/3">
          <div className="flex justify-between items-center mb-1">
            <p className="text-xs text-light-gray font-semibold">AI CONFIDENCE</p>
            {suppressCertainty && (confidencePercentage > 75 || confidencePercentage < 25) ? (
              <span className="text-xs text-amber-400 italic">Unstable</span>
            ) : (
              <span className="text-sm font-bold text-white">{confidencePercentage}%</span>
            )}
          </div>
          {suppressCertainty && (confidencePercentage > 75 || confidencePercentage < 25) ? (
            <div className="text-[10px] text-amber-400/90 italic">⚠️ Directional lean — unstable distribution</div>
          ) : (
            <div className="w-full bg-navy rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full ${getConfidenceColor(prediction.confidence)}`}
                style={{ width: `${confidencePercentage}%` }}
              ></div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EventListItem;