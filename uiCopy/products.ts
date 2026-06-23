/**
 * uiCopy/products.ts
 * BeatVegas Canonical Copy & Compute Module — v2.0.1
 *
 * FROZEN SPECIFICATION. NO MODIFICATIONS WITHOUT WRITTEN OPERATOR APPROVAL.
 * All hardcoded copy, prices, limits, and token costs must be sourced from this module.
 * CI must reject any build where prohibited compliance terms appear in strings
 * exported from this file or rendered in any component.
 *
 * Supersedes: Product & Parlay Compute Spec v2.0.0
 * Version: 2.0.1 — FINAL FROZEN
 */

// ---------------------------------------------------------------------------
// PRODUCT IDENTIFIERS
// ---------------------------------------------------------------------------

export const PLAN_IDS = {
  TELEGRAM_SYNDICATE: 'telegram_syndicate',
  BEATVEGAS_PLATFORM: 'beatvegas_platform',
} as const;

export type PlanId = typeof PLAN_IDS[keyof typeof PLAN_IDS];

// ---------------------------------------------------------------------------
// PRICES
// ---------------------------------------------------------------------------

export const PRICE_DISPLAY = {
  TELEGRAM_SYNDICATE: '$39/month',
  BEATVEGAS_PLATFORM: '$97/month',
  TELEGRAM_PRICE_USD: 39,
  PLATFORM_PRICE_USD: 97,
} as const;

// ---------------------------------------------------------------------------
// PRODUCT COPY
// ---------------------------------------------------------------------------

export const PRODUCT_COPY = {
  TELEGRAM_SYNDICATE: {
    name: 'BeatVegas Telegram Syndicate',
    price: PRICE_DISPLAY.TELEGRAM_SYNDICATE,
    oneLiner: 'Official edge alerts. Real-time Telegram delivery.',
    description:
      'The BeatVegas Telegram Syndicate delivers official engine signals, daily top signals, and real-time market edge alerts directly to Telegram. No dashboard required.',
    cta: 'Join Telegram Syndicate',
    included: [
      'Official edge alerts',
      'Daily top signals',
      'Market edge notifications',
      'Real-time Telegram delivery',
    ],
    notIncluded: [
      'Decision Intelligence Engine',
      'Intelligence Cycles',
      'Parlay Architect',
      'War Room',
      'Community',
    ],
    billingNote: 'Billed monthly. Cancel anytime.',
  },
  BEATVEGAS_PLATFORM: {
    name: 'BeatVegas Platform',
    price: PRICE_DISPLAY.BEATVEGAS_PLATFORM,
    badge: 'Includes Telegram Syndicate',
    oneLiner: 'The full decision intelligence environment.',
    description:
      'BeatVegas Platform provides complete access to the Decision Intelligence Engine, 100,000 Intelligence Cycles per billing period, the Parlay Architect optimizer, War Room, Community analysis, and Telegram Syndicate — included.',
    cta: 'Get Platform Access',
    included: [
      'Decision Intelligence Engine',
      '100,000 Intelligence Cycles per billing period',
      'Full game edge analysis',
      'Parlay Architect optimizer (1,500 Parlay Tokens / period)',
      'War Room access',
      'Community discussion',
      'Telegram Syndicate — included',
    ],
    billingNote: 'Billed monthly. Cancel anytime.',
    billingNoteExtra: 'Telegram Syndicate included at no extra cost.',
  },
} as const;

// ---------------------------------------------------------------------------
// LIMITS
// ---------------------------------------------------------------------------

export const PRODUCT_LIMITS = {
  INTELLIGENCE_CYCLES_MONTHLY: 100_000,
  PARLAY_TOKENS_MONTHLY: 1_500,
  PARLAY_MAX_LEGS: 6,
  PARLAY_MIN_LEGS: 2,
  PARLAY_OVERAGE_MONTHLY_CAP_USD: 200.00,
} as const;

// ---------------------------------------------------------------------------
// INTELLIGENCE CYCLES
// ---------------------------------------------------------------------------

