/**
 * NetSpace IPAM — UI smoke test (headless Edge + puppeteer-core).
 * Run while `npm run dev` and the backend are up on :5173 / :8000.
 * Exercises every page plus the Ark UI dialogs, menus, tabs and toasts.
 */
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

// Browser discovery: EDGE_PATH wins; otherwise try common installs per platform
// (Windows Edge, Linux microsoft-edge/chromium, macOS Edge).
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
const BASE = 'http://localhost:5173'
const SHOTS = join(tmpdir(), 'netspace-smoke')
mkdirSync(SHOTS, { recursive: true })

const problems = []
const results = []
function ok(name, detail = '') {
  const line = `PASS ${name}${detail ? ' — ' + detail : ''}`
  results.push(line)
  console.log(line)
}
function fail(name, detail) {
  const line = `FAIL ${name} — ${detail}`
  results.push(line)
  problems.push(`${name}: ${detail}`)
  console.log(line)
}

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
  defaultViewport: { width: 1440, height: 900 },
})
const page = await browser.newPage()
page.on('console', (m) => {
  if (m.type() === 'error') problems.push('console.error: ' + m.text())
})
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message))
page.on('requestfailed', (r) => {
  if (!r.url().includes('favicon')) problems.push('requestfailed: ' + r.url())
})

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function go(path, waitFor) {
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' })
  if (waitFor) await page.waitForSelector(waitFor, { timeout: 10000 })
  await sleep(250)
}
async function shot(name) {
  await page.screenshot({ path: join(SHOTS, name + '.png') })
}
async function clickText(selector, text) {
  // visible-only: rows that keep closed menus/dialogs mounted must not match
  const handle = await page.evaluateHandle(
    (sel, txt) =>
      [...document.querySelectorAll(sel)].find(
        (el) => el.textContent.includes(txt) && el.getClientRects().length > 0,
      ),
    selector,
    text,
  )
  const el = handle.asElement()
  if (!el) throw new Error(`no element ${selector} containing "${text}"`)
  await sleep(200) // let popover/dialog open animations settle (moving target)
  await el.click()
}

