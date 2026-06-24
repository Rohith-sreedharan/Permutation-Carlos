import React, { useEffect, useState } from 'react';
import { getRecruitmentPopupStatus, dismissRecruitmentPopup } from '../services/api';

const AffiliateRecruitmentPopup: React.FC = () => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getRecruitmentPopupStatus();
        setShow(Boolean(data?.show_popup));
      } catch {
        setShow(false);
      }
    };
    load();
  }, []);

  const dismiss = async () => {
    try {
      await dismissRecruitmentPopup();
    } finally {
      setShow(false);
    }
  };

  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-charcoal border border-gold/30 rounded-xl p-6 space-y-4">
        <h3 className="text-2xl font-bold text-white font-teko">Join the Affiliate Program</h3>
        <p className="text-light-gray text-sm">
          Enjoying BeatVegas? Refer a friend and earn up to $70 per Platform subscriber. Apply to our affiliate program.
        </p>
        <div className="flex gap-3">
          <a href="/become-affiliate" className="flex-1 text-center bg-gold text-dark-navy font-semibold rounded-lg px-4 py-2">
            Learn More
          </a>
          <button onClick={dismiss} className="flex-1 bg-navy border border-border-gray rounded-lg px-4 py-2 text-white">
            Not interested
          </button>
        </div>
      </div>
    </div>
  );
};

export default AffiliateRecruitmentPopup;
