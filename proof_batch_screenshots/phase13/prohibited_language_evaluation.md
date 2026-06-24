# Prohibited Language Evaluation

Source raw output: [4c_prohibited_language_raw_postfix.txt](4c_prohibited_language_raw_postfix.txt)

Evaluation:

- [TermsOfService.tsx](../../components/TermsOfService.tsx): acceptable contextual/legal language. It warns against wagering and references problem gambling help. This does not read as facilitating betting.
- [ParlayBuilder.tsx](../../components/ParlayBuilder.tsx): acceptable contextual language. It refers to decision IDs and disabled probabilities/odds in the parlay builder UI, which is product terminology rather than wagering facilitation.
- [PerformanceMetrics.tsx](../../components/PerformanceMetrics.tsx): acceptable contextual language. It displays average odds as a metric, not as a call to place a wager.
- [WarRoom.tsx](../../components/WarRoom.tsx): acceptable contextual language. "Model Pick" is internal signal labeling.
- [EdgeIndicator.tsx](../../components/EdgeIndicator.tsx): acceptable contextual language. It explicitly says statistical output only and not a betting recommendation.
- [OnboardingWizard.tsx](../../components/OnboardingWizard.tsx): acceptable contextual language. It explicitly says zero betting / wagering / sportsbook framing and includes Not a Sportsbook.
- [EventListItem.tsx](../../components/EventListItem.tsx): acceptable contextual language. PICK is a signal state and not wagering instruction.
- [SocialMetaTags.tsx](../../components/SocialMetaTags.tsx): required follow-up was applied. I removed direct betting framing from the default title/description.
- [CreatorProfile.tsx](../../components/CreatorProfile.tsx): acceptable contextual language. Odds values are data display.
- [SharpsRoom.tsx](../../components/SharpsRoom.tsx): acceptable contextual language. Pick-by-pick CLV analysis is analytics copy.
- [LegalDisclaimer.tsx](../../components/LegalDisclaimer.tsx): acceptable contextual/legal language. It distinguishes decision engine outputs from sportsbook lines.
- [BettingCommandCenter.tsx](../../components/BettingCommandCenter.tsx): needs follow-up review. The component name itself is legacy, but the displayed fields are bet-centric and could still be read as betting facilitation.
- [WarRoomOverlays.tsx](../../components/WarRoomOverlays.tsx): acceptable contextual language. It states statistical output only and not a bet recommendation.
- [GameDetail.tsx](../../components/GameDetail.tsx): acceptable contextual language overall, though it still contains odds and market comparison terminology.
- [ManualBetEntry.tsx](../../components/ManualBetEntry.tsx): required follow-up was applied. The UI copy was rewritten to agentic language, but the page still uses legacy tracker fields and may warrant deeper renaming if a stricter pass is required.
- [WaitlistPage.tsx](../../components/WaitlistPage.tsx): acceptable contextual disclosure language.
- [AffiliateTrial.tsx](../../components/AffiliateTrial.tsx): acceptable contextual support language.
- [ParlayArchitect.tsx](../../components/ParlayArchitect.tsx): acceptable contextual product terminology.
- [CLVTracker.tsx](../../components/CLVTracker.tsx): acceptable analytical language.
- [DailyBestCards.tsx](../../components/DailyBestCards.tsx): acceptable metric labeling.
- [EventCard.tsx](../../components/EventCard.tsx): acceptable signal-state language.

Follow-up fixes applied in this session:
- [SocialMetaTags.tsx](../../components/SocialMetaTags.tsx)
- [CommunityEnhanced.tsx](../../components/CommunityEnhanced.tsx)
- [ManualBetEntry.tsx](../../components/ManualBetEntry.tsx)
