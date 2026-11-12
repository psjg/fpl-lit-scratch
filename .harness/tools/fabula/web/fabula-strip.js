// De fabula-strook bij een gedraaide speedscope, voor rot-beside.html en
// rot-replace.html (<html data-mode=beside|replace>).
//
// Speedscope draait gedraaid in het iframe: de tijd loopt van boven naar
// onder (?ccw: van onder naar boven). De strook tekent de run als tekst op
// diezelfde as, één rij per stap (in υ één rij per op), gekleurd zoals
// speedscope het frame kleurt; links staat het syuzhet (de bron).
//
//   beside   de strook staat naast de flamegraph, die blijft zichtbaar.
//   replace  de strook ligt over het lichaam van de flamegraph; de liniaal
//            (klik = andere maat), de minimap en de detailtabellen blijven.
//            Rechts in de strook staat de aanroepstapel als smalle kolommen,
//            de wortel aan de kant van de liniaal, zodat de diepte die de
//            flamegraph liet zien niet verdwijnt. In de sandwich-view of een
//            maat zonder strook (μ, t) wijkt de strook en is de flamegraph
//            terug.
//
// Beide: klik op een rij zet de selectie in speedscope (PSJ 11-12), hover
// markeert de bronregel, wiel scrolt de tijd, ctrl/knijpen zoomt om de
// cursor, slepen pant. ?run=trace-lex (standaard) | stash-only kiest
// RUN.speedscope.json en RUN.fabula.json; een #hash gaat ongewijzigd naar
// speedscope. window.fab is de toegang voor de headless toetsen.
'use strict'
const MODE=document.documentElement.dataset.mode||'beside'
const Q=new URLSearchParams(location.search),ccw=Q.has('ccw')
if(ccw)document.body.classList.add('ccw')
const hash=location.hash||'#profileURL='+(Q.get('run')||'trace-lex')+
  '.speedscope.json'
const url=new URLSearchParams(hash.slice(1)).get('profileURL')
const fabula=url?fetch(url.replace(/\.speedscope\.json$/,'.fabula.json'))
  .then(r=>r.ok?r.json():null).catch(()=>null):Promise.resolve(null)
const f=document.getElementById('f'),strip=document.getElementById('strip')
const syu=document.getElementById('syu'),tab=document.getElementById('tab')

// iframe (x, y) -> pagina: rechtsom (W - y, x), linksom (y, H - x)
const pagina=r=>({left:ccw?r.top:innerWidth-r.bottom,
  top:ccw?innerHeight-r.right:r.left,width:r.height,height:r.width})

// De blokkentabellen (._1gat8lj, This/All Instances) zijn in het iframe
// onzichtbaar en staan als kopie rechtop in deze pagina, op de plek van het
// origineel: twee DOM-bomen, zodat er niets gedraaid hoeft te passen.
f.onload=()=>{
  const d=f.contentDocument,st=d.createElement('style')
  st.textContent='._1gat8lj{visibility:hidden}'
  d.head.append(st)
  let busy=0;const css=document.createElement('style')
  document.head.prepend(css)
  const sync=()=>{if(busy++)return;requestAnimationFrame(()=>{busy=0
    // speedscope zet zijn css via insertRule: kopieer de regels zelf.
    css.textContent=[...d.styleSheets].flatMap(x=>[...x.cssRules])
      .map(x=>x.cssText).join('\n')
    tab.style.font=getComputedStyle(d.body).font
    tab.replaceChildren(...[...d.querySelectorAll('._1gat8lj')].map(t=>{
      const c=t.cloneNode(true),p=pagina(t.getBoundingClientRect())
      Object.assign(c.style,{visibility:'visible',display:'grid'})
      for(const k in p)c.style[k]=p[k]+'px'
      return c}))
    // het paneel verschuift de strook in replace: opnieuw tekenen
    if(window.fab&&fab.plan)fab.plan()})}
  new MutationObserver(sync).observe(d.body,{subtree:true,childList:true,
    characterData:true,attributes:true})
  addEventListener('resize',sync)
  fabula.then(F=>F&&wacht(F))}
f.src='index.html'+hash

// Wacht tot speedscope zijn atoms op window zet (de regel die README.md
// noemt, in speedscope-H26NIAF6.js).
function wacht(F){
  const w=f.contentWindow
  if(!w.profileGroupAtom||!w.profileGroupAtom.getActiveProfile())
    return setTimeout(wacht,100,F)
  fab(F,w,w.profileGroupAtom)}

