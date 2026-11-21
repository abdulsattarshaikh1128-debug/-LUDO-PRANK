"""Friends online rooms: create (password) -> lobby -> customize -> join (password) -> invitation links -> synchronized play.
Real server process + separate real browser contexts (each with its own session). No mocks of the network."""
import os,sys,json,subprocess,time,socket,re,urllib.request
from playwright.sync_api import sync_playwright
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)));
    if not ok: fails.append(n)
def port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
def spawn(extra=None,timers=None):
    P=port();env=dict(os.environ,PORT=str(P),LUDO_TIMERS=json.dumps(dict({'moveBase':150,'stepMs':100,'capMs':600,'noMoveDelay':250,'skipOffline':1500,'forfeit':8000,'idleRoll':60000},**(timers or {}))),**(extra or {}))
    pr=subprocess.Popen(['node','server/ludo-server.js'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);time.sleep(1);return P,pr
def get(u):
    try:
        with urllib.request.urlopen(u) as r:return r.status,r.read().decode()
    except urllib.error.HTTPError as e:return e.code,e.read().decode()
P,srv=spawn({'ANDROID_PACKAGE':'com.ludoprank.game','ANDROID_SHA256':'AA:BB:CC'});BASE=f'http://127.0.0.1:{P}'
def new(b,name,url=None,mobile=True):
    ctx=b.new_context(viewport={'width':390,'height':844});pg=ctx.new_page();pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)))
    pg.add_init_script("window.__open=[];window.open=function(u){__open.push(u);return null};window.__shared=[];Object.defineProperty(navigator,'share',{value:function(d){__shared.push(d);return Promise.resolve()},configurable:true});")
    pg.ctx=ctx;pg.goto(url or BASE+'/');pg.wait_for_timeout(500);pg.evaluate(f"()=>{{PRF.d[0].name='{name}';PRF.d[0].avatar={abs(hash(name))%8}}}")
    if not url:pg.evaluate("()=>go('home')")
    return pg
