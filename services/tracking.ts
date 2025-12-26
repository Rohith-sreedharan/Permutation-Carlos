/**
 * Client-Side Event Tracking — Phase 1.2
 * 
 * Provides unified tracking interface for:
 * - Server-side propagation (Meta CAPI, TikTok Events API)
 * - Client-side pixel fallback
 * - Deduplication
 * - GTM integration
 * 
 * Usage:
 * 
 * import { trackEvent } from './services/tracking';
 * 
 * trackEvent('WaitlistSubmit', {
 *   email: 'user@example.com',
 *   source: 'landing',
 *   page_url: window.location.href
 * });
 */

// Environment config
const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

// Allowed event names (MUST match backend)
export const ALLOWED_EVENTS = [
  'WaitlistSubmit',
  'DailyPreviewViewed',
  'TelegramJoinClick',
  'ParlayUnlockAttempt',
  'SimRunComplete'
] as const;

export type EventName = typeof ALLOWED_EVENTS[number];

// Event deduplication cache (session-based)
const firedEvents = new Set<string>();

/**
 * Generate unique event ID
 */
function generateEventId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Check if event has already been fired this session
 */
function isDuplicateEvent(eventName: string, eventData: any): boolean {
  const key = `${eventName}-${JSON.stringify(eventData)}`;
  if (firedEvents.has(key)) {
    console.warn(`[Tracking] Duplicate event prevented: ${eventName}`);
    return true;
  }
  firedEvents.add(key);
  return false;
}

/**
 * Track event to server-side endpoint
 * 
 * Server will propagate to Meta CAPI, TikTok Events API, and internal analytics
 */
async function trackServerSide(
  eventName: EventName,
  eventData: Record<string, any>,
  eventId: string
): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/tracking/event`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        event_name: eventName,
        event_data: eventData,
        event_id: eventId
      })
    });

    if (!response.ok) {
      throw new Error(`Server tracking failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`[Tracking] ✓ Server-side: ${eventName} | Platforms: ${result.tracked_on.join(', ')}`);
    return true;
  } catch (error) {
    console.error(`[Tracking] ✗ Server-side failed:`, error);
    return false;
  }
}

/**
 * Track event to GTM (Google Tag Manager)
 * 
 * Fallback for client-side tracking
 */
function trackGTM(eventName: EventName, eventData: Record<string, any>, eventId: string) {
  if (typeof window !== 'undefined' && (window as any).dataLayer) {
    (window as any).dataLayer.push({
      event: eventName,
      event_id: eventId,
      ...eventData
    });
    console.log(`[Tracking] ✓ GTM: ${eventName}`);
  } else {
    console.warn(`[Tracking] GTM not loaded`);
  }
}

/**
 * Track event to Meta Pixel (client-side fallback)
 */
function trackMetaPixel(eventName: EventName, eventData: Record<string, any>) {
  if (typeof window !== 'undefined' && (window as any).fbq) {
    (window as any).fbq('track', eventName, eventData);
    console.log(`[Tracking] ✓ Meta Pixel: ${eventName}`);
  } else {
    console.warn(`[Tracking] Meta Pixel not loaded`);
  }
}

/**
 * Track event to TikTok Pixel (client-side fallback)
 */
function trackTikTokPixel(eventName: EventName, eventData: Record<string, any>) {
  if (typeof window !== 'undefined' && (window as any).ttq) {
    (window as any).ttq.track(eventName, eventData);
    console.log(`[Tracking] ✓ TikTok Pixel: ${eventName}`);
  } else {
    console.warn(`[Tracking] TikTok Pixel not loaded`);
  }
}

/**
 * Master tracking function
 * 
 * Tracks event across all platforms with deduplication
 * 
 * @param eventName - One of ALLOWED_EVENTS
 * @param eventData - Event-specific payload
 * @param options - Tracking options
 */
export async function trackEvent(
  eventName: EventName,
  eventData: Record<string, any> = {},
  options: {
    skipDeduplication?: boolean;
    serverSideOnly?: boolean;
  } = {}
) {
  // Validate event name
  if (!ALLOWED_EVENTS.includes(eventName)) {
    console.error(`[Tracking] Invalid event name: ${eventName}`);
    return;
  }

  // Check for duplicates (unless explicitly disabled)
  if (!options.skipDeduplication && isDuplicateEvent(eventName, eventData)) {
    return;
  }

  // Add page_url if not provided
  if (!eventData.page_url && typeof window !== 'undefined') {
    eventData.page_url = window.location.href;
  }

  // Generate event ID
  const eventId = generateEventId();

  // 1. Server-side tracking (preferred)
  const serverSuccess = await trackServerSide(eventName, eventData, eventId);

  // 2. Client-side fallback (if server fails or as redundancy)
  if (!options.serverSideOnly) {
    trackGTM(eventName, eventData, eventId);
    
    if (!serverSuccess) {
      // Fallback to direct pixel calls if server failed
      trackMetaPixel(eventName, eventData);
      trackTikTokPixel(eventName, eventData);
    }
  }
}

// Convenience functions for specific events

export function trackWaitlistSubmit(email: string, source: string = 'unknown') {
  return trackEvent('WaitlistSubmit', {
    email,
    source,
    page_url: window.location.href
  });
}

export function trackDailyPreviewViewed(
  gameId: string,
  sport: string,
  edgeState: string,
  confidenceBand: string
) {
  return trackEvent('DailyPreviewViewed', {
    game_id: gameId,
    sport,
    edge_state: edgeState,
    confidence_band: confidenceBand,
    page_url: window.location.href
  });
}

export function trackTelegramJoinClick(source: string = 'unknown') {
  return trackEvent('TelegramJoinClick', {
    source,
    page_url: window.location.href
  });
}

export function trackParlayUnlockAttempt(lockReason: string) {
  return trackEvent('ParlayUnlockAttempt', {
    lock_reason: lockReason,
    page_url: window.location.href
  });
}

export function trackSimRunComplete(simCount: number, marketType: string) {
  return trackEvent('SimRunComplete', {
    sim_count: simCount,
    market_type: marketType,
    page_url: window.location.href
  });
}
