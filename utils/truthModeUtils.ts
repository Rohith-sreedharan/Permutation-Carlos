/**
 * Truth Mode UI Utilities
 * Helper functions for displaying Truth Mode validation results
 */

export interface TruthModeValidation {
  is_valid: boolean;
  block_reasons: string[];
  confidence_score: number;
  details: any;
}

export interface NoPlayResponse {
  status: 'NO_PLAY';
  event_id: string;
  event_name: string;
  blocked: boolean;
  block_reasons: string[];
  message: string;
  details: any;
  timestamp: string;
}

/**
 * Format block reasons for user display
 */
export const formatBlockReasons = (reasons: string[]): string => {
  const reasonMap: Record<string, string> = {
    'data_integrity_fail': 'Insufficient data quality',
    'model_validity_fail': 'Model confidence too low',
    'rcl_blocked': 'Failed reasoning validation',
    'missing_simulation': 'No simulation available',
    'insufficient_data': 'Incomplete event data',
    'injury_uncertainty': 'High injury impact uncertainty',
    'line_movement_unstable': 'Unstable betting lines',
    'low_confidence': 'Prediction confidence below threshold'
  };

  return reasons
    .map(r => reasonMap[r] || r)
    .join(' • ');
};

/**
 * Get Truth Mode badge color
 */
export const getTruthModeBadgeColor = (status: string): string => {
  switch (status) {
    case 'VALID':
      return 'bg-green-500';
    case 'NO_PLAY':
      return 'bg-red-500';
    case 'BLOCKED':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-500';
  }
};

/**
 * Get Truth Mode status icon
 */
export const getTruthModeIcon = (status: string): string => {
  switch (status) {
    case 'VALID':
      return '✓';
    case 'NO_PLAY':
      return '⊘';
    case 'BLOCKED':
      return '⚠';
    default:
      return '?';
  }
};

/**
 * Create NO PLAY card props
 */
export const createNoPlayCard = (noPlayResponse: NoPlayResponse) => {
  return {
    title: 'NO PLAY',
    subtitle: noPlayResponse.event_name,
    status: 'blocked',
    message: 'Truth Mode: Data quality or confidence issues',
    reasons: formatBlockReasons(noPlayResponse.block_reasons),
    icon: '🛡️',
    timestamp: noPlayResponse.timestamp
  };
};

/**
 * Check if pick should show NO PLAY UI
 */
export const shouldShowNoPlay = (pick: any): boolean => {
  return (
    pick?.status === 'NO_PLAY' ||
    pick?.blocked === true ||
    (pick?.block_reasons && pick.block_reasons.length > 0)
  );
};

/**
 * Get Truth Mode validation badge text
 */
export const getTruthModeBadgeText = (pick: any): string => {
  if (pick?.truth_mode_validated) {
    return 'Truth Mode ✓';
  }
  if (shouldShowNoPlay(pick)) {
    return 'NO PLAY';
  }
  return 'Validating...';
};