export const INTELLIGENCE_CYCLES = {
  MAX_PER_PERIOD: PRODUCT_LIMITS.INTELLIGENCE_CYCLES_MONTHLY,
  LOW_WARNING_THRESHOLD: 10_000,
} as const;

// ---------------------------------------------------------------------------
// PARLAY TOKEN COST SCHEDULE (v2.0.1 — operator-approved override)
// PARLAY_MAX_LEGS = 6. Prior upstream value of 8 formally superseded.
// ---------------------------------------------------------------------------

export const PARLAY_TOKEN_COST: Record<number, number> = {
  2: 10,
  3: 20,
  4: 35,
  5: 50,
  6: 70,
};

export const PARLAY_CYCLE_COST: Record<number, number> = {
  2: 200,
  3: 350,
  4: 600,
  5: 900,
  6: 1_200,
};

// ---------------------------------------------------------------------------
// PARLAY OVERAGE
// Billing model (v2.0.1):
//   overage_charge = token_shortfall × PARLAY_OVERAGE_RATE_PER_TOKEN
// Prior v1.0.0 formula (token_cost × rate) is superseded.
// ---------------------------------------------------------------------------

export const PARLAY_OVERAGE = {
  RATE_PER_10_TOKENS: 0.20,
  RATE_PER_TOKEN: 0.02,
  MONTHLY_CAP_USD: PRODUCT_LIMITS.PARLAY_OVERAGE_MONTHLY_CAP_USD,
} as const;

// ---------------------------------------------------------------------------
// PARLAY LIMITS
// ---------------------------------------------------------------------------

export const PARLAY_LIMITS = {
  MAX_LEGS: PRODUCT_LIMITS.PARLAY_MAX_LEGS,
  MIN_LEGS: PRODUCT_LIMITS.PARLAY_MIN_LEGS,
  TOKENS_PER_PERIOD: PRODUCT_LIMITS.PARLAY_TOKENS_MONTHLY,
  LOW_TOKEN_THRESHOLD: 150,
} as const;

// ---------------------------------------------------------------------------
// FEATURE GATES
// ---------------------------------------------------------------------------

export const FEATURE_GATES = {
  DECISION_ENGINE: { requiredPlan: PLAN_IDS.BEATVEGAS_PLATFORM },
  INTELLIGENCE_CYCLES: { requiredPlan: PLAN_IDS.BEATVEGAS_PLATFORM },
  PARLAY_ARCHITECT: { requiredPlan: PLAN_IDS.BEATVEGAS_PLATFORM },
  WAR_ROOM: { requiredPlan: PLAN_IDS.BEATVEGAS_PLATFORM },
  COMMUNITY: { requiredPlan: PLAN_IDS.BEATVEGAS_PLATFORM },
  TELEGRAM: {
    requiredPlan: PLAN_IDS.TELEGRAM_SYNDICATE, // included in platform too
  },
} as const;

// ---------------------------------------------------------------------------
// FEATURE DESCRIPTIONS
// ---------------------------------------------------------------------------

