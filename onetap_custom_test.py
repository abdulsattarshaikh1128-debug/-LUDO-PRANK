"""One-tap movement + Customize Players (humans/robots) — real gameplay through the UI."""
import os,sys,time
from playwright.sync_api import sync_playwright
HTML='file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ludo-prank-v2.html'))
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)))
    if not ok: fails.append(n)
INIT="""()=>{window.__f=null;window.__rolls=0;window.__mv=[];window.__bad=[];window.__seq=[];
 const real=crypto.getRandomValues.bind(crypto);
 Object.defineProperty(crypto,'getRandomValues',{value:a=>{if(a.length==1)window.__rolls++;if(window.__f=='cyc'&&a.length==1){if(Math.random()<.5){a[0]=5;return a}}if(window.__f&&window.__f!='cyc'&&a.length==1){a[0]=window.__f-1;return a}return real(a)},configurable:true});
 const mv=window.move;window.move=function(m,t){const p=m.players[m.turn];const ok=t.s<0?m.roll==6:t.s+m.roll<=HOME;if(!ok||p.fin||t.k!=p.k)__bad.push([t.k,t.s,m.roll]);__mv.push([p.k,p.human,t.s,m.roll]);return mv(m,t)};
 const ts=window.turnStart;window.turnStart=function(m){try{__seq.push([m.players[m.turn].k,m.roll])}catch(e){}return ts(m)}}"""
def new(b,w=390,h=844):
    pg=b.new_page(viewport={'width':w,'height':h});pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)));pg.goto(HTML);pg.wait_for_timeout(400);pg.evaluate(INIT);return pg
def start(pg,n,h=None):
    pg.evaluate("([n,h])=>{go('home');startMatch({n,h,diff:'easy'})}",[n,h or n]);pg.wait_for_function("()=>M&&M.canRoll&&!M.busy",timeout=15000)
def setup(pg,k,toks,roll):
    pg.evaluate("([k,toks,roll])=>{const m=M;m.turn=m.players.findIndex(p=>p.k==k);S.filter(t=>t.k==k).forEach((t,i)=>t.s=toks[i]);window.__f=roll;window.__rolls=0;window.__mv.length=0;m.canRoll=true;m.busy=false;m.dice={state:'idle',value:0};render()}",[k,toks,roll])
    pg.wait_for_timeout(800)
def realclick(pg,sel):
    b=pg.evaluate("(s)=>{const e=document.querySelector(s);const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}",sel);pg.mouse.click(b[0],b[1])
