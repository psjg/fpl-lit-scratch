// Screenshots van rot-a.html (linksom, de standaard) op drie zoomstanden:
// ver, cellen en ops. Gebruik: CHROME=... node rot-a-shot.cjs PW
const {chromium} = require(process.argv[2])
;(async () => {
  const b = await chromium.launch({executablePath: process.env.CHROME})
  const p = await b.newPage({viewport: {width: 1200, height: 900}})
  const fout = []
  p.on('pageerror', e => fout.push(String(e)))
  await p.goto('http://127.0.0.1:8792/rot-a.html')
  await p.waitForTimeout(500)
  const f = p.frames()[1]
  await f.waitForFunction(() => window.zui && zui.ready)
  await p.mouse.move(600, 450)
  for (const [n, klik] of [['ver', 0], ['cellen', 14], ['ops', 10]]) {
    for (let i = 0; i < klik; i++) await p.mouse.wheel(0, -120)
    await p.waitForTimeout(300)
    const s = await f.evaluate(() => ({k: zui.state.k, mode: zui.state.mode,
      ...zui.draw()}))
    await p.screenshot({path: `shots/rot-a-${n}.png`})
    console.log(n, s.mode, s.level, 'k', s.k.toFixed(1), 'teksten', s.texts)
  }
  console.log(fout.length ? 'FOUT ' + fout.join('; ') : 'geen paginafouten')
  await b.close()
})()
