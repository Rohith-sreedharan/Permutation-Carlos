import React from 'react';
import type { EventWithPrediction } from '../types';

interface EventCardProps {
  event: EventWithPrediction;
}

const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.75) return 'bg-neon-green';
    if (confidence >= 0.5) return 'bg-vibrant-yellow';
    return 'bg-bold-red';
}

const EventCard: React.FC<EventCardProps> = ({ event, prediction }) => {
  const {
    home_team,
    away_team,
    commence_time,
    sport_key,
    bets = [],
    top_prop_bet = null,
  } = event;
  const gameTime = new Date(commence_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).replace(' ', ' ') + ' EST';

  const confidencePercentage = prediction ? Math.round(prediction.confidence * 100) : 0;
  
  return (
    <div className="bg-charcoal rounded-lg shadow-lg p-5 flex flex-col space-y-4 relative transition-all duration-300 border border-transparent hover:border-electric-blue">
      <div className="absolute top-4 right-4 bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{sport_key}</div>
      <div>
        <h3 className="text-2xl font-bold text-white font-teko">{home_team} vs.</h3>
        <h3 className="text-2xl font-bold text-white font-teko">{away_team}</h3>
        <p className="text-sm text-light-gray">{gameTime}</p>
      </div>
      
      <div className="space-y-2">
        {bets.length > 0 ? (
          bets.map(bet => (
            <div key={bet.type} className="flex justify-between items-center text-sm">
                <span className="text-light-gray">{bet.type}</span>
                <span className="font-semibold text-white">{bet.pick} {bet.value}</span>
            </div>
          ))
        ) : (
          <div className="text-sm text-light-gray italic">No betting lines available yet</div>
        )}
      </div>

      <div className="border-t border-navy pt-3">
        <p className="text-xs text-light-gray font-semibold">TOP PROP BET</p>
        <p className="text-sm font-bold text-white">{top_prop_bet || 'No prop bet available'}</p>
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