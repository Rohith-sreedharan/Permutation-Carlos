import React, { useState } from 'react';
import { PlusCircle, DollarSign, TrendingUp } from 'lucide-react';
import Swal from 'sweetalert2';

interface ManualBetEntryProps {
  onBetSubmitted?: () => void;
}

const ManualBetEntry: React.FC<ManualBetEntryProps> = ({ onBetSubmitted }) => {
  const [selection, setSelection] = useState('');
  const [stake, setStake] = useState('');
  const [odds, setOdds] = useState('');
  const [sport, setSport] = useState('NBA');
  const [pickType, setPickType] = useState<'single' | 'parlay' | 'prop'>('single');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selection || !stake || !odds) {
      Swal.fire({
        icon: 'error',
        title: 'Missing Fields',
        text: 'Please fill in all required fields',
        background: '#1A1F27',
        color: '#fff'
      });
      return;
    }

    setSubmitting(true);

    try {
      const token = localStorage.getItem('authToken');
      
      const response = await fetch('http://localhost:8000/api/bets/manual', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          selection: selection.trim(),
          stake: parseFloat(stake),
          odds: parseFloat(odds),
          sport,
          pick_type: pickType
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit bet');
      }

      const data = await response.json();

      // Check for tilt warning
      if (data.tilt_detected) {
        Swal.fire({
          icon: 'warning',
          title: '🚨 Tilt Alert',
          html: `
            <div class="text-left">
              <p class="mb-2">Bet logged successfully, but we detected:</p>
              <p class="text-yellow-400 font-bold">${data.tilt_warning}</p>
              <p class="mt-3 text-sm text-gray-400">Consider taking a break before placing your next bet.</p>
            </div>
          `,
          background: '#1A1F27',
          color: '#fff',
          confirmButtonColor: '#D4A64A'
        });
      } else {
        Swal.fire({
          icon: 'success',
          title: 'Bet Tracked!',
          text: `${selection} logged successfully`,
          background: '#1A1F27',
          color: '#fff',
          timer: 2000,
          showConfirmButton: false
        });
      }

      // Reset form
      setSelection('');
      setStake('');
      setOdds('');
      
      // Callback to refresh parent
      if (onBetSubmitted) {
        onBetSubmitted();
      }

    } catch (error) {
      console.error('Submit error:', error);
      Swal.fire({
        icon: 'error',
        title: 'Submission Failed',
        text: 'Could not log bet. Please try again.',
        background: '#1A1F27',
        color: '#fff'
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-[#1A1F27] rounded-lg p-6 border border-[#D4A64A]/20">
      <div className="flex items-center gap-3 mb-4">
        <PlusCircle className="w-6 h-6 text-[#D4A64A]" />
        <h2 className="text-xl font-bold text-white">Log a Bet Manually</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Selection Input */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-1">
            Selection <span className="text-[#D4A64A]">*</span>
          </label>
          <input
            type="text"
            placeholder="e.g., Lakers -5, Over 220.5, LeBron 25+ pts"
            value={selection}
            onChange={(e) => setSelection(e.target.value)}
            className="w-full bg-[#0C1018] border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-[#D4A64A]"
          />
          <div className="text-xs text-gray-500 mt-1">
            Enter exactly as shown on your bet slip
          </div>
        </div>

        {/* Stake and Odds Row */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Stake ($) <span className="text-[#D4A64A]">*</span>
            </label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
              <input
                type="number"
                step="0.01"
                placeholder="50.00"
                value={stake}
                onChange={(e) => setStake(e.target.value)}
                className="w-full bg-[#0C1018] border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-[#D4A64A]"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              Odds <span className="text-[#D4A64A]">*</span>
            </label>
            <input
              type="number"
              step="any"
              placeholder="-110 or 1.91"
              value={odds}
              onChange={(e) => setOdds(e.target.value)}
              className="w-full bg-[#0C1018] border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-[#D4A64A]"
            />
          </div>
        </div>

        {/* Sport and Pick Type Row */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Sport</label>
            <select
              value={sport}
              onChange={(e) => setSport(e.target.value)}
              className="w-full bg-[#0C1018] border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-[#D4A64A]"
            >
              <option value="NBA">NBA</option>
              <option value="NCAAB">NCAAB</option>
              <option value="NFL">NFL</option>
              <option value="NCAAF">NCAAF</option>
              <option value="MLB">MLB</option>
              <option value="NHL">NHL</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Pick Type</label>
            <select
              value={pickType}
              onChange={(e) => setPickType(e.target.value as any)}
              className="w-full bg-[#0C1018] border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-[#D4A64A]"
            >
              <option value="single">Single</option>
              <option value="parlay">Parlay</option>
              <option value="prop">Prop Bet</option>
            </select>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-linear-to-r from-[#D4A64A] to-[#B8923D] text-white font-bold py-3 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {submitting ? (
            <>
              <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Logging Bet...
            </>
          ) : (
            <>
              <TrendingUp className="w-4 h-4" />
              Track This Bet
            </>
          )}
        </button>
      </form>

      {/* Helper Text */}
      <div className="mt-4 p-3 bg-[#0C1018] rounded-lg border border-gray-800">
        <div className="text-xs text-gray-400">
          <strong className="text-[#D4A64A]">Pro Tip:</strong> Include event IDs when possible for AI edge analysis. 
          We'll compare your picks against our model predictions.
        </div>
      </div>
    </div>
  );
};

export default ManualBetEntry;
