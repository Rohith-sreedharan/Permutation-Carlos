import React, { useState, useEffect, useMemo } from 'react';
import { fetchEventsFromDB, getPredictions } from '../services/api';
import type { EventWithPrediction, Prediction } from '../types';
import EventCard from './EventCard';
import EventListItem from './EventListItem';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// SVG Icons (replacing lucide-react)
const Target = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 18C15.3137 18 18 15.3137 18 12C18 8.68629 15.3137 6 12 6C8.68629 6 6 8.68629 6 12C6 15.3137 8.68629 18 12 18Z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14Z" />
  </svg>
);

const TrendingUp = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
  </svg>
);

const CheckCircle = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const Brain = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>
);

const Activity = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
  </svg>
);

const sports = ['All', 'NBA', 'NCAAB', 'NFL', 'NCAAF', 'MLB', 'NHL'];
type Layout = 'grid' | 'list';
type DateFilter = 'today' | 'tomorrow' | 'this-week' | 'all';
type TimeOrder = 'soonest' | 'latest';

interface DecisionLog {
  id: string;
  event_id: string;
  event_name: string;
  forecast: string;
  confidence: number;
  followed_at: string;
  alignment: 'high' | 'medium' | 'low';
}

interface DecisionCommandCenterProps {
  onAuthError: () => void;
  onGameClick?: (gameId: string) => void;
}

