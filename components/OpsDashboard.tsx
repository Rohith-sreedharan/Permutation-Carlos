import React, { useEffect, useMemo, useState } from 'react';
import { API_BASE_URL } from '../services/api';

interface DashboardPayload {
  agent_status_grid: Array<{
    agent_id: string;
    status: string;
    last_heartbeat_utc: string | null;
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
    fetch(`${API_BASE_URL}/api/phase8/dashboard/overview`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        setStatus(r.status);
        const bodyText = await r.text();
        if (bodyText.trim().startsWith('<')) {
          throw new Error(`HTTP ${r.status}: Received HTML instead of JSON from ${API_BASE_URL}/api/phase8/dashboard/overview`);
        }
        let json: unknown;
        try {
          json = JSON.parse(bodyText);
        } catch {
          throw new Error(`HTTP ${r.status}: Invalid JSON payload from dashboard endpoint`);
        }
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}: ${JSON.stringify(json)}`);
        }
        return json;
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
                    <div key={a.agent_id} className="grid grid-cols-1 gap-2 rounded border border-slate-700 p-3 md:grid-cols-3">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-400">Agent</p>
                        <p className="font-medium text-slate-100">{a.agent_id}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-400">Last Heartbeat</p>
                        <p className="font-mono text-xs text-slate-200">{a.last_heartbeat_utc || 'N/A'}</p>
                      </div>
                      <div className="md:text-right">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Current Status</p>
                        <p className={a.status === 'ACTIVE' ? 'font-semibold text-emerald-400' : 'font-semibold text-amber-400'}>
                          {a.status} ({a.recent_event_count})
                        </p>
                      </div>
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
