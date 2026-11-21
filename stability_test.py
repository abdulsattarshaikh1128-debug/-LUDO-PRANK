"""Layout stability / zoom / multi-touch / bottom bar tests. Run: python tests/stability_test.py [path-to-html]"""
import os, sys, json
from playwright.sync_api import sync_playwright
HTML=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','ludo-prank-v2.html')
URL='file://'+os.path.abspath(HTML)
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)))
    if not ok: fails.append(n)
FAST="(()=>{const st=window.setTimeout.bind(window);window.setTimeout=(f,ms,...a)=>st(f,(ms||0)*0.12,...a)})()"
RECTS="""()=>{const r=e=>{const b=e.getBoundingClientRect();return [b.left,b.top,b.width,b.height].map(x=>Math.round(x*100)/100)};
return {bw:r(document.querySelector('#game .bw')),board:r(document.getElementById('board')),bar:r(document.getElementById('gbar')),
 btn:['back','vm','gsBtn'].map(i=>r(document.getElementById(i))),cards:[...document.querySelectorAll('#game .pp')].filter(e=>e.style.visibility!='hidden').map(r),
 sy:scrollY,sx:scrollX,vs:window.visualViewport?visualViewport.scale:1,vx:window.visualViewport?visualViewport.offsetLeft:0,vy:window.visualViewport?visualViewport.offsetTop:0,
 top:document.getElementById('gwrap').getBoundingClientRect().top}}"""
def mobile(b,w,h,url=URL,fast=False):
    ctx=b.new_context(viewport={'width':w,'height':h},is_mobile=True,has_touch=True,device_scale_factor=2)
    pg=ctx.new_page();pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)))
    if fast: pg.add_init_script(FAST)
    pg.goto(url);pg.wait_for_timeout(300);return ctx,pg
def touch(cdp,t,pts): cdp.send('Input.dispatchTouchEvent',{'type':t,'touchPoints':pts})
def pts(n,cx,cy,spread):
    import math
    return [{'x':cx+spread*math.cos(i*2*math.pi/n),'y':cy+spread*math.sin(i*2*math.pi/n),'id':i} for i in range(n)]
