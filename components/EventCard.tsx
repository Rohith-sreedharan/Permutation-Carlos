import React from 'react';
import type { EventWithPrediction } from '../types';

interface EventCardProps {
  event: EventWithPrediction;
  isRecalculated?: boolean;
  onClick?: () => void;
}

const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.75) return 'bg-neon-green';
    if (confidence >= 0.5) return 'bg-vibrant-yellow';
    return 'bg-bold-red';
}

const EventCard: React.FC<EventCardProps> = ({ event, isRecalculated = false, onClick }) => {
  const {
    home_team,
    away_team,
    commence_time,
    sport_key,
    bets = [],
    top_prop_bet = null,
  } = event;
  const prediction = event.prediction;
  const gameTime = new Date(commence_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).replace(' ', ' ') + ' EST';

  const confidencePercentage = prediction ? Math.round(prediction.confidence * 100) : 0;
  
  return (
    <div 
      onClick={onClick}
      className={`bg-charcoal rounded-lg shadow-lg p-5 flex flex-col space-y-4 relative transition-all duration-300 border ${
        isRecalculated ? 'border-neon-green shadow-neon-green/50 animate-pulse' : 'border-transparent hover:border-electric-blue'
      } ${onClick ? 'cursor-pointer hover:scale-[1.02]' : ''}`}
    >
      {/* AI Recalculated Badge */}
      {isRecalculated && (
        <div className="absolute top-2 left-2 bg-neon-green text-charcoal text-xs font-bold px-3 py-1 rounded-full flex items-center space-x-1 animate-bounce">
          <span>🤖</span>
          <span>AI RECALCULATED</span>
        </div>
      )}
      
      <div className="absolute top-4 right-4 bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{sport_key}</div>
      <div>
        <h3 className="text-2xl font-bold text-white font-teko">{home_team} vs.</h3>
        <h3 className="text-2xl font-bold text-white font-teko">{away_team}</h3>
        <p className="text-sm text-light-gray">{gameTime}</p>
      </div>
      
      <div className="space-y-2">
        {bets.length > 0 ? (
          bets.map((bet, index) => (
            <div key={`${bet.type}-${bet.pick}-${index}`} className="flex justify-between items-center text-sm">
                <span className="text-light-gray">{bet.type}</span>
                <span className="font-semibold text-white">{bet.pick} {bet.value}</span>
            </div>
          ))
        ) : (
          <div className="text-sm text-light-gray italic">No betting lines available yet</div>
        )}
      </div>

      <div className="border-t border-navy pt-3">
        <p className="text-xs text-light-gray font-semibold mb-2">TOP PROP MISPRICING</p>
        {event.top_prop_mispricings && event.top_prop_mispricings.length > 0 ? (
          <div className="space-y-1">
            <p className="text-sm font-bold text-white">
              {event.top_prop_mispricings[0].player_name} – {event.top_prop_mispricings[0].market}
            </p>
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-light-gray">{event.top_prop_mispricings[0].team}</span>
              <span className="text-light-gray">·</span>
              <span className="text-electric-blue font-semibold">{event.top_prop_mispricings[0].position}</span>
            </div>
            <div className="flex items-center justify-between mt-2">
              <div>
                <span className="text-xs text-light-gray">Line: </span>
                <span className="text-sm font-bold text-white">{event.top_prop_mispricings[0].line}</span>
              </div>
              <div>
                <span className="text-xs text-light-gray">Win Prob: </span>
                <span className="text-sm font-bold text-neon-green">
                  {Math.round(event.top_prop_mispricings[0].win_probability * 100)}%
                </span>
              </div>
              <div>
                <span className="text-xs text-light-gray">EV: </span>
                <span className="text-sm font-bold text-vibrant-yellow">
                  {event.top_prop_mispricings[0].expected_value >= 0 ? '+' : ''}
                  {event.top_prop_mispricings[0].expected_value.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm font-bold text-light-gray italic">
            {top_prop_bet || 'No prop analysis available'}
          </p>
        )}
      </div>
      
      {prediction && (
        <div className="pt-2">
          <p className="text-xs text-light-gray font-semibold mb-1">AI CONFIDENCE</p>
          <div className="w-full bg-navy rounded-full h-3 relative">
            <div
              className={`h-3 rounded-full ${getConfidenceColor(prediction.confidence)}`}
              style={{ width: `${confidencePercentage}%` }}
            ></div>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-navy">{confidencePercentage}%</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default EventCard;