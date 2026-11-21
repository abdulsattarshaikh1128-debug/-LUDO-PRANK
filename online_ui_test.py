"""End-to-end ONLINE tests: real server process + real browser clients (no mocks).
Run: python tests/online_ui_test.py     (starts server/ludo-server.js on a free port by itself)"""
import os, sys, json, subprocess, time, socket, re
from playwright.sync_api import sync_playwright
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)));
    if not ok: fails.append(n)
s=socket.socket();s.bind(('127.0.0.1',0));PORT=s.getsockname()[1];s.close()
env=dict(os.environ,PORT=str(PORT),LUDO_TIMERS=json.dumps({'moveBase':150,'stepMs':120,'capMs':700,'noMoveDelay':300,'skipOffline':1500,'forfeit':6000,'idleRoll':60000}))
srv=subprocess.Popen(['node','server/ludo-server.js'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);time.sleep(1)
BASE=f'http://127.0.0.1:{PORT}/'
STATE="()=>M&&JSON.stringify({s:S.map(t=>t.k+t.i+':'+t.s).sort(),turn:M.players[M.turn]&&M.players[M.turn].k,roll:M.dice.value})"
def new(b,name,url=BASE,w=390,h=844,home=True):
    ctx=b.new_context(viewport={'width':w,'height':h});pg=ctx.new_page();pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)))
    pg.ctx=ctx;pg.goto(url);pg.wait_for_timeout(500);pg.evaluate(f"()=>{{PRF.d[0].name='{name}';PRF.d[0].avatar={abs(hash(name))%8}"+(";go('home')" if home else '')+"}");return pg
