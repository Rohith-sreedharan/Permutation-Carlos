
import React, { useState, useEffect } from 'react';
import { getLeaderboard } from '../services/api';
import type { User } from '../types';
import LoadingSpinner from './LoadingSpinner';
import CreatorProfile from './CreatorProfile';

const Leaderboard: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCreator, setSelectedCreator] = useState<string | null>(null);

  useEffect(() => {
    const loadLeaderboard = async () => {
      try {
        setLoading(true);
        const usersData = await getLeaderboard();
        setUsers(usersData);
        setError(null);
      } catch (err) {
        setError('Failed to fetch leaderboard data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadLeaderboard();
  }, []);

  const handleTailParlay = (slipId: string) => {
    console.log('Tailing slip:', slipId);
    // TODO: Copy slip to parlay builder
    // This will be implemented in future PR
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red">{error}</div>;
  }

  if (selectedCreator) {
    return (
      <CreatorProfile 
        username={selectedCreator}
        onTailParlay={handleTailParlay}
        onBack={() => setSelectedCreator(null)}
      />
    );
  }

  const getRankColor = (rank: number) => {
    if (rank === 1) return 'text-vibrant-yellow';
    if (rank === 2) return 'text-gray-300';
    if (rank === 3) return 'text-yellow-600';
    return 'text-light-gray';
  }

  return (
    <div>
      <h1 className="text-4xl font-bold text-white font-teko mb-6">Top Predictors</h1>
      <div className="bg-charcoal rounded-lg shadow-lg overflow-hidden">
        <table className="min-w-full divide-y divide-navy">
          <thead className="bg-navy/50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-light-gray uppercase tracking-wider">Rank</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-light-gray uppercase tracking-wider">User</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-light-gray uppercase tracking-wider">Score</th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-light-gray uppercase tracking-wider">Streaks</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-navy">
            {users.map((user) => (
              <tr 
                key={user.id} 
                className="hover:bg-navy/50 cursor-pointer transition-colors"
                onClick={() => setSelectedCreator(user.username)}
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`text-lg font-bold ${getRankColor(user.rank)}`}>{user.rank}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 h-10 w-10">
                      <img className="h-10 w-10 rounded-full" src={user.avatarUrl} alt={`${user.username} avatar`} />
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-white">{user.username}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-white font-semibold">{user.score.toLocaleString()}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-neon-green font-bold">
                  🔥 {user.streaks}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Leaderboard;