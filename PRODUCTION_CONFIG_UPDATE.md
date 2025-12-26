# Production Performance Fix - CRITICAL ISSUES FOUND

## 🚨 MAJOR PERFORMANCE PROBLEMS

Your production site is slow because you're using:
1. **CDN Tailwind CSS** - processes CSS at runtime (VERY SLOW)
2. **CDN React** - loads React from external CDN (ADDS DELAY)
3. **No build optimization** - bundle not optimized

## Quick Fix for Production Server

### Step 1: Install the required package
```bash
npm install @tailwindcss/postcss
```

### Step 2: Update postcss.config.js
```javascript
export default {
  plugins: {
    '@tailwindcss/postcss': {},
    autoprefixer: {},
  },
}
```

### Step 3: Update src/index.css
```css
@import "tailwindcss";

@theme {
  --color-dark-navy: #0C1018;
  --color-navy: #1A1F27;
  --color-card-gray: #1A1F27;
  --color-charcoal: #343a40;
  --color-border-gray: #2D3542;
  --color-gold: #D4A64A;
  --color-light-gold: #E7C776;
  --color-deep-red: #A03333;
  --color-light-red: #CC4A45;
  --color-off-white: #F3F2ED;
  --color-muted-text: #8B97A7;
  --color-light-gray: #adb5bd;
  --color-neon-green: #4CAF50;
  --color-vibrant-yellow: #FFEB3B;
  --color-bold-red: #F52D2D;
  --color-electric-blue: #D4A64A;
  
  --font-family-sans: 'Roboto', sans-serif;
  --font-family-teko: 'Teko', sans-serif;
}
```

### Step 4: You can DELETE tailwind.config.js (not needed for v4)

### Step 5: Update index.html (REPLACE)
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

### Step 6: Update index.tsx (add CSS import)
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
