import React from 'react';
import type { EventWithPrediction } from '../types';

interface EventListItemProps {
  event: EventWithPrediction;
}

const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.75) return 'bg-neon-green';
    if (confidence >= 0.5) return 'bg-vibrant-yellow';
    return 'bg-bold-red';
}

const EventListItem: React.FC<EventListItemProps> = ({ event }) => {
  const { home_team, away_team, commence_time, top_prop_bet, prediction, sport_key } = event;
  const gameTime = new Date(commence_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).replace(' ', ' ') + ' EST';

  const confidencePercentage = prediction ? Math.round(prediction.confidence * 100) : 0;
  
  return (
    <div className="bg-charcoal rounded-lg shadow-lg p-4 flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0 md:space-x-4 transition-all duration-300 border border-transparent hover:border-electric-blue">
      <div className="flex items-center gap-4 w-full md:w-1/3">
        <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{sport_key}</span>
        <div>
          <h3 className="font-bold text-white">{home_team} vs. {away_team}</h3>
          <p className="text-sm text-light-gray">{gameTime}</p>
        </div>
      </div>
      
      <div className="w-full md:w-1/3">
        <p className="text-xs text-light-gray font-semibold">TOP PROP BET</p>
        <p className="text-sm font-bold text-white">{top_prop_bet}</p>
      </div>
      
      {prediction && (
        <div className="w-full md:w-1/3">
          <div className="flex justify-between items-center mb-1">
            <p className="text-xs text-light-gray font-semibold">AI CONFIDENCE</p>
            <span className="text-sm font-bold text-white">{confidencePercentage}%</span>
          </div>
          <div className="w-full bg-navy rounded-full h-2.5">
            <div
              className={`h-2.5 rounded-full ${getConfidenceColor(prediction.confidence)}`}
              style={{ width: `${confidencePercentage}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EventListItem;