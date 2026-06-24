import React from 'react';
import type { EventWithPrediction } from '../types';
import { formatAwayAtHome } from '../utils/matchupLabel';
import { getSportDisplayName } from '../utils/sportLabels';

interface EventListItemProps {
  event: EventWithPrediction;
  isRecalculated?: boolean;
  onClick?: () => void;
}

const EventListItem: React.FC<EventListItemProps> = ({ event, isRecalculated = false, onClick }) => {
  const { home_team, away_team, commence_time, sport_key } = event;
  const gameTime = new Date(commence_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).replace(' ', ' ') + ' EST';
  const gameStartUtcMs = Date.parse(commence_time);
  const hasStarted = Number.isFinite(gameStartUtcMs) && gameStartUtcMs < Date.now();
  const rawGameStatus = String((event as any)?.status || '').toUpperCase();
  const isFinal = rawGameStatus === 'FINAL' || rawGameStatus === 'COMPLETED' || rawGameStatus === 'CLOSED' || Boolean((event as any)?.completed);
  const isInProgress = hasStarted && !isFinal;
  const gameStateLabel = isFinal ? 'FINAL' : (isInProgress ? 'IN PROGRESS' : null);
  const homeScore = (event as any)?.home_score;
  const awayScore = (event as any)?.away_score;
  const hasScore = Number.isFinite(homeScore) && Number.isFinite(awayScore);
  const matchupLabel = formatAwayAtHome({ away_team, home_team });
  const canonicalClassification = String((event as any)?.classification || '').toUpperCase();
  const classification = canonicalClassification || 'BLOCKED';
  const classificationLabel = classification === 'MARKET_ALIGNED' ? 'Market Aligned' : classification;
  const canOpenAnalysis = classification === 'EDGE' || classification === 'LEAN';

  const handleRowClick = () => {
    if (!canOpenAnalysis) return;
    onClick?.();
  };
  
  return (
    <div 
      onClick={handleRowClick}
      className={`bg-charcoal rounded-lg shadow-lg p-4 flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0 md:space-x-4 transition-all duration-300 border relative ${
        isRecalculated ? 'border-neon-green shadow-neon-green/50 animate-pulse' : 'border-transparent hover:border-electric-blue'
      } ${(onClick && canOpenAnalysis) ? 'cursor-pointer hover:scale-[1.01]' : ''}`}
    >
      {/* AI Recalculated Badge */}
      {isRecalculated && (
        <div className="absolute top-2 left-2 bg-neon-green text-charcoal text-xs font-bold px-3 py-1 rounded-full flex items-center space-x-1 animate-bounce z-10">
          <span>🤖</span>
          <span>AI RECALCULATED</span>
        </div>
      )}
      
      <div className="flex items-center gap-4 w-full md:w-1/3">
        <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{getSportDisplayName(sport_key)}</span>
        <div>
          <h3 className="font-bold text-white" style={{paddingRight: '56px'}}>{matchupLabel}</h3>
          <p className="text-sm text-light-gray">{gameTime}</p>
          {gameStateLabel && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className={`text-[10px] font-bold px-2 py-1 rounded-full ${isFinal ? 'bg-slate-600/40 text-slate-200' : 'bg-amber-500/20 text-amber-300'}`}>
                {gameStateLabel}
              </span>
              {hasScore && (
                <span className="text-xs text-light-gray">
                  {away_team} {awayScore} - {homeScore} {home_team}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      
      <div className="w-full md:w-1/3">
        <div className="mb-2">
          {hasStarted ? (
            <div className="rounded-lg border border-slate-500/30 bg-slate-900/30 px-3 py-2">
              <p className="text-xs font-semibold text-slate-200">Pre-game analysis archived</p>
              <p className="text-[11px] text-light-gray/80 mt-1">Live market movement is not merged into pre-game signal cards.</p>
            </div>
          ) : (
            <div className="rounded-lg border border-gold/20 bg-navy/20 px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <span className={`text-xs font-bold px-2 py-1 rounded-full ${classification === 'EDGE' ? 'bg-neon-green/20 text-neon-green' : classification === 'LEAN' ? 'bg-gold/20 text-gold' : 'bg-slate-600/30 text-slate-200'}`}>
                  {classificationLabel}
                </span>
              </div>
              <p className="text-sm text-light-gray mt-2">
                {classification === 'MARKET_ALIGNED'
                  ? 'Market Aligned — No signal detected'
                  : classification === 'BLOCKED'
                  ? 'Blocked / unavailable'
                  : 'Open analysis — 1,000 cycles'}
              </p>
            </div>
          )}
        </div>
        <p className="text-xs text-light-gray">
          {hasStarted ? 'Pregame insights archived at kickoff.' : (canOpenAnalysis ? 'Tap to open full analysis card.' : 'No open action required.')}
        </p>
      </div>

      <div className="w-full md:w-1/3">
        <p className="text-xs text-light-gray font-semibold uppercase mb-2">Access</p>
        <div className="bg-navy/20 rounded p-3 text-sm text-light-gray">
          {canOpenAnalysis ? 'Open analysis available for this game.' : 'Model and market are aligned for this card.'}
        </div>
      </div>
    </div>
  );
};

export default EventListItem;