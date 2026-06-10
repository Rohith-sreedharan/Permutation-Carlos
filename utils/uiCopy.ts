/**
 * Language Replacement Specification v1.0 (FROZEN)
 * Presentation-layer copy only. No logic or schema changes.
 */

export const COPY = {
  decisionEngine: 'BeatVegas Decision Engine',
  decisionDepth: 'Decision Depth',
  intelligenceCycles: 'Intelligence Cycles',
  outcomeDistribution: 'Outcome Distribution',
  outcomeDistributionChart: 'Outcome Distribution Chart',
  decisionEngineOutput: 'Decision Engine Output',
  modelConviction: 'Model Conviction',
  outcomeVariance: 'Outcome Variance',

  approvedPlay: 'Approved Play',
  officialEdge: 'Official Edge',
  approvedEdge: 'Approved Edge',

  noOfficialPlay: 'No official play',
  marketAlignedNoPlay: 'Market aligned - no play',
  informationalSignalOnly: 'Informational signal only',
  directionalLeanNotOfficial: 'Directional lean - not an official play',
  analysisAvailableNoPlay: 'Analysis available - no play released',

  poweredByCycles: (count: string) => `Powered by ${count} Intelligence Cycles`,
} as const;
