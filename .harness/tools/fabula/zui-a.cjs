// Toetst zui-a.html (variant A, semantische zoom in de blokken), headless.
// Gebruik: CHROME=... node zui-a.cjs PW BASE SHOTDIR (BASE = http://127.0.0.1:8792)
// Verwachtingen komen uit de fabula-json, hier in node gelezen, niet uit de
// pagina. Invarianten:
// 1. ver: alleen blokken, één run-blok per run, geen stapcellen;
// 2. cellen: per tekening precies de stappen in beeld, elk één keer; een
//    veeg over de hele as tekent elke stap: unie == N;
// 3. sprong stap -> υ en terug: het stap-punt onder de cursor blijft staan,
//    en één wielklik terug over de grens flapt niet;
// 4. ops: per stap volledig in beeld ops-cellen == len(ops) (of u zonder
//    ops); een veeg over de hele υ-as geeft per stap precies die cellen;
// 5. tekst staat alleen in dozen van ≥ 11 px breed en hoog.
const [pw, base, shots] = process.argv.slice(2)
const {chromium} = require(pw)
const http = require('http')
const out = [], fout = []
const ok = (naam, cond, info) => {
  out.push({naam, ok: !!cond, info})
  if (!cond) fout.push(naam)
}
const get = url => new Promise((res, rej) => http.get(url, r => {
  let b = ''
  r.setEncoding('utf8')
  r.on('data', c => (b += c))
  r.on('end', () => res(JSON.parse(b)))
}).on('error', rej))

// verwacht per stap: aantal op-cellen; plus N en het aantal runs
async function verwacht(run) {
  const F = await get(`${base}/${run}.fabula.json`)
  const ops = [], runs = Object.values(F.runs)
  for (const st of runs) for (const s of st)
    ops.push(s.ops ? s.ops.length : s.u)
  const synth = []
  let i = 0
  for (const st of runs) for (const s of st) {
    if (!s.ops && s.synth) synth.push(i)
    i++
  }
  return {N: ops.length, ops, runs: runs.length, synth}
}

async function open(run) {
  const b = await chromium.launch({executablePath: process.env.CHROME})
  const p = await b.newPage({viewport: {width: 1600, height: 1000}})
  p.on('pageerror', e => fout.push('pageerror ' + e))
  const url = `${base}/zui-a.html${run ? '?run=' + run : ''}`
  // 8792's http.server laat soms een laad vallen: één keer opnieuw
  for (let k = 0; ; k++) {
    await p.goto(url)
    const klaar = await p.waitForFunction(() => window.zui && zui.ready,
      null, {timeout: 15000}).then(() => true, () => false)
    if (klaar) break
    if (k) throw new Error('zui-a.html laadt niet')
  }
  return {b, p}
}

const st = p => p.evaluate(() => ({...zui.state, last: zui.draw()}))

// de stappen die [a, b) raakt, onafhankelijk van de pagina uitgerekend
function inBeeld(s) {
  const L = s.last
  if (s.mode !== 'S') return null
  return [Math.max(0, Math.floor(L.a)), Math.min(s.N, Math.ceil(L.b))]
}

function cellenKloppen(s, naam) {
  const c = s.last.cells, [i0, i1] = inBeeld(s)
  const uniek = new Set(c).size === c.length
  const zelfde = c.length === i1 - i0 && c.every((x, j) => x === i0 + j)
  ok(naam, uniek && zelfde && s.last.level === 'cellen',
    {level: s.last.level, cellen: c.length, verwacht: i1 - i0, i0, i1,
      k: +s.k.toFixed(2)})
}