def st(pg,k):return pg.evaluate("(k)=>S.filter(t=>t.k==k).map(t=>t.s)",k)
def rings(pg):return pg.evaluate("()=>document.querySelectorAll('.tg.elig').length")
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---------- one tap: roll 6, single token out
    pg=new(b);start(pg,2)
    setup(pg,'r',[-1,-1,-1,-1],6);realclick(pg,'#dice');maxring=0;t0=time.time()
    while time.time()-t0<3: maxring=max(maxring,rings(pg));time.sleep(.03)
    check('ONE dice tap + roll 6: token leaves the yard by itself (no second tap)',sorted(st(pg,'r'))==[-1,-1,-1,0],st(pg,'r'))
    check('no white ring / selection step was ever shown for the single move',maxring==0,maxring)
    check('exactly one dice result (no duplicate roll)',pg.evaluate("()=>__rolls")==1 and pg.evaluate("()=>__mv.length")==1,pg.evaluate("()=>[__rolls,__mv]"))
    pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000);check('after a 6 the same player rolls again (existing rule), nothing else changed',pg.evaluate("()=>M.players[M.turn].k")=='r')
    # ---------- roll 4 / 5 single token, step-by-step
    for roll in (4,5):
        pg.evaluate("()=>{window.__f=null}");pg.wait_for_function("()=>M.canRoll&&!M.busy");setup(pg,'r',[10,-1,-1,-1],roll);realclick(pg,'#dice');seq=[];maxring=0;t0=time.time()
        while time.time()-t0<4:
            v=pg.evaluate("()=>S.find(t=>t.k=='r'&&t.i==0).s")
            if not seq or seq[-1]!=v:seq.append(v)
            maxring=max(maxring,rings(pg));time.sleep(.02)
        check(f'roll {roll}: only token moves automatically, cell by cell 10 -> {10+roll}',seq==list(range(10,10+roll+1)),seq)
        check(f'roll {roll}: no ring, one dice result, turn passes',maxring==0 and pg.evaluate("()=>__rolls")==1 and pg.evaluate("()=>M.players[M.turn].k")=='y',(maxring,pg.evaluate("()=>[__rolls,M.players[M.turn].k]")))
        pg.wait_for_function("()=>M.canRoll&&!M.busy");pg.evaluate("()=>{window.__f=null}")
    # ---------- multiple choices: one tap moves immediately
    setup(pg,'y',[5,9,-1,-1],3);realclick(pg,'#dice');pg.wait_for_function("()=>M.elig.length==2",timeout=5000);time.sleep(.3)
    check('two valid tokens: both highlighted with a clear prompt, nothing moved yet',rings(pg)==2 and st(pg,'y')==[5,9,-1,-1] and 'Tap' in pg.inner_text('#hint2'),pg.inner_text('#hint2'))
    realclick(pg,'.tg.elig:nth-of-type(1)') if False else None
    xy=pg.evaluate("()=>{const t=M.elig[1];const r=t.el.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2,t.i]}");pg.mouse.click(xy[0],xy[1])
    pg.wait_for_function("()=>S.filter(t=>t.k=='y').map(t=>t.s).join()=='5,12,-1,-1'",timeout=5000)
    check('ONE tap on the chosen token moves it immediately (9 -> 12); the other did not move; no confirm tap',pg.evaluate("()=>__mv.length")==1 and pg.evaluate("()=>__rolls")==1,pg.evaluate("()=>__mv"))
    pg.wait_for_function("()=>M.canRoll&&!M.busy&&M.players[M.turn].k=='r'",timeout=8000);pg.evaluate("()=>{window.__f=null}")
    # 6 with board token + yard tokens
    setup(pg,'r',[7,-1,-1,-1],6);realclick(pg,'#dice');pg.wait_for_function("()=>M.elig.length==4",timeout=5000);time.sleep(.2)
    check('roll 6, one token on board + tokens in yard: choices shown (board token and yard tokens)',rings(pg)==4)
    xy=pg.evaluate("()=>{const t=M.elig.find(t=>t.s<0);const r=t.el.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}");pg.mouse.click(xy[0],xy[1])
    pg.wait_for_function("()=>S.filter(t=>t.k=='r'&&t.s==0).length==1",timeout=5000)
    check('one tap on a yard token brings it out immediately',sorted(st(pg,'r'))==[-1,-1,0,7],st(pg,'r'))
    pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000)
    # spam clicks: dice multiple taps must not cause duplicate rolls / moves
    pg.evaluate("()=>{window.__f=3}");setup(pg,'r',[20,-1,-1,-1],3)
    for _ in range(6):
        try:pg.mouse.click(*pg.evaluate("()=>{const r=document.getElementById('dice').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}"))
        except Exception:pass
        time.sleep(.05)
    time.sleep(3)
    check('rapid repeated dice taps: still exactly one roll and one move',pg.evaluate("()=>__rolls")==1 and pg.evaluate("()=>__mv.length")==1 and st(pg,'r')==[23,-1,-1,-1],pg.evaluate("()=>[__rolls,__mv]"))
    check('no illegal move was ever attempted; no page errors',not pg.evaluate("()=>__bad") and not pg.errs,(pg.evaluate("()=>__bad"),pg.errs));pg.close()
    # ---------- Customize Players UI
    pg=new(b);pg.evaluate("()=>{go('home');$('#m-cpu').click()}");pg.wait_for_timeout(300)
    check('Robot Mode has a "Customize Players" option',pg.is_visible('[data-a=custom]'))
    pg.click('[data-a=custom]');pg.wait_for_timeout(200);t=pg.inner_text('#flow')
    check('customize screen: human + robot selectors, total, list with colour/type, Start and Back',all(x in t for x in ['Human players','Robot players','Total players','Human','Robot','Red']) and pg.is_visible('[data-a=cstart]') and pg.is_visible('[data-a=back]'),t[:200])
    for _ in range(8):pg.click('[data-a=cinc][data-v=r]') if pg.evaluate("()=>!document.querySelector('[data-a=cinc][data-v=r]').disabled") else None
    check('total can never exceed 6 (plus buttons disable)',pg.inner_text('#c-t')=='6' and pg.evaluate("()=>document.querySelector('[data-a=cinc][data-v=h]').disabled&&document.querySelector('[data-a=cinc][data-v=r]').disabled"))
    pg.click('[data-a=cdec][data-v=r]');pg.click('[data-a=cdec][data-v=r]');pg.click('[data-a=cinc][data-v=h]')
    check('changing humans/robots updates total and player list live (2 humans + 3 robots)',pg.inner_text('#c-t')=='5' and pg.inner_text('#c-h')=='2' and pg.inner_text('#c-r')=='3' and pg.evaluate("()=>document.querySelectorAll('#c-list .prow').length")==5)
    pg.screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/custom_390.png')
    pg.click('[data-a=back]');pg.wait_for_timeout(200);check('Back returns to the mode picker',pg.is_visible('[data-a=custom]'))
    pg.click('[data-a=custom]');check('configuration is remembered',pg.inner_text('#c-h')=='2' and pg.inner_text('#c-r')=='3')
    pg.click('[data-a=cstart]');pg.wait_for_function("()=>M&&M.players.length==5",timeout=8000)
    check('Start Game starts the real engine with the saved config (2 humans + 3 robots, 5 players)',pg.evaluate("()=>M.cfg.n==5&&M.cfg.h==2&&M.players.filter(p=>p.human).length==2&&M.players.filter(p=>!p.human).length==3&&S.length==20"))
    check('robots are labelled Robot 1..3 on their cards',pg.evaluate("()=>M.players.filter(p=>!p.human).map(p=>document.querySelector('#p-'+p.k+' .nm').textContent).join()")=='Robot 1,Robot 2,Robot 3')
    check('no page errors (custom UI)',not pg.errs,pg.errs);pg.close()
    # ---------- real play for many combinations
    combos=[(1,1),(1,2),(1,3),(1,4),(1,5),(2,1),(2,2),(2,3),(2,4),(3,1),(3,2),(3,3),(4,1),(4,2),(5,1)]
    for H,R in combos:
        pg=new(b);pg.evaluate("()=>{go('home');$('#m-cpu').click()}");pg.click('[data-a=custom]')
        for _ in range(H-1):pg.click('[data-a=cinc][data-v=h]')
        for _ in range(R-(1 if H==1 else 0)) if False else range(0):pass
        # reset robots to R via UI
        cur=int(pg.inner_text('#c-r'))
        while cur<R:pg.click('[data-a=cinc][data-v=r]');cur+=1
        while cur>R:pg.click('[data-a=cdec][data-v=r]');cur-=1
        tot=int(pg.inner_text('#c-t'));h_ok=pg.inner_text('#c-h')==str(H)
        pg.click('[data-a=cstart]');pg.wait_for_function("()=>M&&M.cfg.custom",timeout=8000);pg.evaluate("()=>{window.__f='cyc';window.__seq.length=0;window.__mv.length=0}")
        t0=time.time();humanmoves=0
        while time.time()-t0<22 or (R and time.time()-t0<90 and not pg.evaluate("()=>__mv.some(x=>!x[1])")):
            r=pg.evaluate("()=>({can:M.canRoll&&!M.busy&&M.players[M.turn].human,multi:M.elig.length>0&&!M.busy&&M.players[M.turn].human&&new Set(M.elig.map(t=>t.s)).size>1})")
            if r['can']:pg.evaluate("()=>document.getElementById('dice').click()")
            if r['multi']:
                xy=pg.evaluate("()=>{const t=M.elig[0];const r=t.el.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}");pg.mouse.click(xy[0],xy[1])
            time.sleep(.12)
        d=pg.evaluate("()=>({n:M.players.length,hum:M.players.filter(p=>p.human).length,mv:__mv,bad:__bad,seq:__seq,tn:M.turnN||0,ks:M.players.map(p=>p.k),S:S.length})")
        hm=sum(1 for x in d['mv'] if x[1]);rm=sum(1 for x in d['mv'] if not x[1]);tag=f'{H} human + {R} robot'
        check(f'{tag}: setup total {H+R}, real engine has {H} humans / {R} robots, {4*(H+R)} tokens',tot==H+R and h_ok and d['n']==H+R and d['hum']==H and d['S']==4*(H+R),d['n'])
        if R:check(f'{tag}: robots really rolled and moved tokens ({rm} robot moves, {hm} human moves)',rm>=1 and (hm>=1 or H>=1) and d['tn']>=3,(rm,hm,d['tn']))
        ks=d['ks'];bad=[];prev=None
        for k,roll in d['seq']:
            if prev and k!=prev[0]:
                if k!=ks[(ks.index(prev[0])+1)%len(ks)]:bad.append((prev,k))
            prev=(k,roll)
        check(f'{tag}: turns follow seat order (human/robot alternate correctly)',not bad,bad[:3])
        check(f'{tag}: robots made only legal moves, no duplicate/invalid moves, no page errors',not d['bad'] and not pg.errs,(d['bad'],pg.errs))
        pg.close()
    b.close()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
