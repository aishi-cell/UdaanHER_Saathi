// Browser driver for UdaanHer Saathi. Screenshots land in <repo>/shots/.
//
//   node .claude/skills/run-udaan-hersaathi/driver.mjs [flow]
//
// Flows:
//   landing   landing page, desktop + mobile          (frontend only)
//   picker    language picker, unselected + selected  (frontend only)
//   ui-demo   every UICommand through the Renderer    (frontend only)
//   session   full flow to the live conversation view (needs backend on :8000)
//
// Env overrides: APP_URL (default http://localhost:5173),
//                PW_BROWSER_PATH (chromium executable),
//                PW_CHANNEL (e.g. msedge/chrome, skips the cache scan)

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(join(repoRoot, 'frontend', 'package.json'));
const { chromium } = require('playwright-core');

const APP_URL = process.env.APP_URL ?? 'http://localhost:5173';
const OUT_DIR = join(repoRoot, 'shots');
mkdirSync(OUT_DIR, { recursive: true });

function findCachedChromium() {
  if (process.env.PW_BROWSER_PATH) return process.env.PW_BROWSER_PATH;
  if (process.env.PW_CHANNEL) return null;
  const cacheRoot =
    process.platform === 'win32'
      ? join(process.env.LOCALAPPDATA ?? '', 'ms-playwright')
      : join(process.env.HOME ?? '', '.cache', 'ms-playwright');
  if (!existsSync(cacheRoot)) return null;
  const dirs = readdirSync(cacheRoot)
    .filter((d) => /^chromium-\d+$/.test(d))
    .sort()
    .reverse();
  for (const d of dirs) {
    for (const rel of ['chrome-win64/chrome.exe', 'chrome-linux/chrome', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']) {
      const p = join(cacheRoot, d, rel);
      if (existsSync(p)) return p;
    }
  }
  return null;
}

async function launch() {
  const args = ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'];
  const exe = findCachedChromium();
  if (exe) return chromium.launch({ executablePath: exe, args });
  // No playwright browser cache: fall back to an installed Edge/Chrome.
  for (const channel of [process.env.PW_CHANNEL, 'msedge', 'chrome'].filter(Boolean)) {
    try {
      return await chromium.launch({ channel, args });
    } catch {
      /* try next */
    }
  }
  throw new Error(
    'No browser found. Set PW_BROWSER_PATH, or run: npx playwright install chromium',
  );
}

const errors = [];
function watch(page) {
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(String(e)));
}

async function shot(page, name) {
  const file = join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file });
  console.log('shot:', file);
}

async function openMobile(browser) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    permissions: ['microphone'],
  });
  const page = await ctx.newPage();
  watch(page);
  await page.goto(APP_URL, { waitUntil: 'networkidle' });
  return page;
}

async function toPicker(page) {
  await page.getByText('Talk to Saathi').click();
  await page.waitForTimeout(800); // hero -> picker slide animation
}

const flows = {
  async landing(browser) {
    const desktop = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    watch(desktop);
    await desktop.goto(APP_URL, { waitUntil: 'networkidle' });
    await desktop.waitForTimeout(1200); // staggered entrance animation
    await shot(desktop, 'landing-desktop');
    const mobile = await openMobile(browser);
    await mobile.waitForTimeout(1200);
    await shot(mobile, 'landing-mobile');
  },

  async picker(browser) {
    const page = await openMobile(browser);
    await toPicker(page);
    await shot(page, 'picker');
    await page.getByText('English').first().click();
    await page.waitForTimeout(400);
    await shot(page, 'picker-selected');
  },

  async 'ui-demo'(browser) {
    // ?ui-demo=1 cycles every UICommand through the real Renderer -- pure
    // frontend, no backend or LLM cost.
    const page = await openMobile(browser);
    await page.goto(`${APP_URL}/?ui-demo=1`, { waitUntil: 'networkidle' });
    for (let i = 0; ; i++) {
      await page.waitForTimeout(700);
      const label = (await page.locator('footer p').innerText()).trim();
      const [pos, type] = label.split(': ');
      await shot(page, `ui-demo-${i}-${type}`);
      const [current, total] = pos.split(' / ').map(Number);
      if (current === total) break;
      await page.getByRole('button', { name: 'Next' }).click();
    }
  },

  async session(browser) {
    const health = await fetch('http://localhost:8000/health').catch(() => null);
    if (!health?.ok) {
      throw new Error('Backend not reachable on :8000 -- start it first (see SKILL.md).');
    }
    const page = await openMobile(browser);
    await toPicker(page);
    await page.getByText('Continue').click();
    await page.waitForTimeout(1000);
    await shot(page, 'session-connecting'); // "Saathi आ रही हैं…" state
    // Session creation does an LLM + TTS warm-up; typically 5-15 s.
    for (let i = 0; i < 45; i++) {
      await page.waitForTimeout(1000);
      const text = await page.locator('body').innerText();
      if (!text.includes('Saathi आ रही हैं')) break;
    }
    await page.waitForTimeout(500);
    await shot(page, 'session-ready');
    const status = (await page.locator('body').innerText()).replace(/\s+/g, ' ');
    console.log('status:', status);
    if (status.includes('Saathi आ रही हैं')) {
      throw new Error('Session never became ready after 45s -- check backend logs.');
    }
  },
};

const flow = process.argv[2] ?? 'session';
if (!flows[flow]) {
  console.error(`Unknown flow "${flow}". Flows: ${Object.keys(flows).join(', ')}`);
  process.exit(2);
}

const browser = await launch();
try {
  await flows[flow](browser);
} finally {
  await browser.close();
}
console.log('console errors:', errors.length ? errors.join('\n') : 'none');
if (errors.length) process.exit(1);
