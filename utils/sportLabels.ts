/**
 * Sport-Specific UI Labels
 * Returns appropriate terminology based on sport type
 * Supports: NFL, NCAA Football, NBA, NCAA Basketball, NHL, MLB
 */

export interface SportLabels {
  impactLabel: string;
  timeUnit: string;
  paceLabel: string;
  headerEmoji: string;
  headerTitle: string;
  durationLabel: string;
  physicsMinutes: string;
  physicsDistribution: string;
  physicsFatigue: string;
}

const SPORT_DISPLAY_NAMES: Record<string, string> = {
  basketball_nba: 'NBA',
  basketball_ncaab: 'NCAAB',
  americanfootball_nfl: 'NFL',
  americanfootball_ncaaf: 'NCAAF',
  icehockey_nhl: 'NHL',
  baseball_mlb: 'MLB',
};

/**
 * Normalize sport keys from either raw enum format (BASKETBALL_NBA)
 * or API format (basketball_nba) and return human-readable labels.
 */
export const getSportDisplayName = (sportKey: string): string => {
  if (!sportKey) return 'SPORT';
  const normalized = sportKey.toLowerCase();
  return SPORT_DISPLAY_NAMES[normalized] || sportKey.replace(/_/g, ' ').toUpperCase();
};

/**
 * Get sport-specific display labels
 * @param sportKey - The sport_key from the event (e.g., "americanfootball_ncaaf", "basketball_nba", "icehockey_nhl", "baseball_mlb")
 */
export const getSportLabels = (sportKey: string): SportLabels => {
  const lowerKey = sportKey?.toLowerCase() || '';
  
  // Football (NFL + NCAA Football)
  if (lowerKey.includes('football')) {
    return {
      impactLabel: 'Scoring Impact',
      timeUnit: 'quarters',
      paceLabel: 'Tempo',
      headerEmoji: '🏈',
      headerTitle: 'FIRST HALF TOTAL',
      durationLabel: '30 min (2 quarters)',
      physicsMinutes: 'Scripted Play Distribution',
      physicsDistribution: 'Fresh Players (No Fatigue)',
      physicsFatigue: 'Opening Drive Advantages',
    };
  }

  // Basketball (NBA + NCAA Basketball)
  if (lowerKey.includes('basketball')) {
    return {
      impactLabel: 'Points Impact',
      timeUnit: 'minutes',
      paceLabel: 'Pace',
      headerEmoji: '🏀',
      headerTitle: 'FIRST HALF TOTAL',
      durationLabel: '24 min (2 quarters)',
      physicsMinutes: 'Starter-Heavy Minutes Distribution',
      physicsDistribution: 'High Pace Multiplier (Early Game Tempo)',
      physicsFatigue: 'Fatigue Curve Disabled (Fresh Legs)',
    };
  }

  // Hockey (NHL)
  if (lowerKey.includes('hockey') || lowerKey.includes('nhl')) {
    return {
      impactLabel: 'Goal Impact',
      timeUnit: 'periods',
      paceLabel: 'Pace',
      headerEmoji: '🏒',
      headerTitle: 'FIRST PERIOD TOTAL',
      durationLabel: '20 min (1 period)',
      physicsMinutes: 'Line Rotation Distribution',
      physicsDistribution: 'High-Energy Opening Period',
      physicsFatigue: 'Fresh Ice Advantage',
    };
  }

  // Baseball (MLB)
  if (lowerKey.includes('baseball') || lowerKey.includes('mlb')) {
    return {
      impactLabel: 'Run Impact',
      timeUnit: 'innings',
      paceLabel: 'Scoring Pace',
      headerEmoji: '⚾',
      headerTitle: 'FIRST 5 INNINGS TOTAL',
      durationLabel: '5 innings',
      physicsMinutes: 'Starter Pitcher Dominance',
      physicsDistribution: 'Early Lineup Optimization',
      physicsFatigue: 'Fresh Bullpen Available',
    };
  }

  // Default fallback
  return {
    impactLabel: 'Impact',
    timeUnit: 'time',
    paceLabel: 'Tempo',
    headerEmoji: '🏆',
    headerTitle: 'FIRST HALF TOTAL',
    durationLabel: '1st Half',
    physicsMinutes: 'Distribution Analysis',
    physicsDistribution: 'Early Game Dynamics',
    physicsFatigue: 'Fresh Player Advantage',
  };
};

/**
 * Get sport type from sport_key
 */
export const getSportType = (sportKey: string): 'football' | 'basketball' | 'hockey' | 'baseball' | 'other' => {
  const lowerKey = sportKey?.toLowerCase() || '';
  if (lowerKey.includes('football')) return 'football';
  if (lowerKey.includes('basketball')) return 'basketball';
  if (lowerKey.includes('hockey') || lowerKey.includes('nhl')) return 'hockey';
  if (lowerKey.includes('baseball') || lowerKey.includes('mlb')) return 'baseball';
  return 'other';
};
