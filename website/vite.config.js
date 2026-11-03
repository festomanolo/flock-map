import { defineConfig } from 'vite';

export default defineConfig({ build: { chunkSizeWarningLimit: 1200, target: 'es2020' } });
