import React, { useEffect } from 'react';
import type { EventWithPrediction } from '../types';

interface SocialMetaTagsProps {
  event?: EventWithPrediction;
  pageType?: 'dashboard' | 'gameDetail' | 'community' | 'affiliates';
}

/**
 * Dynamic SEO/Meta Tags Component
 * 
 * Injects Open Graph and Twitter Card meta tags for social sharing.
 * Updates tags dynamically when user navigates to different games.
 * 
 * Usage:
 * <SocialMetaTags event={event} pageType="gameDetail" />
 */
const SocialMetaTags: React.FC<SocialMetaTagsProps> = ({ event, pageType = 'dashboard' }) => {
  useEffect(() => {
    // Default meta tags for dashboard
    let title = 'BeatVegas - AI Sports Betting Intelligence';
    let description = 'Advanced AI-powered sports betting predictions with Monte Carlo simulations, real-time odds tracking, and professional-grade analytics.';
    let image = 'https://beatvegas.ai/og-default.png'; // Placeholder - replace with your hosted image
    let url = 'https://beatvegas.ai';

    // Game-specific meta tags
    if (pageType === 'gameDetail' && event) {
      const { home_team, away_team, prediction, sport_key } = event;
      const pred = prediction;

      // Extract sport display name
      const sportMap: Record<string, string> = {
        'basketball_nba': 'NBA',
        'americanfootball_nfl': 'NFL',
        'baseball_mlb': 'MLB',
        'icehockey_nhl': 'NHL'
      };
      const sportName = sportMap[sport_key] || sport_key.toUpperCase();

      // Build title with pick details
      if (pred?.recommended_bet && typeof pred.recommended_bet === 'string') {
        title = `${sportName}: ${away_team} @ ${home_team} - ${pred.recommended_bet} | BeatVegas AI`;
      } else {
        title = `${sportName}: ${away_team} @ ${home_team} | BeatVegas AI Predictions`;
      }

      // Build description with key metrics
      const confidence = pred?.confidence ? `${(pred.confidence * 100).toFixed(0)}% confidence` : '';
      const ev = pred?.ev_percent ? `${pred.ev_percent > 0 ? '+' : ''}${pred.ev_percent.toFixed(1)}% EV` : '';
      const volatility = pred?.volatility || '';
      
      const metrics = [confidence, ev, volatility].filter(Boolean).join(' • ');
      description = `AI Prediction: ${metrics}. Monte Carlo-validated pick with real-time odds tracking and advanced analytics.`;

      // Game-specific image URL (you can generate these dynamically)
      image = `https://beatvegas.ai/og-game-${event.id}.png`;
      url = `https://beatvegas.ai/game/${event.id}`;
    }

    // Update Open Graph tags
    updateMetaTag('og:title', title);
    updateMetaTag('og:description', description);
    updateMetaTag('og:image', image);
    updateMetaTag('og:url', url);
    updateMetaTag('og:type', 'website');
    updateMetaTag('og:site_name', 'BeatVegas AI');

    // Update Twitter Card tags
    updateMetaTag('twitter:card', 'summary_large_image');
    updateMetaTag('twitter:title', title);
    updateMetaTag('twitter:description', description);
    updateMetaTag('twitter:image', image);
    updateMetaTag('twitter:site', '@BeatVegasAI'); // Replace with your Twitter handle

    // Update page title
    document.title = title;

    // Update canonical URL
    updateLinkTag('canonical', url);

  }, [event, pageType]);

  return null; // This component only manages meta tags, no UI
};

/**
 * Helper function to update or create meta tags
 */
function updateMetaTag(property: string, content: string) {
  // Check if property is OG or Twitter
  const attr = property.startsWith('og:') ? 'property' : 'name';
  
  // Find existing tag
  let tag = document.querySelector(`meta[${attr}="${property}"]`);
  
  if (!tag) {
    // Create new tag if it doesn't exist
    tag = document.createElement('meta');
    tag.setAttribute(attr, property);
    document.head.appendChild(tag);
  }
  
  // Update content
  tag.setAttribute('content', content);
}

/**
 * Helper function to update or create link tags (e.g., canonical)
 */
function updateLinkTag(rel: string, href: string) {
  let tag = document.querySelector(`link[rel="${rel}"]`);
  
  if (!tag) {
    tag = document.createElement('link');
    tag.setAttribute('rel', rel);
    document.head.appendChild(tag);
  }
  
  tag.setAttribute('href', href);
}

export default SocialMetaTags;
