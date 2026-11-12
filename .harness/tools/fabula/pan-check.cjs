// Kun je in een gedraaide pagina langs de assen bewegen? Wiel horizontaal
// en verticaal, de pijltjes, en voor de strookpagina's ook ctrl+wiel en
// slepen op de strook.
// Gebruik: CHROME=... node pan-check.cjs PW [PAGINA] [SHOTDIR]
//   PAGINA: rot-a.html (standaard; leest window.zui) of rot-beside.html /
//   rot-replace.html (leest speedscope's chrono-beeld: x0 = begin op de
//   tijdas, y0 = diepte, w = breedte in stappen). SHOTDIR: standaard shots.
const {chromium}=require(process.argv[2])
const PAGE=process.argv[3]||'rot-a.html',SHOTS=process.argv[4]||'shots'
;(async()=>{const b=await chromium.launch({executablePath:process.env.CHROME})
const p=await b.newPage({viewport:{width:1200,height:900},colorScheme:'dark'})
const err=[],res=[]
p.on('pageerror',e=>err.push(String(e)))
const ok=(naam,goed,info)=>{res.push(goed)
  console.log((goed?'ok   ':'FOUT ')+naam+' '+JSON.stringify(info))}
await p.goto('http://127.0.0.1:8792/'+PAGE);await p.waitForTimeout(500)
const f=p.frames()[1],zui=PAGE=='rot-a.html'
let st,mx=600,my=450
if(zui){await f.waitForFunction(()=>window.zui&&zui.ready)
  st=()=>f.evaluate(()=>({x0:zui.state.x0,y0:zui.state.y0,k:zui.state.k}))
}else{await p.waitForFunction(()=>window.fab&&fab.rows)
  await p.evaluate(()=>fab.kijk(20,50))
  // replace legt de strook pas bij een tekening op zijn plek: wacht daarop
  await p.waitForFunction(()=>fab.a===20&&strip.getBoundingClientRect()
    .width>0)
  st=()=>f.evaluate(()=>{const v=profileGroupAtom.getActiveProfile()
    .chronoViewState.configSpaceViewportRect
    return {x0:v.origin.x,y0:v.origin.y,w:v.size.x}})
  const r=await p.evaluate(()=>strip.getBoundingClientRect().toJSON())
  mx=r.left+r.width/2;my=r.top+r.height/2}
await p.mouse.move(mx,my);const a=await st()
await p.mouse.wheel(300,0);await p.waitForTimeout(200);const h=await st()
await p.mouse.wheel(0,300);await p.waitForTimeout(200);const v=await st()
await p.keyboard.press('ArrowRight');await p.keyboard.press('ArrowDown')
await p.waitForTimeout(200);const k=await st()
console.log(JSON.stringify({start:a,horiz:h,vert:v,keys:k}))
if(!zui){
  ok('wiel op de strook loopt door de tijd',v.x0>h.x0&&v.w==h.w,
    {voor:h.x0,na:v.x0})
  // het tijdstip onder de cursor, uit het laatst getekende beeld (rechtsom)
  const onder=()=>p.evaluate(y=>(y-fab.y(0))/fab.k,my)
  const zoom=async()=>{await p.keyboard.down('Control')
    await p.mouse.wheel(0,-100);await p.keyboard.up('Control')
    await p.waitForTimeout(200)}
  const t0=await onder()
  await zoom()
  const z=await st(),t1=await onder()
  ok('ctrl+wiel zoomt in om de cursor',z.w<k.w&&Math.abs(t1-t0)<1e-6,
    {voor:k.w,na:z.w,t:[t0,t1]})
  // op de smalste breedte mag verder inzoomen het beeld niet meer schuiven
  await p.evaluate(()=>fab.kijk(20,0));await p.waitForTimeout(200)
  const m=await st();await zoom();const m1=await st()
  ok('ctrl+wiel op de smalste breedte laat het beeld staan',
    m1.w==m.w&&Math.abs(m1.x0-m.x0)<1e-9,{voor:m,na:m1})
  await p.evaluate(([a,b])=>fab.kijk(a,b),[z.x0,z.w])
  await p.waitForTimeout(200)
  await p.mouse.move(mx,my);await p.mouse.down()
  await p.mouse.move(mx,my-60);await p.mouse.move(mx,my-120)
  await p.mouse.up();await p.waitForTimeout(200)
  const s=await st()
  ok('slepen op de strook pant de tijd, zonder te zoomen',s.x0>z.x0&&
    Math.abs(s.w-z.w)<1e-9,{voor:z.x0,na:s.x0})
  // een zijwaartse sleep is ook een sleep: hij kiest geen rij
  const g=await p.evaluate(()=>fab.gekozen)
  await p.mouse.move(mx,my);await p.mouse.down()
  await p.mouse.move(mx+50,my);await p.mouse.move(mx+100,my)
  await p.mouse.up();await p.waitForTimeout(300)
  const g1=await p.evaluate(()=>fab.gekozen)
  ok('zijwaarts slepen is geen klik',g1==g,{voor:g,na:g1})}
ok('geen paginafouten',!err.length,{err})
// rot-beside.html?run=stash-only -> rot-beside-stash-only-pan.png
await p.screenshot({path:`${SHOTS}/${PAGE.replace('.html','')
  .replace('?run=','-')}-pan.png`})
await b.close()
const n=res.filter(Boolean).length
console.log((n==res.length?'PASS ':'FAIL ')+n+'/'+res.length)
process.exit(n==res.length?0:1)})()
