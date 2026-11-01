/**
 * NetSpace IPAM — UI smoke test (headless browser + puppeteer-core).
 * Run while `npm run dev` and the backend are up on :5173 / :8000.
 * Exercises every page plus the Ark UI dialogs, menus, tabs and toasts,
 * the M5 login flow, M6 backend-error/viewport states and M7 subnet fields.
 *
 * Login credentials are supplied by the environment (SMOKE_USER / SMOKE_PASS,
 * default admin) and are never hard-coded into the repository.
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
const BASE = process.env.SMOKE_BASE || 'http://localhost:5173'
const SMOKE_USER = process.env.SMOKE_USER || 'admin'
const SMOKE_PASS = process.env.SMOKE_PASS || ''
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
  if (m.type() === 'error')
    problems.push('console.error: ' + m.text() + ' at ' + (m.location()?.url ?? '?'))
})
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message))
page.on('requestfailed', (r) => {
  if (!r.url().includes('favicon'))
    problems.push(
      'requestfailed T+' +
        ((Date.now() - T0.getTime()) / 1000).toFixed(2) +
        ' [' +
        r.method() +
        ' ' +
        r.url() +
        '] [' +
        (r.failure()?.errorText ?? '?') +
        ']',
    )
})

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function go(path, waitFor) {
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' })
  if (waitFor) await page.waitForSelector(waitFor, { timeout: 10000 })
  await sleep(250)
}
const DEBUG_REQUESTS = process.env.SMOKE_DEBUG === '1'
const T0 = new Date()
if (DEBUG_REQUESTS) {
  page.on('request', (rq) => {
    if (rq.url().includes('/api/'))
      console.log(`REQ T+${((Date.now() - T0.getTime()) / 1000).toFixed(2)}`, rq.method(), rq.url().slice(BASE.length))
  })
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
  /* --- 0. Login (M5 authentication flow) ---------------------------- */
  if (!SMOKE_PASS) {
    fail('login config', 'SMOKE_PASS is not set; refusing to run unauthenticated')
    throw new Error('SMOKE_PASS required')
  }
  // signed out by removing any stale session (the app shows the login card on
  // every route while localStorage holds no user — there is no /login route)
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    localStorage.removeItem('netspace.token')
    localStorage.removeItem('netspace.user')
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForSelector('form', { timeout: 10000 })
  const userField = await page.$('input[name="username"], input[autocomplete="username"]')
  const passField = await page.$('input[name="password"], input[type="password"]')
  if (!userField || !passField) fail('login form', 'username/password inputs not found')
  else {
    await userField.type(SMOKE_USER)
    await passField.type(SMOKE_PASS)
    await page.click('form button[type="submit"], form button')
    await page.waitForSelector('.app-shell', { timeout: 10000 })
    ok('login', `signed in as ${SMOKE_USER}; app shell rendered`)
    await go('/', '.stat')
  }

  /* --- 1. Dashboard ------------------------------------------------ */
  await go('/', '.stat')
  const stats = await page.$$eval('.stat .value', (els) => els.map((e) => e.textContent.trim()))
  if (stats.length === 4) ok('dashboard stats', stats.join(', '))
  else fail('dashboard stats', `expected 4 stat cards, got ${stats.length}`)
  const meters = await page.$$eval('[data-scope="progress"]', (els) => els.length)
  if (meters > 0) ok('dashboard meters', `${meters} Ark Progress meters`)
  else fail('dashboard meters', 'no Ark Progress components rendered')
  const navCount = await page.$$eval('.nav-link', (els) => els.length)
  const navRole = await page.$eval('.role-badge .badge', (el) => el.textContent.trim())
  const expectedNav = navRole === 'admin' ? 8 : 7
  if (navCount === expectedNav) ok('sidebar nav', `${navCount} links for ${navRole}`)
  else fail('sidebar nav', `expected ${expectedNav} links for ${navRole}, got ${navCount}`)
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
  // (a duplicate name would 409 and break the create step below); the fetches
  // carry the operator token — unauthenticated deletes would 401 and pollute
  // the console-error log below
  const tok = await page.evaluate(() => localStorage.getItem('netspace.token'))
  const headers = tok ? { Authorization: `Bearer ${tok}` } : {}
  const existing = await (await fetch(`${BASE}/api/v1/departments?page_size=200`, { headers })).json()
  for (const d of existing.items.filter((x) => x.name === 'Smoke Test Dept')) {
    await fetch(`${BASE}/api/v1/departments/${d.id}`, { method: 'DELETE', headers })
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

  /* --- 8. Backend validation errors surface in the UI (M6-AC-005) --- */
  await go('/networks', 'table')
  await clickText('button', 'New network')
  await page.waitForSelector('[data-scope="dialog"][data-part="content"]', { timeout: 5000 })
  const netInputs = await page.$$('[data-scope="dialog"] [data-scope="field"] [data-part="input"]')
  if (netInputs.length < 2) fail('validation surface', 'network dialog inputs missing')
  else {
    await netInputs[0].type('Smoke Invalid Net')
    await netInputs[1].type('not-a-cidr')
    await clickText('[data-scope="dialog"] button[type="submit"]', 'Create network')
    await page
      .waitForSelector('[data-scope="toast"][data-part="root"][data-type="error"], .banner.error', {
        timeout: 8000,
      })
      .then(() => ok('validation surface', 'invalid CIDR produced a visible backend error'))
      .catch(() => fail('validation surface', 'no visible error for invalid CIDR'))
    await shot('10-validation-error')
  }
  await page.keyboard.press('Escape')

  /* --- 9. Mobile viewport (M6-AC-003) ------------------------------- */
  await page.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true })
  await go('/', '.stat')
  const mobile = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    stats: document.querySelectorAll('.stat').length,
    navVisible: [...document.querySelectorAll('.nav-link')].some(
      (el) => el.getClientRects().length > 0,
    ),
  }))
  if (mobile.stats >= 4 && mobile.overflowX <= 2)
    ok('mobile dashboard', `375px viewport renders all stats (overflow ${mobile.overflowX}px)`)
  else fail('mobile dashboard', JSON.stringify(mobile))
  await go('/networks', 'table')
  const tableFits = await page.evaluate(() => {
    const wrap = document.querySelector('.table-wrap')
    if (!wrap) return null
    return {
      wraps: !!wrap,
      // the wrapper may scroll horizontally for wide tables; the page itself
      // must not be pushed off-screen by raw table overflow
      docOverflow: document.documentElement.scrollWidth - window.innerWidth,
    }
  })
  if (tableFits && tableFits.wraps)
    ok('mobile tables', `networks table wrapped; page overflow ${tableFits.docOverflow}px`)
  else fail('mobile tables', 'no .table-wrap on mobile networks page')
  await shot('11-mobile-networks')
  // restore the desktop viewport for a clean shell state
  await page.setViewport({ width: 1440, height: 900 })

  /* --- 10. Subnet owner/location fields (M7 wire-up) ----------------- */
  await go('/networks/1', 'table')
  const hasOwnerCol = await page.evaluate(() =>
    [...document.querySelectorAll('table th')].some((th) => th.textContent.trim() === 'Owner'),
  )
  if (hasOwnerCol) ok('subnet owner/location columns', 'Owner and Location rendered in subnet table')
  else fail('subnet owner/location columns', 'Owner column missing on network detail page')
  await shot('12-network-detail-m7')

  console.log('\n===== SMOKE RESULTS =====')
  for (const r of results) console.log(r)
  console.log('\n===== PROBLEMS =====')
  if (problems.length === 0) console.log('none')
  else for (const p of [...new Set(problems)]) console.log(p)
  console.log(`\nshots: ${SHOTS}`)
} finally {
  await browser.close()
}
