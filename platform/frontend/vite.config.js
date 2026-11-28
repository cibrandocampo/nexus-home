import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // In the dev stack the API runs in the backend container; the browser only talks to Vite.
    proxy: { '/api': { target: process.env.API_TARGET ?? 'http://localhost:8000' } },
  },
  build: {
    rollupOptions: {
      output: {
        // Libraries change less often than the app: their own chunks stay cached across releases.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('@mantine')) return 'mantine';
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/.test(id)) {
            return 'react';
          }
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
    // Page tests render the whole app (router, Mantine, MSW): 5 s is too tight on a busy machine
    // (several suites at once, CI runners). A real hang still fails, three times later.
    testTimeout: 15_000,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/test/**', 'src/**/*.test.{js,jsx}'],
      thresholds: { statements: 95, branches: 90, functions: 95, lines: 95 },
    },
  },
});
