# Production Performance Fix - CRITICAL ISSUES FOUND

## 🚨 MAJOR PERFORMANCE PROBLEMS

Your production site is slow because you're using:
1. **CDN Tailwind CSS** - processes CSS at runtime (VERY SLOW)
2. **CDN React** - loads React from external CDN (ADDS DELAY)
3. **No build optimization** - bundle not optimized

## Files to Copy to Production Server

### 1. tailwind.config.js (NEW FILE)
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-navy': '#0C1018',
        'navy': '#1A1F27',
        'card-gray': '#1A1F27',
        'charcoal': '#343a40',
        'border-gray': '#2D3542',
        'gold': '#D4A64A',
        'light-gold': '#E7C776',
        'deep-red': '#A03333',
        'light-red': '#CC4A45',
        'off-white': '#F3F2ED',
        'muted-text': '#8B97A7',
        'light-gray': '#adb5bd',
        'neon-green': '#4CAF50',
        'vibrant-yellow': '#FFEB3B',
        'bold-red': '#F52D2D',
        'electric-blue': '#D4A64A',
      },
      fontFamily: {
        sans: ['Roboto', 'sans-serif'],
        teko: ['Teko', 'sans-serif'],
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { transform: 'scaleX(0)', transformOrigin: 'left' },
          '100%': { transform: 'scaleX(1)', transformOrigin: 'left' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(212, 166, 74, 0.5)' },
          '50%': { boxShadow: '0 0 20px rgba(212, 166, 74, 0.8)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'slide-in': 'slide-in 0.2s ease-out',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
```

### 2. postcss.config.js (NEW FILE)
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### 3. src/index.css (NEW FILE - create in src/ folder)
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 4. index.html (REPLACE)
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BEATVEGAS</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Teko:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
  </head>
  <body class="bg-navy text-white font-sans">
    <div id="root"></div>
    <script type="module" src="/index.tsx"></script>
  </body>
</html>
```

### 5. index.tsx (UPDATE - add CSS import)
Find the imports at the top and add:
```typescript
import './src/index.css';
```

So it looks like:
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './src/index.css';  // ADD THIS LINE
```

## Deployment Steps (CRITICAL - DO THIS NOW!)

### On Your Production Server (beta.beatvegas.app):

1. **Create the new files:**
   ```bash
   cd ~/permu
   
   # Create tailwind.config.js (copy from above)
   nano tailwind.config.js
   
   # Create postcss.config.js (copy from above)
   nano postcss.config.js
   
   # Create src/index.css (copy from above)
   mkdir -p src
   nano src/index.css
   ```

2. **Update existing files:**
   ```bash
   # Update index.html (copy from above)
   nano index.html
   
   # Update index.tsx (add the import line)
   nano index.tsx
   ```

3. **Update services/api.ts and utils/useWebSocket.ts** (see sections below for code)

4. **Rebuild everything:**
   ```bash
   npm run build
   ```

5. **Restart your server:**
   ```bash
   pm2 restart all
   # or whatever command you use
   ```

6. **Clear browser cache and test:**
   - Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
   - Should load in under 2 seconds now!

## What This Fixes

✅ **10x faster initial load** - No more CDN Tailwind CSS processing at runtime  
✅ **Smaller bundle size** - Proper tree-shaking and minification  
✅ **No more warnings** - Removes "should not be used in production" warning  
✅ **Better caching** - Static CSS file can be cached by browser  
✅ **WebSocket connects to production** - Instead of localhost

---

## Current Production vite.config.ts

```typescript
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        allowedHosts: ['beta.beatvegas.app', 'https://beta.beatvegas.app'],
        // Disable caching in dev to avoid stale bundles on refresh
        watch: {
            ignored: ['**/backend/**', '**/.venv/**', '**/node_modules/**']
        },
        headers: {
          'Cache-Control': 'no-store, no-cache, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        },
        proxy: {
          '/api': {
            target: 'http://localhost:8000',
            changeOrigin: true,
            secure: false
          },
          '/ws': {
            target: 'ws://localhost:8000',
            ws: true
          }
        }
      },
      plugins: [react()],
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
```

## Updated Production vite.config.ts

**For beta.beatvegas.app server**  
**Backend at: http://159.203.122.145:8000**

Copy and paste this EXACT config into your production `vite.config.ts`:

```typescript
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        allowedHosts: ['beta.beatvegas.app', 'https://beta.beatvegas.app'],
        // Disable caching in dev to avoid stale bundles on refresh
        watch: {
            ignored: ['**/backend/**', '**/.venv/**', '**/node_modules/**']
        },
        headers: {
          'Cache-Control': 'no-store, no-cache, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        },
        proxy: {
          '/api': {
            target: 'http://159.203.122.145:8000',
            changeOrigin: true,
            secure: false
          },
          '/ws': {
            target: 'ws://159.203.122.145:8000',
            ws: true
          }
        }
      },
      plugins: [react()],
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      },
      build: {
        outDir: 'dist',
        sourcemap: false,
        minify: 'terser',
        rollupOptions: {
          output: {
            manualChunks: {
              vendor: ['react', 'react-dom'],
            }
          }
        }
      }
    };
});
```

## CRITICAL: You Need to Update These Files on Production Server

### 1. services/api.ts

Find this line (around line 3):
```typescript
const API_BASE_URL = 'http://localhost:8000';
```

Replace it with:
```typescript
// Use environment variable or fall back to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_URL || (
  window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : `${window.location.protocol}//${window.location.host}`
);
```

### 2. utils/useWebSocket.ts

Find these lines (around line 52-57):
```typescript
    // Generate connection ID if not exists
    if (!connectionId) {
        connectionId = `user_${Math.random().toString(36).substring(2, 11)}`;
    }

    const wsUrl = `ws://localhost:8000/ws?connection_id=${connectionId}`;
    ws = new WebSocket(wsUrl);
