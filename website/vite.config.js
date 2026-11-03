import { defineConfig } from 'vite';

// base './' keeps every asset path relative, so the build works at a domain root or in a subfolder
export default defineConfig({ build: { chunkSizeWarningLimit: 1200, target: 'es2020' } });
