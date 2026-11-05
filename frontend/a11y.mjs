/**
 * NetSpace IPAM — accessibility check (M11-AC-002, headless).
 * Runs axe-core (runtime CDN, no package added) against the real UI pages
 * behind the running stack and reports violations per page + tag.
 *
 * Same environment contract as smoke.mjs: SMOKE_BASE / SMOKE_USER / SMOKE_PASS
 * / EDGE_PATH. Login credentials never appear in outputs.
 */
import puppeteer from 'puppeteer-core'
import { existsSync } from 'node:fs'

const EDGE_CANDIDATES =
  process.platform === 'win32'
    ? [
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
      ]
    : process.platform === 'darwin'
      ? ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
      : ['/usr/bin/microsoft-edge', '/usr/bin/chromium', '/usr/bin/google-chrome', '/usr/bin/chromium-browser']
const EDGE = process.env.EDGE_PATH || EDGE_CANDIDATES.find((p) => existsSync(p)) || EDGE_CANDIDATES[0]
const BASE = process.env.SMOKE_BASE || 'http://localhost:5173'
const SMOKE_USER = process.env.SMOKE_USER || 'admin'
const SMOKE_PASS = process.env.SMOKE_PASS || ''

const PAGES = [
  ['/', 'dashboard'],
  ['/calculator', 'calculator'],
  ['/planner', 'vlsm-planner'],
  ['/plans', 'plans'],
  ['/networks', 'networks'],
  ['/ip-addresses', 'ip-addresses'],
  ['/departments', 'departments'],
]

const AXE = await (await fetch('https://cdn.jsdelivr.net/npm/axe-core@4.11.1/axe.min.js')).text()

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
})
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1280, height: 900 })

  // There is no /login route: clearing the stored session shows the login card.
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    localStorage.removeItem('netspace.token')
    localStorage.removeItem('netspace.user')
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForSelector('form', { timeout: 10000 })
  const userField = await page.$('input[name="username"], input[autocomplete="username"]')
  const passField = await page.$('input[name="password"], input[type="password"]')
  if (!userField || !passField) throw new Error('login form not found')
  await userField.type(SMOKE_USER)
  await passField.type(SMOKE_PASS)
  await page.click('form button[type="submit"], form button')
  await page.waitForSelector('.app-shell', { timeout: 10000 })
  await page.waitForSelector('.stat', { timeout: 10000 })

  const violations = []
  for (const [path, name] of PAGES) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle2' })
    await new Promise((r) => setTimeout(r, 600))
    const res = await page.evaluate((axeSource) => {
      // avoid page-global axe caching across pages: fresh context each time
      const w = window
      if (!w.axe) {
        // eslint-disable-next-line no-new-func
        new Function(axeSource)()
        w.axe = window.axe
      }
      return w.axe.run(w.document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
        resultTypes: ['violations'],
      })
    }, AXE)
    const v = res.violations.filter((x) => x.nodes.length > 0)
    if (v.length === 0) {
      console.log(`PASS ${name} — 0 axe violations (wcag2a/2aa, 2.1a/aa)`)
    } else {
      console.log(`FAIL ${name} — ${v.length} axe violation type(s)`)
      v.forEach((x) => {
        console.log(`   [${x.impact || 'minor'}] ${x.id}: ${x.help} — nodes: ${x.nodes.length}`)
        violations.push(`${name}/${x.id}`)
      })
    }
  }

  if (violations.length > 0) {
    console.log(`A11Y FAILED (${violations.length} violation entries)`)
    process.exit(1)
  }
  console.log('A11Y PASSED')
} finally {
  await browser.close()
}
