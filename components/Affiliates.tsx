import React, { useState, useEffect } from 'react';
import { getAffiliateStats, getRecentReferrals, getUserProfile } from '../services/api';
import type { AffiliateStat, Referral } from '../types';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

const StatCard: React.FC<{ stat: AffiliateStat }> = ({ stat }) => {
    const changeColor = stat.changeType === 'increase' ? 'text-neon-green' : 'text-bold-red';
    return (
        <div className="bg-charcoal rounded-lg p-5">
            <p className="text-sm text-light-gray">{stat.label}</p>
            <p className="text-3xl font-bold text-white font-teko mt-1">{stat.value}</p>
            <p className={`text-sm font-semibold mt-1 ${changeColor}`}>{stat.change}</p>
        </div>
    )
}

const Affiliates: React.FC = () => {
  const [stats, setStats] = useState<AffiliateStat[]>([]);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [statsData, referralsData, profileData] = await Promise.all([
          getAffiliateStats(), 
          getRecentReferrals(),
          getUserProfile().catch(() => null)
        ]);
        setStats(statsData);
        setReferrals(referralsData);
        setProfile(profileData);
        setError(null);
      } catch (err) {
        setError('Failed to fetch affiliate data.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const referralLink = profile?.username 
    ? `https://aibet.co/ref/${profile.username}` 
    : 'https://aibet.co/ref/yourUsername';

  if (error) {
    return <div className="text-center text-bold-red">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Affiliate Dashboard" />
      {loading ? <LoadingSpinner /> : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {stats.map(stat => <StatCard key={stat.label} stat={stat} />)}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-charcoal rounded-lg p-6">
                <h3 className="font-bold text-white mb-2">Your Referral Link</h3>
                <p className="text-sm text-light-gray mb-4">Share this link to earn a commission on every new subscriber!</p>
                <div className="flex items-center space-x-2">
                    <input type="text" readOnly value={referralLink} className="w-full bg-navy border-none rounded-lg px-4 py-2 text-white"/>
                    <button className="bg-electric-blue text-white font-semibold px-6 py-2 rounded-lg hover:bg-opacity-80 transition-colors">Copy Link</button>
                </div>
            </div>
          </div>
          
          <div className="bg-charcoal rounded-lg p-6">
            <h3 className="font-bold text-white mb-4">Recent Referrals</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-navy/50">
                    <th className="text-left text-xs font-semibold text-light-gray uppercase pb-3">User</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase pb-3">Date Joined</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase pb-3">Status</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase pb-3">Commission Earned</th>
                  </tr>
                </thead>
                <tbody>
                  {referrals.map(ref => (
                    <tr key={ref.id} className="border-b border-navy/50">
                      <td className="py-3 text-sm font-medium text-white">{ref.user}</td>
                      <td className="py-3 text-sm text-light-gray">{ref.date_joined}</td>
                      <td className="py-3 text-sm">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${ref.status === 'Active' ? 'bg-neon-green/20 text-neon-green' : 'bg-bold-red/20 text-bold-red'}`}>{ref.status}</span>
                      </td>
                      <td className="py-3 text-sm font-semibold text-white">${ref.commission.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Affiliates;