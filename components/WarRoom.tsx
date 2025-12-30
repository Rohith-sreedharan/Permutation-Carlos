import React, { useState, useEffect, useMemo } from 'react';
import { AlertCircle, Lock, Zap, TrendingUp, Users, Eye, MessageCircle, Clock, Activity, ChevronRight, Filter, RefreshCw, X, Brain, Target, BarChart3 } from 'lucide-react';
import PageHeader from './PageHeader';
import LoadingSpinner from './LoadingSpinner';
import { swalSuccess, swalError } from '../utils/swal';
import { verifyToken, fetchEventsFromDB } from '../services/api';
import type { Event } from '../types';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

// ============================================================================
// TYPES
// ============================================================================

/**
 * Market state from the Market State Registry
 * 🚨 WAR ROOM VISIBILITY CONTRACT:
 *   - War Room shows: state IN (EDGE, LEAN)
 *   - War Room excludes: state == NO_PLAY
 *   - War Room must NEVER depend on Telegram posting
 *   - War Room must render even when zero EDGEs exist (LEAN is the default content)
 */
type MarketState = 'EDGE' | 'LEAN' | 'NO_PLAY';

interface MarketStateInfo {
  game_id: string;
  market_type: string;
  state: MarketState;
  probability?: number;
  edge_points?: number;
  confidence_score?: number;
  selection?: string;
  line_value?: number;
  visibility_flags: {
    telegram_allowed: boolean;
    parlay_allowed: boolean;
    war_room_visible: boolean;
  };
}

interface GameRoom {
  room_id: string;
  event_id: string;
  sport: string;
  sport_key: string;
  home_team: string;
  away_team: string;
  commence_time: string;
  status: 'upcoming' | 'live' | 'final';
  thread_count?: number;
  // Market state info from registry
  market_states?: MarketStateInfo[];
  has_edge?: boolean;  // Has at least one EDGE market
  has_lean?: boolean;  // Has at least one LEAN market
}

interface MarketThread {
  thread_id: string;
  market_type: 'spread' | 'total' | 'moneyline' | 'props';
  post_count: number;
  last_activity: string;
  is_locked: boolean;
  line?: string;
  model_context_attached?: boolean;
  // Market state for this specific thread
  market_state?: MarketState;
  edge_points?: number;
  confidence?: number;
}

interface Post {
  post_id: string;
  username: string;
  user_rank: string;
  post_type: string;
  created_at: string;
  views: number;
  replies: number;
  is_flagged?: boolean;
  market_type?: string;
  line?: string;
  confidence?: string;
  reason?: string;
  result?: string;
  screenshot_url?: string;
  model_context?: ModelContext;
  signal_id?: string;
}

interface DiscussionPost {
  post_id: string;
  thread_id: string;
  user_id: string;
  display_name: string;
  user_tier: string;
  content: string;
  posted_at: string;
  likes: number;
  replies: any[];
  attachments?: Array<{ type: string; signal_id: string }>;
}

interface ModelContext {
  signal_id: string;
  edge_percent: number;
  model_pick: string;
  simulation_iterations: number;
  confidence_band: [number, number];
  key_factors: string[];
  generated_at: string;
}

type SportFilter = 'all' | 'basketball_nba' | 'americanfootball_nfl' | 'icehockey_nhl' | 'baseball_mlb';

const SPORT_OPTIONS: { value: SportFilter; label: string; emoji: string }[] = [
  { value: 'all', label: 'All Sports', emoji: '🎯' },
  { value: 'basketball_nba', label: 'NBA', emoji: '🏀' },
  { value: 'americanfootball_nfl', label: 'NFL', emoji: '🏈' },
  { value: 'icehockey_nhl', label: 'NHL', emoji: '🏒' },
  { value: 'baseball_mlb', label: 'MLB', emoji: '⚾' },
];

