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
page.on('pageerror', (e) => errs.push(`pageerror: ${e.message}`));
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

const shot = async (name, y, wait = 1600) => { await page.evaluate((v) => window.scrollTo(0, v), y); await page.waitForTimeout(wait); await page.screenshot({ path: `${out}/${name}.png` }); console.log('shot', name, Math.round(y)); };
const pos = await page.evaluate(() => {
  const g = (id) => document.getElementById(id); const td = g('teardown');
  return { td: td.offsetTop, tdRange: td.offsetHeight - innerHeight, ids: Object.fromEntries(['lift', 'control', 'energy', 'camera', 'wake', 'gallery', 'evidence'].map((i) => [i, g(i).offsetTop])) };
});
await shot('00-hero', 0, 2200);
for (const [i, p] of [[1, 0.0], [2, 0.18], [3, 0.4], [4, 0.62], [5, 0.8], [6, 0.97]]) await shot(`0${i}-teardown-${Math.round(p * 100)}`, pos.td + p * pos.tdRange + 4, 2000);
let n = 7;
