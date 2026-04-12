import type { EventWithPrediction } from '../types';
import { normalizeTeamAliasesInText } from './matchupLabel';

export const CANONICAL_PROP_LABEL = 'MODEL MISPRICING — INFORMATIONAL ONLY';

export const getCanonicalPropHeadline = (event: EventWithPrediction): string => {
  const fromTopPropBet = normalizeTeamAliasesInText(event.top_prop_bet);
  if (fromTopPropBet) {
    return fromTopPropBet;
  }

  const structured = event.top_prop_mispricings?.[0];
  if (structured) {
    const hasLine = Number.isFinite(structured.line);
    const lineText = hasLine ? ` @ ${structured.line}` : '';
    return `${structured.player_name} - ${structured.market}${lineText}`;
  }

  return 'No prop analysis available';
};
