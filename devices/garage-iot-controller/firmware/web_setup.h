// Setup page, served on "/" in setup mode (jumper on the setup pin at boot, own open network).
#pragma once

static const char SETUP_PAGE[] = R"HTML(<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#11151c">
<title>Garage setup</title>
<style>
:root{color-scheme:dark;--bg:#11151c;--card:#1b222d;--line:#2a3442;--fg:#e8edf4;--mut:#8b98aa;--ok:#3ecf8e;--bad:#ef5350;--acc:#4c9aff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif}
main{max-width:460px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 2px 4px}
.intro{color:var(--mut);font-size:14px;margin:0 2px 14px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
h2{font-size:13px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;font-weight:600}
label{display:block;font-size:14px;color:var(--mut);margin:12px 0 4px}
label:first-of-type{margin-top:0}
input{width:100%;font:inherit;color:var(--fg);background:#253041;border:1px solid var(--line);border-radius:10px;padding:11px 12px}
.row{display:flex;gap:8px}
.row input{flex:1}
.hint{font-size:13px;color:var(--mut);margin-top:4px}
button{font:inherit;font-weight:600;color:var(--fg);background:#253041;border:1px solid var(--line);border-radius:10px;padding:11px 14px;min-height:46px;cursor:pointer}
button.p{background:var(--acc);border-color:var(--acc);color:#fff;width:100%}
button:disabled{opacity:.4;cursor:default}
#msg{font-size:14px;padding:10px 12px;border-radius:10px;margin-bottom:14px}
#msg.ok{background:#173a2b;border:1px solid var(--ok)}
#msg.bad{background:#3a1d22;border:1px solid var(--bad)}
</style></head><body><main>
<h1>Garage setup</h1>
<p class="intro">Setup mode: the jumper on pin 7 is in place. The door, the button and the automatic light keep working.</p>
<div id="msg" hidden></div>
<form id="f">
<section><h2>Device</h2>
<label for="name">Name</label><input id="name" maxlength="32" required>
<div class="hint">Shown on the web page and in Home Assistant.</div>
</section>
<section><h2>WiFi</h2>
<label for="ssid">Network</label><input id="ssid" maxlength="32" required autocapitalize="none" autocomplete="off">
<label for="pass">Password</label>
<div class="row"><input id="pass" type="password" maxlength="63" autocomplete="off"><button type="button" id="show">Show</button></div>
<div class="hint" id="passhint">Empty for an open network.</div>
</section>
<section><h2>Access token</h2>
<label for="token">Token</label>
<div class="row"><input id="token" minlength="8" maxlength="64" required autocapitalize="none" autocomplete="off" spellcheck="false"><button type="button" id="gen">New</button></div>
<div class="hint">Needed to use the buttons on the web page and the API. Write it down: the normal page never shows it.</div>
</section>
<section><h2>Door timings</h2>
<label for="open">Opening time (seconds)</label><input id="open" type="number" min="5" max="120" required>
<div class="hint">How long the door takes to open fully, plus a small margin.</div>
<label for="close">Close confirmation (seconds)</label><input id="close" type="number" min="10" max="180" required>
<div class="hint">If the closed sensor has not confirmed a close in this time, an alert is raised. Allow for slow closes.</div>
</section>
<button class="p" id="save">Save</button>
</form>
<section id="done" hidden><h2>Next step</h2>
<p style="margin:0 0 12px">Remove the jumper from pin 7, then restart. The controller will join the WiFi network.</p>
<button class="p" id="restart">Restart</button>
</section>
</main><script>
const $=id=>document.getElementById(id),API='/api/v1/';
let passSet=false;
function msg(t,ok){const m=$('msg');m.textContent=t;m.className=ok?'ok':'bad';m.hidden=false;m.scrollIntoView({block:'nearest'})}
function token(){const a=new Uint8Array(18);crypto.getRandomValues(a);return btoa(String.fromCharCode(...a)).replace(/\+/g,'-').replace(/\//g,'_')}
fetch(API+'settings').then(r=>r.json()).then(s=>{
  $('name').value=s.name;$('ssid').value=s.wifi_ssid;$('token').value=s.token||token();
  $('open').value=s.open_s;$('close').value=s.close_s;passSet=s.wifi_password_set;
  if(passSet){$('pass').placeholder='(saved password)';$('passhint').textContent='Leave empty to keep the saved password.'}
}).catch(()=>msg('Cannot read the current settings'));
$('show').onclick=()=>{const p=$('pass');const h=p.type=='password';p.type=h?'text':'password';$('show').textContent=h?'Hide':'Show'};
$('gen').onclick=()=>{$('token').value=token()};
$('f').onsubmit=async ev=>{
  ev.preventDefault();$('save').disabled=true;
  const b={name:$('name').value.trim(),wifi_ssid:$('ssid').value,token:$('token').value.trim(),
    open_s:+$('open').value,close_s:+$('close').value};
  if($('pass').value||!passSet)b.wifi_password=$('pass').value;
  try{
    const r=await fetch(API+'setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}),j=await r.json();
    if(r.ok){msg('Settings saved.',true);$('done').hidden=false;$('done').scrollIntoView()}
    else msg((j.error&&j.error.message)||'Error '+r.status);
  }catch(e){msg('Cannot reach the controller')}
  $('save').disabled=false;
};
$('restart').onclick=async()=>{
  $('restart').disabled=true;
  try{const r=await fetch(API+'restart',{method:'POST'}),j=await r.json();
    if(r.ok)msg('Restarting. Connect back to your home WiFi and open the controller at its new address.',true);
    else{msg((j.error&&j.error.message)||'Error '+r.status);$('restart').disabled=false}
  }catch(e){msg('Restarting…',true)}
};
</script></body></html>
)HTML";
