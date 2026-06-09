import React, { useState } from 'react';
import AffiliateDisclosure from './AffiliateDisclosure';
import { submitAffiliateInterest } from '../services/api';

const BecomeAffiliatePage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [audienceDesc, setAudienceDesc] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      await submitAffiliateInterest({
        name,
        email,
        audience_desc: audienceDesc || null,
      });
      setStatus('Thanks for your interest. We review applications and reach out to selected partners.');
      setName('');
      setEmail('');
      setAudienceDesc('');
    } catch (err: any) {
      setError(err.message || 'Failed to submit application');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-darkNavy via-navy to-black text-white px-4 py-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold font-teko tracking-wide">Become a BeatVegas Affiliate</h1>
        <p className="text-light-gray">Apply to join the program. Submitting this form does not automatically enroll you.</p>

        <div className="bg-charcoal rounded-lg border border-border-gray p-4">
          <AffiliateDisclosure />
        </div>

        <form onSubmit={onSubmit} className="bg-charcoal rounded-lg border border-border-gray p-6 space-y-4">
          <div>
            <label className="block text-sm text-light-gray mb-2">Name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
              placeholder="Your full name"
            />
          </div>
          <div>
            <label className="block text-sm text-light-gray mb-2">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm text-light-gray mb-2">Audience Description</label>
            <textarea
              value={audienceDesc}
              onChange={(e) => setAudienceDesc(e.target.value)}
              rows={4}
              className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
              placeholder="Optional: tell us about your audience"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="bg-gold text-dark-navy font-semibold px-6 py-2 rounded-lg disabled:opacity-60"
          >
            {submitting ? 'Submitting...' : 'Submit Interest'}
          </button>

          {status && <p className="text-neon-green text-sm">{status}</p>}
          {error && <p className="text-bold-red text-sm">{error}</p>}
        </form>
      </div>
    </div>
  );
};

export default BecomeAffiliatePage;
