type MatchupTeams = {
  away_team?: string | null;
  home_team?: string | null;
};

const TEAM_DISPLAY_ALIASES: Record<string, string> = {
  'Utah Mammoth': 'Utah Hockey Club',
};

export const getDisplayTeamName = (rawName?: string | null): string => {
  const cleaned = (rawName || '').trim();
  if (!cleaned) return '';
  return TEAM_DISPLAY_ALIASES[cleaned] || cleaned;
};

export const normalizeTeamAliasesInText = (rawText?: string | null): string => {
  const value = (rawText || '').trim();
  if (!value) return '';

  let normalized = value;
  for (const [source, target] of Object.entries(TEAM_DISPLAY_ALIASES)) {
    normalized = normalized.replaceAll(source, target);
  }
  return normalized;
};

/**
 * Canonical matchup display used across card and detail surfaces.
 * Always renders Away @ Home when both teams are available.
 */
export const formatAwayAtHome = (teams: MatchupTeams): string => {
  const away = getDisplayTeamName(teams.away_team);
  const home = getDisplayTeamName(teams.home_team);

  if (away && home) {
    return `${away} @ ${home}`;
  }

  if (away) {
    return away;
  }

  if (home) {
    return home;
  }

  return 'TBD @ TBD';
};
