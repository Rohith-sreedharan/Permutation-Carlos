import React from 'react';
import { UPGRADE_MESSAGING, PLAN_IDS } from '../uiCopy/products';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** planId of the user's current plan */
  currentPlan: string;
  onConfirmUpgrade: () => void;
}



const UpgradeModal: React.FC<UpgradeModalProps> = ({ isOpen, onClose, currentPlan, onConfirmUpgrade }) => {
  if (!isOpen) return null;

  const copy = UPGRADE_MESSAGING.UPGRADE_MODAL;
  const isTelegramSub = currentPlan === PLAN_IDS.TELEGRAM_SYNDICATE;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-linear-to-br from-charcoal to-navy rounded-xl border-2 border-gold/30 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-light-gray/70 hover:text-white text-2xl z-10"
          aria-label="Close"
        >
          ×
        </button>

        {/* Header */}
        <div className="p-8 border-b border-gold/20">
          <h2 className="text-2xl font-bold text-white mb-3">{copy.title}</h2>
          {isTelegramSub && (
            <div className="space-y-1 text-sm text-light-gray">
              <div>
                <span className="text-light-gray/60">Current Plan: </span>
                <span className="text-white">{copy.currentPlan}</span>
              </div>
              <div>
                <span className="text-light-gray/60">Upgrade To: </span>
                <span className="text-gold font-semibold">{copy.upgradeTo}</span>
              </div>
            </div>
          )}
        </div>

        {/* Gains */}
        <div className="p-8 space-y-6">
          <div>
            <p className="text-sm font-semibold text-white mb-3 uppercase tracking-wide">What you gain</p>
            <ul className="space-y-2">
              {copy.gains.map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm text-light-gray">
                  <span className="text-neon-green mt-0.5">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Billing note */}
          <div className="bg-navy/40 rounded-lg p-4 text-xs text-light-gray/70 leading-relaxed">
            {copy.billingNote}
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-3">
            <button
              onClick={onConfirmUpgrade}
              className="w-full py-3 rounded-lg font-bold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
            >
              {copy.ctaConfirm}
            </button>
            <button
              onClick={onClose}
              className="w-full py-3 rounded-lg font-semibold border border-navy text-light-gray hover:text-white hover:border-light-gray/50 transition-all"
            >
              {copy.ctaCancel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UpgradeModal;