const DecisionCommandCenter: React.FC<DecisionCommandCenterProps> = ({ onAuthError, onGameClick }) => {
  const [eventsWithPredictions, setEventsWithPredictions] = useState<EventWithPrediction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [polling, setPolling] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSport, setActiveSport] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [layout, setLayout] = useState<Layout>('grid');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [timeOrder, setTimeOrder] = useState<TimeOrder>('soonest');
  const [decisionLog, setDecisionLog] = useState<DecisionLog[]>([]);
  const [alignmentScore, setAlignmentScore] = useState(0);
  const [analyticalROI, setAnalyticalROI] = useState(0);

  const loadData = async (isPolling = false) => {
    try {
      if (isPolling) {
        setPolling(true);
      } else {
        setLoading(true);
      }
      setError(null);
      
      // Fetch from database with all sports and no date filter
      const [eventsData, predictionsData] = await Promise.all([
        fetchEventsFromDB(undefined, undefined, true, 200),
        getPredictions(),
      ]);

      const predictionsMap = new Map<string, Prediction>();
      predictionsData.forEach((p) => predictionsMap.set(p.event_id, p));

      const mergedData: EventWithPrediction[] = eventsData.map((event) => ({
        ...event,
        prediction: predictionsMap.get(event.id),
      }));

      setEventsWithPredictions(mergedData);

      // Load user's decision log and metrics
      await loadDecisionMetrics();
    } catch (err: any) {
      if (err.message.includes('No authentication token found') || err.message.includes('Session expired')) {
        onAuthError();
      } else {
        setError('Failed to fetch data. Please try again later.');
      }
      console.error(err);
    } finally {
      if (isPolling) {
        setPolling(false);
      } else {
        setLoading(false);
      }
    }
  };

  const loadDecisionMetrics = async () => {
    try {
      // Fetch user's decision log (forecasts they followed)
      const token = localStorage.getItem('authToken');
      const response = await fetch(`${API_BASE_URL}/api/user/decision-log`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setDecisionLog(data.decisions || []);
        setAlignmentScore(data.alignment_score || 0);
        setAnalyticalROI(data.analytical_roi || 0);
      }
    } catch (error) {
      console.error('Failed to load decision metrics:', error);
    }
  };

  useEffect(() => {
    loadData(false);
    
    // Poll for updates every 2 minutes
    const pollingInterval = setInterval(() => {
      loadData(true);
    }, 120000);

    return () => clearInterval(pollingInterval);
  }, []);

  const sportKeyMap: Record<string, string> = {
    'NBA': 'basketball_nba',
    'NCAAB': 'basketball_ncaab',
    'NFL': 'americanfootball_nfl',
    'NCAAF': 'americanfootball_ncaaf',
    'MLB': 'baseball_mlb',
    'NHL': 'icehockey_nhl'
  };

  const filteredEvents = useMemo(() => {
    let filtered = eventsWithPredictions
      .filter(event => {
        if (activeSport === 'All') return true;
        const mappedKey = sportKeyMap[activeSport];
        return event.sport_key === mappedKey || event.sport_key === activeSport;
      })
      .filter(event => 
        event.home_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.away_team.toLowerCase().includes(searchQuery.toLowerCase())
      );
    
    // Apply date filter
    filtered = filtered.filter(event => {
      // Use backend-provided EST date (already in EST from server)
      const eventEstDate = event.local_date_est;
      if (!eventEstDate) return false;
      
      // Get today's date in EST timezone (for comparison)
      const formatter = new Intl.DateTimeFormat('en-CA', { 
        timeZone: 'America/New_York',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      });
      const estToday = formatter.format(new Date());
      
      const tomorrowDate = new Date();
      tomorrowDate.setDate(tomorrowDate.getDate() + 1);
      const estTomorrow = formatter.format(tomorrowDate);
      
      const weekEndDate = new Date();
      weekEndDate.setDate(weekEndDate.getDate() + 7);
      const estWeekEnd = formatter.format(weekEndDate);

      switch (dateFilter) {
        case 'today':
          return eventEstDate === estToday;
        case 'tomorrow':
          return eventEstDate === estTomorrow;
        case 'this-week':
          return eventEstDate >= estToday && eventEstDate < estWeekEnd;
        case 'all':
        default:
          return true;
      }
    });
    
    // Apply time sort
    filtered = [...filtered].sort((a, b) => {
      const timeA = new Date(a.commence_time).getTime();
      const timeB = new Date(b.commence_time).getTime();
      return timeOrder === 'soonest' ? timeA - timeB : timeB - timeA;
    });
    
    return filtered;
  }, [eventsWithPredictions, activeSport, searchQuery, dateFilter, timeOrder]);

  const handleFollowForecast = async (event: EventWithPrediction) => {
    if (!event.prediction) return;

    try {
      const token = localStorage.getItem('authToken');
      await fetch('/api/user/follow-forecast', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          event_id: event.id,
          forecast: event.prediction.recommended_bet,
          confidence: event.prediction.confidence
        })
      });

      // Reload metrics
      await loadDecisionMetrics();
    } catch (error) {
      console.error('Failed to follow forecast:', error);
    }
  };

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Modern Horizontal Loading Bar */}
      {polling && (
        <div className="fixed top-0 left-0 right-0 z-50">
          <div className="h-1 bg-linear-to-r from-gold via-lightGold to-deepRed animate-[shimmer_2s_ease-in-out_infinite] bg-size-[200%_100%]"></div>
          <div className="bg-navy/98 backdrop-blur-md border-b border-gold/30 px-4 py-2.5 text-center shadow-lg">
            <span className="text-sm text-lightGold font-bold animate-pulse flex items-center justify-center gap-2">
              <Activity className="animate-spin h-4 w-4" />
              Synchronizing Intelligence Feed...
            </span>
          </div>
        </div>
      )}

      {/* Command Center Header */}
      <div className="bg-linear-to-r from-purple-900/40 via-blue-900/40 to-purple-900/40 rounded-lg p-6 border border-purple-500/30">
        <div className="flex items-center gap-3 mb-2">
          <Target className="w-8 h-8 text-purple-400" />
          <h1 className="text-3xl font-bold text-white">Decision Command Center</h1>
        </div>
        <p className="text-gray-300 text-sm">
          Analysis-First Intelligence Platform • Make Informed Decisions with Institutional-Grade Forecasting
        </p>
      </div>

      {/* Key Metrics Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-linear-to-br from-blue-500/10 to-purple-500/10 rounded-lg p-5 border border-blue-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-5 h-5 text-blue-400" />
            <div className="text-sm text-gray-400">AI Alignment Score</div>
          </div>
          <div className="text-3xl font-bold text-blue-400">{alignmentScore}%</div>
          <div className="text-xs text-gray-500 mt-1">
            You align with High-Confidence AI forecasts {alignmentScore}% of the time
          </div>
        </div>

        <div className="bg-linear-to-br from-green-500/10 to-emerald-500/10 rounded-lg p-5 border border-green-500/30">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <div className="text-sm text-gray-400">Analytical Performance ROI</div>
          </div>
          <div className="text-3xl font-bold text-green-400">
            {analyticalROI >= 0 ? '+' : ''}{analyticalROI.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Expected value from followed forecasts
          </div>
        </div>

        <div className="bg-linear-to-br from-purple-500/10 to-pink-500/10 rounded-lg p-5 border border-purple-500/30">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-purple-400" />
            <div className="text-sm text-gray-400">Decisions Logged</div>
          </div>
          <div className="text-3xl font-bold text-purple-400">{decisionLog.length}</div>
          <div className="text-xs text-gray-500 mt-1">
            Total forecasts followed this period
          </div>
        </div>
      </div>

      {/* Sport Selector */}
      <PageHeader title="">
        <div className="flex items-center space-x-2 bg-charcoal p-1 rounded-lg">
          {sports.map(sport => (
            <button
              key={sport}
              onClick={() => setActiveSport(sport)}
              className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-colors ${
                activeSport === sport ? 'bg-gold text-white' : 'text-light-gray hover:bg-navy'
              }`}
            >
              {sport}
            </button>
          ))}
        </div>
      </PageHeader>
      
      {/* DATE & TIME SORT CONTROLS */}
      <div className="bg-linear-to-r from-charcoal via-navy to-charcoal rounded-lg p-4 border border-gold/20 shadow-xl">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
          {/* Date Filter */}
          <div className="flex items-center space-x-3">
            <span className="text-xs text-lightGold uppercase font-bold tracking-wider flex items-center gap-1">
              📅 FILTER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-gold/10">
              {[
                { value: 'today', label: 'Today' },
                { value: 'tomorrow', label: 'Tomorrow' },
                { value: 'this-week', label: 'This Week' },
                { value: 'all', label: 'All Upcoming' }
              ].map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setDateFilter(value as DateFilter)}
                  className={`px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                    dateFilter === value 
                      ? 'bg-gold text-white shadow-lg shadow-gold/50 scale-105' 
                      : 'text-light-gray hover:bg-charcoal hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Time Order Toggle */}
          <div className="flex items-center space-x-3">
            <span className="text-xs text-deepRed uppercase font-bold tracking-wider flex items-center gap-1">
              ⏱ ORDER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-deepRed/10">
              <button
                onClick={() => setTimeOrder('soonest')}
                className={`px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                  timeOrder === 'soonest' 
                    ? 'bg-lightGold text-navy shadow-lg shadow-lightGold/50 scale-105' 
                    : 'text-light-gray hover:bg-charcoal hover:text-white'
                }`}
              >
                ⬇ Soonest First
              </button>
              <button
                onClick={() => setTimeOrder('latest')}
                className={`px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                  timeOrder === 'latest' 
                    ? 'bg-deepRed text-navy shadow-lg shadow-deepRed/50 scale-105' 
                    : 'text-light-gray hover:bg-charcoal hover:text-white'
                }`}
              >
                ⬆ Latest First
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:max-w-xs">
          <input
            type="text"
            placeholder="Search by team name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-charcoal border border-navy rounded-lg px-4 py-2 text-white placeholder-light-gray focus:ring-2 focus:ring-gold focus:outline-none pl-10"
          />
          <svg className="w-5 h-5 text-light-gray absolute left-3 top-1/2 -translate-y-1/2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </div>
        <div className="flex items-center space-x-2 bg-charcoal p-1 rounded-lg">
          <button onClick={() => setLayout('grid')} className={`p-2 rounded-md transition-colors ${layout === 'grid' ? 'bg-gold text-white' : 'text-light-gray hover:bg-navy'}`}>
            <svg className="w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
          </button>
          <button onClick={() => setLayout('list')} className={`p-2 rounded-md transition-colors ${layout === 'list' ? 'bg-gold text-white' : 'text-light-gray hover:bg-navy'}`}>
            <svg className="w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
          </button>
        </div>
      </div>

      {loading ? <LoadingSpinner/> : (
        <>
          {filteredEvents.length === 0 ? (
            <div className="text-center py-16 bg-charcoal rounded-lg border border-navy">
              <div className="text-6xl mb-4">🎯</div>
              <p className="text-light-gray text-xl font-semibold mb-2">No games found</p>
              <p className="text-light-gray/60 text-sm">Try adjusting your filters or check back later for upcoming games.</p>
            </div>
          ) : (
            layout === 'grid' ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {filteredEvents.map((event) => (
                  <EventCard 
                    key={event.id} 
                    event={event}
                    onClick={() => {
                      console.log('[DecisionCommandCenter] Card clicked:', event.id, event);
                      onGameClick?.(event.id);
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {filteredEvents.map((event) => (
                  <EventListItem 
                    key={event.id} 
                    event={event}
                    onClick={() => onGameClick?.(event.id)}
                  />
                ))}
              </div>
            )
          )}
        </>
      )}

      {/* Decision Log Panel */}
      {decisionLog.length > 0 && (
        <div className="mt-8 bg-charcoal/50 rounded-lg p-6 border border-navy">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <CheckCircle className="w-6 h-6 text-purple-400" />
            Recent Decision Log
          </h3>
          <div className="space-y-2">
            {decisionLog.slice(0, 5).map((decision) => (
              <div 
                key={decision.id}
                className="flex items-center justify-between bg-navy/50 rounded-lg p-3 border border-gray-700 hover:border-purple-500/50 transition-colors"
              >
                <div>
                  <div className="text-white font-semibold text-sm">{decision.event_name}</div>
                  <div className="text-gray-400 text-xs">{decision.forecast}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold text-purple-400">
                    {(decision.confidence * 100).toFixed(0)}% Confidence
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date(decision.followed_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DecisionCommandCenter;
