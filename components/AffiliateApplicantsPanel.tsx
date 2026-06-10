import React, { useEffect, useState } from 'react';
import { getAffiliateApplicants, inviteAffiliateApplicant, declineAffiliateApplicant } from '../services/api';

interface Applicant {
  interest_id: string;
  name: string;
  email: string;
  audience_desc?: string;
  status: 'PENDING' | 'INVITED' | 'DECLINED';
  submitted_at_utc: string;
}

const AffiliateApplicantsPanel: React.FC = () => {
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await getAffiliateApplicants();
      setApplicants(rows);
    } catch (err: any) {
      setError(err.message || 'Failed to load applicants');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onInvite = async (interestId: string) => {
    await inviteAffiliateApplicant(interestId, 'op_phase11');
    await load();
  };

  const onDecline = async (interestId: string) => {
    await declineAffiliateApplicant(interestId);
    await load();
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-darkNavy via-navy to-black text-white px-4 py-10">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold font-teko tracking-wide">AOS Affiliate Applicants</h1>
        <p className="text-light-gray">Operator review queue. Invite or decline each submission.</p>

        {loading && <p className="text-light-gray">Loading applicants...</p>}
        {error && <p className="text-bold-red">{error}</p>}

        {!loading && (
          <div className="bg-charcoal rounded-lg border border-border-gray overflow-hidden">
            <table className="min-w-full">
              <thead className="bg-navy/60 border-b border-border-gray">
                <tr>
                  <th className="text-left p-3 text-xs uppercase">Name</th>
                  <th className="text-left p-3 text-xs uppercase">Email</th>
                  <th className="text-left p-3 text-xs uppercase">Audience</th>
                  <th className="text-left p-3 text-xs uppercase">Status</th>
                  <th className="text-left p-3 text-xs uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {applicants.map((a) => (
                  <tr key={a.interest_id} className="border-b border-border-gray/50">
                    <td className="p-3">{a.name}</td>
                    <td className="p-3">{a.email}</td>
                    <td className="p-3 text-light-gray">{a.audience_desc || '-'}</td>
                    <td className="p-3">{a.status}</td>
                    <td className="p-3 flex gap-2">
                      <button
                        disabled={a.status !== 'PENDING'}
                        onClick={() => onInvite(a.interest_id)}
                        className="bg-neon-green/20 text-neon-green px-3 py-1 rounded disabled:opacity-40"
                      >
                        Invite
                      </button>
                      <button
                        disabled={a.status !== 'PENDING'}
                        onClick={() => onDecline(a.interest_id)}
                        className="bg-bold-red/20 text-bold-red px-3 py-1 rounded disabled:opacity-40"
                      >
                        Decline
                      </button>
                    </td>
                  </tr>
                ))}
                {applicants.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-light-gray">No submissions yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AffiliateApplicantsPanel;
