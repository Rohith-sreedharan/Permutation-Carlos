


interface ParlayCalculation {
import PageHeader from './PageHeader';
import { API_BASE_URL } from '../services/api';
import PageHeader from './PageHeader';
  combined_probability_pct: number;
  correlation_type: string;
  correlation_label: string;
  decimal_odds: number;
  ev_percent: number;
  ev_interpretation: string;
  ev_label: string;
  volatility: string;
  stake_amount?: number;
  potential_payout?: number;
  potential_profit?: number;
  leg_count: number;
  resolved_legs?: Array<{
    decision_id: string;
    snapshot_hash: string;
    canonical_state: string;
    event_id: string;
  }>;
}

interface StakeAnalysis {
  hit_probability: number;
  hit_probability_label: string;
  risk_level: string;
  ev_interpretation: string;
  context_message: string;
  payout_context: string;
  volatility_alignment: string;
}

const ParlayBuilder: React.FC = () => {
  const [decisionInput, setDecisionInput] = useState('');
  const [decisionIds, setDecisionIds] = useState<string[]>([]);
  const [stake, setStake] = useState(100);
  const [parlayCalc, setParlayCalc] = useState<ParlayCalculation | null>(null);
  const [stakeAnalysis, setStakeAnalysis] = useState<StakeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shareSuccess, setShareSuccess] = useState(false);

  const canCalculate = useMemo(() => decisionIds.length >= 2, [decisionIds.length]);

  const addDecisionId = () => {
    const value = decisionInput.trim();
    if (!value) return;
    if (decisionIds.includes(value)) {
      setDecisionInput('');
      return;
    }
    setDecisionIds([...decisionIds, value]);
    setDecisionInput('');
    setParlayCalc(null);
    setStakeAnalysis(null);
  };

  const removeDecisionId = (target: string) => {
    const next = decisionIds.filter((id) => id !== target);
    setDecisionIds(next);
    if (next.length < 2) {
      setParlayCalc(null);
      setStakeAnalysis(null);
    }
  };

  const calculateParlay = async () => {
    if (!canCalculate) return;

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(`${API_BASE_URL}/api/architect/calculate-parlay`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          decision_ids: decisionIds,
          stake_amount: stake,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || 'Failed to calculate canonical parlay');
      }

      const data: ParlayCalculation = payload;
      setParlayCalc(data);
      await analyzeStake(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to calculate canonical parlay');
      setParlayCalc(null);
      setStakeAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const analyzeStake = async (parlayData: ParlayCalculation) => {
    try {
      const token = localStorage.getItem('authToken');
      let parlayConfidence = 'MODERATE';
      if (parlayData.ev_percent < -5) {
        parlayConfidence = 'SPECULATIVE';
      } else if (parlayData.ev_percent > 5) {
        parlayConfidence = 'HIGH';
      }

      const response = await fetch(`${API_BASE_URL}/api/architect/analyze-stake`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          stake_amount: stake,
          parlay_confidence: parlayConfidence,
          parlay_risk: parlayData.volatility,
          leg_count: parlayData.leg_count,
          combined_probability: parlayData.combined_probability,
          total_odds: parlayData.decimal_odds,
          potential_payout: parlayData.potential_payout || stake * parlayData.decimal_odds,
          ev_percent: parlayData.ev_percent,
        }),
      });

      if (response.ok) {
        setStakeAnalysis(await response.json());
      }
    } catch {
      // Stake intelligence is secondary; keep parlay result if this fails.
    }
  };

  const handleShare = async () => {
    if (!parlayCalc) return;

    const legsText = (parlayCalc.resolved_legs || [])
      .map((leg, index) => `${index + 1}. ${leg.decision_id} (${leg.canonical_state})`)
      .join('\n');

    const evText =
      parlayCalc.ev_percent > 0
        ? `+${parlayCalc.ev_percent.toFixed(1)}%`
        : `${parlayCalc.ev_percent.toFixed(1)}%`;

    const shareText = [
      `Built a ${decisionIds.length}-leg canonical parlay on BeatVegas`,
      '',
      legsText,
      '',
      `Expected Value: ${evText}`,
      `Hit Probability: ${parlayCalc.combined_probability_pct.toFixed(1)}%`,
    ].join('\n');

    try {
      await navigator.clipboard.writeText(shareText);
      setShareSuccess(true);
      setTimeout(() => setShareSuccess(false), 3000);
    } catch {
      setError('Failed to copy parlay summary.');
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <PageHeader title="Canonical Parlay Builder">
        <div className="flex items-center space-x-2">
          <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-3 py-1 rounded-full">
            DECISION-ID ONLY
          </span>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-charcoal rounded-xl p-6 border border-navy space-y-4">
          <h3 className="text-xl font-bold text-white font-teko">CANONICAL LEG INPUT</h3>
          <p className="text-light-gray text-sm">
            Enter canonical decision IDs. Client-side probabilities and odds are disabled.
          </p>

          <div className="flex gap-2">
            <input
              value={decisionInput}
              onChange={(e) => setDecisionInput(e.target.value)}
              placeholder="decision_id"
              className="flex-1 bg-navy border border-navy rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addDecisionId();
                }
              }}
            />
            <button
              type="button"
              onClick={addDecisionId}
              className="px-4 py-2 bg-electric-blue text-white font-semibold rounded-lg hover:bg-electric-blue/90"
            >
              Add
            </button>
          </div>

          <div className="space-y-2 max-h-[340px] overflow-y-auto">
            {decisionIds.length === 0 ? (
              <div className="text-light-gray text-sm">No decision IDs added yet.</div>
            ) : (
              decisionIds.map((decisionId) => (
                <div key={decisionId} className="bg-navy/30 rounded-lg p-3 flex items-center justify-between">
                  <div className="text-sm text-white break-all">{decisionId}</div>
                  <button
                    onClick={() => removeDecisionId(decisionId)}
                    className="text-bold-red hover:text-white text-lg"
                  >
                    x
                  </button>
                </div>
              ))
            )}
          </div>

          <div>
            <label className="block text-light-gray text-sm mb-2">Stake Amount ($)</label>
            <input
              type="number"
              value={stake}
              onChange={(e) => setStake(parseFloat(e.target.value || '0'))}
              className="w-full bg-navy border border-navy rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
            />
          </div>

          <button
            onClick={calculateParlay}
            disabled={!canCalculate || loading}
            className="w-full bg-linear-to-r from-electric-blue to-purple-600 text-white font-bold py-3 px-6 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Calculating...' : canCalculate ? 'Calculate Canonical Parlay' : 'Add 2+ decision IDs'}
          </button>

          {error && <div className="bg-bold-red/20 border border-bold-red rounded-lg p-3 text-bold-red text-sm">{error}</div>}
        </div>

        <div className="bg-charcoal rounded-xl p-6 border border-navy space-y-4">
          <h3 className="text-xl font-bold text-white font-teko">SERVER AUTHORITY OUTPUT</h3>

          {!parlayCalc ? (
            <div className="text-light-gray text-sm">Calculated results appear here after decision_id resolution.</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-navy/50 rounded-lg p-4">
                  <div className="text-light-gray text-xs uppercase mb-1">Win Probability</div>
                  <div className="text-white font-bold text-2xl">{parlayCalc.combined_probability_pct.toFixed(1)}%</div>
                </div>
                <div className="bg-navy/50 rounded-lg p-4">
                  <div className="text-light-gray text-xs uppercase mb-1">Payout Odds</div>
                  <div className="text-white font-bold text-2xl">{parlayCalc.decimal_odds.toFixed(2)}x</div>
                </div>
                <div className="bg-navy/50 rounded-lg p-4">
                  <div className="text-light-gray text-xs uppercase mb-1">Expected Value</div>
                  <div className="text-white font-bold text-xl">{parlayCalc.ev_percent > 0 ? '+' : ''}{parlayCalc.ev_percent.toFixed(1)}%</div>
                </div>
                <div className="bg-navy/50 rounded-lg p-4">
                  <div className="text-light-gray text-xs uppercase mb-1">Volatility</div>
                  <div className="text-white font-bold text-xl">{parlayCalc.volatility}</div>
                </div>
              </div>

              <div className="bg-navy/30 rounded-lg p-4">
                <div className="text-light-gray text-xs uppercase mb-2">Resolved Legs</div>
                <div className="space-y-2">
                  {(parlayCalc.resolved_legs || []).map((leg) => (
                    <div key={leg.decision_id} className="text-sm text-white break-all">
                      {leg.decision_id} | {leg.snapshot_hash} | {leg.canonical_state}
                    </div>
                  ))}
                </div>
              </div>

              {stakeAnalysis && (
                <div className="bg-navy/30 rounded-lg p-4 space-y-2">
                  <div className="text-white font-semibold">Stake Intelligence</div>
                  <div className="text-light-gray text-sm">{stakeAnalysis.context_message}</div>
                  <div className="text-light-gray text-sm">{stakeAnalysis.payout_context}</div>
                </div>
              )}

              <button
                onClick={handleShare}
                className="w-full bg-linear-to-r from-purple-600 to-pink-600 text-white font-bold py-3 px-6 rounded-lg"
              >
                Share Summary
              </button>

              {shareSuccess && (
                <div className="bg-neon-green/20 border border-neon-green rounded-lg p-3 text-center text-neon-green text-sm">
                  Copied to clipboard.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ParlayBuilder;
