import React, { useState, useEffect, useMemo } from 'react';
import { fetchEvents, fetchEventsByDateRealtime, fetchEventsFromDB, getPredictions } from '../services/api';
import type { EventWithPrediction, Prediction } from '../types';
import EventCard from './EventCard';
import EventListItem from './EventListItem';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

const sports = ['All', 'NBA', 'NCAAB', 'NFL', 'NCAAF', 'MLB', 'NHL'];

// Map friendly sport names to API sport_key values
const sportKeyMap: Record<string, string> = {
  'NBA': 'basketball_nba',
  'NCAAB': 'basketball_ncaab',
  'NFL': 'americanfootball_nfl',
  'NCAAF': 'americanfootball_ncaaf',
  'MLB': 'baseball_mlb',
  'NHL': 'icehockey_nhl',
};

type Layout = 'grid' | 'list';
type DateFilter = 'today' | 'tomorrow' | 'this-week' | 'all';
type TimeOrder = 'soonest' | 'latest';

interface DashboardProps {
  onAuthError: () => void;
  onGameClick?: (gameId: string) => void;
}

const Dashboard: React.FC<DashboardProps> = ({ onAuthError, onGameClick }) => {
  const [eventsWithPredictions, setEventsWithPredictions] = useState<EventWithPrediction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [polling, setPolling] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSport, setActiveSport] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [layout, setLayout] = useState<Layout>('grid');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all'); // Changed to 'all' by default
  const [timeOrder, setTimeOrder] = useState<TimeOrder>('soonest');

  const loadData = async (isPolling = false) => {
    console.log('[Dashboard] loadData called, isPolling:', isPolling);
    try {
      if (isPolling) {
        setPolling(true);
      } else {
        setLoading(true);
      }
      setError(null);
      // Decide sportKey for realtime calls
      const sportKey = activeSport === 'All' ? undefined : sportKeyMap[activeSport];

      // Compute EST date string for current filter
      const now = new Date();
      const todayStr = toEstDateString(now);
      const tomorrowStr = toEstDateString(new Date(now.getTime() + 24*60*60*1000));
      const targetDate = dateFilter === 'today' ? todayStr
                        : dateFilter === 'tomorrow' ? tomorrowStr
                        : undefined;

      // Use database fetch which supports all sports and EST filtering
      console.log('[Dashboard] Fetching with:', { sportKey, targetDate, activeSport, dateFilter });
      const eventsData = await fetchEventsFromDB(sportKey, targetDate, true, 200);
      console.log('[Dashboard] Fetched events:', eventsData.length);

      const predictionsData = await getPredictions();

      const predictionsMap = new Map<string, Prediction>();
      predictionsData.forEach((p) => predictionsMap.set(p.event_id, p));

      const mergedData: EventWithPrediction[] = eventsData.map((event) => ({
        ...event,
        prediction: predictionsMap.get(event.id),
      }));

      console.log('[Dashboard] Merged data:', mergedData.length);
      setEventsWithPredictions(mergedData);
    } catch (err: any) {
      console.error('[Dashboard] ERROR in loadData:', err);
      console.error('[Dashboard] Error message:', err.message);
      console.error('[Dashboard] Error stack:', err.stack);
      if (err.message.includes('No authentication token found') || err.message.includes('Session expired')) {
          onAuthError();
      } else {
          setError('Failed to fetch data. Please try again later.');
      }
      } finally {
        if (isPolling) {
          setPolling(false);
        } else {
          setLoading(false);
        }
      }
  };

  useEffect(() => {
    console.log('[Dashboard] useEffect triggered - Initial mount or deps changed:', { activeSport, dateFilter, timeOrder });
    loadData(false);
    const pollingInterval = setInterval(() => {
      loadData(true);
    }, 120000);
    return () => clearInterval(pollingInterval);
  }, [activeSport, dateFilter, timeOrder]);

  // Helper: get YYYY-MM-DD for a date in EST timezone
  const toEstDateString = (date: Date) => {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(date);
    const y = parts.find(p => p.type === 'year')?.value;
    const m = parts.find(p => p.type === 'month')?.value;
    const d = parts.find(p => p.type === 'day')?.value;
    return y && m && d ? `${y}-${m}-${d}` : '';
  };

  // Helper: event EST date from backend if available, else convert
  const eventEstDate = (iso: string, fallbackEst?: string) => {
    if (fallbackEst) return fallbackEst;
    const dt = new Date(iso);
    if (!Number.isFinite(dt.getTime())) return '';
    return toEstDateString(dt);
  };

  // Filter by date in EST (America/New_York)
  const filterByDate = (events: EventWithPrediction[]) => {
    const now = new Date();
    const todayStr = toEstDateString(now);
    const tomorrowStr = toEstDateString(new Date(now.getTime() + 24*60*60*1000));
    const weekEndStr = toEstDateString(new Date(now.getTime() + 7*24*60*60*1000));

    return events.filter(event => {
      const est = eventEstDate(event.commence_time, (event as any).local_date_est);
      if (!est) return false;
      switch (dateFilter) {
        case 'today':
          return est === todayStr;
        case 'tomorrow':
          return est === tomorrowStr;
        case 'this-week':
          return est >= todayStr && est <= weekEndStr;
        case 'all':
        default:
          return true;
      }
    });
  };

  // Sort by time
  const sortByTime = (events: EventWithPrediction[]) => {
    return [...events]
      // filter out invalid or missing dates to avoid NaN issues
      .filter(e => {
        const t = new Date(e.commence_time).getTime();
        return Number.isFinite(t);
      })
      .sort((a, b) => {
        const timeA = new Date(a.commence_time).getTime();
        const timeB = new Date(b.commence_time).getTime();
        return timeOrder === 'soonest' ? timeA - timeB : timeB - timeA;
      });
  };

  const filteredEvents = useMemo(() => {
    let filtered = eventsWithPredictions
      .filter(event => {
        if (activeSport === 'All') return true;
        const sportKey = sportKeyMap[activeSport];
        return event.sport_key === sportKey;
      })
      .filter(event => 
        event.home_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.away_team.toLowerCase().includes(searchQuery.toLowerCase())
      );
    
    // Apply date filter
    let dateFiltered = filterByDate(filtered);

    // Smart fallback: if current date filter yields no games, show all upcoming
    const usedFallback = dateFiltered.length === 0 && dateFilter !== 'all';
    if (usedFallback) {
      // Temporarily override date filter to 'all' for display
      const allUpcoming = sortByTime([...filtered]);
      // Attach a marker so UI can inform the user (via a synthetic flag)
      // We won't modify the event objects; message rendered below.
      return allUpcoming;
    }

    // Sort
    dateFiltered = sortByTime(dateFiltered);
    return dateFiltered;
  }, [eventsWithPredictions, activeSport, searchQuery, dateFilter, timeOrder]);

  // Inline note when fallback is used (Today/Tomorrow had zero)
  const showFallbackNote = useMemo(() => {
    const initial = eventsWithPredictions
      .filter(event => activeSport === 'All' || event.sport_key === sportKeyMap[activeSport])
      .filter(event => 
        event.home_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.away_team.toLowerCase().includes(searchQuery.toLowerCase())
      );
    const byDate = filterByDate(initial);
    return byDate.length === 0 && dateFilter !== 'all';
  }, [eventsWithPredictions, activeSport, searchQuery, dateFilter]);

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Modern Horizontal Loading Bar */}
      {polling && (
        <div className="fixed top-0 left-0 right-0 z-50">
          <div className="h-1 bg-linear-to-r from-electric-blue via-neon-green to-vibrant-yellow animate-[shimmer_2s_ease-in-out_infinite] bg-size-[200%_100%]"></div>
          <div className="bg-navy/98 backdrop-blur-md border-b border-electric-blue/30 px-4 py-2.5 text-center shadow-lg">
            <span className="text-sm text-neon-green font-bold animate-pulse flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Pulling latest games & odds...
            </span>
          </div>
        </div>
      )}

      <PageHeader title="AI Betting Dashboard">
        <div className="flex items-center space-x-2 bg-charcoal p-1 rounded-lg">
          {sports.map(sport => (
            <button
              key={sport}
              onClick={() => setActiveSport(sport)}
              className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-colors ${
                activeSport === sport ? 'bg-electric-blue text-white' : 'text-light-gray hover:bg-navy'
              }`}
            >
              {sport}
            </button>
          ))}
        </div>
      </PageHeader>
      
      {/* DATE & TIME SORT CONTROLS - Command Center Vibe */}
      <div className="bg-linear-to-r from-charcoal via-navy to-charcoal rounded-lg p-4 border border-electric-blue/20 shadow-xl">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
          {/* Date Filter */}
          <div className="flex items-center space-x-3">
            <span className="text-xs text-neon-green uppercase font-bold tracking-wider flex items-center gap-1">
              📅 FILTER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-electric-blue/10">
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
                      ? 'bg-electric-blue text-white shadow-lg shadow-electric-blue/50 scale-105' 
                      : 'text-light-gray hover:bg-charcoal hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-light-gray/70 ml-2">Times shown in UTC</span>
          </div>

          {/* Time Order Toggle */}
          <div className="flex items-center space-x-3">
            <span className="text-xs text-vibrant-yellow uppercase font-bold tracking-wider flex items-center gap-1">
              ⏱ ORDER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-vibrant-yellow/10">
              <button
                onClick={() => setTimeOrder('soonest')}
                className={`px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                  timeOrder === 'soonest' 
                    ? 'bg-neon-green text-navy shadow-lg shadow-neon-green/50 scale-105' 
                    : 'text-light-gray hover:bg-charcoal hover:text-white'
                }`}
              >
                ⬇ Soonest First
              </button>
              <button
                onClick={() => setTimeOrder('latest')}
                className={`px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                  timeOrder === 'latest' 
                    ? 'bg-vibrant-yellow text-navy shadow-lg shadow-vibrant-yellow/50 scale-105' 
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
            className="w-full bg-charcoal border border-navy rounded-lg px-4 py-2 text-white placeholder-light-gray focus:ring-2 focus:ring-electric-blue focus:outline-none pl-10"
          />
          <svg className="w-5 h-5 text-light-gray absolute left-3 top-1/2 -translate-y-1/2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </div>
        <div className="flex items-center space-x-2 bg-charcoal p-1 rounded-lg">
          <button onClick={() => setLayout('grid')} className={`p-2 rounded-md transition-colors ${layout === 'grid' ? 'bg-electric-blue text-white' : 'text-light-gray hover:bg-navy'}`}>
            <svg className="w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
          </button>
          <button onClick={() => setLayout('list')} className={`p-2 rounded-md transition-colors ${layout === 'list' ? 'bg-electric-blue text-white' : 'text-light-gray hover:bg-navy'}`}>
            <svg className="w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
          </button>
        </div>
      </div>

      {loading ? <LoadingSpinner/> : (
        <>
          {showFallbackNote && (
            <div className="mb-3 text-xs text-light-gray/70">
              No games for this date. Showing <span className="text-neon-green font-bold">All Upcoming</span>.
            </div>
          )}
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
                    onClick={() => onGameClick?.(event.id)}
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
    </div>
  );
};

export default Dashboard;