try {
  /* --- 1. Dashboard ------------------------------------------------ */
  await go('/', '.stat')
  const stats = await page.$$eval('.stat .value', (els) => els.map((e) => e.textContent.trim()))
  if (stats.length === 4) ok('dashboard stats', stats.join(', '))
  else fail('dashboard stats', `expected 4 stat cards, got ${stats.length}`)
  const meters = await page.$$eval('[data-scope="progress"]', (els) => els.length)
  if (meters > 0) ok('dashboard meters', `${meters} Ark Progress meters`)
  else fail('dashboard meters', 'no Ark Progress components rendered')
  const navCount = await page.$$eval('.nav-link', (els) => els.length)
  if (navCount === 7) ok('sidebar nav', '7 links in 3 sections')
  else fail('sidebar nav', `expected 7 links, got ${navCount}`)
  await shot('01-dashboard')

  /* --- 1b. Theme toggle + persistence ------------------------------- */
  // direction-agnostic: the first run picks up the OS preference, later runs
  // start from the persisted choice, so assert the flip rather than the side.
  const themeStart = await page.evaluate(() => document.documentElement.dataset.theme)
  const bgStart = await page.$eval('body', (el) => getComputedStyle(el).backgroundColor)
  await page.click('button[aria-label^="Switch to"]')
  await sleep(300)
  const themeMid = await page.evaluate(() => document.documentElement.dataset.theme)
  const bgMid = await page.$eval('body', (el) => getComputedStyle(el).backgroundColor)
  if (themeMid !== themeStart && bgMid !== bgStart)
    ok('theme toggle', `${themeStart} (${bgStart}) -> ${themeMid} (${bgMid})`)
  else fail('theme toggle', `${themeStart}/${bgStart} -> ${themeMid}/${bgMid}`)
  await shot(`01b-dashboard-${themeMid}`)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.stat', { timeout: 10000 })
  const persisted = await page.evaluate(() => document.documentElement.dataset.theme)
  if (persisted === themeMid) ok('theme persistence', `${themeMid} survives reload (localStorage)`)
  else fail('theme persistence', `expected ${themeMid} after reload, got ${persisted}`)
  await page.click('button[aria-label^="Switch to"]')
  await sleep(200)
  const themeEnd = await page.evaluate(() => document.documentElement.dataset.theme)
  if (themeEnd === themeStart) ok('theme restore', `switched back to ${themeStart}`)
  else fail('theme restore', `expected ${themeStart}, got ${themeEnd}`)

  /* --- 2. Calculator (Ark Tabs) ------------------------------------- */
  await go('/calculator', '[data-scope="tabs"][data-part="list"]')
  await clickText('[data-scope="tabs"][data-part="trigger"]', 'Split network')
  await page.waitForSelector('[data-scope="tabs"][data-part="content"]', { timeout: 5000 })
  await clickText('button[type="submit"]', 'Split')
  await page.waitForSelector('.table-wrap tbody tr, .banner.error', { timeout: 8000 })
  const splitRows = await page.$$eval('.table-wrap tbody tr', (rows) => rows.length)
  if (splitRows >= 4) ok('calculator split', `${splitRows} subnets listed`)
  else fail('calculator split', `expected >=4 rows, got ${splitRows}`)
  await shot('02-calculator-split')

  /* --- 3. Planner (Ark NumberInput) --------------------------------- */
  await go('/planner', '[data-scope="number-input"][data-part="control"]')
  const ni = await page.$$eval('[data-scope="number-input"][data-part="control"]', (els) => els.length)
  if (ni >= 15) ok('planner number inputs', `${ni} Ark NumberInputs`)
  else fail('planner number inputs', `expected >=15, got ${ni}`)
  await clickText('button[type="submit"]', 'Preview allocation')
  await page.waitForSelector('.card .table-wrap table', { timeout: 10000 })
  await shot('03-planner-preview')

  /* --- 4. Plans + detail -------------------------------------------- */
  await go('/plans', 'table')
  await page.click('tbody a')
  await page.waitForSelector('[data-scope="progress"], .table-wrap', { timeout: 10000 })
  ok('plan detail', 'opened plan detail view')
  await shot('04-plan-detail')

  /* --- 5. Networks: dialog + create/delete round trip --------------- */
  await go('/networks', 'table')
  const pager = await page.$$('[data-scope="pagination"] [data-part="item"]')
  if (pager.length >= 2) ok('networks pagination', `${pager.length} page buttons`)
  await clickText('button', 'New network')
  await page.waitForSelector('[data-scope="dialog"][data-part="content"]', { timeout: 5000 })
  ok('network dialog', 'Ark Dialog opens')
  await shot('05-network-dialog')
  await page.keyboard.press('Escape')
  await sleep(500)
  const blurClosed = await page.$eval('.app-shell', (el) => getComputedStyle(el).filter)
  if (blurClosed === 'none') ok('blur clears', 'app-shell unblurred after dialog closes')
  else fail('blur clears', `expected filter none after close, got "${blurClosed}"`)

  /* --- 6. Departments: full CRUD round trip through Ark UI ---------- */
  // self-cleaning fixture: remove leftovers from a previously crashed run
  // (a duplicate name would 409 and break the create step below)
  const existing = await (await fetch(`${BASE}/api/v1/departments?page_size=200`)).json()
  for (const d of existing.items.filter((x) => x.name === 'Smoke Test Dept')) {
    await fetch(`${BASE}/api/v1/departments/${d.id}`, { method: 'DELETE' })
  }
  await go('/departments', 'table, .empty')
  await clickText('button', 'New department')
  await page.waitForSelector('[data-scope="dialog"][data-part="content"]', { timeout: 5000 })
  // stacking guard: the dialog content must be the top element at its own
  // center (catches backdrops/popovers painting above the modal)
  const stacking = await page.evaluate(() => {
    const content = document.querySelector('[data-scope="dialog"][data-part="content"]')
    const backdrop = document.querySelector('[data-scope="dialog"][data-part="backdrop"]')
    const pos = document.querySelector('[data-scope="dialog"][data-part="positioner"]')
    if (!content || !backdrop || !pos) return { inside: false, why: 'missing parts' }
    const r = content.getBoundingClientRect()
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + 40)
    const inside = !!hit && (hit === content || content.contains(hit))
    const zb = Number(getComputedStyle(backdrop).zIndex)
    const zp = Number(getComputedStyle(pos).zIndex)
    return { inside, zb, zp, hitTag: hit ? hit.tagName : 'none' }
  })
  if (stacking.inside && stacking.zp > stacking.zb)
    ok('dialog stacking', `content on top at center (z ${stacking.zb} < ${stacking.zp})`)
  else fail('dialog stacking', JSON.stringify(stacking))
  // the backdrop must be completely invisible (operator decision: background
  // behind an open dialog stays unchanged — no blur, no dim); nothing may ever
  // paint over the modal
  await sleep(300) // let any transition finish before sampling
  const backdropBg = await page.$eval(
    '[data-scope="dialog"][data-part="backdrop"]',
    (el) => getComputedStyle(el).backgroundColor,
  )
  if (backdropBg === 'rgba(0, 0, 0, 0)')
    ok('backdrop invisible', `backdrop is transparent: "${backdropBg}"`)
  else fail('backdrop invisible', `backdrop paints a layer: "${backdropBg}"`)
  const shellFilter = await page.$eval('.app-shell', (el) => getComputedStyle(el).filter)
  if (shellFilter === 'none') ok('shell plain', 'app-shell filtered: none while dialog open')
  else fail('shell plain', `app-shell filter while dialog open: "${shellFilter}"`)
  const contentFilter = await page.$eval(
    '[data-scope="dialog"][data-part="content"]',
    (el) => getComputedStyle(el).filter,
  )
  if (contentFilter === 'none') ok('modal crisp', 'dialog content has no filter')
  else fail('modal crisp', `dialog content filter: "${contentFilter}"`)

  // focus must be trapped inside the dialog (Tab cycles within content)
  let focusTrapped = true
  let escapedAt = 0
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab')
    const inside = await page.evaluate(() => {
      const c = document.querySelector('[data-scope="dialog"][data-part="content"]')
      return !!c && c.contains(document.activeElement)
    })
    if (!inside) {
      focusTrapped = false
      escapedAt = i + 1
      break
    }
  }
  if (focusTrapped) ok('focus trap', '12 Tabs keep focus inside the dialog')
  else fail('focus trap', `focus escaped the dialog after ${escapedAt} Tab(s)`)
  const nameInput = await page.$('[data-scope="dialog"] [data-scope="field"][data-part="input"]')
  if (!nameInput) fail('dept form', 'no Ark Field input in dialog')
  else {
    await nameInput.type('Smoke Test Dept')
    await clickText('[data-scope="dialog"] button[type="submit"]', 'Create department')
    await page.waitForSelector('[data-scope="toast"][data-part="root"][data-type="success"]', {
      timeout: 8000,
    })
    ok('dept create toast', 'success toast appeared after Ark Dialog submit')
    await page.waitForFunction(() => document.body.innerText.includes('Smoke Test Dept'), {
      timeout: 8000,
    })
    ok('dept create row', 'new department listed in table')
    await shot('06-dept-toast')
    // wait for the success toast to clear: it floats bottom-right (z-index
    // above menus) and would swallow the clicks on the last row's menu
    await page.waitForFunction(() => !document.querySelector('[data-scope="toast"][data-part="root"]'), {
      timeout: 15000,
    })
    await sleep(300)

    // Row menu -> delete -> alert dialog -> confirm
    await page.waitForSelector('[aria-label="Actions for Smoke Test Dept"]', { timeout: 8000 })
    await page.click('[aria-label="Actions for Smoke Test Dept"]')
    await page.waitForSelector('[data-scope="menu"][data-part="content"]', { timeout: 5000 })
    ok('row menu', 'Ark Menu opens from row actions')
    await shot('07-row-menu')
    await clickText('[data-scope="menu"][data-part="item"]', 'Delete department')
    await page.waitForSelector('[data-scope="dialog"][data-part="content"][role="alertdialog"]', {
      timeout: 5000,
    })
    ok('confirm dialog', 'Ark alert dialog asks for confirmation')
    await shot('08-confirm-delete')
    await clickText('[data-scope="dialog"] button', 'Delete department')
    await page.waitForFunction(() => !document.body.innerText.includes('Smoke Test Dept'), {
      timeout: 8000,
    })
    ok('dept delete', 'department removed after confirming alert dialog')
  }

  /* --- 7. IP Addresses (filters + row menu) -------------------------- */
  await go('/ip-addresses', 'table')
  const selects = await page.$$eval('[data-scope="select"][data-part="trigger"]', (els) => els.length)
  if (selects >= 2) ok('ip filters', `${selects} Ark Selects on page`)
  else fail('ip filters', `expected >=2 selects, got ${selects}`)
  await shot('09-ip-addresses')

  console.log('\n===== SMOKE RESULTS =====')
  for (const r of results) console.log(r)
  console.log('\n===== PROBLEMS =====')
  if (problems.length === 0) console.log('none')
  else for (const p of [...new Set(problems)]) console.log(p)
  console.log(`\nshots: ${SHOTS}`)
} finally {
  await browser.close()
}