// υ-modus: per getekende stap ops-cellen == de op-plekken die [a, b) raakt
// (uit de verwachting); voor een stap volledig in beeld is dat len(ops) of u
async function opsKloppen(p, s, E, naam) {
  const v = await p.evaluate(() => {
    const L = zui.last, r = []
    for (const [i, n] of Object.entries(L.ops)) r.push([+i, n, zui.toU(+i)])
    return {r, a: zui.last.a, b: zui.last.b}
  })
  let vol = 0, deel = 0
  const fout_ = []
  for (const [i, n, u0] of v.r) {
    let wil = 0
    for (let q = 0; q < E.ops[i]; q++)
      if (u0 + q + 1 > v.a && u0 + q < v.b) wil++
    if (wil === E.ops[i]) vol++
    else deel++
    if (n !== wil) fout_.push({i, n, wil, totaal: E.ops[i]})
  }
  ok(naam, s.mode === 'U' && v.r.length >= 1 && !fout_.length,
    {mode: s.mode, pxPerU: +s.k.toFixed(1), volleStappen: vol,
      deelsInBeeld: deel, fout: fout_.slice(0, 5)})
}

// veeg over de hele as op zoom k in modus m; telt cellen en (in U) ops
async function veeg(p, m, k) {
  return p.evaluate(([m, k]) => {
    const S = zui.state, T = m === 'S' ? S.N : S.UT, span = S.W / k
    const cellen = new Set(), ops = {}
    let dubbel = 0, tekst = Infinity, n = 0
    for (let x0 = 0; x0 < T; x0 += span * 0.9) {
      const L = zui.set({mode: m, k, x0})
      if (L.mode !== m) return {fout: 'modus ' + L.mode}
      n++
      if (new Set(L.cells).size !== L.cells.length) dubbel++
      for (const i of L.cells) cellen.add(i)
      for (const [i, q] of Object.entries(L.opq || {}))
        for (const x of q) (ops[i] || (ops[i] = new Set())).add(x)
      tekst = Math.min(tekst, L.minText)
    }
    const per = {}
    for (const [i, s] of Object.entries(ops)) per[i] = s.size
    return {tekeningen: n, cellen: cellen.size, dubbel, per, tekst}
  }, [m, k])
}

async function wiel(p, x, y, dy) {
  await p.mouse.move(x, y)
  await p.mouse.wheel(0, dy)
  await p.waitForTimeout(30)
}

