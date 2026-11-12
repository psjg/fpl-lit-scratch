// Toetst de fabula-strook in rot-beside.html en rot-replace.html, headless.
// Gebruik: CHROME=... node strip-check.cjs PW PAGINA RUN [SHOTDIR]
//   PAGINA: rot-beside.html | rot-replace.html, geladen als PAGINA?run=RUN
//   op 1200x900, donker. DATA (standaard web) is de map met RUN.fabula.json.
//   CHROME: Chrome for Testing (ms-playwright/chromium-*), niet de headless
//   shell: die laat de WebGL-laag van het iframe weg zodra de strook er
//   deels overheen ligt (minimap leeg, gemeten 11-12).
// De verwachting komt uit de fabula-JSON, niet uit de pagina. Het is de
// tegenhanger van gap-check.cjs: daar moest de wachtende aanroeper zijn
// kolom doortrekken; hier is dat de stapelkolom (replace) en de keten.
// Invarianten, per run van RUN (elk zijn profiel "· stappen"):
// 1. keten: per stap de framenamen van wortel tot blad uit speedscope ==
//    de keten van frame.parent in de fabula;
// 2. veeg op 18 px per stap: elke stap getekend, met als tekst een prefix
//    van "ln src" (tabs als vier spaties), afgekapt op de strookbreedte;
// 3. replace: per tekening de stapelkolommen == de aanroepen die [a, b)
//    raken, met diepte, begin en eind; de strook ligt precies over het
//    vlak onder de liniaal;
// 4. klik op een rij zet speedscope's selectie op zijn knoop; een selectie
//    van speedscope's kant markeert de rijen van die knoop;
// 5. buiten de chrono-view wijkt de strook, terug in de chrono-view komt
//    hij terug; geen paginafouten.
const fs = require('fs')
const [PW, PAGE, RUN, SHOTS] = process.argv.slice(2)
const {chromium} = require(PW)
const BASE = 'http://127.0.0.1:8792/', W = 1200, H = 900
const F = JSON.parse(fs.readFileSync(
  `${process.env.DATA || 'web'}/${RUN}.fabula.json`, 'utf8'))
const REPLACE = PAGE.includes('replace')

// --- verwachting -------------------------------------------------------------
// per run: tekst en keten per stap, en de aanroepen als [s, e) op diepte d,
// opgebouwd zoals tospeedscope.py: de open stapel wordt per stap gelijk
// gemaakt aan de keten van zijn frame
function verwacht(steps) {
  const fr = new Map()
  for (const s of steps) fr.set(s.f, s.frame)
  const keten = f => { const k = []
    for (let x = f; x != null; x = fr.get(x).parent) k.unshift(x)
    return k }
  const open = [], calls = []
  const rows = steps.map((s, i) => {
    const k = keten(s.f)
    let j = 0
    while (j < open.length && j < k.length && open[j].f === k[j]) j++
    while (open.length > j) { const o = open.pop(); o.e = i; calls.push(o) }
    for (; j < k.length; j++) open.push({f: k[j], d: j, s: i,
      name: fr.get(k[j]).name})
    return {t: String(s.ln).padStart(4) + ' ' +
      (s.src || '').replace(/\t/g, '    '),
      keten: k.map(f => fr.get(f).name)}
  })
  while (open.length) { const o = open.pop(); o.e = steps.length; calls.push(o) }
  return {rows, calls}
}

const res = []
const ok = (naam, goed, info) => {
  res.push(goed)
  console.log((goed ? 'ok   ' : 'FOUT ') + naam + ' ' + JSON.stringify(info))
}
// wacht tot de strook opnieuw getekend is
const rust = p => p.evaluate(() => new Promise(r =>
  requestAnimationFrame(() => requestAnimationFrame(r))))

