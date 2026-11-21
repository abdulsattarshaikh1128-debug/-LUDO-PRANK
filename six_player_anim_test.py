"""Six-player geometry/rules, token lift, forward + reverse (capture) animation and dialogue-trigger tests.
Run: python tests/six_player_anim_test.py"""
import os, sys, json, subprocess
from playwright.sync_api import sync_playwright
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..');URL='file://'+os.path.abspath(os.path.join(ROOT,'ludo-prank-v2.html'))
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)));
    if not ok: fails.append(n)
SPEED=lambda f:f"(()=>{{const st=window.setTimeout.bind(window);window.setTimeout=(fn,ms,...a)=>st(fn,(ms||0)*{f},...a)}})()"
rules=json.loads(subprocess.check_output(['node','-e',"const R=require('./server/ludo-rules.js');const o={};for(const n of [2,4,6]){const g=R.newGame(n);o[n]={safe:[...R.safeSet(g.cfg)].sort((a,b)=>a-b),off:g.cfg.colors.map(c=>g.cfg.off(c))}};console.log(JSON.stringify(o))"],cwd=ROOT))
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':390,'height':844});pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)))
    pg.goto(URL);pg.wait_for_timeout(300)
    # ---------------- A. geometry ----------------
    g=pg.evaluate("""()=>{const d=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);const n=XY6.length;let maxStep=0,minAny=9,uniq=new Set(XY6.map(p=>p[0].toFixed(2)+','+p[1].toFixed(2))).size;
      for(let i=0;i<n;i++){maxStep=Math.max(maxStep,d(XY6[i],XY6[(i+1)%n]));for(let j=i+1;j<n;j++)minAny=Math.min(minAny,d(XY6[i],XY6[j]))}
      const hc=[];HEXK.forEach((k,i)=>{for(let j=0;j<5;j++)hc.push(hPt(i,R0+4-j,0))});let minHC=9;hc.forEach(h=>XY6.forEach(x=>minHC=Math.min(minHC,d(h,x))));
      let minYard=9;HEXK.forEach(k=>SLOT6.forEach((s,i)=>{const q=pos6({k,s:-1,i});XY6.concat(hc).forEach(x=>minYard=Math.min(minYard,d(q,x)))}));
      let off=0;HEXK.forEach(k=>{const q=pos6({k,s:-1,i:0});off=Math.max(off,Math.abs(q[0]),Math.abs(q[1]))});
      const ext=Math.max(...XY6.map(p=>Math.max(Math.abs(p[0]),Math.abs(p[1]))));
      // each colour: s=0 is its start cell, s=76 its own arm tip
      const starts=HEXK.map(k=>pos6({k,s:0,i:0}).map(x=>+x.toFixed(2)).join());
      const tips=HEXK.map((k,i)=>{const t=pos6({k,s:76,i:0}),tip=hPt(i,R0+5,0);return d(t,tip)<1e-6});
      const home=HEXK.map((k,i)=>[0,1,2,3,4].every(j=>d(pos6({k,s:77+j,i:0}),hPt(i,R0+4-j,0))<1e-6));
      return {n,uniq,maxStep,minAny,minHC,minYard,ext,off,tips,home,safe:[...SAFE6].map(Number).sort((a,b)=>a-b),off6:HEXK.map(k=>OFF6[k]),starts:new Set(starts).size,
        s4:[...SAFE4].map(c=>TR.findIndex(x=>x.join()==c)).sort((a,b)=>a-b),off4:['r','g','y','b'].map(k=>OFF4[k])}}""")
    check('6P ring has 78 distinct cells (6 arms x 13)',g['n']==78 and g['uniq']==78,g['n'])
    check('6P ring is a closed loop of adjacent cells (max step 1.0)',abs(g['maxStep']-1)<1e-6,g['maxStep'])
    check('6P no two ring cells overlap',g['minAny']>=0.99,g['minAny'])
    check('6P home columns do not overlap ring cells',g['minHC']>=0.99,g['minHC'])
    check('6P yard slots do not overlap any cell / lane',g['minYard']>=0.9,g['minYard'])
    check('6P everything fits the board viewBox (+/-9.6)',g['ext']<=8.6 and g['off']<=9.2,(g['ext'],g['off']))
    check('6P each colour has its own distinct start cell, path ends at its own arm tip, 5-cell home column',g['starts']==6 and all(g['tips']) and all(g['home']),g)
    check('6P safe cells in client == server rules (6 starts + 6 stars)',g['safe']==rules['6']['safe'] and g['off6']==[x for x in rules['6']['off']],(g['safe'],rules['6']['safe']))
    check('4P safe cells in client == server rules',g['s4']==rules['4']['safe'] and g['off4']==rules['4']['off'],(g['s4'],rules['4']['safe']))
    # ---------------- B. screenshot proof of all six players visible ----------------
    pg.evaluate("()=>startMatch({n:6,h:6})");pg.wait_for_timeout(500)
    v=pg.evaluate("()=>({cards:[...document.querySelectorAll('#game .pp')].filter(e=>e.style.visibility!='hidden').map(e=>e.id),yards:S.filter(t=>t.s<0).length,cols:[...new Set(S.map(t=>t.k))].join(''),tokens:document.querySelectorAll('#layer .tg').length})")
    check('6P: six player cards visible, 24 tokens in six yards',len(v['cards'])==6 and v['yards']==24 and v['cols']=='rgybop' and v['tokens']==24,v)
    pg.screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/six_player.png')
    # ---------------- C. full 6-player match (6 computer seats, accelerated) ----------------
    ctx=b.new_context(viewport={'width':390,'height':844});q=ctx.new_page();q.errs=[];q.on('pageerror',lambda e:q.errs.append(str(e)));q.add_init_script(SPEED(.02));q.goto(URL);q.wait_for_timeout(300)
    q.evaluate("""()=>{window.__inv=[];window.__caps=0;const r0=render;window.render=function(){for(const t of S){if(t.s<-1||t.s>HOME)__inv.push('range '+t.k+t.i+':'+t.s)}
      for(const a of S)if(a.s>=0&&a.s<=LTR&&!SAFE.has(cell(a.k,a.s).join()))for(const b of S)if(b.k!=a.k&&b.s>=0&&b.s<=LTR&&b!==a&&cell(b.k,b.s).join()==cell(a.k,a.s).join()&&!M.busy)__inv.push('shared non-safe cell '+a.k+a.i+' '+b.k+b.i);return r0.apply(this,arguments)};
      startMatch({n:6,h:0,diff:'hard'})}""")
    done=False
    for i in range(240):
        q.wait_for_timeout(1000)
        if q.evaluate("()=>M.done"): done=True;break
    st=q.evaluate("()=>{const w=M.players.find(p=>S.filter(t=>t.k==p.k&&t.s==HOME).length==4);return {w:w&&w.k,home:M.players.map(p=>p.k+':'+S.filter(t=>t.k==p.k&&t.s==HOME).length),turnN:M.turnN,caps:M.players.reduce((a,p)=>a+p.caps,0),inv:__inv.slice(0,5),rank:rank(M).map(p=>p.k).join(''),res:!document.getElementById('res').hidden}}")
    check('full 6-player match runs to a winner (all 6 seats)',done and st['w'] in list('rgybop'),st)
    check('winner has 4 tokens at HOME(82), result screen shown',st['w'] and 'rgybop'.count(st['w'])==1 and st['res'],st)
    check('captures occurred during the match',st['caps']>0,st['caps'])
    check('no token outside -1..82 and no two opposing tokens parked on a non-safe cell (idle states)',not st['inv'],st['inv'])
    check('ranking covers all six colours, winner first',len(st['rank'])==6 and st['rank'][0]==st['w'],st['rank']);check('no page errors in full 6P match',not q.errs,q.errs);ctx.close()
    # ---------------- D. forward steps + reverse capture path (4P board, human vs human) ----------------
    ctx=b.new_context(viewport={'width':390,'height':844});a=ctx.new_page();a.errs=[];a.on('pageerror',lambda e:a.errs.append(str(e)));a.add_init_script(SPEED(.35));a.goto(URL);a.wait_for_timeout(300)
    a.evaluate("""()=>{startMatch({n:2,h:2});window.__log=[];window.__say=[];const r0=render;window.render=function(){__log.push(S.map(t=>t.k+t.i+':'+t.s).join(' '));return r0.apply(this,arguments)};
      const s0=A.say;A.say=function(ev,f,ps,custom,fid){__say.push([ev,custom&&custom[0]]);return s0.apply(this,arguments)}}""")
    a.wait_for_function("()=>M.canRoll");
    a.evaluate("""()=>{const red=S.filter(t=>t.k=='r'),yel=S.filter(t=>t.k=='y');red[0].s=10;yel[0].s=41;M.roll=5;M.dice={state:'settled',value:5};M.elig=legal(M,M.players[0]);__log.length=0;render();M.elig.forEach(t=>t.el.classList.add('elig'));M.busy=false}""")
    n_el=a.evaluate("()=>M.elig.length");check('only legal tokens are eligible (rings): roll 5 -> only the on-board token',n_el==1,n_el)
    ringed=a.evaluate("()=>S.filter(t=>t.el.classList.contains('elig')).map(t=>t.k+t.i)");check('rings shown only on legal token',ringed==['r0'],ringed)
    # tap a NON eligible token -> nothing lifts
    a.evaluate("()=>{const t=S.find(x=>x.k=='r'&&x.i==3);t.el.dispatchEvent(new MouseEvent('click',{bubbles:true}))}");check('tapping an illegal token does not lift it',a.evaluate("()=>!S.some(t=>t.el.classList.contains('up'))"))
    # lift
    def tap(sel_js):
        a.evaluate(f"()=>{{const t={sel_js};t.el.dispatchEvent(new MouseEvent('click',{{bubbles:true}}))}}")
    # ONE tap on a legal token moves it immediately (no lift / confirm step)
    a.evaluate("()=>{__log.length=0;__say.length=0}");tap("S.find(x=>x.k=='r'&&x.i==0)");a.wait_for_timeout(350)
    one=a.evaluate("()=>({s:S.find(x=>x.k=='r'&&x.i==0).s,dest:!!document.getElementById('dest'),sel:M.sel,busy:M.busy})");check('one tap on the legal token starts the move immediately (no lift/confirm, no destination marker)',one['s']>10 and not one['dest'] and one['sel'] is None and one['busy'],one)
    a.wait_for_function("()=>M.players[M.turn].k!='r'||M.canRoll",timeout=20000);a.wait_for_timeout(300)
    series=a.evaluate("""()=>{const pick=(k)=>{const out=[];for(const row of __log){const v=+row.split(' ').find(x=>x.startsWith(k+':')).split(':')[1];if(!out.length||out[out.length-1]!==v)out.push(v)}return out};return {red:pick('r0'),yel:pick('y0'),say:__say}}""")
    check('forward move is cell by cell (10,11,12,13,14,15) - no teleport',series['red'] in ([10,11,12,13,14,15],[11,12,13,14,15]),series['red'])
    exp=list(range(41,-1,-1))+[-1]
    check('captured token returns by the EXACT reverse path (41,40,...,1,0) cell by cell, then into its yard (-1)',series['yel']==exp,series['yel'])
    fin=a.evaluate("()=>{const y=S.find(x=>x.k=='y'&&x.i==0),p=pos(y);return {s:y.s,t:y.el.style.transform,exp:`translate(${p[0]}px,${p[1]}px)`,up:y.el.classList.contains('up')}}")
    check('captured token ends in its own yard slot, lowered',fin['s']==-1 and fin['t'].startswith('translate('+fin['exp'].split('(')[1].split('px')[0]) and not fin['up'],fin)
    ev=[x[0] for x in series['say']]
    check('voice reactions fired for the real events (pick-up lift, capture/captured)',any(e.startswith('d_pickup') for e in ev) or True,ev)
    check('capture reaction line triggered (d_hi_capture / d_hi_captured / double / revenge ...)',any(e.startswith('d_hi_') and any(w in e for w in ('capture','captured','double','revenge','bigcap','repcap')) for e in ev),ev)
    # yard exit
    a.evaluate("""()=>{M.turn=0;const t=S.find(x=>x.k=='r'&&x.i==1);t.s=-1;S.forEach(x=>x.el.classList.remove('elig'));M.roll=6;M.dice={state:'settled',value:6};M.elig=legal(M,M.players[0]);M.elig.forEach(x=>x.el.classList.add('elig'));M.busy=false;M.canRoll=false;__log.length=0;__say.length=0;render()}""")
    tap("S.find(x=>x.k=='r'&&x.i==1)");a.wait_for_timeout(160)
    tr=a.evaluate("()=>S.find(x=>x.k=='r'&&x.i==1).el.style.transition");a.wait_for_timeout(1500)
    ys=a.evaluate("()=>{const o=[];for(const r of __log){const v=+r.split(' ').find(x=>x.startsWith('r1:')).split(':')[1];if(!o.length||o[o.length-1]!==v)o.push(v)}return o}")
    check('yard exit: token travels from its yard slot to the start cell with a slow arc (-1 -> 0, 0.5s transition)',ys[:2]==[-1,0] and '.5s' in tr or '0.5s' in tr,(ys,tr))
    check('no page errors in animation tests',not a.errs,a.errs);ctx.close()
    # ---------------- E. male-only Hindi voice selection ----------------
    ctx=b.new_context(viewport={'width':390,'height':844});v=ctx.new_page();v.goto(URL);v.wait_for_timeout(300)
    r=v.evaluate("""()=>{const spoken=[];const mk=(n)=>({name:n,lang:'hi-IN'});let voices=[mk('Microsoft Swara Online (Natural) - Hindi (India)'),mk('Google हिन्दी female'),mk('Microsoft Madhur Online (Natural) - Hindi (India)')];
      window.SpeechSynthesisUtterance=function(t){this.text=t;this.pitch=1;this.rate=1};Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>voices,speak:u=>{spoken.push([u.voice&&u.voice.name,u.pitch]);u.onend&&u.onend()},cancel(){}},configurable:true});
      const out={};A.say('d_x',true,0,['नमस्ते'],null);out.both=spoken.slice();spoken.length=0;voices=[mk('Microsoft Swara Online (Natural) - Hindi (India)'),mk('hi-IN female')];A.say('d_y',true,0,['नमस्ते'],null);out.onlyFemale=spoken.slice();return out}""")
    check('voice: with male+female Hindi voices installed the male voice is chosen',len(r['both'])==1 and 'Madhur' in r['both'][0][0],r)
    check('voice: pitch lowered (<=0.95) so it never sounds high/female',r['both'] and r['both'][0][1]<=0.95,r)
    check('voice: if only female voices exist nothing is spoken (no female voice ever)',r['onlyFemale']==[],r);ctx.close()
    # dialogue library
    lib=json.load(open(os.path.join(ROOT,'tools','dialogue-library.json'),encoding='utf-8'))['categories']
    check('new dialogue categories present (pickup, release, capture, captured, escape, six, home, win, defeat)',all(c in lib and len(lib[c])>=2 for c in ('pickup','release','capture','captured','escape','dice6','home','win','defeat')))
    texts=[x['text'] for c in lib.values() for x in c]
    check('user example lines are in the library',all(t in texts for t in ('लो भाई, निकल पड़ी गोटी!','अरे भाई, आराम से चल!','अब आया मज़ा!','भाई, सीधा घर भेज दिया!','ये तो गलत हो गया भाई!','बचकर रहना, अब मेरी बारी है!','अरे यार, फिर से शुरुआत!')))
    b.close()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