export const FEATURE_DESCRIPTIONS = {
  DECISION_ENGINE: {
    oneLiner: 'Engine-powered edge analysis across major sports markets.',
    full: 'The Decision Intelligence Engine processes game state, market data, and context to produce structured edge analysis. Every output is a canonical decision object — traceable, auditable, and replay-ready.',
    access: 'Platform only',
  },
  INTELLIGENCE_CYCLES: {
    oneLiner: '100,000 engine computation cycles per billing period.',
    full: 'Intelligence Cycles are the computational currency of the BeatVegas engine. Each cycle represents a complete analysis pass. Platform subscribers receive 100,000 cycles per billing period. Cycles reset each period and do not roll over.',
    access: 'Platform only',
    limit: '100,000 per billing period',
  },
  PARLAY_ARCHITECT: {
    oneLiner: 'Multi-leg decision optimizer built on engine-approved outputs.',
    full: 'The Parlay Architect assembles multi-leg decision combinations from engine-approved canonical outputs. Each run consumes Parlay Tokens (scaled to leg count) and Intelligence Cycles. Every leg traces to an approved decision object.',
    access: 'Platform only',
    tokenAlloc: '1,500 tokens per billing period',
    maxLegs: 6,
  },
  WAR_ROOM: {
    oneLiner: 'Live operational environment for decision monitoring.',
    full: 'The War Room provides real-time decision feeds, CLV tracking, market movement data, and edge distribution monitoring.',
    access: 'Platform only',
  },
  COMMUNITY: {
    oneLiner: 'Discussion environment anchored to canonical decision objects.',
    full: 'The BeatVegas Community provides discussion threads anchored to engine decisions, historical performance tracking, and daily analysis summaries.',
    access: 'Platform only',
  },
  TELEGRAM_SYNDICATE: {
    oneLiner: 'Official engine signals delivered to Telegram in real time.',
    full: 'The Telegram Syndicate delivers official edge alerts, daily top signals, and market edge notifications via Telegram. All signals originate from the Decision Intelligence Engine and carry traceable decision identifiers.',
    access: `Telegram Syndicate — ${PRICE_DISPLAY.TELEGRAM_SYNDICATE}\nBeatVegas Platform — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM} (included)`,
  },
} as const;

// ---------------------------------------------------------------------------
// UPGRADE MESSAGING
// ---------------------------------------------------------------------------

export const UPGRADE_MESSAGING = {
  TELEGRAM_TO_PLATFORM: {
    headline: "You're on Telegram Syndicate.",
    body: "Upgrade to BeatVegas Platform to access the Decision Intelligence Engine, Parlay Architect, War Room, and Community — plus keep your Telegram Syndicate access.",
    planLine: `BeatVegas Platform — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM}`,
    includedNote: 'Telegram Syndicate included',
    ctaUpgrade: 'Upgrade to Platform',
    ctaStay: 'Continue with Telegram Syndicate',
  },
  FEATURE_BRIDGES: {
    DECISION_ENGINE: {
      header: 'Decision Engine access requires Platform.',
      price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
      cta: 'Upgrade to Platform',
    },
    PARLAY_ARCHITECT: {
      header: 'Parlay Architect requires Platform access.',
      body: `Build up to 6-leg decision combinations with 1,500 Parlay Tokens per billing period.`,
      price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
      cta: 'Upgrade to Platform',
    },
    WAR_ROOM: {
      header: 'War Room requires Platform access.',
      price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
      cta: 'Upgrade to Platform',
    },
    COMMUNITY: {
      header: 'Community requires Platform access.',
      price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
      cta: 'Upgrade to Platform',
    },
  },
  NO_SUBSCRIPTION: {
    body: 'This feature requires a BeatVegas subscription.',
    telegramLine: `BeatVegas Telegram Syndicate — ${PRICE_DISPLAY.TELEGRAM_SYNDICATE}`,
    telegramSub: 'Edge alerts via Telegram. No dashboard required.',
    telegramCta: 'Join Telegram Syndicate',
    platformLine: `BeatVegas Platform — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM}`,
    platformSub: 'Full engine access. Telegram Syndicate included.',
    platformCta: 'Get Platform Access',
  },
  UPGRADE_MODAL: {
    title: 'Upgrade to BeatVegas Platform',
    currentPlan: `Telegram Syndicate — ${PRICE_DISPLAY.TELEGRAM_SYNDICATE}`,
    upgradeTo: `BeatVegas Platform — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM}`,
    gains: [
      'Decision Intelligence Engine',
      '100,000 Intelligence Cycles / billing period',
      'Parlay Architect (1,500 tokens / period, max 6 legs)',
      'War Room access',
      'Community discussion',
      'Telegram Syndicate continues uninterrupted',
    ],
    billingNote:
      'Your Telegram Syndicate subscription will be replaced. You will be billed $97/month starting today. Prorated credit applied for remaining Telegram billing period.',
    ctaConfirm: `Confirm Upgrade — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM}`,
    ctaCancel: 'Cancel',
  },
} as const;

