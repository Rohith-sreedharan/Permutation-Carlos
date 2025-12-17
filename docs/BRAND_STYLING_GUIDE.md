# BEATVEGAS BRAND STYLING GUIDE

## Primary Brand Colors

### Main Brand Color Palette

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Gold** (Primary) | `#D4A64A` | rgb(212, 166, 74) | Primary brand color, CTA buttons, accents, high-value highlights |
| **Light Gold** | `#E7C776` | rgb(231, 199, 118) | Secondary gold, text highlights, hover states |
| **Dark Navy** | `#0C1018` | rgb(12, 16, 24) | Primary background |
| **Navy** | `#1A1F27` | rgb(26, 31, 39) | Cards, secondary backgrounds |
| **Charcoal** | `#343a40` | rgb(52, 58, 64) | Tertiary backgrounds, borders |

### Accent Colors

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Neon Green** | `#4CAF50` | rgb(76, 175, 80) | Success states, positive indicators, wins |
| **Vibrant Yellow** | `#FFEB3B` | rgb(255, 235, 59) | Warnings, attention grabbers |
| **Bold Red** | `#F52D2D` | rgb(245, 45, 45) | Errors, losses, critical alerts |
| **Deep Red** | `#A03333` | rgb(160, 51, 51) | Negative values, danger zones |
| **Light Red** | `#CC4A45` | rgb(204, 74, 69) | Secondary error states |

### UI Support Colors

| Color Name | Hex Code | RGB | Usage |
|------------|----------|-----|-------|
| **Off White** | `#F3F2ED` | rgb(243, 242, 237) | Primary text on dark backgrounds |
| **Light Gray** | `#adb5bd` | rgb(173, 181, 189) | Secondary text, muted content |
| **Muted Text** | `#8B97A7` | rgb(139, 151, 167) | Tertiary text, disabled states |
| **Border Gray** | `#2D3542` | rgb(45, 53, 66) | Borders, dividers |

### Legacy Aliases

| Alias | Maps To | Notes |
|-------|---------|-------|
| `electric-blue` | `#D4A64A` (Gold) | Being migrated to gold - use sparingly |

## Typography

### Fonts

```css
font-family: 'Roboto', sans-serif;  /* Primary - body text */
font-family: 'Teko', sans-serif;     /* Headers, display text */
```

### Font Weights
- **Regular**: 400 (body text)
- **Medium**: 500 (emphasis)
- **Bold**: 700 (headings, CTAs)

## Color Usage Guidelines

### Backgrounds
```css
/* Page backgrounds */
bg-dark-navy     /* #0C1018 - main page background */
bg-navy          /* #1A1F27 - cards, panels */
bg-charcoal      /* #343a40 - tertiary surfaces */

/* Gradients */
bg-gradient-to-br from-charcoal via-navy to-charcoal
bg-gradient-to-b from-navy/30 via-transparent
```

### Text
```css
/* Primary text */
text-off-white    /* #F3F2ED */

/* Secondary text */
text-light-gray   /* #adb5bd */
text-muted-text   /* #8B97A7 */

/* Accent text */
text-gold         /* #D4A64A - primary brand */
text-neon-green   /* #4CAF50 - success/positive */
text-bold-red     /* #F52D2D - errors/losses */
```

### Buttons & CTAs

```css
/* Primary CTA */
bg-gold hover:bg-light-gold text-dark-navy

/* Success */
bg-neon-green hover:bg-neon-green/90 text-dark-navy

/* Danger */
bg-bold-red hover:bg-deep-red text-off-white

/* Secondary */
bg-navy hover:bg-charcoal text-gold border border-gold
```

### Borders & Outlines
```css
border-border-gray   /* #2D3542 - standard borders */
border-gold          /* #D4A64A - highlighted borders */
border-gold/20       /* Subtle brand border */
border-neon-green    /* Success states */
border-bold-red      /* Error states */
```

## Confidence/Tier Color System