// Speedscope's kleur per frame: frames op (file||'')+name gesorteerd,
// emmer b = floor(255·i/n), dan het HCL-recept van het thema. De
// flamegraph (GL) leest b als byte round(255·(b+1)/256)/255, niet b/255.
const donker=matchMedia('(prefers-color-scheme:dark)').matches
function kleur(t){
  const tri=x=>2*Math.abs(x-Math.floor(x)-.5)-1,x=tri(30*t)
  // licht .25,.2,.8,.15: de GLSL-tekst rondt af met toFixed(1)
  const [C0,Cd,L0,Ld]=donker?[.2,.1,.2,.1]:[.3,.2,.8,.1]
  const C=C0+Cd*x,L=L0-Ld*x,h=360*.9*t/60,X=C*(1-Math.abs(h%2-1))
  const [r,g,b]=h<1?[C,X,0]:h<2?[X,C,0]:h<3?[0,C,X]:h<4?[0,X,C]
    :h<5?[X,0,C]:[C,0,X]
  const m=L-(.3*r+.59*g+.11*b),c=v=>Math.round(255*Math.min(1,
    Math.max(0,v+m)))
  return `rgb(${c(r)},${c(g)},${c(b)})`}

// Per profiel: elke aanroep als knoop [s, e) op de as met diepte d en kleur
// c, en elke stap als rij [s, e) met zijn diepste knoop o (zoals de
// chrono-flamechart hem uit forEachCall bouwt) en de keten van wortel tot o.
function leg(p,steps,maat){
  const iv=[],open=[]
  p.forEachCall((n,v)=>open.push({n,s:v,d:open.length}),
    (_,v)=>{const o=open.pop();o.e=v;iv.push(o)})
  const fr=[];p.forEachFrame(x=>fr.push(x))
  const k=x=>(x.file||'')+x.name
  fr.sort((a,b)=>k(a)>k(b)?1:-1)
  const emmer=new Map(fr.map((x,i)=>[x.key,Math.floor(255*i/fr.length)]))
  for(const o of iv)
    o.c=kleur(Math.round(255*((emmer.get(o.n.frame.key)||0)+1)/256)/255)
  let at=0
  const rows=steps.map((st,i)=>{
    const w=maat=='υ'?st.u:1,r={i,st,s:at,e:at+w},t=at+w/2;at+=w
    r.keten=iv.filter(o=>o.s<=t&&t<o.e).sort((a,b)=>a.d-b.d)
    r.o=r.keten[r.keten.length-1];r.n=r.o.n;r.c=r.o.c;return r})
  return {rows,iv,eind:at,diep:Math.max(...iv.map(o=>o.d))+1}}

