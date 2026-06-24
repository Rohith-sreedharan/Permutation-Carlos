import React from 'react';
import type { EventWithPrediction } from '../types';
import { formatAwayAtHome } from '../utils/matchupLabel';
import { getSportDisplayName } from '../utils/sportLabels';

interface EventCardProps {
  event: EventWithPrediction;
  isRecalculated?: boolean;
  onClick?: () => void;
}

const EventCard: React.FC<EventCardProps> = ({ event, isRecalculated = false, onClick }) => {
  const {
    home_team,
    away_team,
    commence_time,
    sport_key,
  } = event;
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

  const handleCardClick = () => {
    if (!canOpenAnalysis) return;
    onClick?.();
  };
  
  return (
    <div 
      onClick={handleCardClick}
      className={`bg-charcoal rounded-xl shadow-lg p-5 flex flex-col space-y-4 relative transition-all duration-300 border ${
        isRecalculated ? 'border-neon-green shadow-neon-green/50 animate-pulse' : 'border-navy/50 hover:border-electric-blue'
      } ${(onClick && canOpenAnalysis) ? 'cursor-pointer hover:scale-[1.01] hover:shadow-xl' : ''}`}
    >
      {/* AI Recalculated Badge */}
      {isRecalculated && (
        <div className="absolute top-2 left-2 bg-neon-green text-charcoal text-xs font-bold px-3 py-1 rounded-full flex items-center space-x-1 animate-bounce">
          <span>🤖</span>
          <span>AI RECALCULATED</span>
        </div>
      )}
      
      <div className="absolute top-4 right-4 bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded-full">{getSportDisplayName(sport_key)}</div>
      <div>
        <h3 className="text-2xl font-bold text-white font-teko" style={{paddingRight: '56px'}}>{matchupLabel}</h3>
        <p className="text-sm text-light-gray">{gameTime}</p>
        {gameStateLabel && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
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

      {hasStarted ? (
        <div className="rounded-lg border border-slate-500/30 bg-slate-900/30 px-3 py-2">
          <p className="text-xs font-semibold text-slate-200">Pre-game analysis archived</p>
          <p className="text-[11px] text-light-gray/80 mt-1">
            Signal cards are locked after kickoff to prevent mixing pre-game analysis with live market movement.
          </p>
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
      
      {!hasStarted && !canOpenAnalysis && (
        <div className="text-xs text-light-gray italic">No card open required for this status.</div>
      )}
    </div>
  );
};

export default EventCard;