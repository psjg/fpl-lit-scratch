// Vult de gedraaide A elk gat van een wachtende aanroeper, en met de goede
// tekst? De verwachting komt uit de fabula-JSON, niet uit de pagina.
// Gebruik: CHROME=... node gap-check.cjs PW PAGINA RUN [SHOTDIR]
//   PAGINA: bv. zui-a.html (geladen als PAGINA?rot=ccw&run=RUN, 900x1200,
//   dezelfde W en H als in rot-a.html op 1200x900)
// Met SHOTDIR ook drie screenshots via rot-a.html (alleen voor zui-a.html).
const fs = require('fs')
const [PW, PAGE, RUN, SHOTS] = process.argv.slice(2)
const {chromium} = require(PW)
const BASE = 'http://127.0.0.1:8792/'
const TOP = 44, ROW = 460, LINE = 18, K = 18, W = 900, H = 1200

// --- verwachting: build() nagespeeld ---------------------------------------
const F = JSON.parse(fs.readFileSync(`build/${RUN}.fabula.json`, 'utf8'))
const steps = [], blocks = []
for (const st of Object.values(F.runs)) {
  const fb = new Map()
  for (const s of st) {
    const i = steps.length
    if (!fb.has(s.f)) {
      const p = fb.get(s.frame.parent)
      const b = {d: p ? p.d + 1 : 1, s: i, e: i + 1, name: s.frame.name,
        up: p, call: p ? p.last : undefined, own: []}
      fb.set(s.f, b); blocks.push(b)
    }
    for (let b = fb.get(s.f); b; b = b.up) b.e = i + 1
    fb.get(s.f).last = i; fb.get(s.f).own.push(i)
    steps.push({ln: s.ln, src: (s.src || '').trim()})
  }
}
const N = steps.length
const gaps = blocks.filter(b => b.up)
const depth = Math.max(...blocks.map(b => b.d)) + 1
const key = g => g.s + '-' + g.e

const res = []
const ok = (naam, goed, info) => {
  res.push(goed)
  console.log((goed ? 'ok   ' : 'FOUT ') + naam + ' ' + JSON.stringify(info))
}

;(async () => {
  // de aannames waarop held() rust, op de data zelf
  const inGap = gaps.filter(g => g.up.own.some(i => i >= g.s && i < g.e))
  ok('aanroeper heeft geen eigen stap in het gat', !inGap.length,
    {gaten: gaps.length, mis: inGap.length})
  const notPrev = gaps.filter(g => g.call !== g.s - 1)
  ok('de aanroepende stap is de stap vlak voor het gat', !notPrev.length,
    {mis: notPrev.length})

  const b = await chromium.launch({executablePath: process.env.CHROME})
  const p = await b.newPage({viewport: {width: W, height: H}})
  const err = []
  p.on('pageerror', e => err.push(String(e)))
  // ALS=bestand: de pagina komt uit dat bestand (de oude versie, voor rood)
  if (process.env.ALS) await p.route('**/' + PAGE + '?*', r =>
    r.fulfill({path: process.env.ALS, contentType: 'text/html'}))
  await p.goto(`${BASE}${PAGE}?rot=ccw&run=${RUN}`)
  await p.waitForFunction(() => window.zui && zui.ready)

  // veeg: tijd in stappen van 40 (50 in beeld), diepte in stappen van 400
  const ymax = Math.max(0, TOP + depth * ROW + 8 - H)
  const ys = []
  for (let y = 0; y < ymax; y += 400) ys.push(y)
  ys.push(ymax)
  const seen = new Map(), mis = []
  let teken = 0, plak = 0, into = 0
  for (const y0 of ys) for (let x = 0; x < N; x += 40) {
    const r = await p.evaluate(o => {
      const l = zui.set(o)
      return {x0: l.x0, y0: zui.state.y0, level: l.level, held: l.held || []}
    }, {k: K, x0: x, y0})
    teken++
    const X = t => (t - r.x0) * K
    // wat deze tekening hoort te vullen
    const want = new Map()
    for (const g of gaps) {
      if (!(g.e > r.x0 && g.s < r.x0 + W / K)) continue
      const y = TOP + g.up.d * ROW - r.y0 + 14, h = ROW - 2 - 14
      if (y + h < TOP || y > H) continue
      const sx = X(g.s), gx = Math.min(X(g.e), W), stuck = sx < LINE
      const c = steps[g.call], line = c.ln + '  ' + c.src
      const L = stuck && gx >= 2 * LINE ? [line, '↳ ' + g.name]
        : ['↳ ' + g.name]
      const t = []
      let tx = Math.max(stuck ? Math.min(sx, 0) : sx, 0)
      for (const s of L) { if (tx + LINE > gx + .5) break; t.push(s); tx += LINE }
      want.set(key(g), {d: g.up.d, call: g.call, t})
    }
    const got = new Map(r.held.map(g => [key(g), g]))
    for (const [k, w] of want) {
      const g = got.get(k)
      if (!g) { mis.push({x0: r.x0, y0: r.y0, k, wat: 'ontbreekt'}); continue }
      if (g.d !== w.d || g.call !== w.call ||
          JSON.stringify(g.t) !== JSON.stringify(w.t))
        mis.push({x0: r.x0, y0: r.y0, k, wil: w, kreeg: g})
      seen.set(k, 1)
      if (w.t.length == 2) plak++
      if (w.t.length) into++
    }
    for (const k of got.keys())
      if (!want.has(k)) mis.push({x0: r.x0, y0: r.y0, k, wat: 'te veel'})
  }
  ok('veeg: elk gat gevuld', seen.size === gaps.length,
    {tekeningen: teken, gevuld: seen.size, gaten: gaps.length})
  ok('per tekening: gaten, diepte, aanroepende stap en tekst kloppen',
    !mis.length, {mis: mis.length, eerste: mis.slice(0, 3),
      metInto: into, metPlakregel: plak})
  ok('geen paginafouten', !err.length, {err})

  if (SHOTS) {
    const q = await b.newPage({viewport: {width: 1200, height: 900}})
    await q.goto(`${BASE}rot-a.html?run=${RUN}`)
    await q.waitForTimeout(500)
    const f = q.frames()[1]
    await f.waitForFunction(() => window.zui && zui.ready)
    const pair = blocks.find(g => g.name == '_pair')
    const lang = gaps.reduce((a, g) => g.e - g.s > a.e - a.s ? g : a)
    for (const [n, o] of [
      ['gat', {k: K, x0: pair.s - 2, y0: (pair.d - 1) * ROW}],
      ['gat-plak', {k: K, x0: lang.s + 20, y0: (lang.up.d - 1) * ROW}],
      ['gat-laag', {k: 8, x0: pair.s - 20, y0: (pair.d - 1) * ROW}]]) {
      await f.evaluate(o => { zui.set(o) }, o)
      await q.waitForTimeout(200)
      await q.screenshot({path: `${SHOTS}/rot-a-${n}.png`})
    }
  }
  await b.close()
  const n = res.filter(Boolean).length
  console.log((n == res.length ? 'PASS ' : 'FAIL ') + n + '/' + res.length)
  process.exit(n == res.length ? 0 : 1)
})()