// ---------------------------------------------------------------------------
// PAYWALL COPY
// ---------------------------------------------------------------------------

export const PAYWALL_COPY = {
  PLATFORM_REQUIRED_TELEGRAM_SUB: {
    title: 'Platform Access Required',
    body: 'This feature is available on BeatVegas Platform.',
    currentPlan: `Current plan: Telegram Syndicate (${PRICE_DISPLAY.TELEGRAM_SYNDICATE}).`,
    upgradeIncludes: [
      'Decision Intelligence Engine',
      'Intelligence Cycles',
      'Parlay Architect',
      'War Room',
      'Community',
    ],
    price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
    cta: 'Upgrade to Platform',
    ctaSecondary: 'Not now',
  },
  NO_SUBSCRIPTION: {
    title: 'Subscription Required',
    telegramLine: `BeatVegas Telegram Syndicate — ${PRICE_DISPLAY.TELEGRAM_SYNDICATE}`,
    telegramCta: 'Join Telegram Syndicate',
    platformLine: `BeatVegas Platform — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
    platformCta: 'Get Platform Access',
    learnMoreCta: 'Learn more first',
  },
  PARLAY_ARCHITECT_NO_PLATFORM: {
    title: 'Parlay Architect — Platform Only',
    body: 'Build up to 6-leg decision combinations from engine-approved outputs.',
    sub: `Available on BeatVegas Platform with 1,500 Parlay Tokens per period.`,
    price: `${PRICE_DISPLAY.BEATVEGAS_PLATFORM} — Telegram Syndicate included`,
     cta: 'Subscribe Now — $97/month',
     ctaSecondary: 'Continue Trial',
  },
} as const;

// ---------------------------------------------------------------------------
// PARLAY TOKEN GATE COPY
// These use dynamic [TOKEN] placeholders injected at render time.
// ---------------------------------------------------------------------------

export const PARLAY_GATE_COPY = {
  TOKEN_EXHAUSTED: {
    title: 'Parlay Tokens Exhausted',
    body: 'You have used all 1,500 Parlay Tokens for this billing period.',
    overageNote: `To continue, additional tokens are billed at $0.20 per 10 tokens.`,
    tokensRemaining: 0,
  },
  TOKEN_PARTIAL: {
    title: 'Additional Tokens Required',
    yourRemainingNote: (remaining: number) =>
      `Your ${remaining} remaining tokens will be used first.`,
    shortfallNote: (shortfall: number) =>
      `Only the shortfall of ${shortfall} tokens is billed.`,
  },
  OVERAGE_CAP_REACHED: {
    title: 'Monthly Overage Limit Reached',
    body: 'You have reached the $200.00 monthly overage limit for Parlay Architect. No additional overage charges can be applied this billing period.',
    resetNote: (date: string) =>
      `Parlay Architect will be available again on ${date} when your tokens reset.`,
    cta: 'View Billing Details',
    ctaSecondary: 'Return to Dashboard',
  },
  CYCLES_EXHAUSTED: {
    title: 'Intelligence Cycles Exhausted',
    body: 'You have used all 100,000 Intelligence Cycles for this period.',
    resetLabel: 'Cycles reset on:',
    cta: 'View Billing Details',
    ctaSecondary: 'Return to Dashboard',
  },
} as const;

// ---------------------------------------------------------------------------
// PRICING PAGE COPY
// ---------------------------------------------------------------------------

export const PRICING_PAGE_COPY = {
  headline: 'Two products. No ambiguity.',
  subheadline: 'Choose the access level that matches how you work.',
  tableFooter: [
    'Platform subscribers receive Telegram Syndicate access automatically.',
    'Telegram Syndicate subscribers may upgrade to Platform at any time.',
    'All prices in USD. Billed monthly.',
  ],
  comparisonRows: [
    { feature: 'Price', telegram: '$39/month', platform: '$97/month' },
    { feature: 'Telegram Syndicate', telegram: '✓', platform: '✓ Included' },
    { feature: 'Official edge alerts', telegram: '✓', platform: '✓' },
    { feature: 'Daily top signals', telegram: '✓', platform: '✓' },
    { feature: 'Market edge notifications', telegram: '✓', platform: '✓' },
    { feature: 'Real-time Telegram delivery', telegram: '✓', platform: '✓' },
    { feature: 'Decision Intelligence Engine', telegram: '—', platform: '✓' },
    { feature: 'Intelligence Cycles', telegram: '—', platform: '100,000 / period' },
    { feature: 'Full game edge analysis', telegram: '—', platform: '✓' },
    { feature: 'Parlay Architect', telegram: '—', platform: '✓' },
    { feature: 'Parlay Tokens (per period)', telegram: '—', platform: '1,500 tokens' },
    { feature: 'Max legs per run', telegram: '—', platform: '6' },
    { feature: 'War Room', telegram: '—', platform: '✓' },
    { feature: 'Community', telegram: '—', platform: '✓' },
  ],
} as const;

// ---------------------------------------------------------------------------
// DASHBOARD COPY
// ---------------------------------------------------------------------------

export const DASHBOARD_COPY = {
  PLATFORM_SUBSCRIBER: {
    planBadge: 'BeatVegas Platform',
    cyclesLabel: 'Intelligence Cycles remaining',
    tokensLabel: 'Parlay Tokens remaining',
    telegramLabel: 'Telegram',
  },
  TELEGRAM_SUBSCRIBER: {
    planBadge: 'Telegram Syndicate',
    upgradeNote: 'Add Platform access for engine analysis and Parlay Architect.',
    upgradePrice: `$97/month — Telegram included.`,
    upgradeCta: 'Upgrade to Platform',
  },
  NO_SUBSCRIPTION: {
    welcome: 'Welcome to BeatVegas.',
    telegramCta: `Join Telegram Syndicate — ${PRICE_DISPLAY.TELEGRAM_SYNDICATE}`,
    platformCta: `Get Platform Access — ${PRICE_DISPLAY.BEATVEGAS_PLATFORM}`,
  },
  CYCLES_WIDGET: {
    normal: (remaining: number) => `${remaining.toLocaleString()} / 100,000 Intelligence Cycles`,
    lowWarning: 'Cycles running low.',
    exhausted: '0 / 100,000 Intelligence Cycles',
    exhaustedNote: 'Exhausted.',
  },
  TOKENS_WIDGET: {
    normal: (remaining: number) => `${remaining.toLocaleString()} / 1,500 Parlay Tokens`,
    lowWarning: 'Tokens running low. Additional runs billed at $0.20 per 10 tokens.',
    exhausted: '0 / 1,500 Parlay Tokens',
    exhaustedNote: 'Exhausted. Additional runs: $0.20 per 10 tokens.',
    capLabel: 'Cap remaining this period:',
  },
} as const;

// ---------------------------------------------------------------------------
// PARLAY ARCHITECT PAGE COPY
// ---------------------------------------------------------------------------

export const PARLAY_ARCHITECT_COPY = {
  pageTitle: 'Parlay Architect',
  subheadline: 'Multi-leg decision optimization. Up to 6 legs.',
  legSelectLabel: 'Select legs (2–6)',
  legGuidance: 'Each optimization run consumes cycles based on leg count.',
  runPreview: {
    sufficient: {
      confirmLabel: 'Run Optimization',
    },
    partial: {
      confirmLabel: (charge: string) => `Confirm and run — ${charge}`,
    },
    zero: {
      confirmLabel: (charge: string) => `Confirm and run — ${charge}`,
    },
  },
  postRun: {
    noOverage: 'Optimization complete.',
    overageCharged: 'Optimization complete.',
  },
} as const;

// ---------------------------------------------------------------------------
// BILLING PAGE COPY
// ---------------------------------------------------------------------------

export const BILLING_PAGE_COPY = {
  pageTitle: 'Billing & Subscription',
  subheadline: 'Manage your BeatVegas subscription and billing details.',
  TELEGRAM_PLAN: {
    label: 'Current Plan',
    name: 'BeatVegas Telegram Syndicate',
    price: '$39/month',
    statusLabel: 'Status',
    included: 'Official edge alerts, daily top signals, market edge notifications, Telegram delivery',
    notIncluded: 'Decision Engine, Intelligence Cycles, Parlay Architect, War Room, Community',
    ctaUpgrade: 'Upgrade to Platform',
    ctaCancel: 'Cancel Subscription',
  },
  PLATFORM_PLAN: {
    label: 'Current Plan',
    name: 'BeatVegas Platform',
    price: '$97/month',
    statusLabel: 'Status',
    cyclesLabel: 'Intelligence Cycles',
    tokensLabel: 'Parlay Tokens',
    overageLabel: 'Overage charges',
    overageCapLabel: 'Monthly overage cap',
    capRemaining: 'Cap remaining',
    ctaHistory: 'View Payment History',
    ctaCancel: 'Cancel Subscription',
  },
  OVERAGE_TABLE: {
    headers: ['Date', 'Run type', 'Tokens billed', 'Charge'],
    totalLabel: 'Total overage this period:',
    capRemainingLabel: 'Cap remaining this period:',
  },
  CANCELLATION: {
    title: 'Cancel Subscription',
    accessNote: (date: string) => `Your access continues until: ${date}`,
    afterNote: 'After that date, access reverts to free.',
    noRefundNote: 'No refunds for partial billing periods.',
    ctaConfirm: 'Confirm Cancellation',
    ctaKeep: 'Keep Subscription',
  },
} as const;

// ---------------------------------------------------------------------------
// TELEGRAM CONNECTION PAGE COPY
// ---------------------------------------------------------------------------

export const TELEGRAM_CONNECTION_COPY = {
  NOT_CONNECTED: {
    pageTitle: 'Connect Telegram',
    subheadline: 'Your subscription includes Telegram Syndicate. Connect to receive edge alerts.',
    instructions: [
      'Open Telegram',
      'Search for @BeatVegasBot',
      'Send the command /connect',
      'Enter the verification code below',
    ],
    codeLabel: 'Your code:',
    expiryLabel: 'Expires in:',
    statusWaiting: 'Waiting for connection...',
    guideCta: 'View connection guide',
  },
  CONNECTED: {
    pageTitle: 'Telegram Connected',
    statusLabel: '✓ Connected',
    usernameLabel: 'Username:',
    connectedLabel: 'Connected:',
    receiving: [
      'Official edge alerts',
      'Daily top signals',
      'Market edge notifications',
    ],
    ctaDisconnect: 'Disconnect Telegram',
    ctaTest: 'Test Signal Delivery',
  },
} as const;

// ---------------------------------------------------------------------------
// COMPLIANCE LANGUAGE RULES
// These terms must NEVER appear in any user-facing copy exported from this
// module or rendered in any component. CI must enforce this.
// ---------------------------------------------------------------------------

export const COMPLIANCE_COPY = {
  PROHIBITED_TERMS: [
    'prediction',
    'guarantee',
    'winning picks',
    'sure bets',
    'picks',
    'tips',
    'forecast',
    'lock',
    'free money',
    'guaranteed',
  ],
  SUBSTITUTION_MAP: {
    prediction: 'signal / analysis / intelligence',
    guarantee: '(remove — no substitute)',
    'winning picks': 'edge alerts / decisions / signals',
    'sure bets': '(remove — no substitute)',
    picks: 'decisions / signals / edge alerts',
    tips: 'signals / intelligence',
    forecast: 'analysis / decision output',
    lock: '(remove — no substitute)',
    'free money': '(remove — no substitute)',
    guaranteed: '(remove — no substitute)',
  },
} as const;

// ---------------------------------------------------------------------------
// HELPER FUNCTIONS
// ---------------------------------------------------------------------------

/** Returns the token cost for a given leg count. */
export function getTokenCost(legCount: number): number {
  const cost = PARLAY_TOKEN_COST[legCount];
  if (cost === undefined) {
    throw new Error(`Invalid leg count: ${legCount}. Must be between ${PARLAY_LIMITS.MIN_LEGS} and ${PARLAY_LIMITS.MAX_LEGS}.`);
  }
  return cost;
}

/** Returns the cycle cost for a given leg count. */
export function getCycleCost(legCount: number): number {
  const cost = PARLAY_CYCLE_COST[legCount];
  if (cost === undefined) {
    throw new Error(`Invalid leg count: ${legCount}. Must be between ${PARLAY_LIMITS.MIN_LEGS} and ${PARLAY_LIMITS.MAX_LEGS}.`);
  }
  return cost;
}

export interface RunPreview {
  legCount: number;
  tokenCost: number;
  cycleCost: number;
  tokensAfter: number;
  tokenShortfall: number;
  overageCharge: number;
  overageChargeFormatted: string;
  hasOverage: boolean;
  isFullOverage: boolean;
}

/**
 * Computes pre-execution run preview per spec v2.0.1 billing model:
 *   overage_charge = token_shortfall × PARLAY_OVERAGE_RATE_PER_TOKEN
 */
export function getRunPreview(legCount: number, tokensRemaining: number): RunPreview {
  const tokenCost = getTokenCost(legCount);
  const cycleCost = getCycleCost(legCount);
  const tokenShortfall = Math.max(0, tokenCost - tokensRemaining);
  const overageCharge = tokenShortfall * PARLAY_OVERAGE.RATE_PER_TOKEN;
  const tokensAfter = Math.max(0, tokensRemaining - tokenCost);
  const hasOverage = tokenShortfall > 0;
  const isFullOverage = tokensRemaining === 0;

  return {
    legCount,
    tokenCost,
    cycleCost,
    tokensAfter,
    tokenShortfall,
    overageCharge,
    overageChargeFormatted: `$${overageCharge.toFixed(2)}`,
    hasOverage,
    isFullOverage,
  };
}

/**
 * Returns whether the user has access to a platform feature.
 * planId: the user's current plan_id value from billing_state.
 */
export function hasAccess(planId: string | null | undefined, feature: keyof typeof FEATURE_GATES): boolean {
  if (!planId) return false;
  const gate = FEATURE_GATES[feature];
  if (gate.requiredPlan === PLAN_IDS.BEATVEGAS_PLATFORM) {
    return planId === PLAN_IDS.BEATVEGAS_PLATFORM;
  }
  // TELEGRAM feature is included in both plans
  return planId === PLAN_IDS.TELEGRAM_SYNDICATE || planId === PLAN_IDS.BEATVEGAS_PLATFORM;
}

/** Returns true if the user can execute a parlay run (has platform + cycles + not at overage cap). */
export function canExecuteParlayRun(opts: {
  platformAccess: boolean;
  engineCyclesLimit: number;
  overageChargesCurrentPeriod: number;
  legCount: number;
  tokensRemaining: number;
}): { allowed: boolean; reason?: string } {
  if (!opts.platformAccess) {
    return { allowed: false, reason: 'NO_PLATFORM_ACCESS' };
  }
  if (opts.engineCyclesLimit <= 0) {
    return { allowed: false, reason: 'CYCLES_EXHAUSTED' };
  }
  const preview = getRunPreview(opts.legCount, opts.tokensRemaining);
  if (
    preview.hasOverage &&
    opts.overageChargesCurrentPeriod >= PARLAY_OVERAGE.MONTHLY_CAP_USD
  ) {
    return { allowed: false, reason: 'OVERAGE_CAP_REACHED' };
  }
  return { allowed: true };
}
