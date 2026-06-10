import React from 'react';

const AffiliateDisclosure: React.FC = () => {
  return (
    <section className="rounded-lg border border-gold/40 bg-gold/10 p-4">
      <h2 className="text-sm font-bold uppercase tracking-wide text-gold">Affiliate Disclosure</h2>
      <p className="mt-2 text-sm text-light-gray leading-relaxed">
        This page includes affiliate links. BeatVegas may earn a commission when you purchase through a referral link.
        This compensation does not change your purchase price.
      </p>
    </section>
  );
};

export default AffiliateDisclosure;
