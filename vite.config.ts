import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      test: {
        globals: true,
        environment: 'jsdom',
      },
      server: {
        port: 3000,
        host: '0.0.0.0',
        allowedHosts: ['beta.beatvegas.app'],
        // Disable caching in dev to avoid stale bundles on refresh
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
      },
      // Explicit esbuild configuration - NO invalid loaders
      esbuild: {
        // Only valid loaders: js, jsx, ts, tsx, css, json, text, base64, dataurl, file, binary
        // NO "map" loader - source maps handled via build.sourcemap
        loader: 'tsx',
        include: /\.(tsx?|jsx?)$/,
        exclude: /node_modules/
      },
      // Build configuration - deterministic and production-ready
      build: {
        sourcemap: true, // Enable source maps the correct way
        target: 'es2015',
        minify: 'esbuild',
        rollupOptions: {
          output: {
            manualChunks: undefined // Prevent chunking issues
          }
        }
      },
      // Optimization configuration
      optimizeDeps: {
        esbuildOptions: {
          // Ensure esbuild uses only valid loaders
          loader: {
            '.js': 'jsx',
            '.ts': 'tsx'
          }
        }
      }
    };
});
