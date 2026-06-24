import React, { useState, useEffect, useMemo } from 'react';
import { fetchEvents, fetchEventsByDateRealtime, fetchEventsFromDB, getPredictions, fetchOpenedPicks, type OpenedPickRow } from '../services/api';
import { DASHBOARD_COPY, PLAN_IDS, PRODUCT_LIMITS, type PlanId } from '../uiCopy/products';
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
  currentPlan?: PlanId | null;
  cyclesRemaining?: number;
  tokensRemaining?: number;
  telegramConnected?: boolean;
  billingPeriodEnd?: string;
  overageCapRemaining?: number;
  onUpgradeToPlatform?: () => void;
  onJoinTelegram?: () => void;
  onGetPlatform?: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({
  onAuthError,
  onGameClick,
  currentPlan,
  cyclesRemaining,
  tokensRemaining,
  telegramConnected,
  billingPeriodEnd,
  overageCapRemaining = PRODUCT_LIMITS.PARLAY_OVERAGE_MONTHLY_CAP_USD,
  onUpgradeToPlatform,
  onJoinTelegram,
  onGetPlatform,
}) => {
  const [eventsWithPredictions, setEventsWithPredictions] = useState<EventWithPrediction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [polling, setPolling] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSport, setActiveSport] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [layout, setLayout] = useState<Layout>('grid');
  const [dateFilter, setDateFilter] = useState<DateFilter>('today');
  const [timeOrder, setTimeOrder] = useState<TimeOrder>('soonest');
  const [openedPicks, setOpenedPicks] = useState<OpenedPickRow[]>([]);
  const [weeklyOpenedRecord, setWeeklyOpenedRecord] = useState<{ wins: number; losses: number; pushes: number }>({ wins: 0, losses: 0, pushes: 0 });

  const isDetailOpenBlocked = typeof cyclesRemaining === 'number' && cyclesRemaining <= 0;

  const handleGameClick = (gameId: string) => {
    if (isDetailOpenBlocked) {
      if (onUpgradeToPlatform) {
        onUpgradeToPlatform();
        return;
      }
      window.location.href = '/upgrade?plan=platform';
      return;
    }
    onGameClick?.(gameId);
  };

  const loadData = async (isPolling = false) => {
    console.log('[Dashboard] loadData called, isPolling:', isPolling);
    try {
      const requestStart = performance.now();
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
      // upcoming_only=false so in-progress/completed games still show on the dashboard
      console.log('[Dashboard] Fetching with:', { sportKey, targetDate, activeSport, dateFilter });
      const [eventsData, predictionsData, openedPicksData] = await Promise.all([
        fetchEventsFromDB(sportKey, targetDate, false, 200),
        getPredictions(),
        fetchOpenedPicks(8).catch(() => ({ count: 0, weekly_record: { wins: 0, losses: 0, pushes: 0 }, opened_picks: [] })),
      ]);

      const elapsedMs = Math.round(performance.now() - requestStart);
      console.log('[Dashboard] Fetched events:', eventsData.length);
      console.log('[Dashboard] Data load timing (ms):', {
        elapsedMs,
        eventCount: eventsData.length,
        predictionCount: predictionsData.length,
      });

      const predictionsMap = new Map<string, Prediction>();
      predictionsData.forEach((p) => predictionsMap.set(p.event_id, p));

      const mergedData: EventWithPrediction[] = eventsData.map((event) => ({
        ...event,
        prediction: predictionsMap.get(event.id),
      }));

      setOpenedPicks(Array.isArray(openedPicksData?.opened_picks) ? openedPicksData.opened_picks : []);
      setWeeklyOpenedRecord(openedPicksData?.weekly_record || { wins: 0, losses: 0, pushes: 0 });

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

  // Load data when filters change
  useEffect(() => {
    console.log('[Dashboard] Filters changed:', { activeSport, dateFilter, timeOrder });
    loadData(false);
  }, [activeSport, dateFilter, timeOrder]);

  // Set up polling interval (runs independently of filter changes)
  useEffect(() => {
    console.log('[Dashboard] Setting up 2-minute polling interval');
    const pollingInterval = setInterval(() => {
      console.log('[Dashboard] Polling: Auto-refresh triggered');
      loadData(true);
    }, 120000); // 2 minutes = 120,000ms
    
    return () => {
      console.log('[Dashboard] Cleaning up polling interval');
      clearInterval(pollingInterval);
    };
  }, []); // Empty deps - interval runs continuously until component unmounts

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

  const edgeLeanCount = useMemo(() => {
    return filteredEvents.filter((event) => {
      const raw = String((event as any)?.classification || '').toUpperCase();
      return raw === 'EDGE' || raw === 'LEAN';
    }).length;
  }, [filteredEvents]);

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6 max-w-450 mx-auto">
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

      {/* Subscription Status Bar */}
      {currentPlan === PLAN_IDS.BEATVEGAS_PLATFORM && (
        <div className="bg-charcoal rounded-xl border border-electric-blue/30 px-5 py-4 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-xs font-bold uppercase tracking-widest text-electric-blue bg-electric-blue/10 px-3 py-1 rounded-full">
              {DASHBOARD_COPY.PLATFORM_SUBSCRIBER.planBadge}
            </span>
            <span className={`text-xs flex items-center gap-1.5 ${telegramConnected ? 'text-neon-green' : 'text-light-gray/60'}`}>
              <span className={`w-2 h-2 rounded-full ${telegramConnected ? 'bg-neon-green' : 'bg-light-gray/40'}`}></span>
              {DASHBOARD_COPY.PLATFORM_SUBSCRIBER.telegramLabel}: {telegramConnected ? 'Connected' : 'Not connected'}
            </span>
          </div>
          {cyclesRemaining !== undefined && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-light-gray/80">
                  {cyclesRemaining <= 0
                    ? <>{DASHBOARD_COPY.CYCLES_WIDGET.exhausted} · <span className="text-bold-red">{DASHBOARD_COPY.CYCLES_WIDGET.exhaustedNote}</span></>
                    : <>{DASHBOARD_COPY.CYCLES_WIDGET.normal(cyclesRemaining)}{cyclesRemaining < 10000 && <span className="ml-2 text-vibrant-yellow">{DASHBOARD_COPY.CYCLES_WIDGET.lowWarning}</span>}</>
                  }
                </span>
                {billingPeriodEnd && cyclesRemaining > 0 && (
                  <span className="text-xs text-light-gray/50">Resets {billingPeriodEnd}</span>
                )}
              </div>
              <div className="w-full bg-navy rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all ${cyclesRemaining <= 0 ? 'w-0' : cyclesRemaining < 10000 ? 'bg-vibrant-yellow' : 'bg-neon-green'}`}
                  style={{ width: `${Math.max(0, Math.min(100, (cyclesRemaining / PRODUCT_LIMITS.INTELLIGENCE_CYCLES_MONTHLY) * 100))}%` }}
                />
              </div>
            </div>
          )}
          {tokensRemaining !== undefined && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-light-gray/80">
                  {tokensRemaining <= 0
                    ? <>{DASHBOARD_COPY.TOKENS_WIDGET.exhausted} · <span className="text-bold-red">{DASHBOARD_COPY.TOKENS_WIDGET.exhaustedNote}</span> {DASHBOARD_COPY.TOKENS_WIDGET.capLabel} <span className="text-vibrant-yellow">${overageCapRemaining}</span></>
                    : <>{DASHBOARD_COPY.TOKENS_WIDGET.normal(tokensRemaining)}{tokensRemaining < 150 && <span className="ml-2 text-vibrant-yellow">{DASHBOARD_COPY.TOKENS_WIDGET.lowWarning}</span>}</>
                  }
                </span>
                {billingPeriodEnd && tokensRemaining > 0 && (
                  <span className="text-xs text-light-gray/50">Resets {billingPeriodEnd}</span>
                )}
              </div>
              <div className="w-full bg-navy rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all ${tokensRemaining <= 0 ? 'w-0' : tokensRemaining < 150 ? 'bg-vibrant-yellow' : 'bg-electric-blue'}`}
                  style={{ width: `${Math.max(0, Math.min(100, (tokensRemaining / PRODUCT_LIMITS.PARLAY_TOKENS_MONTHLY) * 100))}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE && (
        <div className="bg-charcoal rounded-xl border border-electric-blue/20 px-5 py-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-neon-green bg-neon-green/10 px-3 py-1 rounded-full">
                {DASHBOARD_COPY.TELEGRAM_SUBSCRIBER.planBadge}
              </span>
              <p className="text-xs text-light-gray/70 mt-2">
                {DASHBOARD_COPY.TELEGRAM_SUBSCRIBER.upgradeNote}{' '}
                <span className="text-white">{DASHBOARD_COPY.TELEGRAM_SUBSCRIBER.upgradePrice}</span>
              </p>
            </div>
            {onUpgradeToPlatform && (
              <button
                onClick={onUpgradeToPlatform}
                className="text-xs font-bold px-4 py-2 bg-electric-blue hover:bg-electric-blue/90 text-white rounded-lg transition-colors whitespace-nowrap"
              >
                {DASHBOARD_COPY.TELEGRAM_SUBSCRIBER.upgradeCta}
              </button>
            )}
          </div>
        </div>
      )}

      {currentPlan === null && (
        <div className="bg-charcoal rounded-xl border border-electric-blue/20 px-5 py-5 text-center space-y-4">
          <p className="text-white font-semibold text-base">{DASHBOARD_COPY.NO_SUBSCRIPTION.welcome}</p>
          <div className="flex flex-wrap justify-center gap-3">
            <button
              onClick={onJoinTelegram}
              className="text-sm font-bold px-5 py-2.5 bg-neon-green/10 hover:bg-neon-green/20 text-neon-green border border-neon-green/30 rounded-lg transition-colors"
            >
              {DASHBOARD_COPY.NO_SUBSCRIPTION.telegramCta}
            </button>
            <button
              onClick={onGetPlatform}
              className="text-sm font-bold px-5 py-2.5 bg-electric-blue hover:bg-electric-blue/90 text-white rounded-lg transition-colors"
            >
              {DASHBOARD_COPY.NO_SUBSCRIPTION.platformCta}
            </button>
          </div>
        </div>
      )}

      <PageHeader title="Sports Intelligence Command Center">
        <div className="flex items-center gap-2 bg-charcoal p-1 rounded-lg overflow-x-auto w-full sm:w-auto [&::-webkit-scrollbar]:hidden">
          {sports.map(sport => (
            <button
              key={sport}
              onClick={() => setActiveSport(sport)}
              className={`shrink-0 whitespace-nowrap px-3 sm:px-4 py-1.5 text-sm font-semibold rounded-md transition-colors ${
                activeSport === sport ? 'bg-electric-blue text-white' : 'text-light-gray hover:bg-navy'
              }`}
            >
              {sport}
            </button>
          ))}
        </div>
      </PageHeader>

      <div className="bg-charcoal rounded-xl border border-neon-green/20 px-5 py-4 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-bold text-white uppercase tracking-wide">Your Opened Picks</h3>
          <span className="text-xs text-neon-green font-semibold">
            This Week: {weeklyOpenedRecord.wins}-{weeklyOpenedRecord.losses}
            {weeklyOpenedRecord.pushes > 0 ? `-${weeklyOpenedRecord.pushes}` : ''}
          </span>
        </div>
        {openedPicks.length === 0 ? (
          <p className="text-xs text-light-gray/70">Open any EDGE or LEAN card to start tracking outcomes here.</p>
        ) : (
          <div className="space-y-2">
            {openedPicks.map((row) => {
              const outcome = row.settlement_outcome || 'PENDING';
              const outcomeClass = outcome === 'WIN'
                ? 'text-neon-green'
                : outcome === 'LOSS'
                  ? 'text-bold-red'
                  : outcome === 'PUSH'
                    ? 'text-vibrant-yellow'
                    : 'text-light-gray';
              return (
                <div key={`${row.opened_event_id || row.event_id}-${row.opened_at || ''}`} className="flex items-center justify-between gap-3 text-xs bg-navy/30 rounded px-3 py-2 border border-navy/50">
                  <span className="text-light-gray truncate">{row.event_id}</span>
                  <span className={`font-bold ${outcomeClass}`}>{outcome}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
      
      {/* DATE & TIME SORT CONTROLS - Command Center Vibe */}
      <div className="bg-linear-to-r from-charcoal via-navy to-charcoal rounded-xl p-5 border border-electric-blue/20 shadow-xl">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-5">
          {/* Date Filter */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full lg:w-auto">
            <span className="text-xs text-neon-green uppercase font-bold tracking-wider flex items-center gap-1 shrink-0">
              📅 FILTER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-electric-blue/10 overflow-x-auto [&::-webkit-scrollbar]:hidden">
              {[
                { value: 'today', label: 'Today' },
                { value: 'tomorrow', label: 'Tomorrow' },
                { value: 'this-week', label: 'This Week' },
                { value: 'all', label: 'All Upcoming' }
              ].map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setDateFilter(value as DateFilter)}
                  className={`shrink-0 whitespace-nowrap px-3 sm:px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                    dateFilter === value 
                      ? 'bg-electric-blue text-white shadow-lg shadow-electric-blue/50 scale-105' 
                      : 'text-light-gray hover:bg-charcoal hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-light-gray/70 sm:ml-2">Times shown in Eastern Time (ET)</span>
          </div>

          {/* Time Order Toggle */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full lg:w-auto">
            <span className="text-xs text-vibrant-yellow uppercase font-bold tracking-wider flex items-center gap-1 shrink-0">
              ⏱ ORDER:
            </span>
            <div className="flex items-center space-x-1 bg-navy/80 p-1 rounded-lg border border-vibrant-yellow/10 overflow-x-auto [&::-webkit-scrollbar]:hidden">
              <button
                onClick={() => setTimeOrder('soonest')}
                className={`shrink-0 whitespace-nowrap px-3 sm:px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
                  timeOrder === 'soonest' 
                    ? 'bg-neon-green text-navy shadow-lg shadow-neon-green/50 scale-105' 
                    : 'text-light-gray hover:bg-charcoal hover:text-white'
                }`}
              >
                ⬇ Soonest First
              </button>
              <button
                onClick={() => setTimeOrder('latest')}
                className={`shrink-0 whitespace-nowrap px-3 sm:px-4 py-2 text-xs font-bold rounded-md transition-all duration-200 ${
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

      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 py-2">
        <div className="relative w-full md:max-w-sm">
          <input
            type="text"
            placeholder="Search by team name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-charcoal border border-navy rounded-lg px-4 py-2.5 text-white placeholder-light-gray focus:ring-2 focus:ring-electric-blue focus:outline-none pl-10"
          />
          <svg className="w-5 h-5 text-light-gray absolute left-3 top-1/2 -translate-y-1/2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </div>
        <div className="flex items-center justify-center md:justify-start space-x-2 bg-charcoal p-1 rounded-lg w-full md:w-auto">
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
          {/* Upgrade banner — Syndicate users: Platform CTA only */}
          {currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE && (
            <div className="mb-4 flex items-center justify-between gap-3 bg-[#0a0e1a] border border-yellow-400/30 rounded-lg px-4 py-2">
              <span className="text-yellow-400 text-xs font-medium whitespace-nowrap">
                Syndicate — 10,000 cycles/month&nbsp;&nbsp;|&nbsp;&nbsp;Platform — 100,000 cycles — 10x more
              </span>
              <a
                href="https://beatvegas.app/upgrade"
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 bg-yellow-400 text-[#0a0e1a] font-bold text-xs px-3 py-1 rounded hover:bg-yellow-300 transition-colors whitespace-nowrap"
              >
                Upgrade to Platform — $97/month →
              </a>
            </div>
          )}
          {/* Upgrade banner — Preview users: both Syndicate + Platform CTAs */}
          {currentPlan !== PLAN_IDS.BEATVEGAS_PLATFORM && currentPlan !== PLAN_IDS.TELEGRAM_SYNDICATE && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 bg-[#0a0e1a] border border-yellow-400/30 rounded-lg px-4 py-2">
              <span className="text-yellow-400 text-xs font-medium">
                Intelligence Preview — 10,000 cycles&nbsp;&nbsp;|&nbsp;&nbsp;Platform — 100,000 cycles — 10x more
              </span>
              <div className="flex gap-2 shrink-0">
                <a
                  href="https://beatvegas.app/upgrade"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-transparent border border-yellow-400 text-yellow-400 font-bold text-xs px-3 py-1 rounded hover:bg-yellow-400/10 transition-colors whitespace-nowrap"
                >
                  Join Syndicate $39/month
                </a>
                <a
                  href="https://beatvegas.app/upgrade"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-yellow-400 text-[#0a0e1a] font-bold text-xs px-3 py-1 rounded hover:bg-yellow-300 transition-colors whitespace-nowrap"
                >
                  Upgrade $97/month →
                </a>
              </div>
            </div>
          )}
          {showFallbackNote && (
            <div className="mb-3 text-xs text-light-gray/70">
              No games for this date. Showing <span className="text-neon-green font-bold">All Upcoming</span>.
            </div>
          )}
          {filteredEvents.length > 0 && edgeLeanCount === 0 && (
            <div className="mb-4 rounded-lg border border-electric-blue/30 bg-electric-blue/10 px-4 py-3 text-sm text-electric-blue">
              No EDGE or LEAN opportunities in this view right now. Cards shown are informational and market-aligned.
            </div>
          )}
          {filteredEvents.length === 0 ? (
            <div className="text-center py-20 bg-charcoal rounded-xl border border-navy">
              <div className="text-6xl mb-4">🎯</div>
              <p className="text-light-gray text-xl font-semibold mb-2">No games found</p>
              <p className="text-light-gray/60 text-sm">Try adjusting your filters or check back later for upcoming games.</p>
            </div>
          ) : (
            layout === 'grid' ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
                {filteredEvents.map((event) => (
                  <EventCard 
                    key={event.id} 
                    event={event}
                    onClick={() => handleGameClick(event.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredEvents.map((event) => (
                  <EventListItem 
                    key={event.id} 
                    event={event}
                    onClick={() => handleGameClick(event.id)}
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
