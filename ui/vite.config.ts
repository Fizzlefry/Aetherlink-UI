import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const entryPoints: Record<string, string> = {
    default: './src/App.tsx', // Command Center dashboard
    peakpro: './src/verticals/PeakProCRM.tsx',
    policypal: './src/verticals/PolicyPalCRM.tsx',
  };

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        input: entryPoints[mode] || entryPoints.default,
      },
    },
  };
});
