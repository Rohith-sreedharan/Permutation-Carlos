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
    ? `https://beatvegas.ai/ref/${profile.username}` 
    : 'https://beatvegas.ai/ref/yourUsername';

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

          <div className="bg-charcoal rounded-lg p-6">
            <h3 className="font-bold text-white mb-2">Your Referral Link</h3>
            <p className="text-sm text-light-gray mb-4">Share this link to earn a commission on every new subscriber!</p>
            <div className="flex items-center gap-3">
                <input type="text" readOnly value={referralLink} className="flex-1 bg-navy border border-border-gray rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-gold"/>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(referralLink);
                    alert('Link copied to clipboard!');
                  }}
                  className="bg-gold hover:bg-light-gold text-dark-navy font-semibold px-6 py-2.5 rounded-lg transition-all whitespace-nowrap"
                >
                  Copy Link
                </button>
            </div>
          </div>
          
          <div className="bg-charcoal rounded-lg p-6">
            <h3 className="font-bold text-white mb-4">Recent Referrals</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-border-gray">
                    <th className="text-left text-xs font-semibold text-light-gray uppercase tracking-wider pb-3 px-2">User</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase tracking-wider pb-3 px-2">Date Joined</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase tracking-wider pb-3 px-2">Status</th>
                    <th className="text-left text-xs font-semibold text-light-gray uppercase tracking-wider pb-3 px-2">Commission Earned</th>
                  </tr>
                </thead>
                <tbody>
                  {referrals.length > 0 ? (
                    referrals.map(ref => (
                      <tr key={ref.id} className="border-b border-border-gray hover:bg-navy/30 transition-colors">
                        <td className="py-4 px-2 text-sm font-medium text-white">{ref.user}</td>
                        <td className="py-4 px-2 text-sm text-light-gray">{ref.date_joined}</td>
                        <td className="py-4 px-2 text-sm">
                          <span className={`px-3 py-1 text-xs font-semibold rounded-full ${ref.status === 'Active' ? 'bg-neon-green/20 text-neon-green' : 'bg-bold-red/20 text-bold-red'}`}>{ref.status}</span>
                        </td>
                        <td className="py-4 px-2 text-sm font-semibold text-gold">${ref.commission.toFixed(2)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-12 text-center">
                        <div className="flex flex-col items-center justify-center">
                          <svg className="w-16 h-16 text-muted-text mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                          </svg>
                          <p className="text-muted-text text-sm font-medium">No referrals yet</p>
                          <p className="text-light-gray text-xs mt-1">Share your referral link to start earning commissions</p>
                        </div>
                      </td>
                    </tr>
                  )}
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