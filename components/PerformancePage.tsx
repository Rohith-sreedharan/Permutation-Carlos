import React, { useEffect, useState } from 'react';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface MetricValue {
  value?: string | number;
  unit?: string;
  n?: number;
  source_table?: string;
  avg_clv?: string | number;
  beat_rate?: string | number;
}

interface BrierWindow {
  '7d': MetricValue;
  '30d': MetricValue;
  '90d': MetricValue;
}

interface HomepageSummary {
  value?: string;
  overall_win_rate?: number;
  total_graded?: number;
  n?: number;
}

interface PerformanceMetrics {
  win_rate_by_classification?: Record<string, MetricValue>;
  win_rate_by_league?: Record<string, MetricValue>;
  win_rate_by_market_type?: Record<string, MetricValue>;
  brier_score?: BrierWindow;
  log_loss?: BrierWindow;
  clv?: Record<string, { avg_clv: string | number; beat_rate: string | number; n?: number }>;
  total_decisions_graded?: { value?: number };
  homepage_summary?: HomepageSummary;
  disclosure?: string;
  powered_by?: string;
  sample_thresholds?: { N_SEGMENT_MIN: number; N_HOMEPAGE_MIN: number; N_PROMOTION_MIN: number };
}

interface PerformanceResponse {
  metrics?: PerformanceMetrics;
  response_hash?: string;
  generated_at_utc?: string;
  disclosure?: string;
  powered_by?: string;
  error?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const DISCLOSURE =
  'Past performance does not guarantee future results. BeatVegas is a sports intelligence platform — not a sportsbook.';

const POWERED_BY = 'Powered by agentic simulation';

const API_URL = '/api/phase7/performance';

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function MetricCell({ label, data }: { label: string; data?: MetricValue | null }) {
  if (!data) return null;
  const raw = data.value;
  if (raw === undefined || raw === null) return null;

  const isBuildingState =
    typeof raw === 'string' &&
    (raw.includes('Track record building') || raw.includes('Simulation intelligence'));

  return (
    <div className="bg-[#0d1526] border border-[#1e2d4a] rounded-lg p-4">
      <div className="text-xs text-gray-400 mb-1 uppercase tracking-wide">{label}</div>
      {isBuildingState ? (
        <div className="text-amber-400 text-sm italic">{raw}</div>
      ) : (
        <div className="text-white text-xl font-semibold">
          {typeof raw === 'number' ? raw.toFixed(typeof raw === 'number' && raw < 1 ? 4 : 1) : raw}
          {data.unit && <span className="text-gray-400 text-sm ml-1">{data.unit}</span>}
        </div>
      )}
      {data.n !== undefined && (
        <div className="text-gray-500 text-xs mt-1">N={data.n} — sample-gated (N≥{data.source_table === 'calibration_records' ? 50 : 50})</div>
      )}
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="text-[#c9a84c] text-sm font-semibold uppercase tracking-widest mt-8 mb-3 border-b border-[#1e2d4a] pb-2">
      {title}
    </h2>
  );
}

function BuildingBanner({ message }: { message: string }) {
  return (
    <div className="bg-[#1a2235] border border-amber-700/40 rounded-lg p-4 text-amber-300 text-sm italic">
      {message}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main PerformancePage
// ─────────────────────────────────────────────────────────────────────────────

export default function PerformancePage() {
  const [data, setData] = useState<PerformanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    fetch(API_URL)
      .then((r) => r.json())
      .then((json: PerformanceResponse) => {
        setData(json);
        setLoading(false);
      })
      .catch((e) => {
        setFetchError('Unable to load performance data. Please try again shortly.');
        setLoading(false);
      });
  }, []);

  const metrics = data?.metrics;
  const generatedAt = data?.generated_at_utc ? new Date(data.generated_at_utc).toLocaleString() : null;

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-white">
      {/* ── Sticky disclosure — visible at ALL viewports without scrolling ─────── */}
      <div
        role="complementary"
        aria-label="Performance disclosure"
        className="sticky top-0 z-50 w-full bg-[#0f1828] border-b border-[#1e2d4a] px-4 py-3"
      >
        <p className="text-amber-300 text-xs leading-snug max-w-5xl mx-auto text-center">
          {DISCLOSURE}
        </p>
      </div>

      {/* ── Page body ──────────────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold text-white tracking-tight">Intelligence Record</h1>
          <span className="bg-[#1a2a40] border border-[#2a3f60] rounded-full px-3 py-1 text-xs text-[#c9a84c] font-medium">
            {POWERED_BY}
          </span>
        </div>
        {generatedAt && (
          <div className="text-gray-500 text-xs mb-4">Last updated: {generatedAt}</div>
        )}

        {/* Response hash for auditability */}
        {data?.response_hash && (
          <div className="text-gray-600 text-xs font-mono mb-6 break-all">
            Response hash: {data.response_hash}
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex justify-center py-20">
            <div className="animate-spin w-8 h-8 border-2 border-[#c9a84c] border-t-transparent rounded-full" />
          </div>
        )}

        {/* Fetch error */}
        {fetchError && (
          <BuildingBanner message="Simulation intelligence active. Track record begins accumulating as games settle." />
        )}

        {/* Metrics */}
        {!loading && !fetchError && metrics && (
          <>
            {/* Homepage summary */}
            {metrics.homepage_summary && (
              <div className="mb-6">
                {metrics.homepage_summary.overall_win_rate !== undefined ? (
                  <div className="bg-[#0d1526] border border-[#c9a84c]/30 rounded-xl p-6 text-center">
                    <div className="text-gray-400 text-xs uppercase tracking-widest mb-1">Overall Win Rate</div>
                    <div className="text-5xl font-bold text-[#c9a84c]">
                      {metrics.homepage_summary.overall_win_rate.toFixed(1)}%
                    </div>
                    <div className="text-gray-500 text-xs mt-2">
                      {metrics.homepage_summary.total_graded?.toLocaleString()} graded decisions — sample-gated (N≥200)
                    </div>
                  </div>
                ) : (
                  <BuildingBanner message={metrics.homepage_summary.value || 'Track record building — check back soon.'} />
                )}
              </div>
            )}

            {/* Win rate by classification */}
            {metrics.win_rate_by_classification && Object.keys(metrics.win_rate_by_classification).length > 0 && (
              <>
                <SectionHeader title="Win Rate by Signal Classification" />
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-3">
                  {Object.entries(metrics.win_rate_by_classification).map(([cls, d]) => (
                    <MetricCell key={cls} label={cls} data={d} />
                  ))}
                </div>
              </>
            )}

            {/* Win rate by league */}
            {metrics.win_rate_by_league && Object.keys(metrics.win_rate_by_league).length > 0 && (
              <>
                <SectionHeader title="Win Rate by League" />
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                  {Object.entries(metrics.win_rate_by_league).map(([league, d]) => (
                    <MetricCell key={league} label={league} data={d} />
                  ))}
                </div>
              </>
            )}

            {/* Win rate by market type */}
            {metrics.win_rate_by_market_type && Object.keys(metrics.win_rate_by_market_type).length > 0 && (
              <>
                <SectionHeader title="Win Rate by Market Type" />
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                  {Object.entries(metrics.win_rate_by_market_type).map(([mt, d]) => (
                    <MetricCell key={mt} label={mt} data={d} />
                  ))}
                </div>
              </>
            )}

            {/* Brier score */}
            {metrics.brier_score && (
              <>
                <SectionHeader title="Calibration — Brier Score (lower is better)" />
                <div className="grid grid-cols-3 gap-3">
                  {(['7d', '30d', '90d'] as const).map((w) => {
                    const d = metrics.brier_score?.[w];
                    return (
                      <MetricCell key={w} label={`${w} window`} data={d ? { value: d.value, n: d.n, source_table: d.source_table } : null} />
                    );
                  })}
                </div>
              </>
            )}

            {/* Log loss */}
            {metrics.log_loss && (
              <>
                <SectionHeader title="Calibration — Log Loss (lower is better)" />
                <div className="grid grid-cols-3 gap-3">
                  {(['7d', '30d', '90d'] as const).map((w) => {
                    const d = metrics.log_loss?.[w];
                    return (
                      <MetricCell key={w} label={`${w} window`} data={d ? { value: d.value, n: d.n, source_table: d.source_table } : null} />
                    );
                  })}
                </div>
              </>
            )}

            {/* CLV */}
            {metrics.clv && Object.keys(metrics.clv).length > 0 && (
              <>
                <SectionHeader title="Closing Line Value" />
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(metrics.clv).map(([cls, d]) => {
                    const avgIsBuild = typeof d.avg_clv === 'string' && d.avg_clv.includes('Track record');
                    return (
                      <div key={cls} className="bg-[#0d1526] border border-[#1e2d4a] rounded-lg p-4">
                        <div className="text-xs text-gray-400 mb-1 uppercase tracking-wide">{cls}</div>
                        {avgIsBuild ? (
                          <div className="text-amber-400 text-sm italic">{d.avg_clv}</div>
                        ) : (
                          <>
                            <div className="text-white text-lg font-semibold">
                              Avg CLV:{' '}
                              <span className={typeof d.avg_clv === 'number' && d.avg_clv > 0 ? 'text-green-400' : 'text-red-400'}>
                                {typeof d.avg_clv === 'number' ? d.avg_clv.toFixed(4) : d.avg_clv}
                              </span>
                            </div>
                            <div className="text-white text-sm">
                              Beat rate:{' '}
                              <span className="text-[#c9a84c]">
                                {typeof d.beat_rate === 'number' ? d.beat_rate.toFixed(1) : d.beat_rate}%
                              </span>
                            </div>
                          </>
                        )}
                        {d.n !== undefined && (
                          <div className="text-gray-500 text-xs mt-1">N={d.n} — sample-gated (N≥50)</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* Total decisions */}
            {metrics.total_decisions_graded?.value !== undefined && (
              <div className="mt-6 text-center text-gray-400 text-sm">
                Total decisions graded:{' '}
                <span className="text-white font-medium">
                  {typeof metrics.total_decisions_graded.value === 'number'
                    ? metrics.total_decisions_graded.value.toLocaleString()
                    : metrics.total_decisions_graded.value}
                </span>
              </div>
            )}

            {/* Sample threshold note */}
            <div className="mt-6 bg-[#0d1526] border border-[#1e2d4a] rounded-lg p-4 text-gray-500 text-xs leading-relaxed">
              All figures above are sample-gated. A minimum of 50 graded decisions per segment is required
              before any metric is displayed. Homepage summary requires N≥200. Segments below threshold show
              &quot;Track record building — check back soon.&quot; — no estimates or projections are shown.
            </div>
          </>
        )}

        {/* Bottom disclosure — always visible */}
        <div className="mt-8 border-t border-[#1e2d4a] pt-6 text-center">
          <p className="text-gray-500 text-xs leading-relaxed max-w-2xl mx-auto">
            {DISCLOSURE}
          </p>
          <p className="text-gray-600 text-xs mt-2">{POWERED_BY}</p>
        </div>
      </div>
    </div>
  );
}