async function main() {
  const E = await verwacht('trace-lex')
  const {b, p} = await open()
  // 1. ver
  let s = await st(p)
  ok('ver: alleen namen, één blok per run, geen cellen',
    s.last.level === 'namen' && s.last.runBlocks === E.runs &&
    s.N === E.N && s.last.cells.length === 0 && s.last.minText >= 11,
    {level: s.last.level, runBlokken: s.last.runBlocks, runs: E.runs,
      N: s.N, blokken: s.last.blocks, pxPerStap: +s.k.toFixed(2)})
  await p.screenshot({path: `${shots}/zui-a-1.png`})

  // doel: een synth-stap midden in de as, met een stap met ops ervoor
  const doel = E.synth.find(i => i > E.N * 0.45 && E.ops[i - 1])
  const cx = await p.evaluate(i => (i - zui.state.x0) * zui.state.k, doel)
  const cy = 300
  // 2. middel: echt wiel tot ≥ 70 px per stap
  const anker = []
  for (let n = 0; n < 200; n++) {
    s = await st(p)
    if (s.mode === 'S' && s.k >= 70) break
    const voor = await p.evaluate(x => zui.at(x), cx)
    await wiel(p, cx, cy, -100)
    const na = await p.evaluate(x => zui.at(x), cx)
    anker.push(Math.abs(na - voor) * (await p.evaluate(() =>
      zui.state.mode === 'S' ? zui.state.k : zui.state.k * zui.state.MEAN)))
  }
  ok('wiel om de cursor: het stap-punt eronder blijft (< 1 px)',
    Math.max(...anker) < 1, {wielklikken: anker.length,
      maxAfwijkingPx: Math.max(...anker)})
  s = await st(p)
  cellenKloppen(s, 'middel: cellen == stappen in beeld, elk één keer')
  ok('middel: tekst alleen ≥ 11 px', s.last.texts > 0 &&
    s.last.minText >= 11, {teksten: s.last.texts, min: s.last.minText})
  await p.screenshot({path: `${shots}/zui-a-2.png`})
  const middel = {mode: s.mode, k: s.k, x0: s.x0}
  const vs = await veeg(p, 'S', 70)
  ok('veeg in stappen: unie stapcellen == N, geen dubbele per tekening',
    vs.cellen === E.N && vs.dubbel === 0 && vs.tekst >= 11,
    {tekeningen: vs.tekeningen, cellen: vs.cellen, N: E.N,
      dubbel: vs.dubbel, minTekst: vs.tekst})
  await p.evaluate(v => zui.set(v), middel)

  // 3. sprong naar υ, anker over de grens
  let sprong = null
  for (let n = 0; n < 200; n++) {
    s = await st(p)
    if (s.mode === 'U' && s.k >= 32) break
    const voor = await p.evaluate(x => zui.at(x), cx)
    const m0 = s.mode
    await wiel(p, cx, cy, -100)
    const na = await p.evaluate(x => ({t: zui.at(x), ...zui.state}), cx)
    if (m0 === 'S' && na.mode === 'U')
      sprong = {voor, na: na.t, px: Math.abs(na.t - voor) * na.k * na.MEAN}
  }
  ok('sprong stap -> υ: stap-punt onder de cursor blijft (< 1 px)',
    sprong && sprong.px < 1, sprong)
  s = await st(p)
  await opsKloppen(p, s, E, 'diep: ops-cellen per stap == op-plekken in beeld (vol: len(ops) of u)')
  await p.screenshot({path: `${shots}/zui-a-3.png`})
  const diep = {mode: s.mode, k: s.k, x0: s.x0}

  // geen flap: uitzoomen tot S, dan één klik in blijft S
  let terug = null
  for (let n = 0; n < 50; n++) {
    await wiel(p, cx, cy, 100)
    s = await st(p)
    if (s.mode === 'S') { terug = s.k; break }
  }
  await wiel(p, cx, cy, -100)
  s = await st(p)
  ok('hysterese: terug naar stap bij < 150 px/stap, één klik in flapt niet',
    terug !== null && terug < 150 && s.mode === 'S',
    {terugBij: terug && +terug.toFixed(1), naKlikIn: s.mode,
      k: +s.k.toFixed(1)})
  await p.evaluate(v => zui.set(v), diep)

  // 4. diepst
  for (let n = 0; n < 200; n++) {
    s = await st(p)
    if (s.mode === 'U' && s.k >= 125) break
    await wiel(p, cx, cy, -100)
  }
  s = await st(p)
  await opsKloppen(p, s, E,
    'diepst: ops-cellen per stap == op-plekken in beeld (vol: len(ops) of u)')
  ok('diepst: tekst alleen ≥ 11 px', s.last.texts > 0 &&
    s.last.minText >= 11, {teksten: s.last.texts, min: s.last.minText})
  await p.screenshot({path: `${shots}/zui-a-4.png`})
  const vu = await veeg(p, 'U', 125)
  const mis = E.ops.map((n, i) => [i, n, vu.per[i] || 0])
    .filter(([, n, m]) => n !== m)
  ok('veeg in υ: per stap ops-cellen == len(ops) of u, alle N stappen',
    !vu.fout && mis.length === 0 && Object.keys(vu.per).length === E.N,
    {tekeningen: vu.tekeningen, stappen: Object.keys(vu.per).length,
      somCellen: Object.values(vu.per).reduce((a, x) => a + x, 0),
      somVerwacht: E.ops.reduce((a, x) => a + x, 0), mis: mis.slice(0, 5)})
  // slepen pant: 200 px naar links = x0 + 200/k; ctrl+wiel (pinch) zoomt
  {
    const v = await p.evaluate(() => zui.set({mode: 'S', k: 40, x0: 300}))
    await p.mouse.move(800, 500)
    await p.mouse.down()
    await p.mouse.move(700, 500)
    await p.mouse.move(600, 500)
    const tijdens = await p.evaluate(() => c.classList.contains('drag'))
    await p.mouse.up()
    await p.waitForTimeout(50)
    const n = await p.evaluate(() => ({...zui.state,
      drag: c.classList.contains('drag')}))
    const px = Math.abs((n.x0 - v.x0) * n.k - 200)
    ok('slepen pant x0 met 200/k, sleepklasse aan en weer uit',
      px < 0.5 && tijdens && !n.drag, {afwijkingPx: px, tijdens,
        na: n.drag})
    await p.keyboard.down('Control')
    await p.mouse.wheel(0, -50)
    await p.keyboard.up('Control')
    await p.waitForTimeout(50)
    const z = await p.evaluate(() => zui.state.k)
    ok('ctrl+wiel (pinch in Chromium) zoomt in', z > n.k * 1.3,
      {voor: n.k, na: +z.toFixed(2)})
  }
  await b.close()

  // 5. stash-only
  {
    // diepte uit frame.parent: hier in node uit de fabula-json herleid,
    // per frame diepte(ouder)+1, wortel (parent null) op 1
    const F = await get(`${base}/trace-lex.fabula.json`)
    const wil = []
    for (const st of Object.values(F.runs)) {
      const d = new Map()
      for (const s of st) if (!d.has(s.f)) {
        const p = s.frame.parent
        d.set(s.f, p == null ? 1 : d.get(p) + 1)
        wil.push(s.frame.name + '@' + d.get(s.f))
      }
    }
    const {b, p} = await open()
    const rows = await p.evaluate(() => zui.rows)
    const heb = rows.slice(1).flat().sort((x, y) => x.s - y.s || x.d - y.d)
      .map(x => x.name + '@' + x.d)
    const mis = wil.filter((w, i) => w !== heb[i])
    const span = rows.slice(1).flat().filter(x => x.name === 'Lines.span')
    ok('diepte = keten van frame.parent, geen gok',
      heb.length === wil.length && mis.length === 0 &&
      span.filter(x => x.d === 1).length === 2,
      {frames: wil.length, blokken: heb.length, mis: mis.slice(0, 3),
        spanDiepte: span.map(x => x.d)})
    const r0 = await p.evaluate(() => (zui.set({mode: 'S', k: 300}), zui.ROW))
    const r1 = await p.evaluate(() => (zui.set({mode: 'U', k: 40}), zui.ROW))
    ok('rijhoogte gelijk in stap en υ', r0 === r1, {stap: r0, u: r1})
    await b.close()
  }
  {
    const E2 = await verwacht('stash-only')
    const {b, p} = await open('stash-only')
    const s = await st(p)
    ok('stash-only: N en één run-blok', s.N === E2.N &&
      s.last.runBlocks === 1, {N: s.N, wil: E2.N})
    const a = await veeg(p, 'S', 70), u = await veeg(p, 'U', 125)
    const mis = E2.ops.filter((n, i) => n !== (u.per[i] || 0)).length
    ok('stash-only: veeg stappen == N, veeg ops == len(ops) of u',
      a.cellen === E2.N && a.dubbel === 0 && mis === 0,
      {cellen: a.cellen, mis})
    await b.close()
  }
  for (const r of out)
    console.log((r.ok ? 'ok   ' : 'FOUT ') + r.naam + ' ' +
      JSON.stringify(r.info))
  const n = out.filter(r => r.ok).length
  console.log(fout.length ? `FOUT ${n}/${out.length}: ${fout.join('; ')}`
    : `PASS ${n}/${out.length}`)
  process.exit(fout.length ? 1 : 0)
}
main()
