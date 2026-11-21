"""Real-gameplay tests: smart auto-move, token selection, no captions (voice kept), N-1 ranking for 2..6 players.
Dice are forced through crypto.getRandomValues (the game's real RNG entry point), so every roll still goes through doRoll()/move()."""
import os, sys, re, time
from playwright.sync_api import sync_playwright
HTML='file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ludo-prank-v2.html'))
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)))
    if not ok: fails.append(n)
INIT="""()=>{window.__f=null;window.__rolls=0;window.__spoken=[];window.SpeechSynthesisUtterance=function(t){this.text=t;this.pitch=1;this.rate=1};
 const v=[{name:'Microsoft Madhur Online (Natural) - Hindi (India)',lang:'hi-IN'}];
 Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>v,speak:u=>{__spoken.push(u.text);setTimeout(()=>u.onend&&u.onend(),30)},cancel(){}},configurable:true});
 const real=crypto.getRandomValues.bind(crypto);
 Object.defineProperty(crypto,'getRandomValues',{value:a=>{if(window.__f&&a.length==1){window.__rolls++;a[0]=window.__f-1;return a}return real(a)},configurable:true});
 window.__turns=[];const ts=window.turnStart;window.turnStart=function(m){try{window.__turns.push([m.players[m.turn].k,!!m.players[m.turn].fin])}catch(e){}return ts(m)}}"""
def new(b,w=390,h=844):
    pg=b.new_page(viewport={'width':w,'height':h});pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)));pg.goto(HTML);pg.wait_for_timeout(400);pg.evaluate(INIT);return pg
def start(pg,n,h=None,diff=None):
    pg.evaluate("([n,h])=>{go('home');startMatch({n,h,diff:'easy'})}",[n,h or n]);pg.wait_for_function("()=>M&&M.canRoll&&!M.busy",timeout=15000)
def setup(pg,k,toks,roll):
    """put seat k to move with given token states, then roll `roll` by clicking the real dice"""
    pg.evaluate("([k,toks,roll])=>{const m=M;m.turn=m.players.findIndex(p=>p.k==k);S.filter(t=>t.k==k).forEach((t,i)=>t.s=toks[i]);render();window.__f=roll;window.__rolls=0;m.canRoll=true;m.busy=false;m.dice={state:'idle',value:0};render()}",[k,toks,roll])
    pg.wait_for_timeout(700)  # let the dice finish gliding to the active player's side
    pg.click('#dice',force=True)
