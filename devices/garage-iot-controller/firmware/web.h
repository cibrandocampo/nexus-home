// Web UI served on "/". Single self-contained page that talks to /api/v1.
#pragma once

static const char WEB_PAGE[] = R"HTML(<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#11151c">
<title>Garage</title>
<style>
:root{color-scheme:dark;--bg:#11151c;--card:#1b222d;--line:#2a3442;--fg:#e8edf4;--mut:#8b98aa;--ok:#3ecf8e;--warn:#f5b041;--bad:#ef5350;--acc:#4c9aff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif}
main{max-width:460px;margin:0 auto;padding:16px}
header{display:flex;justify-content:space-between;align-items:center;margin:4px 2px 14px}
h1{font-size:20px;margin:0}
#conn{font-size:13px;color:var(--mut)}
#conn.off{color:var(--bad)}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
h2{font-size:13px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;font-weight:600}
.st{display:flex;align-items:center;gap:10px;font-size:26px;font-weight:700;margin-bottom:4px}
.dot{width:14px;height:14px;border-radius:50%;background:var(--mut);flex:none}
.sub{color:var(--mut);font-size:14px;min-height:20px;margin-bottom:14px}
.row{display:flex;gap:8px;flex-wrap:wrap}
button,select{font:inherit;color:var(--fg);background:#253041;border:1px solid var(--line);border-radius:10px;padding:13px 10px;min-height:48px}
button{flex:1;font-weight:600;cursor:pointer}
button.p{background:var(--acc);border-color:var(--acc);color:#fff}
button:disabled{opacity:.35;cursor:default}
button:active:not(:disabled){filter:brightness(1.25)}
select{flex:1.2}
dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:0;font-size:14px}
dt{color:var(--mut)}dd{margin:0;text-align:right}
#msg{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:var(--bad);color:#fff;padding:10px 16px;border-radius:10px;font-size:14px;max-width:90%}
#msg.ok{background:#1f7a52}
details summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between}
details summary::-webkit-details-marker{display:none}
details summary h2{margin:0}details summary:after{content:'▸';color:var(--mut)}details[open] summary:after{content:'▾'}
details[open] summary{margin-bottom:10px}
label{display:block;font-size:14px;color:var(--mut);margin:12px 0 4px}
input{width:100%;font:inherit;color:var(--fg);background:#253041;border:1px solid var(--line);border-radius:10px;padding:11px 12px}
.hint{font-size:13px;color:var(--mut);margin-top:4px}
.sep{border-top:1px solid var(--line);margin:16px 0 4px}
.alert{background:#3a1d22;border:1px solid var(--bad);color:#ffb4b4;border-radius:10px;padding:10px 12px;font-size:14px;margin-bottom:14px}
#log{list-style:none;margin:0;padding:0;font-size:14px}
#log li{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-top:1px solid var(--line)}
#log b{font-weight:600;display:block}
#log small{color:var(--mut);font-size:13px;display:block}
#log li:first-child{border:0}
#log li.bad b{color:var(--bad)}
#log span:last-child{color:var(--mut);white-space:nowrap;font-size:13px}
.blink{animation:b 1s infinite}@keyframes b{50%{opacity:.25}}
</style></head><body><main>
<header><h1 id="title">Garage</h1><span id="conn">connecting…</span></header>

<section><h2>Door</h2>
<div class="st"><span class="dot" id="dd"></span><span id="ds">—</span></div>
<div class="sub" id="dsub"></div>
<div class="alert" id="dfail" hidden><b>Close not confirmed.</b> The door was told to close but the sensor did not report it closed. It may be open.</div>
<div class="row">
<button disabled class="p" id="bo" data-c="door/open">Open</button>
<button disabled class="p" id="bc" data-c="door/close">Close</button>
<button disabled id="bs" data-c="door/stop">Stop</button>
</div>
<div class="row" style="margin-top:8px"><button disabled id="bt" data-c="door/toggle">Push button (single pulse)</button></div>
</section>

<section><h2>Light</h2>
<div class="st"><span class="dot" id="ld"></span><span id="ls">—</span></div>
<div class="sub" id="lsub"></div>
<div class="row">
<select id="dur" aria-label="Duration">
<option value="120">2 min</option><option value="600">10 min</option>
<option value="1800">30 min</option><option value="3600">1 hour</option>
<option value="0">No limit</option></select>
<button disabled class="p" id="bon">Turn on</button>
<button disabled id="bof" data-c="light/off">Turn off</button>
</div></section>

<section><h2>Status</h2><dl>
<dt>Ambient light</dt><dd id="ni">—</dd>
<dt>Door sensor</dt><dd id="se">—</dd>
<dt>Last triggered by</dt><dd id="so">—</dd>
<dt>WiFi</dt><dd id="wf">—</dd>
<dt>Uptime</dt><dd id="up">—</dd>
<dt>Firmware</dt><dd id="fw">—</dd>
<dt>Last restart</dt><dd id="rr">—</dd>
</dl></section>

<section><details id="set"><summary><h2>Settings</h2></summary>
<form id="sf">
<label for="s_name">Name</label><input id="s_name" maxlength="32" required>
<label for="s_open">Opening time (seconds)</label><input id="s_open" type="number" min="5" max="120" required>
<label for="s_close">Close confirmation (seconds)</label><input id="s_close" type="number" min="10" max="180" required>
<div class="hint">A close not confirmed by the sensor within this time raises an alert.</div>
<label for="s_ssid">WiFi network</label><input id="s_ssid" maxlength="32" required autocapitalize="none" autocomplete="off">
<label for="s_pass">WiFi password</label><input id="s_pass" type="password" maxlength="63" placeholder="(unchanged)" autocomplete="new-password">
<div class="hint">A new network is tried first: if it does not connect within 60 s, the controller goes back to the current one.</div>
<label for="s_token">New access token</label><input id="s_token" minlength="8" maxlength="64" placeholder="(unchanged)" autocapitalize="none" autocomplete="off" spellcheck="false">
<div class="row" style="margin-top:14px"><button class="p" id="s_save">Save settings</button></div>
</form>
<div class="sep"></div>
<div class="row" style="margin-top:12px"><button id="s_restart">Restart controller</button></div>
<div class="hint">Refused while the door is moving. The activity list is cleared on restart.</div>
<div class="hint" style="margin-top:12px">Firmware <span id="fw_cur">—</span>. To update it, run tools/update.sh from a computer on this network.</div>
</details></section>

<section><h2>Recent activity</h2>
<ul id="log"><li><span>—</span></li></ul>
<div class="sub" style="margin:10px 0 0">Kept in memory: cleared when the controller restarts.</div>
</section>
<div id="msg" hidden></div>
</main><script>
const $=id=>document.getElementById(id),API='/api/v1/';
const DOOR={closed:['Closed','--ok'],open:['Open','--warn'],opening:['Opening…','--acc'],closing:['Closing…','--acc']};
const SRC={button:'button or remote',api:'web / API',sensor:'closed sensor',auto:'automatic',none:'—'};
// Log entry -> [what happened, why]. Door entries read as cause -> effect.
const WHO={button:'Push button or remote',api:'Web / API command',sensor:'Closed sensor',auto:'Automatic'};
const lt=v=>v?dur(v).replace(/ 0 s$/,'').replace(/ 0 min$/,''):'no limit';
let resetReason='';
function describe(e){
  const who=WHO[e.source]||e.source;
  switch(e.event+'/'+e.reason){
    case 'door_opening/command':return['Door opening',who+' · door was closed'];
    case 'door_opening/sensor_released':return['Door opening','Detected by the closed sensor (released), no command from this controller'];
    case 'door_closing/command':return['Door closing',who+' · door was open'];
    case 'door_open/travel_end':return['Door open','Opening time over, sensor not closed'];
    case 'door_open/stopped':return['Door stopped, open',who+' while it was moving'];
    case 'door_closed/stopped':return['Door stopped, closed',who+' while it was moving'];
    case 'door_closed/sensor_closed':return['Door closed',e.source=='sensor'?'Detected by the closed sensor':'Close confirmed by the closed sensor'];
    case 'door_closed/came_back':return['Door closed','Detected by the closed sensor during the opening'];
    case 'door_closed/startup':return['Door closed','Read from the sensor at start-up'];
    case 'door_open/startup':return['Door open','Read from the sensor at start-up (sensor not closed)'];
    case 'door_closed/no_movement':return['Door did not move','Opening time over, sensor still closed'];
    case 'button_ignored/too_soon':return['Push button ignored','Less than 1.2 s since the last pulse'];
  }
  switch(e.event){
    case 'close_failed':return['Close NOT confirmed: may be open','Sensor not closed '+e.value+' s after the close'];
    case 'light_on':return['Light on ('+lt(e.value)+')',e.source=='auto'?'Door opening at night':who];
    case 'light_off':return['Light off',e.source=='auto'?'Timer ended':who];
    case 'night':return['Night','Light sensor'];
    case 'day':return['Daylight','Light sensor'];
    case 'wifi_up':return['WiFi connected',''];
    case 'wifi_down':return['WiFi lost','Door and button keep working; reconnecting'];
    case 'boot':return['Controller started',resetReason];
    case 'watchdog_reset':return['Restarted by the watchdog','The program stopped responding'];
    case 'settings_changed':return['Settings saved',e.source=='api'?'From the settings page':'From the setup page'];
    case 'settings_save_failed':return['Settings NOT saved','Could not write them to the controller memory'];
    case 'wifi_changed':return['WiFi network changed','The new network connected and was saved'];
    case 'wifi_change_failed':return['WiFi change failed','The new network did not connect: back to the previous one'];
    case 'firmware_update_failed':return['Firmware update failed','The file could not be downloaded, did not pass the checks, or the update could not start'];
    case 'setup_mode':return['Setup mode','Jumper on pin 7 at start-up: own WiFi network for the setup page'];
  }
  return[e.event,who];
}
const RR={power:'power on',pin:'reset button',software:'firmware update or restart',watchdog:'watchdog (hang)',unknown:'—'};
let log=null,logRev=-1;
const ERR={door_busy:'The door is moving, please wait',unauthorized:'Wrong token',forbidden:'Request rejected'};
let last=null,lastAt=0,fails=0,busy=false,mt;
const dur=s=>s<60?s+' s':s<3600?Math.floor(s/60)+' min '+(s%60)+' s':s<86400?Math.floor(s/3600)+' h '+Math.floor(s%3600/60)+' min':Math.floor(s/86400)+' d '+Math.floor(s%86400/3600)+' h';
const DAYS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
// Recent events: relative time. Older ones: clock time, with the weekday or date if not today.
function when(ago){
  if(ago<60)return ago<5?'just now':ago+' s ago';
  if(ago<3600)return Math.floor(ago/60)+' min ago';
  const d=new Date(Date.now()-ago*1000),n=new Date(),hm=String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
  if(d.toDateString()==n.toDateString())return hm;
  return (ago<6*86400?DAYS[d.getDay()]:d.getDate()+'/'+(d.getMonth()+1))+' '+hm;
}
function msg(t,ok){const m=$('msg');m.textContent=t;m.className=ok?'ok':'';m.hidden=false;clearTimeout(mt);mt=setTimeout(()=>m.hidden=true,ok&&t.length>40?9000:4000)}
function render(){
  const s=last;if(!s)return;
  const el=Math.floor((Date.now()-lastAt)/1000),d=DOOR[s.door.state],mv=s.door.moving;
  $('ds').textContent=d[0];$('dd').style.background='var('+d[1]+')';$('dd').className='dot'+(mv?' blink':'');
  $('dsub').textContent='for '+dur(s.door.since_s+el);
  $('dfail').hidden=!s.door.close_failed;
  $('bo').disabled=busy||s.door.state!='closed';
  $('bc').disabled=busy||s.door.state!='open';
  $('bs').disabled=busy||!mv;$('bt').disabled=busy;
  const on=s.light.state=='on',rem=Math.max(0,s.light.remaining_s-el);
  $('ls').textContent=on?'On':'Off';$('ld').style.background=on?'var(--warn)':'';
  $('lsub').textContent=!on?'':s.light.timed?'turns off in '+dur(rem):'no timer';
  $('bof').disabled=busy||!on;$('bon').disabled=busy;
  $('ni').textContent=s.night?'Night':'Day';
  $('se').textContent=s.door.sensor_closed?'closed':'not closed';
  $('so').textContent=SRC[s.door.last_source]||s.door.last_source;
  $('wf').textContent=s.wifi.ip+' · '+s.wifi.rssi+' dBm';
  $('up').textContent=dur(s.uptime_s+el);
}
function online(ok){const c=$('conn');c.textContent=ok?'online':'offline';c.className=ok?'':'off'}
// Builds the list once per new log, so a scrolled list keeps its position.
function buildLog(){
  const ul=$('log');ul.textContent='';
  for(const e of log.events){
    const li=document.createElement('li'),a=document.createElement('span'),b=document.createElement('span');
    const [what,why]=describe(e),w=document.createElement('b'),y=document.createElement('small');
    w.textContent=what;y.textContent=why;a.append(w);if(why)a.append(y);
    if(['close_failed','watchdog_reset','settings_save_failed','wifi_change_failed','firmware_update_failed'].includes(e.event))li.className='bad';
    b.dataset.t=e.t;li.append(a,b);ul.append(li);
  }
  if(!log.events.length)ul.innerHTML='<li><span>No events yet</span></li>';
  logTimes();
}
// Refreshes only the times.
function logTimes(){
  if(!log)return;
  const now=log.uptime_s+Math.floor((Date.now()-log.at)/1000);
  for(const b of $('log').querySelectorAll('[data-t]'))b.textContent=when(Math.max(0,now-b.dataset.t));
}
async function loadLog(rev){
  logRev=rev;
  try{const r=await fetch(API+'log',{cache:'no-store'}),j=await r.json();j.at=Date.now();log=j;buildLog()}
  catch(e){logRev=-1}
}
function got(s){last=s;lastAt=Date.now();fails=0;online(true);render();if(s.rev!==logRev)loadLog(s.rev)}
async function poll(){
  if(document.hidden||busy)return;
  try{const r=await fetch(API+'state',{cache:'no-store'});got(await r.json())}
  catch(e){if(++fails>1)online(false)}
}
// Calls the API with the stored token; asks for the token once on 401.
async function api(method,path,body,retry){
  const h={},t=localStorage.getItem('token');if(t)h.Authorization='Bearer '+t;
  if(body)h['Content-Type']='application/json';
  const r=await fetch(API+path,{method,headers:h,body:body?JSON.stringify(body):undefined,cache:'no-store'}),j=await r.json();
  if(r.status==401&&!retry){
    const n=prompt('Access token');
    if(n){localStorage.setItem('token',n.trim());return api(method,path,body,true)}
  }
  return{r,j};
}
const errText=(r,j)=>ERR[j.error&&j.error.code]||(j.error&&j.error.message)||'Error '+r.status;
async function cmd(path){
  busy=true;render();
  try{
    const{r,j}=await api('POST',path);
    if(j.state)got(j.state);
    if(!r.ok)msg(errText(r,j));
  }catch(e){msg('Cannot reach the garage controller')}
  busy=false;render();
}
async function loadSettings(){
  try{
    const{r,j}=await api('GET','settings');
    if(!r.ok){msg(errText(r,j));$('set').open=false;return}
    $('s_name').value=j.name;$('s_open').value=j.open_s;$('s_close').value=j.close_s;$('s_ssid').value=j.wifi_ssid;
    $('s_pass').value='';$('s_token').value='';
  }catch(e){msg('Cannot reach the garage controller')}
}
$('set').ontoggle=()=>{if($('set').open)loadSettings()};
$('sf').onsubmit=async ev=>{
  ev.preventDefault();$('s_save').disabled=true;
  const b={name:$('s_name').value.trim(),open_s:+$('s_open').value,close_s:+$('s_close').value,wifi_ssid:$('s_ssid').value};
  if($('s_pass').value)b.wifi_password=$('s_pass').value;
  const nt=$('s_token').value.trim();if(nt)b.token=nt;
  try{
    const{r,j}=await api('POST','settings',b);
    if(!r.ok)msg(errText(r,j));
    else{
      if(nt)localStorage.setItem('token',nt);
      $('s_pass').value='';$('s_token').value='';
      if(j.result=='testing_wifi')msg('Switching WiFi network. If it does not connect within 60 s the controller goes back to the current one. Open it at its new address.',true);
      else msg('Settings saved',true);
      $('title').textContent=document.title=j.settings.name;
    }
  }catch(e){msg('Cannot reach the garage controller')}
  $('s_save').disabled=false;
};
$('s_restart').onclick=async()=>{
  if(!confirm('Restart the garage controller now?'))return;
  try{
    const{r,j}=await api('POST','restart');
    if(r.ok){msg('Restarting… the page reconnects by itself',true);log=null;logRev=-1}
    else msg(errText(r,j));
  }catch(e){msg('Cannot reach the garage controller')}
};
document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>cmd(b.dataset.c));
$('bon').onclick=()=>cmd('light/on?duration='+$('dur').value);
fetch(API+'info').then(r=>r.json()).then(i=>{$('fw').textContent=i.sw_version;$('fw_cur').textContent=i.sw_version;$('rr').textContent=RR[i.reset_reason]||i.reset_reason;resetReason='Cause: '+$('rr').textContent;if(log)buildLog();document.title=i.name;$('title').textContent=i.name}).catch(()=>{});
setInterval(poll,1500);setInterval(()=>{render();if(!document.hidden)logTimes()},1000);
document.addEventListener('visibilitychange',poll);poll();
</script></body></html>
)HTML";
