import React, { useEffect, useMemo, useState } from 'react';
import type { EventWithPrediction } from '../types';
import { formatAwayAtHome } from '../utils/matchupLabel';
import { getDisplayTeamName } from '../utils/matchupLabel';
import { CANONICAL_PROP_LABEL, getCanonicalPropHeadline } from '../utils/propDisplay';
import { getSportDisplayName } from '../utils/sportLabels';
import MarketDecisionCard from './MarketDecisionCard';
import { fetchGameDecisions, fetchSimulation } from '../services/api';
import type { MarketDecision } from '../types/MarketDecision';
import { compareCardsByClassification, renderMarketSignalCard } from '../utils/cardMarketSignal';

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

// UI TRUST LAYER: Suppress extreme certainty for non-PICK states
const shouldSuppressDisplay = (event: EventWithPrediction): boolean => {
  const pickState = (event as any).pick_state;
  const confidence = event.prediction?.confidence || 0;
  
  return pickState !== 'PICK' || confidence < 0.20;
};

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
  const matchupLabel = formatAwayAtHome({ away_team, home_team });
  const canonicalPropHeadline = getCanonicalPropHeadline(event);
  const [decision, setDecision] = useState<MarketDecision | null>(null);
  const [decisionLoading, setDecisionLoading] = useState<boolean>(true);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const retryRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const mapSportKeyToLeague = (sportKey: string): string => {
    const key = (sportKey || '').toLowerCase();
    if (key.includes('basketball_nba')) return 'NBA';
    if (key.includes('basketball_ncaab')) return 'NCAAB';
    if (key.includes('americanfootball_nfl')) return 'NFL';
    if (key.includes('americanfootball_ncaaf')) return 'NCAAF';
    if (key.includes('icehockey_nhl')) return 'NHL';
    if (key.includes('baseball_mlb')) return 'MLB';
    return sportKey?.split('_').pop()?.toUpperCase() || 'NBA';
  };

  const league = useMemo(() => mapSportKeyToLeague(sport_key), [sport_key]);

  const selectTopDecision = (decisions: {
    spread: MarketDecision | null;
    moneyline: MarketDecision | null;
    total: MarketDecision | null;
  }): MarketDecision | null => {
    const candidates = [decisions.spread, decisions.moneyline, decisions.total].filter(Boolean) as MarketDecision[];
    if (candidates.length === 0) return null;
    return candidates.sort((a, b) => {
      const ra = renderMarketSignalCard(a);
      const rb = renderMarketSignalCard(b);
      return compareCardsByClassification(ra, rb);
    })[0];
  };

  const loadDecision = async () => {
    if (!event.id) {
      setDecisionLoading(false);
      return;
    }
    setDecisionLoading(true);
    setDecisionError(null);
    try {
      const data = await fetchGameDecisions(league, event.id);
      const top = selectTopDecision(data);
      setDecision(top);

      // Auto-retry once if all markets are BLOCKED — simulation may not be
      // generated yet. Fire fetchSimulation (which auto-generates it), then
      // re-fetch the decision after a short delay.
      const allBlocked =
        top === null ||
        (top as any).classification === 'BLOCKED' ||
        (top as any).classification === undefined;
      if (allBlocked) {
        // Warm the simulation cache in background, then retry decision fetch
        fetchSimulation(event.id).catch(() => null);
        if (retryRef.current) clearTimeout(retryRef.current);
        retryRef.current = setTimeout(async () => {
          try {
            const retryData = await fetchGameDecisions(league, event.id);
            setDecision(selectTopDecision(retryData));
          } catch {
            // Keep the original BLOCKED result — silent retry failure
          }
        }, 4000);
      }
    } catch (err: any) {
      setDecisionError(err?.message || 'Failed to load decision');
      setDecision(null);
    } finally {
      setDecisionLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
    };
  }, []);

  useEffect(() => {
    loadDecision();
  }, [event.id, league]);

  const confidencePercentage = prediction ? Math.round(prediction.confidence * 100) : 0;
  const suppressCertainty = shouldSuppressDisplay(event);
  
  return (
    <div 
      onClick={onClick}
      className={`bg-charcoal rounded-xl shadow-lg p-5 flex flex-col space-y-4 relative transition-all duration-300 border ${
        isRecalculated ? 'border-neon-green shadow-neon-green/50 animate-pulse' : 'border-navy/50 hover:border-electric-blue'
      } ${onClick ? 'cursor-pointer hover:scale-[1.01] hover:shadow-xl' : ''}`}
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
        <h3 className="text-2xl font-bold text-white font-teko">{matchupLabel}</h3>
        <p className="text-sm text-light-gray">{gameTime}</p>
      </div>

      <MarketDecisionCard
        decision={decision}
        league={league}
        gameId={event.id}
        isLoading={decisionLoading}
        isError={!!decisionError}
        errorMessage={decisionError || undefined}
        onRetry={loadDecision}
      />
      
      <div className="space-y-2">
        {bets.length > 0 ? (
          bets.map((bet, index) => (
            <div key={`${bet.type}-${bet.pick}-${index}`} className="flex justify-between items-center text-sm">
                <span className="text-light-gray">{bet.type}</span>
                <span className="font-semibold text-white">{bet.pick} {bet.value}</span>
            </div>
          ))
        ) : (
          <div className="text-sm text-light-gray italic">No market lines available yet</div>
        )}
      </div>

      <div className="border-t border-navy pt-3">
        <p className="text-xs text-light-gray font-semibold mb-2">{CANONICAL_PROP_LABEL}</p>
        {event.top_prop_mispricings && event.top_prop_mispricings.length > 0 ? (
          <div className="space-y-1">
            <p className="text-sm font-bold text-white">{canonicalPropHeadline}</p>
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-light-gray">{getDisplayTeamName(event.top_prop_mispricings[0].team)}</span>
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
            {canonicalPropHeadline}
          </p>
        )}
      </div>
      
      {prediction && (
        <div className="pt-2">
          <p className="text-xs text-light-gray font-semibold mb-1">AI CONFIDENCE</p>
          {suppressCertainty && (confidencePercentage > 75 || confidencePercentage < 25) ? (
            <div className="text-xs text-amber-400 italic">⚠️ Directional lean only — unstable distribution</div>
          ) : (
            <div className="w-full bg-navy rounded-full h-3 relative">
              <div
                className={`h-3 rounded-full ${getConfidenceColor(prediction.confidence)}`}
                style={{ width: `${confidencePercentage}%` }}
              ></div>
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-navy">{confidencePercentage}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EventCard;