// Dev tool: screenshot each chapter of the built site and report console errors.
// Usage: node scripts/shots.mjs [url] [width] [height] [theme]
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW || '/Users/festomanolo/.claude/skills/teardown/node_modules/playwright');

const url = process.argv[2] || 'http://localhost:4173/';
const W = +(process.argv[3] || 1440), H = +(process.argv[4] || 900), theme = process.argv[5] || 'light';
const out = `.shots/${W}x${H}-${theme}`; fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--hide-scrollbars'] });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, colorScheme: theme, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const errs = [];
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(`${m.type()}: ${m.text()}`); });
