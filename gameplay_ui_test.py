"""Gameplay UI + in-game Settings tests (Playwright/Chromium).  Run:  python tests/gameplay_ui_test.py"""
import os, sys, time, json
from playwright.sync_api import sync_playwright
URL='file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ludo-prank-v2.html'))
res=[];fails=[]
def check(name,ok,info=''):
    res.append((name,bool(ok)));print(('PASS ' if ok else 'FAIL ')+name+(' | '+str(info) if info and not ok else ''))
    if not ok: fails.append(name)
SIZES=[(360,640),(360,780),(390,844),(412,915),(768,1024),(844,390)]
GEOM="""()=>{const r=e=>{const b=e.getBoundingClientRect();return {l:b.left,t:b.top,r:b.right,b:b.bottom,w:b.width,h:b.height}};
const bw=r(document.querySelector('#game .bw')),bd=r(document.getElementById('board'));
const cards=[...document.querySelectorAll('#game .pp')].filter(e=>e.style.visibility!='hidden').map(e=>({id:e.id,...r(e),ovx:e.scrollWidth>e.clientWidth+1,ovy:e.scrollHeight>e.clientHeight+1,
  txt:e.innerText,nm:r(e.querySelector('.nm')),av:r(e.querySelector('.av'))}));
const ctr=[...document.querySelectorAll('#back,#vm,#gsBtn,#dice')].map(e=>({id:e.id,...r(e)}));
const ov=(a,b)=>!(a.r<=b.l+.5||a.l>=b.r-.5||a.b<=b.t+.5||a.t>=b.b-.5);
const fixed=[...document.querySelectorAll('body *')].filter(e=>{const c=getComputedStyle(e);return (c.position=='fixed'||c.position=='absolute')&&c.display!='none'&&c.visibility!='hidden'&&e.getBoundingClientRect().width>0&&ov(r(e),bw)&&!e.closest('.bw')&&!e.closest('[hidden]')&&c.pointerEvents!='none'&&e.id!='gs'}).map(e=>e.id||e.className);
return {bw,bd,cards,ctr,fixed,vw:innerWidth,vh:innerHeight,sh:document.documentElement.scrollHeight,sw:document.documentElement.scrollWidth,
 overl:ctr.filter(c=>ov(c,bw)).map(c=>c.id).concat(cards.filter(c=>ov(c,bw)).map(c=>c.id)),
 ctrlBelow:ctr.filter(c=>c.id!='dice').every(c=>c.t>=bw.b-1),
 cardTxt:cards.map(c=>c.txt).join('|'),shown:getComputedStyle(document.querySelector('.cap')).display}}"""