### Stability Tiers
```javascript
LOW: {
  color: '#8B4513',      // Saddle Brown
  bgColor: '#8B451320',
  borderColor: '#8B451340',
  textColor: '#D2691E'   // Chocolate
}

MEDIUM: {
  color: '#C0C0C0',      // Silver
  bgColor: '#C0C0C020',
  borderColor: '#C0C0C040',
  textColor: '#E8E8E8'   // Light Gray
}

HIGH: {
  color: '#D4A64A',      // Gold (Primary Brand)
  bgColor: '#D4A64A20',
  borderColor: '#D4A64A40',
  textColor: '#E7C776'   // Light Gold
}
```

### Subscription Tiers
```javascript
free: '#9CA3AF',    // Gray
starter: '#3B82F6', // Blue
pro: '#8B5CF6',     // Purple
elite: '#F59E0B',   // Amber/Gold
admin: '#EF4444'    // Red
```

## Animations

```javascript
shimmer: 'shimmer 2s ease-in-out infinite'
fade-in: 'fade-in 0.3s ease-out'
slide-up: 'slide-up 0.3s ease-out'
slide-in: 'slide-in 0.2s ease-out'
pulse-glow: 'pulse-glow 2s ease-in-out infinite'
```

## Component Patterns

### Card Pattern
```html
<div class="bg-navy rounded-lg border border-border-gray p-4">
  <!-- Card content -->
</div>
```

### Elevated Card
```html
<div class="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border-2 border-gold/20 shadow-xl">
  <!-- Premium content -->
</div>
```

### Status Badge
```html
<!-- Success -->
<span class="bg-neon-green/20 border border-neon-green text-neon-green px-3 py-1 rounded-full text-xs font-bold">
  WIN
</span>

<!-- Danger -->
<span class="bg-bold-red/20 border border-bold-red text-bold-red px-3 py-1 rounded-full text-xs font-bold">
  LOSS
</span>

<!-- Brand -->
<span class="bg-gold/20 border border-gold text-gold px-3 py-1 rounded-full text-xs font-bold">
  PREMIUM
</span>
```

### Command Center Style
```html
<div class="bg-gradient-to-r from-charcoal via-navy to-charcoal rounded-lg p-4 border border-gold/20 shadow-xl">
  <!-- High-tech interface elements -->
</div>
```

## Usage Examples

### Hero Section
```css
background: linear-gradient(to bottom right, #1a1f35, #0a0f1e, black);
```

### Grid Pattern Overlay
```css
background-image: 
  linear-gradient(45deg, #FFD700 1px, transparent 1px),
  linear-gradient(-45deg, #FFD700 1px, transparent 1px);
background-size: 30px 30px;
```

### Glow Effects
```css
box-shadow: 0 0 20px rgba(212, 166, 74, 0.8);  /* Gold glow */
box-shadow: 0 0 20px rgba(76, 175, 80, 0.8);   /* Green glow */
```

## Brand Voice

- **Professional yet accessible** - Sharp, data-driven analysis without jargon
- **Confident but transparent** - Show wins AND losses
- **Tech-forward** - Monte Carlo, AI, simulation language
- **Premium** - Gold accents signify value and quality

## Don'ts

❌ Don't use pure white (#FFFFFF) - use off-white (#F3F2ED)  
❌ Don't use pure black (#000000) - use dark-navy (#0C1018)  
❌ Avoid harsh contrast - use opacity for subtle effects  
❌ Don't overuse animations - keep interactions purposeful  
❌ Avoid mixing cold blues with warm golds - stick to the palette

## Quick Reference: Tailwind Classes

```css
/* Backgrounds */
bg-dark-navy bg-navy bg-charcoal

/* Brand Colors */
bg-gold text-gold border-gold

/* Status */
text-neon-green    /* Success */
text-bold-red      /* Error */
text-vibrant-yellow /* Warning */

/* Text */
text-off-white text-light-gray text-muted-text

/* Interactive */
hover:bg-gold/90
hover:border-gold
hover:shadow-lg
transition-all duration-200
```