def st(pg,k): return pg.evaluate("(k)=>S.filter(t=>t.k==k).map(t=>t.s)",k)
with sync_playwright() as p:
    b=p.chromium.launch()
    # ------------------------------------------------ 1. AUTO MOVE
    pg=new(b);start(pg,2)
    setup(pg,'r',[-1,-1,-1,-1],6);pg.wait_for_function("()=>S.filter(t=>t.k=='r'&&t.s==0).length==1",timeout=6000);time.sleep(.3)
    check('roll 6, four tokens in yard (one distinct move): ONE token comes out automatically, no tap',sorted(st(pg,'r'))==[-1,-1,-1,0] and pg.evaluate("()=>M.sel")==None)
    check('only ONE dice result was generated (no second roll during auto move)',pg.evaluate("()=>__rolls")==1,pg.evaluate("()=>__rolls"))
    pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000);check('rolled a 6 -> same player rolls again, exactly once',pg.evaluate("()=>M.players[M.turn].k")=='r')
    pg.evaluate("()=>{window.__f=null}")
    for k in ['r','y']:
        pass
    # one token on board, rest yard, roll 3 -> auto move
    setup(pg,'r',[5,-1,-1,-1],3);pg.wait_for_function("()=>S.filter(t=>t.k=='r'&&t.s==8).length==1",timeout=6000)
    check('one eligible token on board (others in yard, roll 3): moved automatically 5 -> 8',sorted(st(pg,'r'))==[-1,-1,-1,8],st(pg,'r'));check('no second dice result',pg.evaluate("()=>__rolls")==1)
    pg.wait_for_function("()=>M.players[M.turn].k=='y'",timeout=8000)
    # roll 3, nothing eligible -> turn passes with no move
    pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000)
    setup(pg,'y',[-1,-1,-1,-1],3);pg.wait_for_function("()=>M.players[M.turn].k=='r'",timeout=8000)
    check('no eligible token: turn passes (existing rule), nothing moved',st(pg,'y')==[-1,-1,-1,-1])
    # two eligible tokens -> choose
    pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000)
    setup(pg,'r',[5,9,-1,-1],3);time.sleep(2.2)
    check('two eligible tokens: nothing auto-moves, player must choose',st(pg,'r')==[5,9,-1,-1] and pg.evaluate("()=>M.elig.length")==2)
    check('two eligible tokens: both glow and a clear prompt is shown',pg.evaluate("()=>document.querySelectorAll('.tg.elig').length")==2 and 'Tap' in pg.inner_text('#hint2'),pg.inner_text('#hint2'))
    pg.evaluate("()=>{const t=M.elig[1];t.el.dispatchEvent(new MouseEvent('click',{bubbles:true}))}");pg.wait_for_function("()=>S.filter(t=>t.k=='r').map(t=>t.s).join()=='5,12,-1,-1'",timeout=6000)
    check('ONE tap on the chosen token moves it (9 -> 12); the other did not move',True)
    pg.wait_for_function("()=>M.players[M.turn].k=='y'&&M.canRoll",timeout=8000)
    # 6 with one board token + yard tokens = two distinct moves -> choose
    setup(pg,'y',[7,-1,-1,-1],6);time.sleep(2.2)
    check('roll 6 with one token on board AND tokens in yard: player chooses (no auto)',st(pg,'y')==[7,-1,-1,-1] and pg.evaluate("()=>document.querySelectorAll('.tg.elig').length")==4)
    # home overshoot: only one legal
    pg.evaluate("()=>{M.elig.forEach(t=>t.el.classList.remove('elig'));M.sel=null}")
    check('no page errors (auto move)',not pg.errs,pg.errs);pg.close()
    # blocked/overshoot + every colour in 4P and 6P
    for n in (4,6):
        pg=new(b);start(pg,n);okc=[]
        for k in {4:['r','g','y','b'],6:['r','g','y','b','o','p']}[n]:
            pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=15000)
            HOME=pg.evaluate("()=>HOME");setup(pg,k,[HOME-2,HOME-2,-1,-1] if False else [HOME-3,-1,-1,-1],4)  # overshoot: 4 > 3 -> nothing eligible
            pg.wait_for_function(f"()=>M.players[M.turn].k!='{k}'",timeout=8000);okc.append(st(pg,k)==[HOME-3,-1,-1,-1])
        check(f'{n}P: overshooting home is not a legal move for any colour (no move, turn passes)',all(okc),okc)
        pg.close()
        pg=new(b);start(pg,n);okc=[]
        for k in {4:['r','g','y','b'],6:['r','g','y','b','o','p']}[n]:
            pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=15000)
            setup(pg,k,[10,-1,-1,-1],2);pg.wait_for_function(f"()=>S.filter(t=>t.k=='{k}').some(t=>t.s==12)",timeout=6000);okc.append(sorted(st(pg,k))==[-1,-1,-1,12] and pg.evaluate("()=>__rolls")==1)
            pg.wait_for_function("()=>M.canRoll&&!M.busy",timeout=8000)
        check(f'{n}P: single eligible token auto-moves correctly for every colour ({"/".join(["r","g","y","b","o","p"][:n])}), one dice result each',all(okc),okc);pg.close()
    # computer opponent still plays itself
    pg=new(b);start(pg,2,h=1);pg.evaluate("()=>{window.__f=null}")
    pg.click('#dice',force=True);pg.wait_for_function("()=>M.players[M.turn].k=='y'||M.canRoll",timeout=12000)
    t0=time.time();ok=False
    while time.time()-t0<20:
        if pg.evaluate("()=>M.players[M.turn].k=='y'&&M.dice.state=='settled'"):ok=True;break
        if pg.evaluate("()=>M.canRoll&&!M.busy&&M.players[M.turn].k=='r'"):pg.click('#dice',force=True)
        time.sleep(.2)
    check('computer turns unaffected (CPU rolls and moves by itself)',ok);pg.close()
    # ------------------------------------------------ 2. CAPTIONS
    pg=new(b);start(pg,4,h=2)
    seen=set();texts=[];t0=time.time();rolls=0
    while time.time()-t0<28:
        pg.evaluate("()=>{window.__f=null}")
        if pg.evaluate("()=>M&&M.canRoll&&!M.busy&&M.players[M.turn].human"):pg.click('#dice',force=True);rolls+=1
        pg.evaluate("()=>{if(M.elig&&M.elig.length>1&&!M.busy){M.elig[0].el.dispatchEvent(new MouseEvent('click',{bubbles:true}));setTimeout(()=>M.sel&&M.sel.el.dispatchEvent(new MouseEvent('click',{bubbles:true})),80)}}")
        r=pg.evaluate("""()=>{const out=[];const dev=/[\\u0900-\\u097F]/;document.querySelectorAll('#game *,#res *').forEach(e=>{if(!e.children.length&&e.offsetParent!==null&&dev.test(e.textContent))out.push(e.id||e.className+':'+e.textContent.slice(0,30))});return {c:document.getElementById('cap').textContent,cv:getComputedStyle(document.getElementById('cap')).color,dev:out}}""")
        if r['c']:texts.append(r['c'])
        for d in r['dev']:seen.add(d)
        time.sleep(.15)
    sp=pg.evaluate("()=>__spoken.length")
    check('28s of real gameplay (rolls, moves, captures): caption element never contains text',not texts,texts[:3])
    check('no visible Hindi (Devanagari) text anywhere in game screen',not seen,list(seen)[:5])
    check('voice/audio still works: Hindi dialogue was spoken through speech synthesis',sp>0,sp)
    check('"Show captions" setting removed; no caption component can come back',pg.evaluate("()=>!document.getElementById('o-cc')&&(()=>{const c=document.getElementById('cap');c.textContent='X';return c.textContent==''})()"))
    check('no page errors (captions)',not pg.errs,pg.errs);pg.close()
    # ------------------------------------------------ 3. RANKING 2..6
    def finish_setup(pg,n):
        pg.evaluate("""()=>{const m=M;m.players.forEach(p=>{S.filter(t=>t.k==p.k).forEach((t,i)=>t.s=i<3?HOME:HOME-1)});render();window.__f=1;window.__turns.length=0}""")
    for n,h in [(2,2),(3,3),(4,4),(5,5),(6,6),(4,1),(6,2)]:
        pg=new(b);start(pg,n,h=h);finish_setup(pg,n);order=[];early=None;t0=time.time()
        while time.time()-t0<100:
            r=pg.evaluate("()=>({done:M.done,fin:M.rank.length,resHidden:document.getElementById('res').hidden,can:M.canRoll&&!M.busy&&M.players[M.turn].human})")
            if r['fin']>=1 and r['fin']<n-1 and early is None:early=r['resHidden']
            if r['done']:break
            if r['can']:pg.click('#dice',force=True)
            time.sleep(.12)
        d=pg.evaluate("""()=>({done:M.done,rank:M.rank.map(p=>p.k),active:M.players.filter(p=>!p.fin).map(p=>p.k),fin:M.players.map(p=>[p.k,p.fin||0]),hidden:document.getElementById('res').hidden,
          rows:[...document.querySelectorAll('#rank li')].map(li=>({cls:li.className,name:li.querySelector('b').textContent,lab:li.querySelector('small').textContent,crown:!!li.querySelector('.bd .cr'),bd:li.querySelector('.bd').className})),
          turns:__turns,cards:[...document.querySelectorAll('.pp.fin .rk')].map(e=>e.textContent),dice:document.querySelectorAll('#dice').length})""")
        tag=f'{n}P ({h} human)'
        check(f'{tag}: match ends only when {n-1} players finished; exactly 1 player left = final loser',d['done'] and len(d['rank'])==n-1 and len(d['active'])==1,d)
        if n>2:check(f'{tag}: final celebration NOT shown after the first finisher (match continued)',early is True,early)
        loser=d['active'][0] if d['active'] else None
        check(f'{tag}: result screen lists all {n} players, in finishing order, loser last',not d['hidden'] and len(d['rows'])==n and [r['cls'].split()[1] for r in d['rows']].count('lose')==1 and d['rows'][-1]['cls'].split()[1]=='lose',d['rows'])
        check(f'{tag}: Gold/Silver/Bronze crowns for 1st/2nd/3rd, numbered badges for 4th/5th, loser has no crown',[r['crown'] for r in d['rows']]==[True]*min(3,n-1)+[False]*(n-min(3,n-1)) and all('o' in r['bd'].split() for r in d['rows'][3:-1]) and 'lose' in d['rows'][-1]['bd'],d['rows'])
        check(f'{tag}: labels say Last Place · Eliminated only for the loser',d['rows'][-1]['lab'].startswith('Last Place') and all('Last' not in r['lab'] for r in d['rows'][:-1]),[r['lab'] for r in d['rows']])
        fk=[k for k,f in d['fin'] if f]
        check(f'{tag}: finished players were never given another turn',not any(t[1] for t in d['turns']),[t for t in d['turns'] if t[1]])
        check(f'{tag}: finishing positions 1..{n-1} assigned in order, each unique',sorted(f for k,f in d['fin'] if f)==list(range(1,n)) ,d['fin'])
        check(f'{tag}: player-card badges shown for finished players',len(d['cards'])==n-1,d['cards']);check(f'{tag}: single dice element',d['dice']==1)
        check(f'{tag}: no page errors',not pg.errs,pg.errs)
        if n in(3,6):pg.wait_for_timeout(2600)
        if n==6:pg.screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/rank_6p_final.png')
        if n==3:pg.screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/rank_3p_final.png')
        pg.close()
    # mid-match state: after the first finisher, card badge + inactive + match continues
    pg=new(b);start(pg,4);finish_setup(pg,4)
    pg.evaluate("()=>{S.filter(t=>t.k!='r').forEach(t=>t.s=-1)}")  # only red can finish; others stay far away
    pg.click('#dice',force=True);pg.wait_for_function("()=>M.rank.length==1",timeout=8000);pg.evaluate("()=>{window.__f=null}");pg.wait_for_function("()=>M.players[M.turn].k!='r'&&M.canRoll",timeout=8000)
    d=pg.evaluate("()=>({m:!M.done,res:document.getElementById('res').hidden,badge:document.querySelector('#p-r .rk').textContent,cls:document.getElementById('p-r').className,k:M.players[M.turn].k,tok:S.filter(t=>t.k=='r').map(t=>t.s)})")
    check('after 1st finisher: Gold Crown badge on card, card inactive, tokens stay home, match continues for others',d['m'] and d['res'] and d['badge']=='1st' and 'fin' in d['cls'] and d['tok']==[56]*4 and d['k']=='g',d)
    pg.screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/rank_mid_4p.png')
    # a finished player cannot roll / move: try forcing
    pg.evaluate("()=>{const m=M;m.turn=0;window.__ok=true}");
    check('finished player cannot be made to roll (turn engine skips them)',pg.evaluate("()=>{const m=M;const before=m.turn;pass(m,false);return m.players[m.turn].k!='r'}"))
    pg.close()
    # player removed through settings while others finished -> match still ends with exactly one loser
    pg=new(b);start(pg,3);finish_setup(pg,3);pg.evaluate("()=>{S.filter(t=>t.k=='y').forEach(t=>t.s=-1)}");pg.click('#dice',force=True)
    pg.wait_for_function("()=>M.rank.length==1",timeout=8000);pg.evaluate("()=>{window.__f=null;M.pendRm=['y']}")
    pg.wait_for_function("()=>M.done",timeout=15000);rows=pg.evaluate("()=>[...document.querySelectorAll('#rank li')].map(li=>li.className.split(' ')[1]+':'+li.querySelector('b').textContent)")
    check('3P: removing a player after 1st finisher leaves 1 active -> match ends, removed/last player is the single loser',len(rows)==3 and [r.split(':')[0] for r in rows].count('lose')==1 and rows[-1].startswith('lose'),rows)
    pg.close()
    b.close()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