// De strook en het syuzhet, gevoed door één abonnement op het atom.
function fab(F,w,A){
  const V=w.viewModeAtom,cx=strip.getContext('2d'),T=window.fab={mode:MODE}
  const vars=getComputedStyle(document.documentElement)
  const kl=n=>vars.getPropertyValue('--'+n).trim()
  let memo=null,hov=null,tik=null,cur=null,fold=new Set(),bron=null
  const stap=()=>{
    const st=A.getActiveProfile(),p=st.profile,naam=p.getName()
    const j=naam.lastIndexOf(' · '),steps=F.runs[naam.slice(0,j)]
    if(!steps)return null
    if(!memo||memo.p!==p)memo={p,...leg(p,steps,naam.slice(j+3)),
      maat:naam.slice(j+3),steps}
    return {st,...memo}}
  // Het pan-zoom-vlak (iframe-coördinaten): de hoogste canvas met een
  // klasse. Bovenin ligt de liniaal, één framehoogte (configruimte y = -1).
  const vlak=()=>[...f.contentDocument.querySelectorAll('canvas[class]')]
    .map(c=>c.getBoundingClientRect()).sort((a,b)=>b.height-a.height)[0]
  // Tijd op de as -> pagina-y, en terug.
  const as=(vp,r)=>{const k=r.width/vp.size.x,H=innerHeight
    return {k,y:t=>{const x=r.x+(t-vp.origin.x)*k;return ccw?H-x:x},
      t:y=>vp.origin.x+((ccw?H-y:y)-r.x)/k}}
  const bij=(rows,t)=>rows.find(r=>r.s<=t&&t<r.e)||null
  let rq=0
  const plan=()=>{if(!rq++)requestAnimationFrame(()=>{rq=0;teken()})}
  A.subscribe(plan);V.subscribe(plan);addEventListener('resize',plan)

  // replace: de strook over het lichaam van het vlak, onder de liniaal en
  // boven het detailpaneel (de tabellen die een selectie opent; het vlak
  // krimpt daar niet voor, het paneel ligt eroverheen)
  function leg_over(r,vp){
    const lin=r.height/vp.size.y,eind=Math.min(r.bottom,...[...f
      .contentDocument.querySelectorAll('._1gat8lj')]
      .map(t=>t.getBoundingClientRect().top))
    const p=pagina({top:r.top+lin,bottom:eind,left:r.left,right:r.right,
      height:eind-r.top-lin,width:r.width})
    for(const k in p)strip.style[k]=p[k]+'px'
    return lin}

  function teken(){
    const S=stap(),ok=S&&V.get()===0&&(S.maat=='stappen'||S.maat=='υ')
    document.body.classList.toggle('dicht',!ok)
    if(!S)return
    const c=S.st.chronoViewState,vp=c.configSpaceViewportRect,r=vlak()
    // hover in de flamegraph: de stap onder de muis
    let h=hov
    if(h==null&&ok&&c.hover&&r&&vp.size.x){
      const t=vp.origin.x+(c.hover.event.clientX-r.x)/(r.width/vp.size.x)
      h=bij(S.rows,t)}
    const sel=c.selectedNode,eigen=S.rows.filter(x=>x.n===sel)
    zet(S,h||(cur&&cur.n===sel?cur:eigen[0])||null)
    // nog niet opgemeten: later opnieuw
    if(!ok||!r||!vp.size.x)return ok&&setTimeout(plan,100)
    if(MODE=='replace')T.liniaal=leg_over(r,vp)
    const dpr=devicePixelRatio,Wd=strip.clientWidth,Hd=strip.clientHeight
    const oy=strip.getBoundingClientRect().top
    strip.width=Wd*dpr;strip.height=Hd*dpr;cx.setTransform(dpr,0,0,dpr,0,0)
    cx.fillStyle=kl('bg');cx.fillRect(0,0,Wd,Hd)
    const M=as(vp,r),k=M.k,tekst=k>=12,a=vp.origin.x,b=a+vp.size.x
    const fs=Math.min(13,Math.floor(k*.8))
    cx.font=`${fs}px ui-monospace,Menlo,monospace`;cx.textBaseline='middle'
    // replace: de stapelkolommen aan de wortelkant (rechtsom rechts)
    const DK=MODE=='replace'?Math.min(16,Math.floor(Wd*.3/S.diep)):0
    const kol=d=>ccw?d*DK:Wd-(d+1)*DK,x0=ccw?S.diep*DK+2:2
    const tw=Wd-S.diep*DK
    const cw=tekst?cx.measureText('M').width:7,rij=(t0,t1)=>{
      const y0=M.y(t0)-oy,y1=M.y(t1)-oy
      return [Math.min(y0,y1),Math.abs(y1-y0)]}
    // tekst of, onder 12 px per rij, een streep van zijn vorm
    const regel=(s,x,y,hh,kleur,max=x0+tw-2)=>{
      s=s.slice(0,Math.max(0,Math.floor((max-x)/cw)))
      if(tekst){cx.fillStyle=kleur;cx.fillText(s,x,y+hh/2);return s}
      const lead=s.length-s.trimStart().length
      cx.fillStyle=donker?'rgba(255,255,255,.3)':'rgba(0,0,0,.3)'
      cx.fillRect(x+lead*cw,y+hh*.2,(s.length-lead)*cw,Math.max(hh*.6,.5))
      return s}
    const src=x=>(x.st.src||'').replace(/\t/g,'    ')
    const ops=x0+tw*.5,getekend=[]
    let n=0,tikken=0,gekozen=0
    for(const x of S.rows){
      if(x.e<=a||x.s>=b)continue
      const [y,hh]=rij(x.s,x.e),g={i:x.i}
      cx.fillStyle=x.c;cx.fillRect(x0-2,y,tw,hh)
      if(S.maat=='stappen'){
        n++
        g.t=regel(String(x.st.ln).padStart(4)+' '+src(x),x0,y,hh,kl('fg'))
      }else{
        // υ: de bronregel op de eerste zichtbare rij, de ops eronder,
        // één per rij
        const v0=Math.max(x.s,Math.min(Math.ceil(a),x.e-1))
        const [y0,h0]=rij(v0,v0+1)
        g.t=regel(String(x.st.ln).padStart(4)+' '+src(x),x0,y0,h0,kl('fg'),
          ops-cw)
        for(let q=0;q<x.st.u;q++){
          if(x.s+q+1<=a||x.s+q>=b)continue
          n++
          const o=x.st.ops&&x.st.ops[q]
          if(!o)continue
          const [yq,hq]=rij(x.s+q,x.s+q+1)
          regel(o.op+(o.arg?' '+o.arg:''),ops,yq,hq,kl('fg'))}}
      getekend.push(g)
      if(x===h){cx.fillStyle=donker?'rgba(255,255,255,.15)':'rgba(0,0,0,.12)'
        cx.fillRect(x0-2,y,tw,hh)}
      if(x.n===sel){gekozen++;cx.strokeStyle=kl('sel');cx.lineWidth=2
        cx.strokeRect(x0-1,y+1,tw-2,Math.max(hh-2,0))}
      if(tik&&x.st.file===tik[0]&&x.st.ln===tik[1]){tikken++
        cx.fillStyle=kl('tik');cx.fillRect(x0-2,y,6,Math.max(hh,2))}}
    // de stapel: elke knoop in beeld als blok in de kolom van zijn diepte,
    // met zijn naam langs de tijd als die past (zoals de gedraaide
    // flamegraph); de geselecteerde krijgt een rand
    const kolommen=[]
    if(DK){cx.font=`${Math.min(11,DK-4)}px ui-monospace,Menlo,monospace`
      const nw=cx.measureText('M').width
      for(const o of S.iv){if(o.e<=a||o.s>=b)continue
        const [y,hh]=rij(o.s,o.e),x=kol(o.d),zy=Math.max(y,0)
        const zh=Math.min(y+hh,Hd)-zy
        cx.fillStyle=o.c;cx.fillRect(x,y,DK-1,Math.max(hh-1,.5))
        if(o.n===sel){cx.strokeStyle=kl('sel');cx.lineWidth=2
          cx.strokeRect(x+1,y+1,DK-3,Math.max(hh-3,0))}
        let s=o.n.frame.name;const m=Math.floor((zh-6)/nw)
        if(DK>=12&&m>=3){if(s.length>m)s=s.slice(0,m-1)+'…'
          cx.save();cx.translate(x+DK/2,zy+3);cx.rotate(Math.PI/2)
          cx.fillStyle=kl('fg');cx.fillText(s,0,0);cx.restore()}
        kolommen.push({d:o.d,s:o.s,e:o.e,name:o.n.frame.name})}}
    // beside: de hele spanne van de geselecteerde knoop, aan de rand
    if(!DK)for(const o of S.iv)if(o.n===sel){const [y,hh]=rij(o.s,o.e)
      cx.fillStyle=kl('sel');cx.fillRect(Wd-4,y,4,hh)}
    Object.assign(T,{rijen:n,tikken,gekozen,eind:S.eind,y:M.y,k,rows:S.rows,
      totaal:S.st.profile.getTotalWeight(),tekst,maat:S.maat,getekend,
      kolommen,a,b,DK})}

  // Syuzhet: de bron van het bestand van de huidige stap.
  function zet(S,x){
    const fi=x?x.st.file:S.steps[0].file
    if(bron!==fi+'|'+S.p.getName()){bron=fi+'|'+S.p.getName();bouw(S,fi)}
    syu.querySelector('.cur')?.classList.remove('cur')
    if(!x)return
    const el=syu.children[x.st.ln-1+voor(x.st.ln)]
    el.classList.add('cur')
    // alleen meescrollen als de regel wisselt, niet bij elke tekenbeurt
    if(T.cur!==bron+x.st.ln)el.scrollIntoView({block:'nearest'})
    T.cur=bron+x.st.ln}
  // aantal open dis-rijen boven regel ln
  const voor=ln=>[...syu.querySelectorAll('.d')]
    .filter(e=>+e.dataset.ln<ln).length
  function bouw(S,fi){
    const tel={},lines=F.files[fi].lines,dis=F.dis[fi]
    for(const s of S.steps)if(s.file===fi)tel[s.ln]=(tel[s.ln]||0)+1
    const max=Math.max(1,...Object.values(tel))
    syu.replaceChildren(...lines.map((l,i)=>{
      const ln=i+1,n=tel[ln]||0,e=document.createElement('div')
      e.dataset.ln=ln
      e.innerHTML=`<i>${dis[ln]?'▸':''}</i><b>${n?`<s style="width:${
        Math.max(2,30*n/max)}px"></s>${n}`:''}</b><u>${ln}</u>`
      e.append(l||' ');if(!n)e.classList.add('z')
      if(tik&&tik[0]===fi&&tik[1]===ln)e.classList.add('tik')
      e.onclick=ev=>{
        if(ev.target.tagName=='I'&&dis[ln])return vouw(e,fi,ln)
        syu.querySelector('.tik')?.classList.remove('tik')
        tik=tik&&tik[0]===fi&&tik[1]===ln?null:[fi,ln]
        if(tik)e.classList.add('tik');plan()}
      return e}))
    for(const k of fold){const [g,ln]=k.split('|').map(Number)
      if(g===fi)vouw(syu.children[ln-1+voor(ln)],fi,ln,1)}}
  // de statische disassembly als vouw onder een bronregel
  function vouw(e,fi,ln,her){
    const open=e.nextSibling&&e.nextSibling.dataset.ln==ln+.5
    if(open&&!her){fold.delete(fi+'|'+ln);e.firstChild.textContent='▸'
      while(e.nextSibling&&e.nextSibling.dataset.ln==ln+.5)
        e.nextSibling.remove();return}
    fold.add(fi+'|'+ln);e.firstChild.textContent='▾'
    e.after(...F.dis[fi][ln].map(([off,op,arg])=>{
      const d=document.createElement('div');d.className='d'
      d.dataset.ln=ln+.5;d.textContent=`${off} ${op} ${arg}`;return d}))}

  // Het beeld langs de tijd zetten, met speedscope's eigen Rect en Vec2;
  // de diepte (y) blijft. Hooguit 60 px per eenheid, hooguit de hele run
  // in beeld, en het begin binnen [0, totaal - breedte]. Met t blijft dat
  // tijdstip op zijn plek in beeld, ook als de breedte hier wordt begrensd
  // (x telt dan niet).
  function kijk(x,wd,t){const S=stap(),vp=S.st.chronoViewState
    .configSpaceViewportRect,r=vlak(),tot=S.st.profile.getTotalWeight()
    wd=Math.min(tot,Math.max(r.width/60,wd))
    if(t!=null)x=t-(t-vp.origin.x)*wd/vp.size.x
    x=Math.min(Math.max(0,x),tot-wd)
    const R=vp.constructor,V2=vp.origin.constructor
    A.setConfigSpaceViewportRect('CHRONO',
      new R(new V2(x,vp.origin.y),new V2(wd,vp.size.y)))}
  const nu=()=>{const S=stap(),vp=S.st.chronoViewState
    .configSpaceViewportRect;return {S,vp,M:as(vp,vlak())}}

  // strook: hover markeert de bron, klik zet de selectie in speedscope
  const onder=ev=>{const S=stap(),r=vlak()
    if(!S||!r)return null
    const vp=S.st.chronoViewState.configSpaceViewportRect
    return bij(S.rows,as(vp,r).t(ev.clientY))}
  // wiel: scrollen loopt door de tijd, ctrl (knijpen) zoomt om de cursor
  strip.addEventListener('wheel',e=>{e.preventDefault()
    const {vp,M}=nu(),dy=e.deltaY*(e.deltaMode==1?16:1)
    if(e.ctrlKey||e.metaKey){const t=M.t(e.clientY),z=Math.exp(dy*.01)
      kijk(0,vp.size.x*z,t);return}
    kijk(vp.origin.x+(ccw?-1:1)*dy/M.k,vp.size.x)},{passive:false})
  // slepen pant; een sleep van meer dan 3 px is geen klik
  let sleep=null
  strip.onpointerdown=e=>{strip.setPointerCapture(e.pointerId)
    sleep={x0:e.clientX,y0:e.clientY,x:nu().vp.origin.x,ver:0}}
  strip.onpointermove=e=>{
    if(!sleep){hov=onder(e);plan();return}
    const {vp,M}=nu(),dy=e.clientY-sleep.y0
    sleep.ver=Math.max(sleep.ver,Math.hypot(e.clientX-sleep.x0,dy))
    if(sleep.ver>3){strip.classList.add('drag')
      kijk(sleep.x-(ccw?-1:1)*dy/M.k,vp.size.x)}}
  strip.onpointerup=e=>{const s=sleep;sleep=null
    strip.classList.remove('drag')
    if(s&&s.ver<=3){const x=onder(e);if(!x)return
      cur=x;A.setSelectedNode('CHRONO',x.n);plan()}}
  strip.onpointercancel=()=>{sleep=null;strip.classList.remove('drag')}
  strip.onmouseleave=()=>{hov=null;plan()}
  T.kijk=kijk;T.plan=plan
  plan()}