const MARKET_TABS = [
  { id: 'spread', label: 'Spread', icon: Target },
  { id: 'total', label: 'Total', icon: BarChart3 },
  { id: 'moneyline', label: 'ML', icon: TrendingUp },
  { id: 'props', label: 'Props', icon: Users },
];

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const WarRoom: React.FC = () => {
  // Game data
  const [games, setGames] = useState<Event[]>([]);
  const [rooms, setRooms] = useState<GameRoom[]>([]);
  const [selectedGame, setSelectedGame] = useState<GameRoom | null>(null);
  
  // Thread data
  const [selectedMarket, setSelectedMarket] = useState<string>('spread');
  const [threads, setThreads] = useState<MarketThread[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  
  // UI state
  const [loading, setLoading] = useState(true);
  const [dataStatus, setDataStatus] = useState<'loading' | 'syncing' | 'ready' | 'error'>('loading');
  const [sportFilter, setSportFilter] = useState<SportFilter>('all');
  const [postingMode, setPostingMode] = useState<string | null>(null);
  const [showContextPanel, setShowContextPanel] = useState(false);
  const [userTier, setUserTier] = useState('free');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // ============================================================================
  // DATA LOADING
  // ============================================================================

  useEffect(() => {
    loadInitialData();
    loadUserTier();
    // Set up auto-refresh every 60 seconds
    const interval = setInterval(() => {
      loadGames();
      setLastRefresh(new Date());
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const loadUserTier = async () => {
    try {
      const user = await verifyToken();
      setUserTier(user?.tier || 'free');
    } catch (err) {
      console.error('Failed to load user tier:', err);
      setUserTier('free');
    }
  };

  const loadInitialData = async () => {
    setDataStatus('loading');
    await loadGames();
  };

  /**
   * Load games and their market states from the Market State Registry
   * 
   * 🚨 WAR ROOM VISIBILITY CONTRACT:
   *   - Shows: state IN (EDGE, LEAN)
   *   - Excludes: state == NO_PLAY
   *   - Must NEVER depend on Telegram posting
   *   - Must render even when zero EDGEs exist (LEAN is the default content)
   */
  const loadGames = async () => {
    try {
      // Fetch today's games from the existing events API
      const events = await fetchEventsFromDB(undefined, undefined, false, 100);
      setGames(events);
      
      // Fetch market states from registry
      let marketStates: MarketStateInfo[] = [];
      try {
        const statesResponse = await fetch(`${API_BASE_URL}/api/market-states/war-room-visible`);
        if (statesResponse.ok) {
          const statesData = await statesResponse.json();
          marketStates = statesData.states || [];
        }
      } catch (err) {
        console.warn('Could not fetch market states from registry:', err);
        // Continue without market states - War Room should still render
      }
      
      // Convert events to game rooms with market state info
      const gameRooms: GameRoom[] = events.map((event) => {
        // Get market states for this game
        const gameMarketStates = marketStates.filter(s => s.game_id === event.id);
        const hasEdge = gameMarketStates.some(s => s.state === 'EDGE');
        const hasLean = gameMarketStates.some(s => s.state === 'LEAN');
        
        return {
          room_id: `room_${event.id}`,
          event_id: event.id,
          sport: getSportLabel(event.sport_key),
          sport_key: event.sport_key,
          home_team: event.home_team,
          away_team: event.away_team,
          commence_time: event.commence_time,
          status: getGameStatus(event.commence_time),
          thread_count: 4, // Default market threads
          market_states: gameMarketStates,
          has_edge: hasEdge,
          has_lean: hasLean,
        };
      });
      
      // 🚨 WAR ROOM SHOWS ALL GAMES - does NOT filter by market state
      // NO_PLAY games still appear but with fewer highlights
      // This ensures War Room is never empty when there are games
      setRooms(gameRooms);
      
      if (gameRooms.length > 0 && !selectedGame) {
        // Prefer game with EDGE, then LEAN, then any
        const preferredGame = 
          gameRooms.find(g => g.has_edge) || 
          gameRooms.find(g => g.has_lean) || 
          gameRooms[0];
        setSelectedGame(preferredGame);
      }
      
      setDataStatus(gameRooms.length > 0 ? 'ready' : 'syncing');
      setLoading(false);
    } catch (err) {
      console.error('Failed to load games:', err);
      setDataStatus('error');
      setLoading(false);
    }
  };

  const getSportLabel = (sportKey: string): string => {
    const labels: Record<string, string> = {
      'basketball_nba': 'NBA',
      'americanfootball_nfl': 'NFL',
      'icehockey_nhl': 'NHL',
      'baseball_mlb': 'MLB',
    };
    return labels[sportKey] || sportKey.toUpperCase();
  };

  const getGameStatus = (commenceTime: string): 'upcoming' | 'live' | 'final' => {
    const now = new Date();
    const gameTime = new Date(commenceTime);
    const hoursUntil = (gameTime.getTime() - now.getTime()) / (1000 * 60 * 60);
    
    if (hoursUntil > 0) return 'upcoming';
    if (hoursUntil > -3) return 'live'; // Assume game is live for ~3 hours
    return 'final';
  };

  // Load threads when game or market changes
  useEffect(() => {
    if (selectedGame) {
      loadThreads(selectedGame.room_id, selectedMarket, selectedGame);
    }
  }, [selectedGame, selectedMarket]);

  /**
   * Load threads for a game room
   * 🚨 WAR ROOM NON-EMPTY FALLBACK:
   *   - If no user posts exist for a game: Auto-seed system discussion threads
   *   - System threads include model context and market state
   *   - Never show completely empty War Room
   */
  const loadThreads = async (roomId: string, marketType: string, game?: GameRoom) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/war-room/game-rooms/${roomId}?market=${marketType}`);
      if (response.ok) {
        const data = await response.json();
        const userThreads = data.threads || [];
        const userPosts = data.posts || [];

        // If no user threads exist, auto-seed with system discussion threads
        if (userThreads.length === 0) {
          const seededThreads = createAutoSeededThreads(roomId, marketType, game);
          setThreads(seededThreads);
          setPosts(createSystemPosts(seededThreads, game));
        } else {
          setThreads(userThreads);
          setPosts(userPosts);
        }
      } else {
        // Auto-seed default thread if API fails
        const seededThreads = createAutoSeededThreads(roomId, marketType, game);
        setThreads(seededThreads);
        setPosts(createSystemPosts(seededThreads, game));
      }
    } catch (err) {
      // Fallback: create auto-seeded threads
      const seededThreads = createAutoSeededThreads(roomId, marketType, game);
      setThreads(seededThreads);
      setPosts(createSystemPosts(seededThreads, game));
    }
  };

  /**
   * Create auto-seeded system discussion threads
   * These ensure the War Room is never empty
   */
  const createAutoSeededThreads = (roomId: string, marketType: string, game?: GameRoom): MarketThread[] => {
    const now = new Date().toISOString();
    const marketState = game?.market_states?.find(m => m.market_type === marketType);
    
    return [{
      thread_id: `${roomId}_${marketType}_main`,
      market_type: marketType as MarketThread['market_type'],
      post_count: 1, // System post counts as 1
      last_activity: now,
      is_locked: false,
      model_context_attached: true,
      // Attach market state from registry
      market_state: marketState?.state,
      edge_points: marketState?.edge_points,
      confidence: marketState?.confidence_score,
    }];
  };

  /**
   * Create system posts for auto-seeded threads
   * These provide initial context and model insights
   */
  const createSystemPosts = (threads: MarketThread[], game?: GameRoom): Post[] => {
    if (threads.length === 0) return [];
    
    const thread = threads[0];
    const marketState = game?.market_states?.find(m => m.market_type === thread.market_type);
    const stateLabel = marketState?.state === 'EDGE' ? '🟢 EDGE' : marketState?.state === 'LEAN' ? '🟡 LEAN' : '📊 Analysis';
    
    return [{
      post_id: `${thread.thread_id}_system_init`,
      username: 'BeatVegas AI',
      user_rank: 'system',
      post_type: 'system_message',
      created_at: new Date().toISOString(),
      views: 0,
      replies: 0,
      reason: `**${stateLabel} Signal Active**\n\nModel analysis is attached to this thread. Share your thoughts, fade or follow the model's position.\n\n${marketState?.edge_points ? `Edge: ${marketState.edge_points.toFixed(1)}pts` : ''} ${marketState?.confidence_score ? `| Confidence: ${marketState.confidence_score}%` : ''}`,
    }];
  };

  // Filter games by sport
  const filteredGames = useMemo(() => {
    if (sportFilter === 'all') return rooms;
    return rooms.filter((room) => room.sport_key === sportFilter);
  }, [rooms, sportFilter]);

  // Format time for display
  const formatGameTime = (commenceTime: string): string => {
    const date = new Date(commenceTime);
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      timeZoneName: 'short'
    });
  };

  const getNextRefreshTime = (): string => {
    const next = new Date(lastRefresh.getTime() + 60000);
    return next.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  // ============================================================================
  // RENDER
  // ============================================================================

  if (loading) return <LoadingSpinner />;

  return (
    <div className="flex flex-col bg-linear-to-b from-charcoal to-midnight min-h-screen">
      {/* Compact Header */}
      <div className="px-6 pt-4 pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white font-teko tracking-wide">WAR ROOM</h1>
            <span className="text-xs text-electric-blue bg-electric-blue/10 px-2 py-1 rounded-full font-medium">
              LIVE INTELLIGENCE
            </span>
          </div>
          <div className="flex items-center gap-3">
            {userTier === 'free' && (
              <span className="text-xs text-yellow-400 bg-yellow-500/10 px-2 py-1 rounded-full">
                Read-only
              </span>
            )}
            <button 
              onClick={() => { loadGames(); setLastRefresh(new Date()); }}
              className="text-light-gray hover:text-white transition p-1"
              title="Refresh games"
            >
              <RefreshCw size={16} />
            </button>
            <span className="text-xs text-light-gray">
              Updated {lastRefresh.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
            </span>
          </div>
        </div>
      </div>

      {/* Main 2-Pane Layout */}
      <div className="flex-1 flex gap-4 p-4 h-[calc(100vh-100px)]">
        
        {/* LEFT PANE: Today's Slate */}
        <div className="w-80 shrink-0 flex flex-col bg-charcoal/50 rounded-xl border border-navy overflow-hidden">
          {/* Slate Header */}
          <div className="p-4 border-b border-navy">
            <h2 className="text-lg font-bold text-white font-teko mb-3">TODAY'S SLATE</h2>
            
            {/* Sport Filter Pills */}
            <div className="flex flex-wrap gap-1.5">
              {SPORT_OPTIONS.map((sport) => (
                <button
                  key={sport.value}
                  onClick={() => setSportFilter(sport.value)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition ${
                    sportFilter === sport.value
                      ? 'bg-electric-blue text-charcoal'
                      : 'bg-navy/50 text-light-gray hover:bg-navy hover:text-white'
                  }`}
                >
                  {sport.emoji} {sport.label}
                </button>
              ))}
            </div>
          </div>

          {/* Games List */}
          <div className="flex-1 overflow-y-auto p-2">
            {dataStatus === 'syncing' ? (
              <DataSyncingState nextRefresh={getNextRefreshTime()} />
            ) : filteredGames.length === 0 ? (
              <NoGamesState sportFilter={sportFilter} />
            ) : (
              <div className="space-y-2">
                {filteredGames.map((game) => (
                  <GameCard
                    key={game.room_id}
                    game={game}
                    isSelected={selectedGame?.room_id === game.room_id}
                    onClick={() => setSelectedGame(game)}
                    formatTime={formatGameTime}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANE: Market Threads */}
        <div className="flex-1 flex flex-col bg-charcoal/50 rounded-xl border border-navy overflow-hidden">
          {selectedGame ? (
            <>
              {/* Game Header + Market Tabs */}
              <div className="p-4 border-b border-navy">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-white">
                      {selectedGame.away_team} @ {selectedGame.home_team}
                    </h3>
                    <p className="text-xs text-light-gray flex items-center gap-2">
                      <StatusPill status={selectedGame.status} />
                      <span>{formatGameTime(selectedGame.commence_time)}</span>
                    </p>
                  </div>
                  <button
                    onClick={() => setShowContextPanel(!showContextPanel)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                      showContextPanel 
                        ? 'bg-electric-blue text-charcoal' 
                        : 'bg-navy/50 text-electric-blue hover:bg-navy'
                    }`}
                  >
                    <Brain size={14} />
                    Model Context
                  </button>
                </div>

                {/* Market Tabs */}
                <div className="flex gap-1">
                  {MARKET_TABS.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setSelectedMarket(tab.id)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition ${
                        selectedMarket === tab.id
                          ? 'bg-electric-blue text-charcoal'
                          : 'bg-navy/30 text-light-gray hover:bg-navy/50 hover:text-white'
                      }`}
                    >
                      <tab.icon size={14} />
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Thread Content */}
              <div className="flex-1 flex overflow-hidden">
                {/* Posts Feed */}
                <div className={`flex-1 flex flex-col ${showContextPanel ? 'border-r border-navy' : ''}`}>
                  {/* Composer Area (only for paid tiers) */}
                  {userTier !== 'free' && !postingMode && (
                    <div className="p-3 border-b border-navy/50">
                      <div className="flex gap-2">
                        <button
                          onClick={() => setPostingMode('market_callout')}
                          className="px-3 py-2 bg-electric-blue text-charcoal font-bold text-xs rounded-lg hover:bg-electric-blue/90 transition flex items-center gap-1.5"
                        >
                          <Target size={14} />
                          Market Callout
                        </button>
                        <button
                          onClick={() => setPostingMode('receipt')}
                          className="px-3 py-2 bg-green-500/20 text-green-400 font-bold text-xs rounded-lg hover:bg-green-500/30 transition border border-green-500/30"
                        >
                          📸 Receipt
                        </button>
                        <button
                          onClick={() => setPostingMode('parlay_build')}
                          className="px-3 py-2 bg-purple-500/20 text-purple-400 font-bold text-xs rounded-lg hover:bg-purple-500/30 transition border border-purple-500/30"
                        >
                          🧩 Parlay
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Posting Template */}
                  {postingMode && (
                    <div className="p-4 border-b border-navy/50">
                      <PostTemplateContainer
                        type={postingMode}
                        threadId={threads[0]?.thread_id || ''}
                        game={selectedGame}
                        marketType={selectedMarket}
                        userTier={userTier}
                        onClose={() => setPostingMode(null)}
                        onSubmit={() => {
                          setPostingMode(null);
                          if (selectedGame) loadThreads(selectedGame.room_id, selectedMarket);
                        }}
                      />
                    </div>
                  )}

                  {/* Posts */}
                  <div className="flex-1 overflow-y-auto p-4">
                    {posts.length === 0 ? (
                      <EmptyThreadState 
                        marketType={selectedMarket} 
                        gameName={`${selectedGame.away_team} @ ${selectedGame.home_team}`}
                        userTier={userTier}
                        onStartPost={() => setPostingMode('market_callout')}
                      />
                    ) : (
                      <div className="space-y-3">
                        {posts.map((post) => (
                          <PostCard key={post.post_id} post={post} />
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Model Context Panel (Moat Panel) */}
                {showContextPanel && (
                  <ModelContextPanel 
                    game={selectedGame}
                    marketType={selectedMarket}
                    onClose={() => setShowContextPanel(false)}
                  />
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-16 h-16 bg-navy/50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Target size={32} className="text-light-gray" />
                </div>
                <p className="text-light-gray">Select a game from Today's Slate</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// GAME CARD
// ============================================================================

interface GameCardProps {
  game: GameRoom;
  isSelected: boolean;
  onClick: () => void;
  formatTime: (time: string) => string;
}

const GameCard: React.FC<GameCardProps> = ({ game, isSelected, onClick, formatTime }) => {
  // Determine the best market state badge to show
  // Priority: EDGE (strongest signal) > LEAN (actionable) > nothing (NO_PLAY excluded by filter)
  const getStateBadge = () => {
    if (game.has_edge) {
      return (
        <span className="bg-emerald-500/20 text-emerald-400 text-[9px] font-bold px-1.5 py-0.5 rounded flex items-center gap-0.5">
          <TrendingUp size={8} />
          EDGE
        </span>
      );
    }
    if (game.has_lean) {
      return (
        <span className="bg-amber-500/20 text-amber-400 text-[9px] font-bold px-1.5 py-0.5 rounded flex items-center gap-0.5">
          <Target size={8} />
          LEAN
        </span>
      );
    }
    return null;
  };

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg transition border ${
        isSelected
          ? 'bg-electric-blue/10 border-electric-blue text-white'
          : game.has_edge
            ? 'bg-emerald-900/20 border-emerald-500/30 hover:bg-emerald-900/30 text-white'
            : game.has_lean
              ? 'bg-amber-900/10 border-amber-500/20 hover:bg-amber-900/20 text-white'
              : 'bg-navy/30 border-transparent hover:bg-navy/50 text-white hover:border-navy'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-light-gray">{game.sport}</span>
          {getStateBadge()}
        </div>
        <StatusPill status={game.status} />
      </div>
      <div className="font-bold text-sm mb-0.5">{game.away_team}</div>
      <div className="text-xs text-light-gray mb-1">@ {game.home_team}</div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-light-gray flex items-center gap-1">
          <Clock size={10} />
          {formatTime(game.commence_time)}
        </span>
        <span className="text-electric-blue flex items-center gap-1">
          <MessageCircle size={10} />
          {game.thread_count || 0}
        </span>
      </div>
    </button>
  );
};

// ============================================================================
// STATUS PILL
// ============================================================================

interface StatusPillProps {
  status: 'upcoming' | 'live' | 'final';
}

const StatusPill: React.FC<StatusPillProps> = ({ status }) => {
  const config = {
    live: { bg: 'bg-red-500/20', text: 'text-red-400', label: '🔴 LIVE' },
    upcoming: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'UPCOMING' },
    final: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'FINAL' },
  };
  const { bg, text, label } = config[status];
  
  return (
    <span className={`${bg} ${text} text-[10px] font-bold px-1.5 py-0.5 rounded`}>
      {label}
    </span>
  );
};

// ============================================================================
// EMPTY STATES
// ============================================================================

const DataSyncingState: React.FC<{ nextRefresh: string }> = ({ nextRefresh }) => (
  <div className="flex flex-col items-center justify-center h-full text-center p-6">
    <div className="w-12 h-12 bg-electric-blue/10 rounded-full flex items-center justify-center mb-4">
      <RefreshCw size={24} className="text-electric-blue animate-spin" />
    </div>
    <h4 className="text-white font-bold mb-1">Models are updating</h4>
    <p className="text-xs text-light-gray mb-3">
      Game data is syncing. Check back shortly.
    </p>
    <p className="text-xs text-electric-blue">
      Next refresh: {nextRefresh}
    </p>
    <p className="text-xs text-light-gray mt-4">
      💡 Telegram signals still running
    </p>
  </div>
);

const NoGamesState: React.FC<{ sportFilter: SportFilter }> = ({ sportFilter }) => (
  <div className="flex flex-col items-center justify-center h-full text-center p-6">
    <div className="w-12 h-12 bg-navy/50 rounded-full flex items-center justify-center mb-4">
      <Activity size={24} className="text-light-gray" />
    </div>
    <h4 className="text-white font-bold mb-1">No games scheduled</h4>
    <p className="text-xs text-light-gray">
      {sportFilter !== 'all' 
        ? `No ${SPORT_OPTIONS.find(s => s.value === sportFilter)?.label} games today. Try "All Sports".`
        : 'Check back tomorrow for upcoming matchups.'
      }
    </p>
  </div>
);

interface EmptyThreadStateProps {
  marketType: string;
  gameName: string;
  userTier: string;
  onStartPost: () => void;
}

const EmptyThreadState: React.FC<EmptyThreadStateProps> = ({ marketType, gameName, userTier, onStartPost }) => (
  <div className="flex flex-col items-center justify-center h-full text-center">
    <div className="max-w-sm">
      {/* Auto-seeded system thread indicator */}
      <div className="bg-navy/30 border border-navy rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain size={16} className="text-electric-blue" />
          <span className="text-xs font-bold text-electric-blue">MODEL CONTEXT ATTACHED</span>
        </div>
        <h4 className="text-white font-bold text-sm mb-1">
          {marketType.charAt(0).toUpperCase() + marketType.slice(1)} Discussion
        </h4>
        <p className="text-xs text-light-gray">{gameName}</p>
      </div>

      <p className="text-sm text-light-gray mb-4">
        Be the first to share analysis on this market. All posts require structured format.
      </p>

      {userTier !== 'free' ? (
        <button
          onClick={onStartPost}
          className="px-4 py-2 bg-electric-blue text-charcoal font-bold text-sm rounded-lg hover:bg-electric-blue/90 transition"
        >
          + Add Market Callout
        </button>
      ) : (
        <p className="text-xs text-yellow-400">
          Upgrade to participate in discussions
        </p>
      )}
    </div>
  </div>
);

// ============================================================================
// MODEL CONTEXT PANEL (MOAT)
// ============================================================================

interface ModelContextPanelProps {
  game: GameRoom;
  marketType: string;
  onClose: () => void;
}

const ModelContextPanel: React.FC<ModelContextPanelProps> = ({ game, marketType, onClose }) => {
  // This would fetch real model context from the backend
  const mockContext: ModelContext = {
    signal_id: `sig_${game.event_id}_${marketType}`,
    edge_percent: 4.2,
    model_pick: `${game.home_team} -3.5`,
    simulation_iterations: 10000,
    confidence_band: [52, 58],
    key_factors: [
      'Home team 8-2 ATS last 10',
      'Away team on B2B',
      'Key player questionable',
    ],
    generated_at: new Date().toISOString(),
  };

  return (
    <div className="w-72 bg-navy/20 p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-bold text-white text-sm flex items-center gap-2">
          <Brain size={16} className="text-electric-blue" />
          BeatVegas Context
        </h4>
        <button onClick={onClose} className="text-light-gray hover:text-white">
          <X size={16} />
        </button>
      </div>

      {/* Model Pick */}
      <div className="bg-charcoal/50 rounded-lg p-3 mb-3 border border-electric-blue/30">
        <p className="text-xs text-light-gray mb-1">Model Pick</p>
        <p className="text-lg font-bold text-electric-blue">{mockContext.model_pick}</p>
        <p className="text-xs text-green-400 mt-1">+{mockContext.edge_percent}% Edge</p>
      </div>

      {/* Confidence Band */}
      <div className="bg-charcoal/50 rounded-lg p-3 mb-3">
        <p className="text-xs text-light-gray mb-2">Win Probability</p>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-navy rounded-full overflow-hidden">
            <div 
              className="h-full bg-electric-blue rounded-full"
              style={{ width: `${(mockContext.confidence_band[0] + mockContext.confidence_band[1]) / 2}%` }}
            />
          </div>
          <span className="text-xs font-bold text-white">
            {mockContext.confidence_band[0]}-{mockContext.confidence_band[1]}%
          </span>
        </div>
      </div>

      {/* Key Factors */}
      <div className="bg-charcoal/50 rounded-lg p-3 mb-3">
        <p className="text-xs text-light-gray mb-2">Key Factors</p>
        <ul className="space-y-1.5">
          {mockContext.key_factors.map((factor, i) => (
            <li key={i} className="text-xs text-white flex items-start gap-2">
              <span className="text-electric-blue">•</span>
              {factor}
            </li>
          ))}
        </ul>
      </div>

      {/* Meta */}
      <div className="text-xs text-light-gray">
        <p>Signal ID: {mockContext.signal_id}</p>
        <p>{mockContext.simulation_iterations.toLocaleString()} simulations</p>
      </div>
    </div>
  );
};

// ============================================================================
// POST TEMPLATE CONTAINER
// ============================================================================

interface PostTemplateContainerProps {
  type: string;
  threadId: string;
  game: GameRoom;
  marketType: string;
  userTier: string;
  onClose: () => void;
  onSubmit: () => void;
}

// Component defined below after main component

// ============================================================================
// POST TEMPLATE CONTAINER
// ============================================================================

interface PostTemplateContainerProps {
  type: string;
  threadId: string;
  game: GameRoom;
  marketType: string;
  userTier: string;
  onClose: () => void;
  onSubmit: () => void;
}

const PostTemplateContainer: React.FC<PostTemplateContainerProps> = ({
  type,
  threadId,
  game,
  marketType,
  userTier,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState<any>({
    market_type: marketType,
    confidence: 'med',
    line: '',
    reason: '',
    played_this: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Blocked words for anti-spam
  const BLOCKED_WORDS = ['lock', 'guarantee', 'free money', 'sure thing', 'can\'t lose', 'ez money'];

  const handleChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const validateReason = (text: string): string | null => {
    const lowerText = text.toLowerCase();
    for (const word of BLOCKED_WORDS) {
      if (lowerText.includes(word)) {
        return `Hype language detected: "${word}" is not allowed`;
      }
    }
    if (text.length < 10) return 'Min 10 characters';
    if (text.length > 240) return 'Max 240 characters';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.line) newErrors.line = 'Required';
    const reasonError = validateReason(formData.reason);
    if (reasonError) newErrors.reason = reasonError;

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSubmitting(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/war-room/posts/market-callout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          thread_id: threadId,
          game_matchup: `${game.away_team} @ ${game.home_team}`,
          market_type: formData.market_type,
          line: formData.line,
          confidence: formData.confidence,
          reason: formData.reason,
          played_this: formData.played_this || false,
        }),
      });

      if (response.ok) {
        await swalSuccess('Posted', 'Your market callout is live');
        onSubmit();
      } else {
        const data = await response.json();
        await swalError('Error', data.detail || 'Failed to post');
      }
    } catch (err) {
      await swalError('Error', 'Network error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-navy/20 rounded-lg border border-navy p-4">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h4 className="font-bold text-white text-sm">Market Callout</h4>
          <p className="text-xs text-light-gray">
            {game.away_team} @ {game.home_team} • {marketType.charAt(0).toUpperCase() + marketType.slice(1)}
          </p>
        </div>
        <button type="button" onClick={onClose} className="text-light-gray hover:text-white">
          <X size={16} />
        </button>
      </div>

      {/* Format hint - compact, not a banner */}
      <div className="bg-charcoal/50 rounded px-3 py-2 mb-4 text-xs text-light-gray border-l-2 border-electric-blue">
        <strong className="text-electric-blue">Format:</strong> Line + Confidence + Reason (max 240 chars, no hype)
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Line */}
        <div>
          <label className="text-xs font-bold text-light-gray block mb-1">
            Line <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            placeholder="e.g., Lakers -5.5"
            value={formData.line}
            onChange={(e) => handleChange('line', e.target.value)}
            className="w-full bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm focus:border-electric-blue focus:outline-none"
          />
          {errors.line && <p className="text-xs text-red-400 mt-1">{errors.line}</p>}
        </div>

        {/* Confidence */}
        <div>
          <label className="text-xs font-bold text-light-gray block mb-1">Confidence</label>
          <div className="grid grid-cols-3 gap-1">
            {['low', 'med', 'high'].map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => handleChange('confidence', level)}
                className={`py-2 rounded text-xs font-bold transition ${
                  formData.confidence === level
                    ? level === 'high' ? 'bg-green-500 text-white' :
                      level === 'med' ? 'bg-yellow-500 text-charcoal' :
                      'bg-red-500/80 text-white'
                    : 'bg-navy text-light-gray hover:bg-navy/70'
                }`}
              >
                {level.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Reason */}
      <div className="mb-3">
        <label className="text-xs font-bold text-light-gray block mb-1">
          Reason <span className="text-light-gray">({formData.reason.length}/240)</span>
        </label>
        <textarea
          placeholder="Why this play? Be specific about edge."
          value={formData.reason}
          onChange={(e) => handleChange('reason', e.target.value)}
          maxLength={240}
          className="w-full bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm focus:border-electric-blue focus:outline-none resize-none"
          rows={2}
        />
        {errors.reason && <p className="text-xs text-red-400 mt-1">{errors.reason}</p>}
      </div>

      {/* Played This + Submit */}
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.played_this}
            onChange={(e) => handleChange('played_this', e.target.checked)}
            className="w-4 h-4 rounded border-navy"
          />
          <span className="text-xs text-light-gray">I played this</span>
        </label>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 text-xs text-light-gray hover:text-white transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-electric-blue text-charcoal font-bold text-xs rounded-lg hover:bg-electric-blue/90 transition disabled:opacity-50"
          >
            {submitting ? 'Posting...' : 'Post Callout'}
          </button>
        </div>
      </div>
    </form>
  );
};

// ============================================================================
// POST CARD
// ============================================================================

interface PostCardProps {
  post: Post;
}

const PostCard: React.FC<PostCardProps> = ({ post }) => {
  const getRankStyle = (rank: string) => {
    const styles: Record<string, string> = {
      elite: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      verified: 'bg-green-500/20 text-green-400 border-green-500/30',
      contributor: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      rookie: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    };
    return styles[rank] || styles.rookie;
  };

  const getConfidenceStyle = (confidence: string) => {
    const styles: Record<string, string> = {
      high: 'bg-green-500/20 text-green-400',
      med: 'bg-yellow-500/20 text-yellow-400',
      low: 'bg-red-500/20 text-red-400',
    };
    return styles[confidence] || styles.med;
  };

  return (
    <div className="bg-navy/30 border border-navy rounded-lg p-4 hover:border-electric-blue/30 transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-sm">{post.username}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${getRankStyle(post.user_rank)}`}>
            {post.user_rank?.toUpperCase() || 'USER'}
          </span>
        </div>
        <span className="text-xs text-light-gray">
          {new Date(post.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
        </span>
      </div>

      {/* Market Callout Content */}
      {post.post_type === 'market_callout' && (
        <>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-white font-bold">{post.line}</span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${getConfidenceStyle(post.confidence || 'med')}`}>
              {(post.confidence || 'med').toUpperCase()}
            </span>
            {post.model_context && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-electric-blue/20 text-electric-blue flex items-center gap-1">
                <Brain size={10} />
                MODEL
              </span>
            )}
          </div>
          <p className="text-sm text-light-gray bg-charcoal/30 rounded px-3 py-2 border-l-2 border-electric-blue/50">
            {post.reason}
          </p>
        </>
      )}

      {/* Receipt Content */}
      {post.post_type === 'receipt' && (
        <div className="flex gap-3">
          {post.screenshot_url && (
            <img src={post.screenshot_url} alt="receipt" className="w-16 h-16 object-cover rounded" />
          )}
          <div className="text-sm">
            <p className="text-white font-medium">{post.line}</p>
            <p className={`font-bold ${
              post.result === 'W' ? 'text-green-400' : 
              post.result === 'L' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {post.result === 'W' ? '✓ WIN' : post.result === 'L' ? '✗ LOSS' : '~ PUSH'}
            </p>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-navy/50 text-xs text-light-gray">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <Eye size={12} />
            {post.views}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle size={12} />
            {post.replies}
          </span>
        </div>
        {post.is_flagged && (
          <span className="text-red-400 font-bold flex items-center gap-1">
            <AlertCircle size={12} />
            Flagged
          </span>
        )}
      </div>
    </div>
  );
};

export default WarRoom;