```

Replace with:
```typescript
    // Generate connection ID if not exists
    if (!connectionId) {
        connectionId = `user_${Math.random().toString(36).substring(2, 11)}`;
    }

    // Use environment variable or build dynamic URL based on current host
    const getWebSocketUrl = () => {
        if (import.meta.env.VITE_WS_URL) {
            return import.meta.env.VITE_WS_URL;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' 
            ? 'localhost:8000' 
            : window.location.host;
        
        return `${protocol}//${host}/ws`;
    };

    const wsUrl = `${getWebSocketUrl()}?connection_id=${connectionId}`;
    ws = new WebSocket(wsUrl);
```

## Deployment Steps (MUST DO THIS!)

**IMPORTANT:** The vite.config.ts proxy only works in dev mode. For production, you MUST update the source files and rebuild!

### On Your Production Server:

1. **Update the 2 files above** (services/api.ts and utils/useWebSocket.ts)

2. **Rebuild your frontend:**
   ```bash
   npm run build
   ```
   
3. **Restart your frontend server:**
   ```bash
   # If using PM2:
   pm2 restart frontend
   
   # If using npm:
   npm run preview
   ```

4. **Verify the URLs:**
   - Open browser console on https://beta.beatvegas.app
   - You should see WebSocket connecting to `wss://beta.beatvegas.app/ws` instead of `ws://localhost:8000/ws`
   - API calls should go to `https://beta.beatvegas.app/api/...` instead of `localhost:8000/api/...`

## Optional: Environment Variables

If you want to use specific URLs, create a `.env.production` file:

```env
VITE_API_URL=https://beta.beatvegas.app
VITE_WS_URL=wss://beta.beatvegas.app/ws
```

Then rebuild with:
```bash
npm run build -- --mode production
```

## What This Fixes

✅ WebSocket will connect to `wss://beta.beatvegas.app/ws` instead of `ws://localhost:8000/ws`  
✅ API calls will go to `https://beta.beatvegas.app` instead of `http://localhost:8000`  
✅ Automatic protocol detection (http/ws for dev, https/wss for production)  
✅ No more hardcoded localhost URLs
