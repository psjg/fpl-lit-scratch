// Kun je in rot-a.html langs beide assen bewegen? Wiel horizontaal en
// verticaal, en de pijltjes. Gebruik: CHROME=... node pan-check.cjs PW
const {chromium}=require(process.argv[2])
;(async()=>{const b=await chromium.launch({executablePath:process.env.CHROME})
const p=await b.newPage({viewport:{width:1200,height:900}});const err=[]
p.on('pageerror',e=>err.push(String(e)))
await p.goto('http://127.0.0.1:8792/rot-a.html');await p.waitForTimeout(500)
const f=p.frames()[1];await f.waitForFunction(()=>window.zui&&zui.ready)
const st=()=>f.evaluate(()=>({x0:zui.state.x0,y0:zui.state.y0,k:zui.state.k}))
await p.mouse.move(600,450);const a=await st()
await p.mouse.wheel(300,0);await p.waitForTimeout(200);const h=await st()
await p.mouse.wheel(0,300);await p.waitForTimeout(200);const v=await st()
await p.keyboard.press('ArrowRight');await p.keyboard.press('ArrowDown')
await p.waitForTimeout(200);const k=await st()
console.log(JSON.stringify({start:a,horiz:h,vert:v,keys:k}))
console.log(err.length?'FOUT '+err:'geen paginafouten')
await p.screenshot({path:'shots/rot-a-pan.png'});await b.close()})()