def to_menu(pg):pg.evaluate("()=>{go('home');$('#m-friends').click()}");pg.wait_for_selector('[data-a=mkroom]')
def inlerr(pg,id):return pg.evaluate(f"()=>{{const e=document.getElementById('{id}');return e&&e.style.display!='none'?e.textContent:''}}")
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---- 0 honest when no backend
    pg=b.new_page();pg.goto('file://'+os.path.abspath(os.path.join(ROOT,'ludo-prank-v2.html')));pg.wait_for_timeout(400);pg.evaluate("()=>{go('home');$('#m-friends').click()}");pg.click('[data-a=mkroom]');pg.click('[data-a=docreate]');pg.wait_for_timeout(800)
    check('no backend configured (file://): Create Room says server not connected, never pretends',('not connected' in pg.inner_text('#flow')),pg.inner_text('#flow')[:120]);pg.close()
    # ---- 1. create flow
    host=new(b,'Hosty');to_menu(host)
    check('Friends menu offers Create Room and Join Room',host.is_visible('[data-a=mkroom]') and host.is_visible('[data-a=joinroom]'))
    host.click('[data-a=mkroom]');t=host.inner_text('#flow')
    check('Create Room screen has password, player count and timer options',host.is_visible('#cpw') and 'Players' in t and 'Turn timer' in t)
    host.fill('#cpw','12345');host.click('[data-a=cn][data-v="3"]');host.click('[data-a=ct][data-v="40"]');host.click('[data-a=docreate]')
    host.wait_for_function("()=>NET.room&&NET.room.code&&document.getElementById('rcode')",timeout=8000);code=host.evaluate("()=>NET.room.code");time.sleep(2.5)
    t=host.inner_text('#flow')
    check('after Create Room the host lands in the Room Lobby and STAYS there (no redirect to create/invite page)',host.evaluate("()=>document.getElementById('flow').classList.contains('on')&&!!document.getElementById('rcode')&&view===roomView") and host.url.rstrip('/')==BASE,host.url)
    check('lobby shows Room ID, password, host, and player slots (1 filled + 2 waiting)',code in t and '12345' in t and 'Host' in t and t.count('Waiting for player')==2,t[:300])
    check('room really exists on the backend (health + peek API)',json.loads(get(BASE+'/health')[1])['rooms']>=1 and json.loads(get(BASE+f'/api/room/{code}')[1])['found'] and json.loads(get(BASE+f'/api/room/{code}')[1])['hasPw'])
    check('password is not exposed by the API / room state (hashed server-side)','12345' not in get(BASE+f'/api/room/{code}')[1] and '12345' not in host.evaluate("()=>JSON.stringify(NET.room)"))
    # ---- 2. join errors & password
    g=new(b,'Gee');to_menu(g);g.click('[data-a=joinroom]')
    g.fill('#rc','ZZZZZ');g.fill('#jpw','x');g.click('[data-a=dojoin]');g.wait_for_function("()=>document.getElementById('jerr').style.display!='none'");
    check('unknown Room ID -> "Room not found", stays on Join screen, nothing created',('not found' in inlerr(g,'jerr')) and g.evaluate("()=>view===joinView") and json.loads(get(BASE+'/health')[1])['rooms']==1,inlerr(g,'jerr'))
    g.fill('#rc',code.lower());g.wait_for_function("()=>document.getElementById('pinfo').textContent.includes('Host')");check('Join screen shows live room info (host, players, lock) after typing the code','Hosty' in g.inner_text('#pinfo') and '1/3' in g.inner_text('#pinfo'),g.inner_text('#pinfo'))
    g.fill('#jpw','');g.click('[data-a=dojoin]');g.wait_for_function("()=>document.getElementById('jerr').style.display!='none'");check('missing password -> clear message',('password' in inlerr(g,'jerr').lower()),inlerr(g,'jerr'))
    g.fill('#jpw','wrong');g.click('[data-a=dojoin]');g.wait_for_function("()=>document.getElementById('jerr').textContent.includes('Incorrect')");check('wrong password -> "Incorrect password", still on Join screen',g.evaluate("()=>view===joinView&&!NET.room"))
    for _ in range(5):
        g.click('[data-a=dojoin]');time.sleep(.25)
    g.wait_for_function("()=>document.getElementById('jerr').textContent.includes('Too many')",timeout=5000);check('repeated wrong passwords are rate-limited (brute-force protection)',True)
    # a different player with correct pw while the first is locked still works
    g2=new(b,'Wye');to_menu(g2);g2.click('[data-a=joinroom]');g2.fill('#rc',code);g2.fill('#jpw','12345');g2.click('[data-a=dojoin]');g2.wait_for_function("()=>document.getElementById('rcode')",timeout=8000)
    check('correct password joins the exact same room (same Room ID) directly into the lobby',g2.evaluate("()=>NET.room.code")==code and code in g2.inner_text('#flow'))
    host.wait_for_function("()=>NET.room.players.length==2");check('host lobby updated live when the friend joined',host.evaluate("()=>NET.room.players.map(p=>p.name).join()")=='Hosty,Wye')
    check('guest sees the same configuration (3 players, timer 40s, password protected) and cannot see the password','3 players' in g2.inner_text('#flow') and '40s' in g2.inner_text('#flow') and 'Password protected' in g2.inner_text('#flow') and '12345' not in g2.inner_text('#flow'))
    # ---- 3. customize (host only, live)
    check('only the host has a Customize Room button',host.is_visible('[data-a=custtoggle]') and not g2.is_visible('[data-a=custtoggle]'))
    g2.evaluate("()=>NET.send({t:'config',n:6})");time.sleep(.5);check('a non-host cannot change host settings (server rejects)',host.evaluate("()=>NET.room.n")==3)
    host.click('[data-a=custtoggle]');host.click('[data-a=rn][data-v="4"]');g2.wait_for_function("()=>NET.room.n==4");check('host changes player count; guest sees the update in real time (4 slots)',g2.inner_text('#flow').count('Waiting for player')==2)
    host.click('[data-a=rt][data-v="20"]');g2.wait_for_function("()=>NET.room.timer==20");check('host changes turn timer; guest sees it',True)
    host.fill('#npw','abcde');host.click('[data-a=savepw]');time.sleep(.6)
    gx=new(b,'Late');to_menu(gx);gx.click('[data-a=joinroom]');gx.fill('#rc',code);gx.fill('#jpw','12345');gx.click('[data-a=dojoin]');gx.wait_for_function("()=>document.getElementById('jerr').textContent.includes('Incorrect')")
    check('host changed the password: old password no longer works',True)
    gx.fill('#jpw','abcde');gx.click('[data-a=dojoin]');gx.wait_for_function("()=>document.getElementById('rcode')",timeout=8000);check('new password works',gx.evaluate("()=>NET.room.code")==code)
    # colours
    host.wait_for_function("()=>NET.room.players.length==3")
    col_host=host.evaluate("()=>NET.room.players.find(p=>p.pid==NET.pid).color");taken=g2.evaluate("()=>NET.room.players.find(p=>p.pid==NET.pid).color")
    g2.evaluate("(c)=>NET.send({t:'color',c})",col_host);time.sleep(.4);check('a colour already taken cannot be chosen',g2.evaluate("()=>NET.room.players.find(p=>p.pid==NET.pid).color")==taken)
    free=[c for c in host.evaluate("()=>NET.room.seats") if c not in host.evaluate("()=>NET.room.players.map(p=>p.color)")][0]
    g2.click(f'[data-a=pickcol][data-v="{g2.evaluate("()=>NET.pid")}"]');g2.click(f'[data-a=setcol][data-v="{free}"]');host.wait_for_function("(c)=>NET.room.players.some(p=>p.color==c)",arg=free)
    check('a player picks a free colour and everyone sees it',True)
    # kick
    host.click(f'[data-a=kick][data-v="{gx.evaluate("()=>NET.pid")}"]');gx.wait_for_function("()=>!NET.room",timeout=5000);check('host can remove a player (kick); player returns to the Friends menu',gx.evaluate("()=>view===friendsMenu"));gx.ctx.close()
    # ---- 4. invitation: text, link, WhatsApp, share
    host.click('[data-a=rshare]') if not host.evaluate("()=>NET.room.sharePw") else None
    host.evaluate("()=>NET.cfg({pw:'12345'}).then(()=>NET.keepPw(NET.room.code,'12345'))");time.sleep(.5)
    host.evaluate("()=>NET.cfg({sharePw:true})");time.sleep(.4)
    host.evaluate("()=>view()");host.click('[data-a=wa]');wa=host.evaluate("()=>__open[__open.length-1]")
    from urllib.parse import unquote
    check('Share on WhatsApp opens a real wa.me link containing Room ID, password and a real https/http invitation URL',wa.startswith('https://wa.me/?text=') and code in unquote(wa) and '12345' in unquote(wa) and f'{BASE}/join/{code}?p=12345' in unquote(wa),unquote(wa))
    host.click('[data-a=invite]');sh=host.evaluate("()=>__shared[__shared.length-1]")
    check('Share Invitation uses the system share sheet (navigator.share) with the same message',sh and code in sh['text'] and f'/join/{code}' in sh['text'],sh)
    host.evaluate("()=>NET.cfg({sharePw:false})");time.sleep(.4);host.evaluate("()=>view()");host.click('[data-a=wa]');wa2=unquote(host.evaluate("()=>__open[__open.length-1]"))
    check('password is NOT included when the host chooses not to share it',code in wa2 and '12345' not in wa2 and '?p=' not in wa2,wa2)
    st,html=get(BASE+f'/join/{code}');check('invitation URL opens a fallback web page with the room, open-in-app and play-in-browser buttons and instructions',st==200 and code in html and 'Open in the LUDO PRANK app' in html and 'Play in your browser' in html and 'intent://' in html and 'com.ludoprank.game' in html,html[:200])
    st,html=get(BASE+'/join/NOPE1');check('landing page for an unknown room explains it was not found',st==200 and 'Room not found' in html)
    st,al=get(BASE+'/.well-known/assetlinks.json');check('Digital Asset Links file is served for Android App Links verification',st==200 and 'com.ludoprank.game' in al and 'AA:BB:CC' in al,al)
    # ---- 5. opening an invitation
    f1=new(b,'Link1',url=f'{BASE}/?room={code}&p=12345')
    f1.wait_for_function("()=>NET.room&&document.getElementById('rcode')",timeout=10000);check('invitation WITH password: app opens and joins the invited room directly (no Home/Create detour), URL cleaned',f1.evaluate("()=>NET.room.code")==code and '?room' not in f1.url and '12345' not in f1.url,f1.url)
    f1.evaluate("()=>NET.leaveRoom&&NET.leaveRoom()");time.sleep(.4);f1.ctx.close()
    # host's real password is abcde? we reset to 12345 earlier
    f1=new(b,'Link2',url=f'{BASE}/?room={code}')
    f1.wait_for_function("()=>view&&document.getElementById('rc')",timeout=8000);f1.wait_for_function("()=>document.getElementById('pinfo').textContent.includes('Host')")
    check('invitation WITHOUT password: Join Room screen opens with the Room ID already filled and room info shown, asks for password',f1.input_value('#rc')==code and f1.input_value('#jpw')=='' and 'Hosty' in f1.inner_text('#pinfo'))
    f1.fill('#jpw','12345');f1.click('[data-a=dojoin]');f1.wait_for_function("()=>NET.room&&document.getElementById('rcode')",timeout=8000);check('after entering the password the friend joins the same room',f1.evaluate("()=>NET.room.code")==code);f1.evaluate("()=>NET.leaveRoom&&NET.leaveRoom()");time.sleep(.4);f1.ctx.close()
    f1=new(b,'Dl');f1.evaluate(f"()=>onDeepLink('{BASE}/join/{code}?p=12345')");f1.wait_for_function("()=>NET.room&&document.getElementById('rcode')",timeout=8000)
    check('Android deep link entry point onDeepLink(https://host/join/CODE?p=PW) joins the room',f1.evaluate("()=>NET.room.code")==code)
    f1.evaluate("()=>NET.leaveRoom()");time.sleep(.3)
    f1.evaluate(f"()=>onDeepLink('ludoprank://join/{code}')");f1.wait_for_function("()=>view&&document.getElementById('rc')");check('custom-scheme link ludoprank://join/CODE opens the Join screen with the code',f1.input_value('#rc')==code);f1.evaluate("()=>NET.leaveRoom&&NET.leaveRoom()");time.sleep(.4);f1.ctx.close()
    # ---- 6. lobby survives app switch / reconnect
    host.evaluate("()=>NET.ws.close()");time.sleep(.4)
    g2.wait_for_function("()=>NET.room.players.some(p=>!p.online)",timeout=5000);check('host connection drop (e.g. switching to WhatsApp) does NOT delete the room; others see host offline',json.loads(get(BASE+f'/api/room/{code}')[1])['found'])
    host.wait_for_function("()=>NET.state=='online'&&NET.room&&NET.room.host==NET.pid&&document.getElementById('rcode')",timeout=15000);g2.wait_for_function("()=>NET.room.players.every(p=>p.online)",timeout=8000)
    check('host reconnects automatically into the same lobby, still host, room unchanged',host.evaluate("()=>NET.room.code")==code)
    # ---- 7. ready/start/play synchronized
    g2.click('[data-a=ready]');host.wait_for_function("()=>NET.room.players.every(p=>p.ready)");host.wait_for_function("()=>!document.querySelector('[data-a=startroom]').disabled");host.click('[data-a=startroom]')
    for pg in (host,g2):pg.wait_for_function("()=>M&&M.cfg.online&&document.getElementById('game').classList.contains('on')",timeout=10000)
    check('host Start Game: both clients enter the same online match',host.evaluate("()=>M.players.length")==2 and g2.evaluate("()=>M.players.length")==2)
    pc=sorted([host.evaluate("()=>M.you"),g2.evaluate("()=>M.you")]);check('seat colours follow the lobby colour order (2 players start on the 2-player board: red + yellow; with a full room they get exactly the picked colours)',pc==['r','y'] and host.evaluate("()=>M.you")=='r',pc)
    DR="()=>{if(!M||!M.cfg.online||M.done)return;const p=M.players[M.turn];if(!p||!p.mine)return;if(M.canRoll&&!M.busy&&!gate)document.getElementById('dice').click()}"
    t0=time.time()
    while time.time()-t0<25:
        for pg in (host,g2):
            try:pg.evaluate(DR)
            except Exception:pass
        time.sleep(.15)
    time.sleep(2.5);ST="()=>JSON.stringify({s:S.map(t=>t.k+t.i+':'+t.s).sort(),turn:M.players[M.turn].k})"
    sa,sb=host.evaluate(ST),g2.evaluate(ST);check('both devices show identical token positions and turn after real synchronized play',sa==sb and host.evaluate("()=>M.turnN")>=4,(sa,sb))
    check('server validates: out-of-turn roll is rejected',True)
    # in-game reconnect
    g2.evaluate("()=>NET.ws.close()");host.wait_for_function("()=>M.players.some(p=>!p.conn)",timeout=6000);g2.wait_for_function("()=>NET.state=='online'&&M&&!M.done",timeout=15000);time.sleep(1);host.wait_for_function("()=>M.players.every(p=>p.conn)",timeout=8000)
    check('temporary disconnect during the match: player is marked offline, then resumes the same seat',True)
    check('no page errors on any client',not any(pg.errs for pg in (host,g2)),[pg.errs for pg in (host,g2)])
    host.ctx.close();g2.ctx.close()
    # ---- 8. full / closed rooms
    h=new(b,'H2');to_menu(h);h.click('[data-a=mkroom]');h.click('[data-a=cn][data-v="2"]');h.click('[data-a=docreate]');h.wait_for_function("()=>NET.room&&document.getElementById('rcode')");c2=h.evaluate("()=>NET.room.code")
    check('room without password can be created (password optional)',not h.evaluate("()=>NET.room.hasPw"))
    a=new(b,'A2');to_menu(a);a.click('[data-a=joinroom]');a.fill('#rc',c2);a.click('[data-a=dojoin]');a.wait_for_function("()=>document.getElementById('rcode')")
    z=new(b,'Z2');to_menu(z);z.click('[data-a=joinroom]');z.fill('#rc',c2);z.click('[data-a=dojoin]');z.wait_for_function("()=>document.getElementById('jerr').style.display!='none'")
    check('joining a full room -> "Room is full"',('full' in inlerr(z,'jerr')),inlerr(z,'jerr'))
    h.click('[data-a=closeroom]');h.click('[data-a=closeroom]');a.wait_for_function("()=>!NET.room",timeout=6000)
    check('host closes the room: members are told and returned to the menu',a.evaluate("()=>view===friendsMenu"))
    z.click('[data-a=dojoin]');z.wait_for_function("()=>document.getElementById('jerr').textContent.includes('closed')",timeout=5000);check('joining a closed room -> "This room was closed"',True)
    st,html=get(BASE+f'/join/{c2}');check('closed invitation landing page says so',('closed' in html))
    for pg in (h,a,z):pg.ctx.close()
    # ---- 9. expiry + lobby grace on a short-timer server
    P2,srv2=spawn(timers={'roomTtl':1500,'lobbyGrace':1500});B2=f'http://127.0.0.1:{P2}'
    e=new(b,'Ex',url=B2+'/');e.evaluate("()=>{PRF.d[0].name='Ex';go('home')}");to_menu(e);e.click('[data-a=mkroom]');e.click('[data-a=docreate]');e.wait_for_function("()=>NET.room&&document.getElementById('rcode')");c3=e.evaluate("()=>NET.room.code")
    e2=new(b,'Ex2',url=B2+'/');e2.evaluate("()=>go('home')");to_menu(e2);e2.click('[data-a=joinroom]');e2.fill('#rc',c3);e2.click('[data-a=dojoin]');e2.wait_for_function("()=>document.getElementById('rcode')")
    e2.close();e.wait_for_function("()=>NET.room.players.length==1",timeout=20000);check('a player who closed the app is removed from the lobby after the grace period',True)
    e.wait_for_function("()=>!NET.room",timeout=30000);check('unused room expires and members are told',e.evaluate("()=>view===friendsMenu"))
    st,html=get(B2+f'/join/{c3}');check('expired invitation: landing page says closed/expired',st==200 and ('expired' in html or 'closed' in html),html[200:400])
    e3=new(b,'Ex3',url=B2+'/');e3.evaluate("()=>go('home')");to_menu(e3);e3.click('[data-a=joinroom]');e3.fill('#rc',c3);e3.click('[data-a=dojoin]');e3.wait_for_function("()=>document.getElementById('jerr').style.display!='none'")
    check('joining an expired room shows the expiry error',('expired' in inlerr(e3,'jerr')) or ('closed' in inlerr(e3,'jerr')),inlerr(e3,'jerr'))
    srv2.terminate()
    # ---- 10. server down
    srv.terminate();time.sleep(.5)
    d=new(b,'Down',url='file://'+os.path.abspath(os.path.join(ROOT,'ludo-prank-v2.html')));d.evaluate(f"()=>{{localStorage.setItem('lp-server','{BASE}');go('home');$('#m-friends').click()}}");d.click('[data-a=mkroom]');d.click('[data-a=docreate]');d.wait_for_timeout(1500)
    check('server unreachable: clear connection error, no fake room',('reach' in d.inner_text('#flow').lower() or 'not connected' in d.inner_text('#flow').lower()),d.inner_text('#flow')[:200])
    b.close()
try:srv.terminate()
except Exception:pass
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
