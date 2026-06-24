import { resolveGameEdgeState, canPublish } from './utils/resolveGameEdgeState';

const BASE = process.env.PARITY_BASE || 'https://beta.beatvegas.app';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODIwMzI2MzUsImV4cCI6MTc4MjExOTAzNX0.GmBaojugKYdd8RPwaZ0TQ5202AMYLPUWr2_T80I-5Ng';

type AnyObj = Record<string, any>;

function teaserClassification(dec: AnyObj): string {
  const cls: string[] = [];
  for (const k of ['spread', 'total', 'moneyline']) {
    const c = String(dec?.[k]?.classification || '').toUpperCase();
    if (c) cls.push(c);
  }
  if (cls.includes('EDGE')) return 'EDGE';
  if (cls.includes('LEAN')) return 'LEAN';
  if (cls.includes('MARKET_ALIGNED')) return 'MARKET_ALIGNED';
  if (cls.includes('BLOCKED')) return 'BLOCKED';
  return 'NO_ACTION';
}

async function api(path: string) {
  let lastErr: unknown = null;
  for (let i = 0; i < 3; i += 1) {
    try {
      const r = await fetch(`${BASE}${path}`, {
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          'Content-Type': 'application/json',
        },
      });
      if (!r.ok) throw new Error(`${path} => ${r.status}`);
      return r.json();
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr;
}

(async () => {
  const out: AnyObj[] = [];
  const eventsRaw = await api('/api/odds/list?date=2026-06-21&upcoming_only=false&limit=200');
  const events = Array.isArray(eventsRaw) ? eventsRaw : (eventsRaw.events || []);

  let totalVisible = 0;
  let edge = 0;
  let lean = 0;
  let marketAligned = 0;
  let blocked = 0;
  let opensSuccess = 0;
  let opensBlocked = 0;

  for (const ev of events) {
    const eventId = ev.event_id || ev.id;
    if (!eventId) continue;
    totalVisible += 1;
    const league = String(ev.sport_key || '').toLowerCase().includes('mlb') ? 'MLB' : 'NBA';

    let decisions: AnyObj;
    let simulation: AnyObj;

    try {
      decisions = await api(`/api/games/${league}/${eventId}/decisions`);
      simulation = await api(`/api/simulations/${eventId}`);
    } catch {
      continue;
    }

    const teaser = teaserClassification(decisions);
    if (teaser === 'EDGE') edge += 1;
    else if (teaser === 'LEAN') lean += 1;
    else if (teaser === 'MARKET_ALIGNED') marketAligned += 1;
    else if (teaser === 'BLOCKED') blocked += 1;

    const state = resolveGameEdgeState(simulation as any, eventId, ev.home_team || '', ev.away_team || '');
    const detailCanRender = !!state && canPublish(state);
    const spreadInvalid = String(simulation?.market_views?.spread?.edge_class || '').toUpperCase() === 'INVALID';
    const detailBlocked = !detailCanRender || spreadInvalid;

    const actionable = teaser === 'EDGE' || teaser === 'LEAN';
    if (actionable) {
      if (detailBlocked) opensBlocked += 1;
      else opensSuccess += 1;
    }

    out.push({
      event_id: eventId,
      teaser,
      actionable,
      detailBlocked,
      detailClassification: state?.classification || null,
      detailCanRender,
      spreadEdgeClass: simulation?.market_views?.spread?.edge_class || null,
      totalEdgeClass: simulation?.market_views?.total?.edge_class || null,
    });
  }

  const divergencePct = (opensSuccess + opensBlocked) > 0 ? (opensBlocked / (opensSuccess + opensBlocked)) * 100 : 0;
  console.log(JSON.stringify({
    totalVisible,
    edge,
    lean,
    marketAligned,
    blocked,
    opensSuccess,
    opensBlocked,
    divergencePct: Number(divergencePct.toFixed(2)),
    sample: out.slice(0, 14),
  }, null, 2));
})();
