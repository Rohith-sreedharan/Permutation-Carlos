import React, { useEffect, useMemo, useState } from 'react';

interface DashboardPayload {
  agent_status_grid: Array<{
    agent_id: string;
    status: string;
    recent_event_count: number;
    latest_event?: Record<string, unknown> | null;
  }>;
  sentinel_events: Array<Record<string, unknown>>;
  response_actions: Array<Record<string, unknown>>;
  recovery_actions: Array<Record<string, unknown>>;
  pending_approvals: Array<Record<string, unknown>>;
  config_viewer: {
    phase8: Record<string, unknown>;
    operator_team: string[];
  };
}

function panel(title: string, content: React.ReactNode) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-amber-300">{title}</h2>
      {content}
    </section>
  );
}

export default function OpsDashboard() {
  const [token, setToken] = useState<string>('');
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string>('');
  const [status, setStatus] = useState<number | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams(window.location.search);
    const queryToken = qs.get('operator_token');
    const storedOperator = localStorage.getItem('operatorToken') || '';
    const fallbackUser = localStorage.getItem('authToken') || '';
    const initial = queryToken || storedOperator || fallbackUser;
    if (initial) {
      setToken(initial);
      if (queryToken) {
        localStorage.setItem('operatorToken', queryToken);
      }
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    fetch('/api/phase8/dashboard/overview', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        setStatus(r.status);
        if (!r.ok) {
          const txt = await r.text();
          throw new Error(`HTTP ${r.status}: ${txt}`);
        }
        return r.json();
      })
      .then((json) => {
        setData(json as DashboardPayload);
        setError('');
      })
      .catch((e) => {
        setData(null);
        setError(String(e?.message || e));
      });
  }, [token]);

  const forbidden = status === 403;

  const tokenHint = useMemo(() => {
    if (!token) return 'No token found. Add ?operator_token=<jwt> or set localStorage.operatorToken.';
    return `Token detected (${token.slice(0, 14)}...)`;
  }, [token]);

  return (
    <div className="min-h-screen bg-[#050a14] text-slate-100 p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="rounded-xl border border-slate-700 bg-slate-950/80 p-5">
          <h1 className="text-2xl font-bold tracking-tight text-white">AOS Operator Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">Read-only operational view for all seven agents.</p>
          <p className="mt-2 text-xs text-slate-500">Route: /ops/dashboard (not linked from user navigation)</p>
          <p className="mt-2 text-xs text-amber-300">{tokenHint}</p>
        </header>

        {forbidden && (
          <div className="rounded-xl border border-red-700/50 bg-red-950/40 p-4 text-red-300">
            Forbidden: regular user JWT is not authorized for operator endpoints.
          </div>
        )}

        {!!error && !forbidden && (
          <div className="rounded-xl border border-rose-700/50 bg-rose-950/40 p-4 text-rose-300">{error}</div>
        )}

        {data && (
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {panel(
                'Agent Status Grid',
                <div className="space-y-2 text-sm">
                  {data.agent_status_grid.map((a) => (
                    <div key={a.agent_id} className="flex items-center justify-between rounded border border-slate-700 p-2">
                      <span>{a.agent_id}</span>
                      <span className={a.status === 'ACTIVE' ? 'text-emerald-400' : 'text-amber-400'}>
                        {a.status} ({a.recent_event_count})
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {panel(
                'Pending Approvals',
                <pre className="max-h-72 overflow-auto text-xs text-slate-300">{JSON.stringify(data.pending_approvals, null, 2)}</pre>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              {panel('Sentinel Events (Last 50)', <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(data.sentinel_events, null, 2)}</pre>)}
              {panel('Response Actions (Last 20)', <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(data.response_actions, null, 2)}</pre>)}
              {panel('Recovery Actions (Last 20)', <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(data.recovery_actions, null, 2)}</pre>)}
            </div>

            {panel('Config Viewer (Read-only)', <pre className="max-h-96 overflow-auto text-xs">{JSON.stringify(data.config_viewer, null, 2)}</pre>)}
          </>
        )}
      </div>
    </div>
  );
}