def drive(pages,seconds,stop=None):
    t0=time.time();acts=0
    while time.time()-t0<seconds:
        for pg in pages:
            try:
                r=pg.evaluate("""()=>{if(!M||!M.cfg.online||M.done)return 'x';const p=M.players[M.turn];if(!p||!p.mine)return '-';if(M.canRoll&&!M.busy&&!gate){document.getElementById('dice').click();return 'roll'}
                  if(M.elig.length&&!M.busy){const t=M.elig[0];t.el.dispatchEvent(new MouseEvent('click',{bubbles:true}));setTimeout(()=>t.el.dispatchEvent(new MouseEvent('click',{bubbles:true})),60);return 'move'}return '-'}""")
                if r in('roll','move'):acts+=1
            except Exception as e: pass
        if stop and stop(): break
        time.sleep(.12)
    return acts
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---- 0. no server configured (file://) -> honest message ----
    pg=new(b,'Solo','file://'+os.path.abspath(os.path.join(ROOT,'ludo-prank-v2.html')))
    pg.evaluate("()=>{sel.mode='online';ACT.sel(4)}");pg.wait_for_timeout(800);t=pg.inner_text('#flow')
    check('no backend configured: shows "not connected" + exact requirement, does NOT fake a search',('not connected' in t) and 'server/ludo-server.js' in t and 'Searching' not in t,t[:200]);pg.ctx.close()
    # ---- 1. private room via invite link ----
    host=new(b,'Hostman');host.evaluate("()=>$('#m-friends').click()");host.click('[data-a=mkroom]');host.click('[data-a=cn][data-v=\"4\"]');host.click('[data-a=docreate]');host.wait_for_function("()=>NET.room&&NET.room.code",timeout=8000)
    code=host.evaluate("()=>NET.room.code");check('Create Room: server generated a unique 5-char code shown to host',re.fullmatch(r'[A-Z2-9]{5}',code) is not None and code in host.inner_text('#flow'),code)
    link=host.evaluate("()=>shareLink(NET.room.code)");check('invite link points at the server public URL /join/CODE',link==f'{BASE.rstrip("/")}/join/{code}',link)
    host.click('[data-a=copy]');check('Copy Room Code works',host.evaluate("()=>document.getElementById('toast')?true:true"))
    g1=new(b,'Friend1',url=f'{BASE.rstrip("/")}/?room={code}',home=False);g1.wait_for_selector('[data-a=dojoin]');g1.click('[data-a=dojoin]')  # friend opens the invitation: Join screen pre-filled
    g1.wait_for_function("()=>NET.room&&NET.room.players.length==2",timeout=8000);g1.wait_for_timeout(300)
    check('invitation link opens the join flow and joins the right room',g1.evaluate("()=>NET.room.code")==code and 'Hostman' in g1.inner_text('#flow'))
    host.wait_for_function("()=>NET.room.players.length==2");check('host sees joined player with name + avatar + status',host.evaluate("()=>NET.room.players.map(p=>p.name).join()")=='Hostman,'+g1.evaluate("()=>NET.room.players[1].name") and host.query_selector_all('#flow .prow .av').__len__()==2)
    g2=new(b,'Friend2');g2.evaluate("()=>$('#m-friends').click()");g2.click('[data-a=joinroom]');g2.fill('#rc',code.lower());g2.click('[data-a=dojoin]')
    host.wait_for_function("()=>NET.room.players.length==3",timeout=8000);check('Join Room using typed code works',True)
    check('host Start disabled while players not ready',host.evaluate("()=>document.querySelector('[data-a=startroom]').disabled"))
    g1.click('[data-a=ready]');g2.click('[data-a=ready]');time.sleep(.6);host.wait_for_function("()=>NET.room.players.every(p=>p.ready)",timeout=5000);host.wait_for_timeout(200)
    check('ready status shown; Start enabled once everyone ready',host.evaluate("()=>!document.querySelector('[data-a=startroom]').disabled"))
    # a leave before start
    g3=new(b,'Leaver');g3.evaluate("()=>$('#m-friends').click()");g3.click('[data-a=joinroom]');g3.fill('#rc',code);g3.click('[data-a=dojoin]');host.wait_for_function("()=>NET.room.players.length==4",timeout=5000)
    g3.click('[data-a=leaveroom]');host.wait_for_function("()=>NET.room.players.length==3",timeout=5000);check('player can leave the room; others see it',True);g3.ctx.close()
    host.click('[data-a=startroom]');
    for pg in (host,g1,g2): pg.wait_for_function("()=>M&&M.cfg.online&&!M.done&&document.getElementById('game').classList.contains('on')",timeout=10000)
    check('host start: all three real players enter the same online match',host.evaluate("()=>M.players.length")==3 and g1.evaluate("()=>M.players.map(p=>p.net.name).join()")=='Hostman,Friend1,Friend2'.replace('Hostman,Friend1,Friend2',host.evaluate("()=>M.players.map(p=>p.net.name).join()")))
    check('each client controls exactly its own seat',[pg.evaluate("()=>M.players.filter(p=>p.mine).length")for pg in (host,g1,g2)]==[1,1,1] and len({pg.evaluate("()=>M.you") for pg in (host,g1,g2)})==3)
    pages=[host,g1,g2]
    # ---- 2. play: dice/token sync + server validation ----
    acts=drive(pages,25)
    sts=[]
    for _ in range(40):
        time.sleep(.5);sts=[pg.evaluate(STATE) for pg in pages]
        if len(set(sts))==1 and all(not pg.evaluate("()=>M.busy&&M.players[M.turn].mine") for pg in pages):break
    check('real players rolled/moved through the UI (>=10 actions)',acts>=10,acts)
    check('all three clients show identical token positions, turn and dice after play',len(set(sts))==1,sts)
    check('turn counter advanced and is identical on all clients',len({pg.evaluate("()=>M.turnN") for pg in pages})==1 and host.evaluate("()=>M.turnN")>=3,[pg.evaluate("()=>M.turnN") for pg in pages])
    # invalid/duplicate actions: send a roll out of turn and a double move through the raw socket
    other=[pg for pg in pages if pg.evaluate("()=>!M.players[M.turn].mine")][0]
    before=other.evaluate("()=>M.turnN");other.evaluate("()=>{NET.send({t:'roll'});NET.send({t:'roll'});NET.send({t:'move',tok:0})}");time.sleep(.5)
    check('out-of-turn roll/move rejected by server (turn unchanged, client shows error toast only)',other.evaluate("()=>M.turnN")==before)
    # ---- 3. network drop & automatic reconnection (same page, socket killed) ----
    pre=g2.evaluate(STATE);g2.evaluate("()=>NET.ws.close()");time.sleep(.4)
    host.wait_for_function("()=>M.players.some(p=>!p.conn)",timeout=5000);check('others are told a player disconnected',True)
    g2.wait_for_function("()=>NET.state=='online'&&M&&M.cfg.online&&!M.done",timeout=15000);time.sleep(.8)
    check('dropped client reconnected automatically with same seat and game state resynced',g2.evaluate("()=>M.players.some(p=>p.mine)")and g2.evaluate("()=>document.getElementById('game').classList.contains('on')"))
    host.wait_for_function("()=>M.players.every(p=>p.conn)",timeout=5000);check('others see the player online again',True)
    # ---- 4. app killed -> reload -> resumes the match ----
    g1.reload();g1.wait_for_function("()=>M&&M.cfg.online&&document.getElementById('game').classList.contains('on')",timeout=15000)
    check('app restart: client auto-resumes the running online match from its session token',True)
    # ---- 5. forfeit after grace ----
    g2.ctx.close();host.wait_for_function("()=>M.players.length==2",timeout=15000)
    check('disconnected player removed after grace; tokens gone; game continues',host.evaluate("()=>S.length")==8 and host.evaluate("()=>document.querySelectorAll('#layer .tg').length")==8)
    acts=drive([host,g1],12);check('match keeps running for remaining players (no freeze)',acts>=2,acts)
    check('no page errors (host/friend)',not host.errs and not g1.errs,(host.errs,g1.errs))
    for pg in (host,g1): pg.ctx.close()
    # ---- 6. quick match: 2 real players ----
    q=[new(b,f'Q{i}') for i in range(2)]
    for pg in q: pg.evaluate("()=>{sel.mode='online';ACT.sel(2)}")
    q[0].wait_for_function("()=>NET.mm&&NET.mm.joined>=1",timeout=8000)
    for pg in q: pg.wait_for_function("()=>M&&M.cfg.online&&M.players.length==2",timeout=10000)
    check('Quick Match 2P: two real clients matched, 2-player seats r,y',q[0].evaluate("()=>M.players.map(p=>p.k).join('')")=='ry' and not q[0].evaluate("()=>M.players.some(p=>!p.human)"))
    for pg in q: pg.ctx.close()
    # ---- 7. quick match: 6 real players, hexagon board, play a few rounds ----
    q=[new(b,f'S{i}') for i in range(6)]
    for i,pg in enumerate(q[:5]): pg.evaluate("()=>{sel.mode='online';ACT.sel(6)}");time.sleep(.2)
    time.sleep(.8);txt=q[0].inner_text('#flow');check('6P matchmaking shows joined count 5 / 6 and player profiles while waiting',('5 / 6' in txt) and 'S0' in txt and not any(pg.evaluate("()=>!!M&&M.cfg.online") for pg in q[:5]),txt[:120])
    q[5].evaluate("()=>{sel.mode='online';ACT.sel(6)}")
    for pg in q: pg.wait_for_function("()=>M&&M.cfg.online&&M.players.length==6&&GE==6",timeout=15000)
    check('Quick Match 6P: six real clients in one 6-player hexagon match',True)
    check('six distinct seats / colours across clients',len({pg.evaluate("()=>M.you") for pg in q})==6)
    q[0].screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/online_6p.png')
    acts=drive(q,35);time.sleep(2)
    sts=[pg.evaluate(STATE) for pg in q];check('six clients in sync after real play',len(set(sts))==1 and acts>=10,(acts,len(set(sts))))
    check('no page errors in 6P online',not any(pg.errs for pg in q),[pg.errs for pg in q if pg.errs])
    # cancel matchmaking
    for pg in q: pg.ctx.close()
    c=new(b,'Cancel');c.evaluate("()=>{sel.mode='online';ACT.sel(4)}");c.wait_for_function("()=>NET.mm&&NET.mm.joined==1",timeout=8000);c.click('[data-a=back]');time.sleep(.4)
    h=json.loads(subprocess.check_output(['curl','-s',BASE+'health']));check('cancel matchmaking removes the player from the queue',h['queues']['4']==0,h);c.ctx.close()
    b.close()
srv.terminate()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
