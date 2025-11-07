
import React, { useState, useEffect, useMemo } from 'react';
import { fetchEvents, getPredictions } from '../services/api';
import type { EventWithPrediction, Prediction } from '../types';
import EventCard from './EventCard';
import EventListItem from './EventListItem';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

const sports = ['All', 'NBA', 'NFL', 'MLB'];
type Layout = 'grid' | 'list';

interface DashboardProps {
  onAuthError: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({ onAuthError }) => {
  const [eventsWithPredictions, setEventsWithPredictions] = useState<EventWithPrediction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSport, setActiveSport] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [layout, setLayout] = useState<Layout>('grid');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
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
        setLoading(false);
      }
    };

    loadData();
  }, [onAuthError]);

  const filteredEvents = useMemo(() => {
    return eventsWithPredictions
      .filter(event => activeSport === 'All' || event.sport_key === activeSport)
      .filter(event => 
        event.home_team.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.away_team.toLowerCase().includes(searchQuery.toLowerCase())
      );
  }, [eventsWithPredictions, activeSport, searchQuery]);

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  return (
    <div className="space-y-6">
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
        layout === 'grid' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredEvents.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {filteredEvents.map((event) => (
              <EventListItem key={event.id} event={event} />
            ))}
          </div>
        )
      )}
    </div>
  );
};

export default Dashboard;