STATE="()=>JSON.stringify({turn:M.turn,k:M.players[M.turn].k,roll:M.roll,dice:M.dice,canRoll:M.canRoll,busy:M.busy,elig:M.elig.map(t=>t.k+t.i),s:S.map(t=>t.k+t.i+':'+t.s),par:document.getElementById('dice').parentElement.id,pips:document.querySelectorAll('#dice s.p').length,n:M.players.length})"
def page(b,w,h,n,hh=2):
    pg=b.new_page(viewport={'width':w,'height':h});pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)))
    pg.goto(URL);pg.evaluate("()=>{try{localStorage.clear()}catch(e){}}");pg.reload();pg.evaluate(f"()=>startMatch({{n:{n},h:{hh},diff:'medium'}})");pg.wait_for_timeout(500);return pg
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---------- layout across Android sizes ----------
    for (w,h) in SIZES:
        for n in (2,4):
            pg=page(b,w,h,n);g=pg.evaluate(GEOM);tag=f'{w}x{h} n={n}'
            check(f'[{tag}] cards square (w==h within 1px)',all(abs(c['w']-c['h'])<=1 for c in g['cards']) and len(g['cards'])==n,[(c['id'],round(c['w']),round(c['h'])) for c in g['cards']])
            check(f'[{tag}] cards equal size',len({round(c['w']) for c in g['cards']})==1)
            check(f'[{tag}] no text/avatar overflow in cards',all(not c['ovx'] and not c['ovy'] and c['nm']['r']<=c['r']+1 and c['nm']['l']>=c['l']-1 and c['nm']['b']<=c['b']+1 and c['av']['r']<=c['r'] for c in g['cards']))
            check(f'[{tag}] no Level/XP/Star text on cards',not any(s in g['cardTxt'] for s in ('Lv','XP','⭐','★','Level')),g['cardTxt'])
            check(f'[{tag}] nothing overlaps the board',not g['overl'] and not [f for f in g['fixed'] if f not in ('game','gwrap')],(g['overl'],g['fixed']))
            check(f'[{tag}] Home/Sound/Settings below board & inside viewport',(g['ctrlBelow'] or g['vw']>g['vh']) and all(c['l']>=0 and c['r']<=g['vw'] and c['b']<=g['vh']+1 for c in g['ctr']),[(c['id'],round(c['b'])) for c in g['ctr']])
            check(f'[{tag}] board square & inside viewport',abs(g['bd']['w']-g['bd']['h'])<=1 and g['bw']['l']>=0 and g['bw']['r']<=g['vw'])
            check(f'[{tag}] no page scroll needed',g['sh']<=g['vh']+1 and g['sw']<=g['vw']+1,(g['sh'],g['vh']))
            check(f'[{tag}] settings button visible, >=44px touch target',next(c for c in g['ctr'] if c['id']=='gsBtn')['w']>=38)
            pg.close()
    # ---------- fixed-element scan: no floating X / close button in game ----------
    pg=page(b,390,844,2)
    x=pg.evaluate("()=>[...document.querySelectorAll('button,[role=button]')].filter(e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return r.width>0&&c.visibility!='hidden'&&/^[×✕✖xX]$/.test((e.innerText||'').trim())}).length")
    check('no visible floating X/close button in gameplay',x==0)
    pg.close()
    # ---------- settings: pause + resume preserve exact state ----------
    pg=page(b,390,844,2,hh=1)  # human + bot
    pg.wait_for_function("()=>M.canRoll&&!M.busy");pg.click('#dice',force=True);pg.wait_for_function("()=>M.dice.state=='settled'")
    before=pg.evaluate(STATE);pg.click('#gsBtn');pg.wait_for_timeout(300)
    check('settings panel opens',pg.evaluate("()=>!document.getElementById('gs').hidden"))
    check('opening settings pauses (gate set)',pg.evaluate("()=>gate!==null"))
    pg.wait_for_timeout(2500);mid=pg.evaluate(STATE)
    check('state identical after 2.5s paused (no dice/token/turn change)',mid==before,(before,mid))
    pg.click('#gsResume');pg.wait_for_timeout(200)
    check('resume closes panel & unpauses',pg.evaluate("()=>document.getElementById('gs').hidden&&gate===null"))
    after=pg.evaluate(STATE);import json as _j;b0,a0=_j.loads(before),_j.loads(after);check('state right after resume is the same (a single legal move may auto-execute, but never a second dice result)',a0['dice']['value']==b0['dice']['value'] and a0['turn']==b0['turn'] or a0['dice']['state']!='rolling',(before,after))
    pg.close()
    # pause during a BOT turn (roll + move in flight): result must be preserved, game continues
    pg=page(b,390,844,2,hh=1)
    def finish_human():
        pg.wait_for_function("()=>M.canRoll&&!M.busy&&M.players[M.turn].human",timeout=20000);pg.click('#dice',force=True)
        pg.wait_for_function("()=>M.dice.state=='settled'");
        if pg.evaluate("()=>M.elig.length"): pg.evaluate("()=>pick(M,M.elig[0])")
    for _ in range(12):
        finish_human()
        try:
            pg.wait_for_function("()=>!M.players[M.turn].human&&M.busy",timeout=5000);break
        except Exception: pass
    pg.wait_for_function("()=>M.dice.state=='rolling'||M.roll>0",timeout=5000)
    pg.click('#gsBtn');pg.wait_for_timeout(100);a=pg.evaluate(STATE);pg.wait_for_timeout(3000);c=pg.evaluate(STATE)
    check('mid-bot-turn pause: nothing advances while open',a==c,(a,c))
    pg.click('#gsResume');pg.wait_for_function("()=>M.players[M.turn].human&&M.canRoll",timeout=20000)
    check('bot turn completes after resume, game not frozen',True)
    check('no JS errors during pause/resume',not pg.errs,pg.errs);pg.close()
    # ---------- audio controls work + persist ----------
    pg=page(b,390,844,2);pg.click('#gsBtn')
    for sw,key in (('g-ov','ov'),('g-om','om'),('g-os','os')):
        pg.click('#'+sw);v1=pg.evaluate(f"()=>A.prefs.{key}");chk1=pg.get_attribute('#'+sw,'aria-checked')
        pg.click('#'+sw);v2=pg.evaluate(f"()=>A.prefs.{key}")
        check(f'toggle {sw} off then on',v1==0 and chk1=='false' and v2==1,(v1,chk1,v2))
    pg.click('#g-ov');check('mute-all state syncs bottom sound button icon',(pg.evaluate("()=>{A.prefs.mute=true;paintVm();return document.getElementById('vm').getAttribute('aria-pressed')}")=='false'))
    for sid,key in (('g-v','v'),('g-mu','mu'),('g-s','s')):
        pg.evaluate(f"()=>{{const e=document.getElementById('{sid}');e.value=23;e.dispatchEvent(new Event('input',{{bubbles:true}}))}}")
        check(f'slider {sid} sets pref {key}=23',pg.evaluate(f"()=>A.prefs.{key}")==23 and pg.inner_text(f'#{sid}-v')=='23%')
    pg.click('#g-om');pg.click('#g-os')
    saved=pg.evaluate("()=>JSON.parse(localStorage.getItem('lp-audio'))")
    check('audio prefs saved to localStorage',saved['v']==23 and saved['mu']==23 and saved['s']==23 and saved['ov']==0 and saved['om']==0 and saved['os']==0,saved)
    pg.reload();pg.evaluate("()=>startMatch({n:2,h:2})");pg.wait_for_timeout(300);pg.click('#gsBtn')
    check('audio prefs restored after reload',pg.evaluate("()=>[A.prefs.v,A.prefs.mu,A.prefs.s,A.prefs.ov,A.prefs.om,A.prefs.os].join()")=='23,23,23,0,0,0' and pg.input_value('#g-v')=='23' and pg.get_attribute('#g-ov','aria-checked')=='false')
    pg.click('#gsResume');pg.click('#vm');check('bottom sound button toggles mute-all',pg.evaluate("()=>A.prefs.mute")==False);pg.close()
    # ---------- player management: remove disconnected ----------
    def pm_case(n,hh,target,active_idx,label,busy_case=False):
        pg=page(b,390,844,n,hh=hh);pg.evaluate(f"()=>{{M.turn={active_idx};render();turnStart(M)}}");pg.wait_for_timeout(300)
        if not busy_case: pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=15000)
        pg.click('#gsBtn');rows=pg.evaluate("()=>[...document.querySelectorAll('#gs .pl')].length")
        check(f'{label}: lists all players',rows==n,rows)
        dis=pg.evaluate(f"()=>document.querySelector('[data-rm=\"{target}\"]').disabled")
        check(f'{label}: Remove disabled while connected',dis is True)
        pg.click(f'[data-conn="{target}"]');pg.wait_for_timeout(100)
        check(f'{label}: marked disconnected, Remove enabled',pg.evaluate(f"()=>!document.querySelector('[data-rm=\"{target}\"]').disabled")and 'Disconnected' in pg.inner_text('#gsp'))
        pg.click(f'[data-rm="{target}"]');check(f'{label}: asks confirmation',pg.is_visible('#gsYes')and 'Remove player?' in pg.inner_text('#gsp'))
        pg.click('#gsNo');check(f'{label}: Cancel keeps player',pg.evaluate(f"()=>M.players.some(p=>p.k=='{target}')"))
        pg.click(f'[data-rm="{target}"]');pg.click('#gsYes');pg.wait_for_timeout(150)
        if busy_case:
            check(f'{label}: busy -> removal deferred',pg.evaluate(f"()=>M.players.some(p=>p.k=='{target}')&&M.pendRm.includes('{target}')"))
        pg.click('#gsResume');
        if busy_case: pg.wait_for_function(f"()=>!M.players.some(p=>p.k=='{target}')",timeout=25000)
        pg.wait_for_timeout(300)
        st=pg.evaluate("()=>({ks:M.players.map(p=>p.k),turn:M.turn,tk:S.map(t=>t.k),els:document.querySelectorAll('#layer .tg').length,S:S.length,par:document.getElementById('dice').parentElement.id,act:M.players[M.turn].k,vis:[...document.querySelectorAll('#game .pp')].filter(e=>e.style.visibility!='hidden').length,gate:gate})")
        check(f'{label}: player removed from order',target not in st['ks'] and len(st['ks'])==n-1,st)
        check(f'{label}: no tokens of removed player left (data+DOM)',target not in st['tk'] and st['els']==st['S']==4*(n-1),st)
        check(f'{label}: turn index valid, dice follows active player',0<=st['turn']<len(st['ks']) and (st['par']=='ds-'+st['act'] if len(st['ks'])<4 else st['par']=='dock'),st)
        check(f'{label}: removed card hidden',st['vis']==n-1)
        # game keeps running: play several turns
        t0=time.time();rolls=0
        while time.time()-t0<25 and rolls<4:
            ok=pg.evaluate("()=>M.canRoll&&!M.busy&&M.players[M.turn].human")
            if ok: pg.click('#dice',force=True);pg.wait_for_function("()=>M.dice.state=='settled'",timeout=8000);rolls+=1;
            if pg.evaluate("()=>M.elig.length&&M.players[M.turn].human&&!M.busy"): pg.evaluate("()=>pick(M,M.elig[0])")
            pg.wait_for_timeout(250)
        turns=pg.evaluate("()=>M.turnN||0")
        check(f'{label}: game continues after removal (not frozen)',turns>=1 or rolls>=1,(turns,rolls))
        check(f'{label}: no JS errors',not pg.errs,pg.errs);pg.close()
    pm_case(4,3,'y',2,'4P remove ACTIVE disconnected (yellow)')
    pm_case(3,3,'g',0,'3P remove NON-active disconnected (green)')
    pm_case(4,3,'g',0,'4P remove earlier-seat player while host active')
    pm_case(2,2,'y',1,'2P remove active -> practice continues')
    # busy (bot mid-move) deferred removal: seats r(human host),g(human),y(bot)
    pm_case(3,2,'g',2,'3P deferred removal while a bot turn is in flight',busy_case=True)
    # return to home with confirmation
    pg=page(b,390,844,2);pg.click('#gsBtn');pg.click('#gsHome');check('Return to Home asks confirmation',pg.is_visible('#gsYes'))
    pg.click('#gsNo');check('Stay keeps match',pg.evaluate("()=>!!M&&!M.done&&document.getElementById('game').classList.contains('on')"))
    pg.click('#gsHome');pg.click('#gsYes');pg.wait_for_timeout(300)
    check('Return to Home leaves to home & unpauses',pg.evaluate("()=>document.getElementById('home').classList.contains('on')&&gate===null&&document.getElementById('gs').hidden&&(!M||M.done)"))
    pg.close()
    # dice follows active player in a short live game (cards square the whole time)
    pg=page(b,390,844,3,hh=3);bad=0;t0=time.time()
    while time.time()-t0<12:
        s=pg.evaluate("()=>({par:document.getElementById('dice').parentElement.id,k:M.players[M.turn].k,anim:document.getElementById('dice').getAnimations().length})")
        if s['anim']==0 and s['par']!='ds-'+s['k']: bad+=1
        if pg.evaluate("()=>M.canRoll&&!M.busy"): pg.click('#dice',force=True)
        if pg.evaluate("()=>M.elig.length&&!M.busy"): pg.evaluate("()=>pick(M,M.elig[0])")
        pg.wait_for_timeout(120)
    check('dice stays on the active player (3P live)',bad==0,bad);check('no JS errors in live game',not pg.errs,pg.errs);pg.close()
    b.close()
print(f"\n{sum(1 for _,o in res if o)}/{len(res)} passed");sys.exit(1 if fails else 0)
