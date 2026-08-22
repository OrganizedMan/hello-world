import { chromium } from '@playwright/test';
const [,, url, out, storey] = process.argv;
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=swiftshader','--enable-unsafe-swiftshader','--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
const bad = [];
page.on('pageerror', e => bad.push('PAGEERROR ' + String(e).slice(0,200)));
page.on('response', r => { if (!r.ok() && !r.url().includes('favicon')) bad.push(`${r.status()} ${r.url().slice(0,90)}`); });
await page.goto(url, { waitUntil: 'networkidle', timeout: 120000 });
await page.waitForTimeout(13000);
if (storey) { await page.getByRole('button', { name: storey }).click(); await page.waitForTimeout(3500); }
await page.locator('canvas').screenshot({ path: out });
console.log('ISSUES:', bad.length ? bad.join('\n  ') : 'none');
await browser.close();
