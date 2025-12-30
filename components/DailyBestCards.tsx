import React, { useState, useEffect } from 'react';
import api from '../services/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface DailyCard {
  event_id?: string;
  matchup?: string;
  sport?: string;
  commence_time?: string;
  win_probability?: number;
  confidence?: number;
  volatility?: string;
  recommended_bet?: string;
  odds?: number;
  card_type: string;
  reasoning?: string;
  player_name?: string;
  prop_type?: string;
  line?: number;
  over_under?: string;
  expected_value?: number;
  probability?: number;
  mispricing_explanation?: string;
  parlay_odds?: number;
  leg_count?: number;
  legs_preview?: any[];
  status?: string;
  message?: string;
}

interface DailyCards {
  best_game_overall: DailyCard | null;
  top_nba_game: DailyCard | null;
  top_ncaab_game: DailyCard | null;
  top_ncaaf_game: DailyCard | null;
  top_prop_mispricing: DailyCard | null;
  parlay_preview: DailyCard | null;
  generated_at?: string;
}

const DailyBestCards: React.FC = () => {
  const [cards, setCards] = useState<DailyCards | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<string | null>(null);

  useEffect(() => {
    fetchDailyCards();
  }, []);

  const fetchDailyCards = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[DailyCards] Fetching from API...');
      const response = await api.get('/api/daily-cards');
      console.log('[DailyCards] Raw response:', response);
      console.log('[DailyCards] Response data:', response.data);
      console.log('[DailyCards] Cards:', response.data.cards);
      setCards(response.data.cards);
      console.log('[DailyCards] State updated successfully');
    } catch (err: any) {
      console.error('[DailyCards] Error caught:', err);
      console.error('[DailyCards] Error message:', err.message);
      console.error('[DailyCards] Error stack:', err.stack);
      setError(err.message || 'Failed to load daily cards');
    } finally {
      setLoading(false);
    }
  };

  const getSportIcon = (sport?: string) => {
    if (!sport) return '🎯';
    if (sport.includes('nba')) return '🏀';
    if (sport.includes('ncaab')) return '🏀';
    if (sport.includes('ncaaf')) return '🏈';
    if (sport.includes('nfl')) return '🏈';
    if (sport.includes('nhl')) return '🏒';
    if (sport.includes('mlb')) return '⚾';
    return '🎯';
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return 'TBD';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  };

  const renderGameCard = (card: DailyCard | null, cardKey: string) => {
    if (!card) {
      return (
        <div className="bg-charcoal rounded-xl p-6 border border-gold/20 opacity-50">
          <div className="text-center text-light-gray">
            <div className="text-4xl mb-2">📭</div>
            <div className="text-sm">No game available</div>
          </div>
        </div>
      );
    }

    const isFlagship = cardKey === 'best_game_overall';

    return (
      <div
        className={`bg-linear-to-br from-charcoal to-navy rounded-xl p-6 border-2 cursor-pointer transition-all hover:scale-105 ${
          isFlagship
            ? 'border-gold shadow-lg shadow-gold/30'
            : 'border-gold/30 hover:border-gold/60'
        }`}
        onClick={() => setSelectedCard(cardKey)}
      >
        {/* Card Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-3xl">{getSportIcon(card.sport)}</span>
            <div>
              <div className={`text-xs uppercase font-bold ${isFlagship ? 'text-gold' : 'text-lightGold'}`}>
                {card.card_type}
              </div>
              {isFlagship && (
                <div className="text-[10px] text-gold/70">⭐ FLAGSHIP POST</div>
              )}
            </div>
          </div>
          {card.volatility && (
            <div className={`text-xs px-2 py-1 rounded border ${
              card.volatility === 'LOW'
                ? 'bg-electric-blue/20 text-electric-blue border-electric-blue/30'
                : card.volatility === 'MODERATE'
                ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30'
                : 'bg-orange-500/20 text-orange-500 border-orange-500/30'
            }`}>
              {card.volatility}
            </div>
          )}
        </div>

        {/* Matchup */}
        <div className="mb-4">
          <div className="text-lg font-bold text-white mb-1">{card.matchup}</div>
          <div className="text-xs text-light-gray">{formatTime(card.commence_time)}</div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-navy/50 rounded-lg p-3 border border-gold/10">
            <div className="text-[10px] text-light-gray uppercase mb-1">Win Probability</div>
            <div className="text-xl font-bold text-gold">
              {card.win_probability ? `${(card.win_probability * 100).toFixed(1)}%` : 'N/A'}
            </div>
          </div>
          <div className="bg-navy/50 rounded-lg p-3 border border-gold/10">
            <div className="text-[10px] text-light-gray uppercase mb-1">Confidence</div>
            <div className="text-xl font-bold text-gold">
              {card.confidence ? `${(card.confidence * 100).toFixed(0)}%` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Reasoning */}
        {card.reasoning && (
          <div className="bg-electric-blue/10 rounded-lg p-3 border border-electric-blue/30">
            <div className="text-xs text-white">{card.reasoning}</div>
          </div>
        )}

        {/* Model Projection */}
        {card.recommended_bet && (
          <div className="mt-3 text-center">
            <div className="text-xs text-light-gray mb-1">Model Projection</div>
            <div className="text-lg font-bold text-white">{card.recommended_bet}</div>
            {card.odds && card.odds !== 0 && (
              <div className="text-sm text-gold">
                {card.odds > 0 ? '+' : ''}{card.odds}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderPropCard = (card: DailyCard | null) => {
    if (!card) {
      return (
        <div className="bg-charcoal rounded-xl p-6 border border-gold/20 opacity-50">
          <div className="text-center text-light-gray">
            <div className="text-4xl mb-2">📭</div>
            <div className="text-sm">No prop available</div>
          </div>
        </div>
      );
    }

    return (
      <div
        className="bg-linear-to-br from-purple-900/50 to-navy rounded-xl p-6 border-2 border-purple-500/30 cursor-pointer transition-all hover:scale-105 hover:border-purple-500/60"
        onClick={() => setSelectedCard('top_prop_mispricing')}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xs uppercase font-bold text-purple-400">
              {card.card_type}
            </div>
            <div className="text-[10px] text-purple-300">🔥 BEST ENGAGEMENT CONTENT</div>
          </div>
          {card.expected_value && (
            <div className="text-2xl font-bold text-neon-green">
              +{card.expected_value.toFixed(1)}%
            </div>
          )}
        </div>

        {/* Player Info */}
        <div className="mb-4">
          <div className="text-lg font-bold text-white mb-1">{card.player_name}</div>
          <div className="text-sm text-purple-300">
            {card.prop_type} • {card.line} {card.over_under || ''}
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-navy/50 rounded-lg p-3 border border-purple-500/20">
            <div className="text-[10px] text-light-gray uppercase mb-1">Probability</div>
            <div className="text-xl font-bold text-white">
              {card.probability ? `${(card.probability * 100).toFixed(1)}%` : 'N/A'}
            </div>
          </div>
          <div className="bg-navy/50 rounded-lg p-3 border border-purple-500/20">
            <div className="text-[10px] text-light-gray uppercase mb-1">Model Variance Gap</div>
            <div className="text-xl font-bold text-neon-green">
              +{card.expected_value?.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Explanation */}
        {card.mispricing_explanation && (
          <div className="bg-electric-blue/10 rounded-lg p-3 border border-electric-blue/30">
            <div className="text-xs text-white italic">"{card.mispricing_explanation}"</div>
          </div>
        )}
      </div>
    );
  };

  const renderParlayCard = (card: DailyCard | null) => {
    if (!card) {
      return (
        <div className="bg-charcoal rounded-xl p-6 border border-gold/20 opacity-50">
          <div className="text-center text-light-gray">
            <div className="text-4xl mb-2">📭</div>
            <div className="text-sm">No parlay available</div>
          </div>
        </div>
      );
    }

    return (
      <div
        className="bg-linear-to-br from-gold/20 to-navy rounded-xl p-6 border-2 border-gold/50 cursor-pointer transition-all hover:scale-105 hover:border-gold"
        onClick={() => setSelectedCard('parlay_preview')}
      >
        {/* Header */}
        <div className="text-center mb-4">
          <div className="text-xs uppercase font-bold text-gold mb-1">
            {card.card_type}
          </div>
          <div className="text-2xl font-bold text-white">
            {card.status === 'success' ? 'TODAY\'S AI PARLAY' : 'PARLAY GENERATING...'}
          </div>
        </div>

        {card.status === 'success' ? (
          <>
            {/* Parlay Metrics */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-navy/50 rounded-lg p-3 border border-gold/20 text-center">
                <div className="text-[10px] text-light-gray uppercase mb-1">Legs</div>
                <div className="text-xl font-bold text-gold">{card.leg_count}</div>
              </div>
              <div className="bg-navy/50 rounded-lg p-3 border border-gold/20 text-center">
                <div className="text-[10px] text-light-gray uppercase mb-1">Odds</div>
                <div className="text-xl font-bold text-gold">
                  {card.parlay_odds && card.parlay_odds > 0 ? '+' : ''}{card.parlay_odds}
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-3 border border-gold/20 text-center">
                <div className="text-[10px] text-light-gray uppercase mb-1">EV</div>
                <div className="text-xl font-bold text-neon-green">
                  +{card.expected_value?.toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Legs Preview (Blurred) */}
            <div className="space-y-2 mb-4">
              {card.legs_preview?.slice(0, 3).map((leg, idx) => (
                <div key={idx} className="bg-navy/30 rounded-lg p-2 blur-sm select-none">
                  <div className="text-xs text-light-gray">
                    Leg {idx + 1}: {leg.matchup || '████████'}
                  </div>
                </div>
              ))}
            </div>

            <div className="text-center text-xs text-gold">
              🔒 Click to view full parlay
            </div>
          </>
        ) : (
          <div className="text-center py-8">
            <div className="animate-pulse text-4xl mb-4">🎲</div>
            <div className="text-sm text-light-gray">{card.message || 'Analyzing optimal structure...'}</div>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-darkNavy p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-12">
            <div className="animate-pulse text-6xl mb-4">📊</div>
            <div className="text-xl text-gold">Loading Today's Best Cards...</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-darkNavy p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-deepRed/20 border border-deepRed rounded-xl p-8 text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <div className="text-xl text-white mb-2">Failed to Load Cards</div>
            <div className="text-sm text-light-gray mb-4">{error}</div>
            <button
              onClick={fetchDailyCards}
              className="px-6 py-3 bg-gold text-darkNavy font-bold rounded-lg hover:bg-lightGold transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Check if cards are empty (no games/simulations available)
  const hasAnyCards = cards && (
    cards.best_game_overall || 
    cards.top_nba_game || 
    cards.top_ncaab_game || 
    cards.top_ncaaf_game || 
    cards.top_prop_mispricing || 
    cards.parlay_preview
  );

  if (!hasAnyCards) {
    return (
      <div className="min-h-screen bg-darkNavy p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📭</div>
            <div className="text-2xl text-gold mb-4">No Cards Available</div>
            <div className="text-light-gray mb-6">
              {(cards as any)?.message || 'No games or simulations available for today\'s slate.'}
            </div>
            <div className="text-sm text-light-gray/60">
              This happens when:
              <ul className="mt-2 space-y-1">
                <li>• No upcoming games in the next 24 hours</li>
                <li>• Simulations are still processing (check back in 5-10 minutes)</li>
                <li>• Database was recently cleared</li>
              </ul>
            </div>
            <button
              onClick={fetchDailyCards}
              className="mt-6 px-6 py-3 bg-gold text-darkNavy font-bold rounded-lg hover:bg-lightGold transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-darkNavy p-8">
      <div className="max-w-7xl mx-auto">
        {/* Hero Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gold mb-4">
            TODAY'S BEST CARDS
          </h1>
          <p className="text-lightGold text-lg mb-2">
            6 Flagship Posts • Curated by Monte Carlo Simulation
          </p>
          <div className="text-sm text-light-gray">
            Generated at {cards?.generated_at ? new Date(cards.generated_at).toLocaleTimeString() : 'N/A'}
          </div>
        </div>

        {/* Flagship Card - Full Width */}
        <div className="mb-8">
          {renderGameCard(cards?.best_game_overall || null, 'best_game_overall')}
        </div>

        {/* Sport-Specific Cards - 3 Column Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {renderGameCard(cards?.top_nba_game || null, 'top_nba_game')}
          {renderGameCard(cards?.top_ncaab_game || null, 'top_ncaab_game')}
          {renderGameCard(cards?.top_ncaaf_game || null, 'top_ncaaf_game')}
        </div>

        {/* Prop + Parlay - 2 Column Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {renderPropCard(cards?.top_prop_mispricing || null)}
          {renderParlayCard(cards?.parlay_preview || null)}
        </div>

        {/* Compliance Footer */}
        <div className="mt-12 text-center">
          <div className="inline-block bg-charcoal/50 rounded-lg px-6 py-3 border border-gold/20">
            <div className="text-xs text-light-gray">
              This platform provides statistical modeling only. No recommendations or betting instructions are provided.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DailyBestCards;
