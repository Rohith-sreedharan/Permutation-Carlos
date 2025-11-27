import React, { useState, useEffect, useMemo } from 'react';
import { fetchEvents, getPredictions } from '../services/api';
import type { EventWithPrediction, Prediction } from '../types';
import EventCard from './EventCard';
import EventListItem from './EventListItem';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

const sports = ['All', 'NBA', 'NFL', 'MLB', 'NHL'];
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
    try {
      if (isPolling) {
        setPolling(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const [eventsData, predictionsData] = await Promise.all([
        fetchEvents(),
        getPredictions(),
      ]);

      const predictionsMap = new Map<string, Prediction>();
      predictionsData.forEach((p) => predictionsMap.set(p.event_id, p));

      const mergedData: EventWithPrediction[] = eventsData.map((event) => ({
        ...event,
        prediction: predictionsMap.get(event.id),
      }));

      setEventsWithPredictions(mergedData);
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

  useEffect(() => {
    loadData(false);
    
    // Poll for updates every 2 minutes
    const pollingInterval = setInterval(() => {
      loadData(true);
    }, 120000);

    return () => clearInterval(pollingInterval);
  }, []);

  // Filter by date
  const filterByDate = (events: EventWithPrediction[]) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const weekEnd = new Date(today);
    weekEnd.setDate(weekEnd.getDate() + 7);

    return events.filter(event => {
      const eventDate = new Date(event.commence_time);
      
      switch (dateFilter) {
        case 'today':
          return eventDate >= today && eventDate < tomorrow;
        case 'tomorrow':
          const dayAfter = new Date(tomorrow);
          dayAfter.setDate(dayAfter.getDate() + 1);
          return eventDate >= tomorrow && eventDate < dayAfter;
        case 'this-week':
          return eventDate >= today && eventDate < weekEnd;
        case 'all':
        default:
          return true;
      }
    });
  };

  // Sort by time
  const sortByTime = (events: EventWithPrediction[]) => {
    return [...events].sort((a, b) => {
      const timeA = new Date(a.commence_time).getTime();
      const timeB = new Date(b.commence_time).getTime();
      return timeOrder === 'soonest' ? timeA - timeB : timeB - timeA;
    });
  };

  const filteredEvents = useMemo(() => {
    let filtered = eventsWithPredictions
      .filter(event => activeSport === 'All' || event.sport_key === activeSport)
      .filter(event => 
        event.home_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.away_team.toLowerCase().includes(searchQuery.toLowerCase())
      );
    
    filtered = filterByDate(filtered);
    filtered = sortByTime(filtered);
    
    return filtered;
  }, [eventsWithPredictions, activeSport, searchQuery, dateFilter, timeOrder]);

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Modern Horizontal Loading Bar */}
      {polling && (
        <div className="fixed top-0 left-0 right-0 z-50">
          <div className="h-1 bg-gradient-to-r from-electric-blue via-neon-green to-vibrant-yellow animate-[shimmer_2s_ease-in-out_infinite] bg-[length:200%_100%]"></div>
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
      <div className="bg-gradient-to-r from-charcoal via-navy to-charcoal rounded-lg p-4 border border-electric-blue/20 shadow-xl">
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
