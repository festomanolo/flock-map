// Dev tool: screenshot each chapter of the built site and report console errors.
// Usage: node scripts/shots.mjs [url] [width] [height] [theme]
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