;(async () => {
  const b = await chromium.launch({executablePath: process.env.CHROME})
  const p = await b.newPage({viewport: {width: W, height: H},
    colorScheme: 'dark'})
  const err = []
  p.on('pageerror', e => err.push(String(e)))
  // ALS=bestand: fabula-strip.js komt uit dat bestand (een kapotte kopie,
  // om te zien dat de toets rood wordt)
  if (process.env.ALS) await p.route('**/fabula-strip.js', r =>
    r.fulfill({path: process.env.ALS, contentType: 'text/javascript'}))
  await p.goto(`${BASE}${PAGE}?run=${RUN}`)
  await p.waitForFunction(() => window.fab && fab.rows, null,
    {timeout: 20000})
  const f = p.frames()[1]
  const namen = await f.evaluate(() =>
    profileGroupAtom.state.profiles.map(x => x.profile.getName()))

  const ketenMis = [], veegMis = [], kolMis = []
  let stappen = 0, tekeningen = 0, kolommen = 0
  for (const [call, steps] of Object.entries(F.runs)) {
    const E = verwacht(steps), idx = namen.indexOf(call + ' · stappen')
    await f.evaluate(i => profileGroupAtom.setProfileIndexToView(i), idx)
    await p.waitForFunction(n => fab.rows && fab.rows.length === n &&
      fab.maat === 'stappen', steps.length)
    // 1. keten
    const ket = await p.evaluate(() =>
      fab.rows.map(r => r.keten.map(o => o.n.frame.name)))
    ket.forEach((k, i) => {
      if (JSON.stringify(k) !== JSON.stringify(E.rows[i].keten))
        ketenMis.push({call, i, kreeg: k, wil: E.rows[i].keten})
    })
    // 2 en 3. veeg in vensters van 50 stappen, stap 40
    const seen = new Set()
    for (let x = 0; x < steps.length; x += 40) {
      await p.evaluate(x => fab.kijk(x, 900 / 18), x)
      await rust(p)
      const r = await p.evaluate(() => ({a: fab.a, b: fab.b, k: fab.k,
        tekst: fab.tekst, g: fab.getekend, kol: fab.kolommen}))
      tekeningen++
      for (const g of r.g) {
        seen.add(g.i)
        const w = E.rows[g.i].t
        if (!r.tekst || !g.t || g.t !== w.slice(0, g.t.length) ||
            g.t.length < Math.min(w.length, 30))
          veegMis.push({call, i: g.i, kreeg: g.t, wil: w, k: r.k})
      }
      if (REPLACE) {
        const key = c => c.d + ':' + c.s + '-' + c.e + ':' + c.name
        const wil = E.calls.filter(c => c.e > r.a && c.s < r.b).map(key)
          .sort()
        const kreeg = r.kol.map(key).sort()
        kolommen += kreeg.length
        if (JSON.stringify(wil) !== JSON.stringify(kreeg))
          kolMis.push({call, a: r.a, wil: wil.length, kreeg: kreeg.length,
            eerste: wil.find(x => !kreeg.includes(x)) ||
              kreeg.find(x => !wil.includes(x))})
      }
    }
    stappen += steps.length
    for (let i = 0; i < steps.length; i++)
      if (!seen.has(i)) veegMis.push({call, i, wat: 'niet getekend'})
  }
  const runs = Object.keys(F.runs).length
  ok('keten per stap == frame.parent-keten uit de fabula', !ketenMis.length,
    {runs, stappen, mis: ketenMis.length, eerste: ketenMis[0]})
  ok('veeg: elke stap getekend met zijn regel als tekst', !veegMis.length,
    {tekeningen, stappen, mis: veegMis.length, eerste: veegMis.slice(0, 2)})
  if (REPLACE)
    ok('veeg: stapelkolommen == aanroepen in beeld (diepte, begin, eind)',
      !kolMis.length && kolommen > 0,
      {kolommen, mis: kolMis.length, eerste: kolMis[0]})

  // terug naar de eerste run, midden in beeld
  await f.evaluate(() => profileGroupAtom.setProfileIndexToView(0))
  await p.waitForFunction(() => fab.rows && fab.maat === 'stappen')
  await p.evaluate(() => fab.kijk(20, 50))
  await rust(p)

  // 3. ligging: in replace ligt de strook over het vlak, tussen de liniaal
  // en het detailpaneel (als een selectie dat opent); in beide modi ligt
  // geen kopie van de detailtabellen onder de strook
  const ligging = async wanneer => {
    const l = await p.evaluate(() => {
      const d = f.contentDocument
      const c = [...d.querySelectorAll('canvas[class]')]
        .map(x => x.getBoundingClientRect())
        .sort((a, b) => b.height - a.height)[0]
      const tabs = [...d.querySelectorAll('._1gat8lj')]
      const eind = Math.min(c.bottom,
        ...tabs.map(t => t.getBoundingClientRect().top))
      const s = strip.getBoundingClientRect(), lin = fab.liniaal
      const onder = [...tab.children].filter(x => {
        const r = x.getBoundingClientRect()
        return r.left < s.right - .5 && r.right > s.left + .5 &&
          r.top < s.bottom - .5 && r.bottom > s.top + .5 })
      // rechtsom: iframe-y -> pagina-x = innerWidth - y
      return {s: [s.left, s.right, s.top, s.bottom],
        wil: [innerWidth - eind, innerWidth - c.top - lin, c.left, c.right],
        lin, tabellen: tabs.length, onder: onder.length}
    })
    if (REPLACE) {
      const d = Math.max(...l.s.map((v, i) => Math.abs(v - l.wil[i])))
      ok(`replace (${wanneer}): strook == vlak tussen liniaal en paneel`,
        d < 0.5 && l.lin > 0, {strook: l.s, wil: l.wil, liniaal: l.lin,
          tabellen: l.tabellen})
    }
    ok(`${wanneer}: geen detailtabel onder de strook`, !l.onder,
      {tabellen: l.tabellen, onder: l.onder})
    return l.tabellen
  }
  await ligging('voor de klik')

  // 4. klik -> selectie, en terug
  const doel = await p.evaluate(() => {
    const r = fab.rows.find(x => x.s >= fab.a + 10 && x.keten.length > 2)
    const s = strip.getBoundingClientRect()
    return {i: r.i, x: s.left + 40, y: fab.y((r.s + r.e) / 2)}
  })
  await p.mouse.click(doel.x, doel.y)
  await rust(p)
  const k1 = await p.evaluate(i => ({zelfde: fab.rows[i].n ===
    f.contentWindow.profileGroupAtom.getActiveProfile().chronoViewState
      .selectedNode, gekozen: fab.gekozen}), doel.i)
  ok('klik op een rij zet de selectie in speedscope', k1.zelfde &&
    k1.gekozen > 0, {rij: doel.i, ...k1})
  // het paneel komt na speedscope's render: wacht tot de kopieën er zijn
  await p.waitForFunction(() => tab.children.length > 0)
  await rust(p)
  const tabellen = await ligging('na de klik')
  ok('de klik opent het detailpaneel', tabellen > 0, {tabellen})
  if (SHOTS) await p.screenshot({path: `${SHOTS}/${PAGE.replace('.html',
    '')}-${RUN}-klik.png`})
  const k2 = await p.evaluate(() => {
    const r = fab.rows.filter(x => x.s >= fab.a && x.e <= fab.b)
      .find(x => x.n !== f.contentWindow.profileGroupAtom.getActiveProfile()
        .chronoViewState.selectedNode)
    f.contentWindow.profileGroupAtom.setSelectedNode('CHRONO', r.n)
    return {n: fab.rows.filter(x => x.n === r.n && x.e > fab.a &&
      x.s < fab.b).length}
  })
  await rust(p)
  const g2 = await p.evaluate(() => fab.gekozen)
  ok('selectie van speedscope markeert de rijen van die knoop',
    g2 === k2.n && g2 > 0, {gekozen: g2, wil: k2.n})

  // 5. buiten de chrono-view wijkt de strook
  const zicht = () => p.evaluate(() => {
    const r = strip.getBoundingClientRect()
    return getComputedStyle(strip).display != 'none' && r.width > 0 })
  await f.evaluate(() => viewModeAtom.set(1))
  await rust(p)
  const weg = !(await zicht())
  await f.evaluate(() => viewModeAtom.set(0))
  await rust(p)
  ok('strook wijkt buiten de chrono-view en komt terug', weg &&
    await zicht(), {weg})

  if (SHOTS) {
    const n = PAGE.replace('.html', '')
    await p.evaluate(() => fab.kijk(0, 1e9))
    await rust(p)
    await p.screenshot({path: `${SHOTS}/${n}-${RUN}-ver.png`})
    await p.evaluate(() => fab.kijk(20, 50))
    await rust(p)
    await p.screenshot({path: `${SHOTS}/${n}-${RUN}-dicht.png`})
  }
  ok('geen paginafouten', !err.length, {err})
  await b.close()
  const n = res.filter(Boolean).length
  console.log((n == res.length ? 'PASS ' : 'FAIL ') + n + '/' + res.length)
  process.exit(n == res.length ? 0 : 1)
})()