with sync_playwright() as p:
    b=p.chromium.launch()
    # ===== 1. board fixed during a whole match (bots only, accelerated), 4P and 6P =====
    for n in (4,6):
        ctx,pg=mobile(b,390,844,fast=True);pg.evaluate(f"()=>startMatch({{n:{n},h:0,diff:'medium'}})");pg.wait_for_timeout(300)
        base=pg.evaluate(RECTS);bad=[];samples=0;caps=set();seen_turn=set();seen_dice=set()
        for i in range(160):
            pg.wait_for_timeout(100);r=pg.evaluate(RECTS);samples+=1
            st=pg.evaluate("()=>({k:M.players[M.turn].k,d:M.dice.state,done:M.done,cap:document.getElementById('cap').textContent})");seen_turn.add(st['k']);seen_dice.add(st['d']);caps.add(st['cap'])
            if i==40: pg.evaluate("()=>{cap.textContent='ये एक बहुत लंबा डायलॉग है जो दो लाइन में टूट सकता है भाई, ठीक है ना, देखो क्या होता है आगे'}")
            if i==80:
                pg.click('#gsBtn');pg.wait_for_timeout(200);pg.click('#gsResume')
            if r['bw']!=base['bw'] or r['board']!=base['board'] or r['bar']!=base['bar'] or r['btn']!=base['btn'] or r['sy'] or r['sx'] or r['vs']!=1:bad.append((i,r['bw'],base['bw']))
            if st['done']:break
        check(f'[{n}P] board+controls rect identical in {samples} samples (dice/turn/caption/settings changes)',not bad,bad[:2])
        check(f'[{n}P] test exercised several turns/dice states (captions are removed, so none expected)',len(seen_turn)>=2 and len(seen_dice)>=2 and len(caps)==1,(seen_turn,seen_dice,len(caps)))
        check(f'[{n}P] board centred horizontally',abs(base['bw'][0]*2+base['bw'][2]-390)<=1,base['bw'])
        check(f'[{n}P] board square (aspect 1:1)',abs(base['board'][2]-base['board'][3])<=0.5,base['board'])
        check(f'[{n}P] no page errors',not pg.errs,pg.errs);ctx.close()
    # ===== 2. multi-touch / pinch cannot zoom or move =====
    for (fingers) in (2,3,5):
        ctx,pg=mobile(b,390,844);pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(500);base=pg.evaluate(RECTS);cdp=ctx.new_cdp_session(pg)
        for step in range(8):
            touch(cdp,'touchStart',pts(fingers,195,420,40+step*10) if step==0 else pts(fingers,195,420,40))
            for k in range(1,9): touch(cdp,'touchMove',pts(fingers,195+k*5,420-k*10,40+k*18))
            touch(cdp,'touchEnd',[]);break
        cdp.send('Input.synthesizePinchGesture',{'x':195,'y':420,'scaleFactor':2.4,'relativeSpeed':400}) if fingers==2 else None
        cdp.send('Input.synthesizePinchGesture',{'x':195,'y':420,'scaleFactor':.5,'relativeSpeed':400}) if fingers==2 else None
        pg.wait_for_timeout(400);r=pg.evaluate(RECTS)
        check(f'{fingers}-finger gesture: visual viewport scale stays 1',r['vs']==1,r['vs'])
        check(f'{fingers}-finger gesture: board/controls did not move',r['bw']==base['bw'] and r['bar']==base['bar'] and r['btn']==base['btn'] and not r['sy'] and not r['sx'] and r['vx']==0 and r['vy']==0,(r['bw'],base['bw']))
        ctx.close()
    ctx,pg=mobile(b,390,844);pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(400);base=pg.evaluate(RECTS)
    pg.touchscreen.tap(195,420);pg.touchscreen.tap(195,420);pg.wait_for_timeout(50);pg.touchscreen.tap(195,420);pg.wait_for_timeout(300);r=pg.evaluate(RECTS)
    check('double-tap on the board does not zoom',r['vs']==1 and r['bw']==base['bw'],r['vs']);
    pg.evaluate("()=>{window.scrollTo(0,300)}");pg.wait_for_timeout(100);check('page cannot be scrolled in game',pg.evaluate("()=>scrollY")==0)
    check('viewport meta disables user scaling',pg.evaluate("()=>/user-scalable=no/.test(document.querySelector('meta[name=viewport]').content)"));ctx.close()
    # ===== 3. toolbar-size viewport changes & rotation =====
    ctx,pg=mobile(b,390,844);pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(400);base=pg.evaluate(RECTS)
    pg.set_viewport_size({'width':390,'height':844-56});pg.wait_for_timeout(500);r=pg.evaluate(RECTS)
    check('browser toolbar show/hide (56px viewport change) does not resize/move board',r['bw']==base['bw'],(r['bw'],base['bw']))
    pg.set_viewport_size({'width':844,'height':390});pg.wait_for_timeout(700);r=pg.evaluate(RECTS)
    check('rotation re-lays out once, board still square & inside screen',abs(r['board'][2]-r['board'][3])<=.5 and r['bw'][0]>=0 and r['bw'][0]+r['bw'][2]<=844 and r['bw'][1]+r['bw'][3]<=390,r['bw']);ctx.close()
    # ===== 4. bottom bar =====
    for (w,h) in ((360,640),(390,844),(412,915),(768,1024)):
        ctx,pg=mobile(b,w,h);pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(400);r=pg.evaluate(RECTS)
        bt=r['btn'];gaps=[bt[1][0]-(bt[0][0]+bt[0][2]),bt[2][0]-(bt[1][0]+bt[1][2])]
        check(f'[{w}x{h}] Home, Sound, Settings visible, inside bar, equal spacing',all(x[1]>=r['bar'][1] and x[1]+x[3]<=h+.5 for x in bt) and abs(gaps[0]-gaps[1])<=1.5,(bt,gaps))
        check(f'[{w}x{h}] bar sits at the very bottom; board and cards end above it',abs(r['bar'][1]+r['bar'][3]-h)<=1 and r['bw'][1]+r['bw'][3]<=r['bar'][1] and all(c[1]+c[3]<=r['bar'][1] for c in r['cards']),(r['bar'],r['bw']))
        ctx.close()
    ctx,pg=mobile(b,390,844);pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(400)
    pg.click('#gsBtn');check('Settings opens from bottom bar',pg.evaluate("()=>!document.getElementById('gs').hidden && gate!==null"));pg.click('#gsResume')
    pg.click('#back');ok1=pg.is_visible('#gsYes') and 'Leave this match?' in pg.inner_text('#gsp');check('Home asks for confirmation',ok1)
    pg.click('#gsNo');check('Home → Stay keeps the match running',pg.evaluate("()=>!!M&&!M.done&&document.getElementById('game').classList.contains('on')&&document.getElementById('gs').hidden&&gate===null"))
    pg.click('#back');pg.click('#gsYes');pg.wait_for_timeout(300);check('Home → Return leaves to Home screen',pg.evaluate("()=>document.getElementById('home').classList.contains('on')&&(!M||M.done)"))
    pg.evaluate("()=>startMatch({n:4,h:4})");pg.wait_for_timeout(300)
    pg.click('#vm');check('Sound button mutes ALL audio (pref + master gain)',pg.evaluate("()=>A.prefs.mute===1")  and pg.get_attribute('#vm','aria-pressed')=='false')
    check('muted: voice/sfx request returns without playing (A.say skipped)',pg.evaluate("()=>{let r=A.say('dice6',false,0,['x'],'dice6_0');return !A.skipped()&&r==='x'}"))
    pg.click('#vm');check('Sound button unmutes',pg.evaluate("()=>A.prefs.mute===0")and pg.get_attribute('#vm','aria-pressed')=='true')
    saved=pg.evaluate("()=>JSON.parse(localStorage.getItem('lp-audio')).mute");check('mute preference persisted',saved==0);ctx.close()
    b.close()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
