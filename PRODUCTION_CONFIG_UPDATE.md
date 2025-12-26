# Production Configuration Update

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
