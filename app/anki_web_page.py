# -*- coding: utf-8 -*-
import json

import fragile_assets      # дизайн Fragile (генерирует lab/sync_fragile.py)

"""anki_web_page.py — HTML/CSS/JS веб-интерфейса AnkiVoice (одним файлом).

Отдельный модуль, чтобы anki_web.py остался читаемым: сервер — про HTTP
и запуск пайплайна, здесь — только вид. Никаких внешних библиотек и CDN:
страница полностью работает офлайн (сырьё — system-ui/Segoe UI).

Виджеты повторяют tkinter-окно (Голос / Anki / Финализация), но живут в
браузере: вкладки, карточки, живой лог потоком (SSE), полоса прогресса,
модальный выбор файлов вместо системного диалога.
"""

HTML = r"""<!doctype html>
<html lang="ru" data-theme="dark" data-design="sharp" data-density="regular" data-mono-labels="on" data-reduce-transparency="off">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnkiVoice</title>
<script>
/* Оформление (дизайн Fragile) ставится ДО первой отрисовки: без вспышки
   не той темы. Настройки подставляет сервер (config.json → appearance):
   у страницы каждый запуск новый порт, localStorage бы их терял. */
window.AV_APPEARANCE = /*__APPEARANCE__*/{};
(function(){
  try{
    var s = window.AV_APPEARANCE || {}, d = document.documentElement.dataset;
    var light = s.builtinScheme ? s.builtinScheme === "light"
      : s.colorScheme === "light" ||
        (s.colorScheme !== "dark" && matchMedia("(prefers-color-scheme: light)").matches);
    d.theme = light ? "light" : "dark";
    if(s.builtinTheme) d.builtinTheme = s.builtinTheme;
    d.design = s.designType || "sharp";
    d.density = s.density || "regular";
    d.monoLabels = s.monoLabels === false ? "off" : "on";
    d.reduceTransparency = s.reduceTransparency ? "on" : "off";
    if(/^#[0-9a-fA-F]{6}$/.test(s.accentColor || "")) avAccent(s.accentColor);
  }catch(e){ document.documentElement.dataset.design = "sharp"; }
})();
/* свой акцент: --accent-h/-s/-l на корне, остальные --color-accent* считаются сами */
function avAccent(hex){
  var st = document.documentElement.style;
  if(!hex){ ["--accent-h","--accent-s","--accent-l"].forEach(function(k){ st.removeProperty(k); }); return; }
  var r = parseInt(hex.substr(1,2),16)/255, g = parseInt(hex.substr(3,2),16)/255,
      b = parseInt(hex.substr(5,2),16)/255;
  var mx = Math.max(r,g,b), mn = Math.min(r,g,b), h = 0, sat = 0, l = (mx+mn)/2;
  if(mx !== mn){
    var dd = mx - mn;
    sat = l > .5 ? dd/(2-mx-mn) : dd/(mx+mn);
    h = mx === r ? (g-b)/dd + (g < b ? 6 : 0) : mx === g ? (b-r)/dd + 2 : (r-g)/dd + 4;
    h *= 60;
  }
  st.setProperty("--accent-h", Math.round(h));
  st.setProperty("--accent-s", Math.round(sat*100) + "%");
  st.setProperty("--accent-l", Math.round(l*100) + "%");
}
</script>
<style>/*__FRAGILE_CSS__*/</style>
<style>
/* Свои переменные интерфейса — только поверх токенов Fragile: цвет задают
   тема и акцент, форму — тип интерфейса (data-design). Ни одного hex. */
:root{
  --r:var(--radius-l); --r-s:var(--radius-m);
  --font:var(--font-interface);
  --mono:var(--font-mono);
  --page:var(--background-primary);
  --card:var(--background-group);
  --border:var(--background-modifier-border);
  --line:var(--background-modifier-border);
  --text:var(--text-normal);
  --sub:var(--text-muted);
  --accent:var(--interactive-accent);
  --accent-hv:var(--interactive-accent-hover);
  --tint:color-mix(in srgb,var(--interactive-accent) 15%,transparent);
  --onaccent:var(--text-on-accent);
  --ok:var(--color-green); --ok-t:color-mix(in srgb,var(--color-green) 14%,transparent);
  --warn:var(--color-orange); --warn-t:color-mix(in srgb,var(--color-orange) 14%,transparent);
  --err:var(--color-red); --err-t:color-mix(in srgb,var(--color-red) 14%,transparent);
  --chip:var(--background-secondary);
  --input:var(--background-modifier-form-field);
  --hover:var(--background-modifier-hover);
  --console:var(--code-background);
  --console-fg:var(--text-normal);
  --disabled:var(--text-faint);
  --shadow:var(--shadow-s);
}
.console .l-ok{color:var(--color-green)}
.console .l-err{color:var(--color-red)}
.console .l-cmd{color:var(--text-accent)}
.console .l-brak{color:var(--color-orange)}
.console .l-dim{color:var(--text-faint)}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;background:var(--page);color:var(--text);
  font:14px/1.5 var(--font);
  -webkit-font-smoothing:antialiased;
}
button,input,select,textarea{font:inherit;color:inherit}

/* ---------------------------------------------------------- каркас */
.app{display:grid;grid-template-columns:216px 1fr;grid-template-rows:56px 1fr;
     min-height:100vh}
.topbar{
  grid-column:1/-1;display:flex;align-items:center;gap:14px;
  padding:0 18px;background:var(--card);border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:20
}
.brand{display:flex;align-items:center;gap:10px;font-weight:650;letter-spacing:.2px}
.logo{width:26px;height:26px;border-radius:8px;
  background:var(--interactive-accent);
  display:grid;place-items:center;color:var(--onaccent);font-size:14px;font-weight:800}
.chips{display:flex;gap:8px;margin-left:auto;align-items:center}
.chip{display:inline-flex;align-items:center;gap:7px;background:var(--chip);
  border:1px solid var(--border);border-radius:999px;padding:5px 12px;
  font-size:12.5px;color:var(--sub);white-space:nowrap}
.dot{width:8px;height:8px;border-radius:50%;background:var(--disabled);flex:none}
.chip.good .dot{background:var(--ok);box-shadow:0 0 0 3px color-mix(in srgb,var(--ok) 22%,transparent)}
.chip.bad  .dot{background:var(--err)}
.chip.live .dot{background:var(--accent);animation:pulse 1.4s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.8)}}

.sidebar{background:var(--card);border-right:1px solid var(--border);padding:14px 10px;
  display:flex;flex-direction:column;gap:4px;position:sticky;top:56px;height:calc(100vh - 56px)}
.nav{display:flex;align-items:center;gap:11px;padding:10px 12px;border-radius:var(--r-s);
  color:var(--sub);cursor:pointer;border:1px solid transparent;background:none;
  text-align:left;width:100%;transition:var(--transition)}
.nav:hover{background:var(--hover);color:var(--text)}
.nav.on{background:var(--tint);color:var(--accent);border-color:color-mix(in srgb,var(--accent) 30%,transparent);font-weight:600}
.nav .ic{width:18px;text-align:center;font-size:15px}
.nav .badge{margin-left:auto;background:var(--err);color:#fff;border-radius:999px;
  font-size:11px;padding:1px 6px;font-weight:700}
.side-foot{display:none !important;margin-top:auto;font-size:11.5px;color:var(--sub);
  border-top:1px solid var(--line);padding-top:10px}
.side-foot b{display:block;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-weight:600}

.main{padding:22px 26px 60px;max-width:1180px;width:100%}
.panel{display:none;animation:fade .18s ease}
.panel.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

h1{font-size:20px;margin:0 0 4px;font-weight:650;letter-spacing:-.2px}
h2{font-size:14px;margin:0 0 12px;font-weight:650;letter-spacing:.2px;
   text-transform:uppercase;color:var(--sub)}
.sub{color:var(--sub);font-size:13px;margin:0 0 20px}

.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media(max-width:900px){
  .grid2,.grid3{grid-template-columns:1fr}
  .app{grid-template-columns:1fr;grid-template-rows:56px auto 1fr}
  /* В узком окне сайдбар превращается в горизонтальную панель вкладок:
     раньше он просто скрывался и переключить вкладку было нечем. */
  .sidebar{
    display:flex;flex-direction:row;gap:6px;align-items:center;overflow-x:auto;
    position:sticky;top:56px;height:auto;padding:8px 10px;z-index:19;
    border-right:none;border-bottom:1px solid var(--border);scrollbar-width:none}
  .sidebar::-webkit-scrollbar{display:none}
  .sidebar .nav{width:auto;flex:none;white-space:nowrap;padding:8px 12px}
  .sidebar .nav .badge{margin-left:6px}
  .side-foot{display:none}
  .main{padding:16px 14px 48px}
  .topbar{gap:10px;padding:0 12px}
  .brand{flex:none}
  .chips{min-width:0;overflow-x:auto;scrollbar-width:none}
  .chips::-webkit-scrollbar{display:none}
  .tblwrap{overflow-x:auto}
}
@media(max-width:560px){
  .brandname{display:none}
  .chip{padding:4px 9px;font-size:11.5px}
  .main{padding:14px 10px 40px}
}

label.f{display:block;font-size:12.5px;color:var(--sub);margin-bottom:6px;font-weight:600}
.row{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.row>*{min-width:0}
.grow{flex:1 1 180px}
input[type=text],input[type=number],select,textarea{
  width:100%;background:var(--input);border:1px solid var(--border);
  border-radius:var(--r-s);padding:9px 11px;outline:none;transition:var(--transition)}
input:focus,select:focus,textarea:focus{border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent)}
input:disabled{color:var(--disabled);background:var(--chip)}
textarea{resize:vertical;min-height:76px;line-height:1.6}
select{cursor:pointer}
.hint{font-size:12px;color:var(--sub);margin-top:6px}
.hint b{color:var(--text);font-weight:600}

/* ------------------------------------------------- ползунки (как в Gradio)
   Дорожка + круглая бегунок + поле числа справа — привычная раскладка
   веба GPT-SoVITS, только в наших цветах темы. */
.sld-row{display:flex;align-items:center;gap:10px}
.sld-row input[type=range]{
  flex:1 1 auto;min-width:60px;-webkit-appearance:none;appearance:none;
  height:5px;border-radius:999px;background:var(--line);outline:none;cursor:pointer}
.sld-row input[type=range]::-webkit-slider-thumb{
  -webkit-appearance:none;appearance:none;width:15px;height:15px;border-radius:50%;
  background:var(--accent);border:2px solid var(--card);cursor:pointer;
  box-shadow:0 1px 3px rgba(0,0,0,.35);transition:transform .12s ease}
.sld-row input[type=range]:hover::-webkit-slider-thumb{transform:scale(1.2)}
.sld-row input[type=range]:active::-webkit-slider-thumb{transform:scale(1.32)}
.sld-row input[type=range]::-moz-range-thumb{
  width:15px;height:15px;border-radius:50%;background:var(--accent);
  border:2px solid var(--card);cursor:pointer}
.sld-row input[type=range]::-moz-range-track{
  height:5px;border-radius:999px;background:var(--line)}
.sld-row input[type=number]{width:74px;flex:none;text-align:center}

.btn{display:inline-flex;align-items:center;gap:8px;justify-content:center;
  background:var(--hover);border:1px solid var(--border);color:var(--text);
  border-radius:var(--r-s);padding:9px 15px;cursor:pointer;transition:var(--transition);
  font-weight:550;white-space:nowrap}
.btn:hover{border-color:color-mix(in srgb,var(--text) 25%,transparent)}
.btn:active{transform:translateY(1px)}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn.primary{background:var(--accent);border-color:transparent;color:var(--onaccent);font-weight:650}
.btn.primary:hover{background:var(--accent-hv)}
.btn.danger{background:var(--err);border-color:transparent;color:#fff;font-weight:650}
.btn.danger:disabled{background:var(--chip);color:var(--sub);opacity:1}
.btn.ghost{background:transparent}
.btn.sm{padding:7px 11px;font-size:13px}
.btn.big{padding:13px 22px;font-size:15px;width:100%}

.seg{display:inline-flex;background:var(--chip);border:1px solid var(--border);
  border-radius:var(--r-s);padding:3px;gap:3px;flex-wrap:wrap}
.seg button{background:none;border:0;padding:7px 13px;border-radius:6px;
  cursor:pointer;color:var(--sub);transition:var(--transition);font-weight:550}
.seg button:hover{color:var(--text)}
.seg button.on{background:var(--accent);color:var(--onaccent);font-weight:650}

/* ---------------------------------------------------------- выбор движка */
.engines{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.engines.one{grid-template-columns:1fr}
.eng{text-align:left;background:var(--card);border:1px solid var(--border);
  border-radius:var(--r-s);padding:12px 14px;cursor:pointer;color:var(--text);
  display:flex;flex-direction:column;gap:5px;transition:var(--transition);font:inherit}
.eng:hover{border-color:color-mix(in srgb,var(--accent) 55%,var(--border))}
.eng.on{border-color:var(--accent);background:var(--tint);
  box-shadow:0 0 0 1px var(--accent) inset}
.eng-t{font-weight:650;font-size:14.5px;display:flex;align-items:center;gap:8px}
.eng-t .mark{font-size:12px;color:var(--ok)}
.eng.on .eng-t .mark{color:var(--accent)}
.eng-d{font-size:12.5px;color:var(--sub);line-height:1.45}
.eng-note{font-size:12.5px;color:var(--sub);margin-top:10px;line-height:1.5}

/* ---------------------------------------------------------- узкое окно */
@media (max-width:780px){
  .app{grid-template-columns:1fr;grid-template-rows:auto 1fr}
  .topbar{height:auto;flex-wrap:wrap;padding:8px 12px;gap:8px}
  .chips{margin-left:0;flex-wrap:wrap}
  .sidebar{position:static;height:auto;flex-direction:row;gap:6px;
    overflow-x:auto;border-right:0;border-bottom:1px solid var(--border);
    padding:8px 10px}
  .nav{width:auto;white-space:nowrap;flex:none}
  .side-foot{display:none}
  .main{padding:14px 12px 40px}
  .grid2{grid-template-columns:1fr}
  .engines{grid-template-columns:1fr}
  .modal,.modal.wizard{width:calc(100vw - 16px);max-height:92vh}
  .card{padding:12px}
}

.switch{display:inline-flex;align-items:center;gap:9px;cursor:pointer;
  font-size:13.5px;color:var(--sub);user-select:none}
.switch input{appearance:none;width:36px;height:20px;border-radius:999px;
  background:var(--chip);border:1px solid var(--border);position:relative;
  cursor:pointer;transition:.16s;margin:0;flex:none}
.switch input::after{content:"";position:absolute;top:2px;left:2px;width:14px;height:14px;
  border-radius:50%;background:var(--sub);transition:.16s}
.switch input:checked{background:var(--accent);border-color:transparent}
.switch input:checked::after{transform:translateX(16px);background:var(--onaccent)}
.switch:hover{color:var(--text)}

/* ---------------------------------------------------------- статус / прогресс */
.banner{border-radius:var(--r);padding:12px 15px;margin-bottom:16px;
  font-size:13.5px;display:none;border:1px solid;overflow-wrap:anywhere;word-break:break-word}
.banner.show{display:block}
.banner.bad{background:var(--err-t);border-color:color-mix(in srgb,var(--err) 38%,transparent);color:var(--err)}
.banner.warn{background:var(--warn-t);border-color:color-mix(in srgb,var(--warn) 38%,transparent);color:var(--warn)}
.banner.good{background:var(--ok-t);border-color:color-mix(in srgb,var(--ok) 38%,transparent);color:var(--ok)}
.banner b{font-weight:700}
.banner .acts{margin-top:9px;display:flex;gap:8px}

.prog{height:8px;border-radius:999px;background:var(--chip);overflow:hidden;
  border:1px solid var(--border);position:relative}
.prog i{display:block;height:100%;width:0;border-radius:999px;
  background:var(--interactive-accent);transition:width .4s ease}
.prog.indet i{width:32%;animation:slide 1.3s ease-in-out infinite}
@keyframes slide{0%{margin-left:-32%}100%{margin-left:100%}}
.prog-meta{display:flex;justify-content:space-between;font-size:12.5px;
  color:var(--sub);margin-top:7px}

/* ---------------------------------------------------------- лог */
.console{background:var(--console);border:1px solid var(--border);
  border-radius:var(--r);height:340px;overflow:auto;padding:12px 14px;
  font:12.5px/1.65 var(--mono);color:var(--console-fg);white-space:pre-wrap;
  word-break:break-word;scroll-behavior:smooth}
.console::-webkit-scrollbar{width:10px}
.console::-webkit-scrollbar-thumb{background:var(--scrollbar-thumb);border-radius:99px;border:2px solid var(--console)}
.log-head{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.log-head h2{margin:0}
.log-head .sp{margin-left:auto;display:flex;gap:8px;align-items:center}

/* ---------------------------------------------------------- голоса */
.vlist{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:10px}
.vcard{background:var(--input);border:1px solid var(--border);border-radius:var(--r-s);
  padding:12px 13px;cursor:pointer;transition:var(--transition);position:relative}
.vcard:hover{border-color:color-mix(in srgb,var(--accent) 45%,transparent)}
.vcard.on{border-color:var(--accent);background:var(--tint);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 16%,transparent)}
.vcard .nm{font-weight:640;display:flex;align-items:center;gap:7px}
.vcard .st{font-size:11.5px;color:var(--sub);margin-top:3px}
.vcard .st.ok{color:var(--ok)}
.vcard .st.no{color:var(--err)}

/* ---------------------------------------------------------- таблица полей */
.tbl{width:100%;border-collapse:collapse;font-size:13.5px}
.tbl th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;
  color:var(--sub);padding:0 10px 8px;font-weight:650}
.tbl td{padding:7px 10px;border-top:1px solid var(--line)}
.tbl tr:hover td{background:var(--hover)}
.tbl .k{color:var(--sub);white-space:nowrap}
.tbl .k.wrap{white-space:normal;line-height:1.35;vertical-align:top}
.tbl .ksub{font-size:11.5px;color:var(--sub);opacity:.85;font-weight:400;margin-top:2px}
.tbl .v{font-weight:600}

/* ---------------------------------------------------------- модалка файлов */
.overlay{position:fixed;inset:0;background:var(--background-modifier-cover);
  display:none;place-items:center;z-index:50;padding:20px}
.overlay.on{display:grid}
#overlay{z-index:60}
.modal{background:var(--card);border:1px solid var(--border);border-radius:14px;
  width:min(660px,100%);max-height:82vh;display:flex;flex-direction:column;
  box-shadow:0 24px 70px rgba(0,0,0,.5);overflow:hidden}
.modal header{padding:15px 18px;border-bottom:1px solid var(--border);font-weight:650;
  display:flex;align-items:center;gap:10px}
.modal header .x{margin-left:auto;background:none;border:0;font-size:20px;
  cursor:pointer;color:var(--sub);line-height:1}
.modal header .x:hover{color:var(--text)}
.crumbs{padding:9px 18px;font:12.5px var(--mono);color:var(--sub);
  border-bottom:1px solid var(--line);word-break:break-all}
.plist{overflow:auto;padding:8px;flex:1;min-height:180px}
.pitem{display:flex;gap:10px;align-items:center;padding:8px 11px;border-radius:7px;
  cursor:pointer;transition:.1s;font-size:13.5px}
.pitem:hover{background:var(--hover)}
.pitem .ic{width:16px;text-align:center;opacity:.75}
.pitem.dir .ic{color:var(--warn)}
.modal footer{padding:13px 18px;border-top:1px solid var(--border);
  display:flex;gap:9px;justify-content:flex-end}
.empty{color:var(--sub);text-align:center;padding:26px 10px;font-size:13px}

.toast{position:fixed;bottom:22px;left:50%;transform:translate(-50%,20px);
  background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:11px 17px;box-shadow:var(--shadow);opacity:0;pointer-events:none;
  transition:.22s;z-index:60;font-size:13.5px;max-width:80vw}
.toast.on{opacity:1;transform:translate(-50%,0)}
.toast.bad{border-color:color-mix(in srgb,var(--err) 50%,transparent);color:var(--err)}
.toast.good{border-color:color-mix(in srgb,var(--ok) 50%,transparent);color:var(--ok)}

/* ---------------------------------------------------------- мастер и обновления */
#wizardOverlay{z-index:55}
.modal.wizard{width:min(840px,100%);max-height:90vh}
.wsteps{display:flex;gap:6px;padding:11px 18px;border-bottom:1px solid var(--line);
  flex-wrap:wrap;background:var(--chip)}
.wstep{display:inline-flex;align-items:center;gap:7px;border:1px solid transparent;
  border-radius:999px;padding:5px 10px;font-size:12px;color:var(--sub);white-space:nowrap}
.wstep .n{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;
  background:var(--border);color:var(--text);font-size:10.5px;font-weight:700}
.wstep.on{background:var(--tint);border-color:color-mix(in srgb,var(--accent) 35%,transparent);color:var(--accent)}
.wstep.on .n{background:var(--accent);color:var(--onaccent)}
.wstep.ok .n{background:var(--ok);color:var(--background-primary)}
.wbody{padding:18px;overflow:auto;flex:1;min-height:300px}
.wbody h3{font-size:16px;margin:0 0 6px;font-weight:650}
.wbody p{margin:0 0 10px;color:var(--sub);font-size:13px}
.wbody ul{margin:8px 0 12px;padding-left:20px;color:var(--sub);font-size:13px}
.wbody li{margin:4px 0}
.wbody code{font:12px var(--mono);background:var(--chip);border:1px solid var(--border);
  border-radius:5px;padding:1px 5px;color:var(--text)}
.wstate{display:flex;align-items:center;gap:9px;border:1px solid var(--border);
  border-radius:9px;padding:10px 12px;margin:10px 0 14px;font-size:13px;background:var(--input)}
.wstate .dot{width:9px;height:9px}
.wstate.ok{border-color:color-mix(in srgb,var(--ok) 40%,transparent)}
.wstate.ok .dot{background:var(--ok)}
.wstate.bad{border-color:color-mix(in srgb,var(--err) 40%,transparent)}
.wstate.bad .dot{background:var(--err)}
.wstate.warn{border-color:color-mix(in srgb,var(--warn) 40%,transparent)}
.wstate.warn .dot{background:var(--warn)}
.wcard{background:var(--chip);border:1px solid var(--line);border-radius:10px;
  padding:13px 14px;margin:12px 0}
.wcard .row{margin-top:8px}
.wactions{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}
.wactions a.btn{text-decoration:none;display:inline-flex;align-items:center}
.wresult{background:var(--ok-t);border:1px solid color-mix(in srgb,var(--ok) 35%,transparent);
  border-radius:10px;padding:13px 14px;margin-top:12px;color:var(--ok);font-size:13px}
.wresult.bad{background:var(--err-t);border-color:color-mix(in srgb,var(--err) 35%,transparent);color:var(--err)}
.wresult audio{width:100%;margin-top:10px}
.update-pre{white-space:pre-wrap;word-break:break-word;background:var(--console);
  border:1px solid var(--border);border-radius:9px;padding:12px 14px;color:var(--console-fg);
  font:12px/1.55 var(--mono);max-height:260px;overflow:auto;margin-top:10px}
.update-bar{height:6px;border-radius:999px;background:var(--chip);overflow:hidden;
  border:1px solid var(--border);margin:10px 0 4px}
.update-bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .25s}
.update-meta{font-size:12px;color:var(--sub)}
@media(max-width:700px){
  .modal.wizard{max-height:94vh}
  .wsteps{gap:4px;padding:9px 12px}
  .wstep{font-size:11px;padding:4px 7px}
  .wstep .n{width:16px;height:16px}
  .wbody{padding:14px}
}
.spacer{height:6px}
/* ------------------------------------------- файлы голоса во вкладке «Голос» */
.vfiles{display:grid;gap:6px;margin:4px 0 16px}
.vf{display:grid;grid-template-columns:18px 150px 1fr;gap:8px;align-items:center;
  padding:7px 10px;border-radius:var(--r-s);background:var(--chip)}
.vf.no{background:var(--err-t)}
.vf-m{font-weight:800}
.vf.ok .vf-m{color:var(--ok)}
.vf.no .vf-m{color:var(--err)}
.vf-t{font-weight:600}
.vf-p{font-family:var(--mono);font-size:12px;color:var(--sub);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* ------------------------------------- главный экран: готовность и шаги */
.ready{padding:14px 16px}
.ready-list{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.ready-it{display:flex;align-items:center;gap:8px;min-width:0;text-align:left;
  background:var(--chip);border:1px solid var(--border);border-radius:var(--r-s);
  padding:9px 11px;cursor:pointer}
.ready-it:hover{background:var(--hover)}
.rd-dot{width:9px;height:9px;border-radius:50%;flex:none;background:var(--disabled)}
.ready-it.ok .rd-dot{background:var(--ok)}
.ready-it.bad .rd-dot{background:var(--err)}
.ready-it.warn .rd-dot{background:var(--warn)}
.rd-t{font-weight:650;flex:none}
.rd-s{color:var(--sub);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ready-next{margin-top:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;
  padding:10px 12px;border-radius:var(--r-s);background:var(--tint)}
.ready-next.ok{background:var(--ok-t)}
.ready-next.bad{background:var(--err-t)}
.ready-next .rn-t{flex:1;min-width:220px}
.step{display:flex;gap:14px;padding:4px 0 16px}
.step + .step{border-top:1px solid var(--line);padding-top:16px}
.step-n{flex:none;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;
  background:var(--tint);color:var(--accent);font-weight:750}
.step-b{flex:1;min-width:0}
.go{border-top:1px solid var(--line);padding-top:16px}
.go-sum{margin-bottom:10px;color:var(--sub)}
.go-sum b{color:var(--text)}
details.more{padding:0}
details.more > summary{list-style:none;cursor:pointer;padding:14px 16px;
  display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;border-radius:var(--r)}
details.more > summary::-webkit-details-marker{display:none}
details.more > summary::before{content:"▸";color:var(--sub);transition:transform .15s}
details.more[open] > summary::before{transform:rotate(90deg)}
details.more > summary:hover{background:var(--hover)}
details.fine{margin-top:6px}
details.fine > summary{cursor:pointer;list-style:none;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:6px 0}
details.fine > summary::-webkit-details-marker{display:none}
details.fine > summary::before{content:"▸";color:var(--sub);transition:transform var(--pop-dur) var(--pop-ease)}
details.fine[open] > summary::before{transform:rotate(90deg)}
.more-t{font-weight:650}
.more-b{padding:6px 16px 16px}
.opts{display:grid;gap:4px}
.opts .hint{margin:0 0 10px 26px}
.tools{display:grid;grid-template-columns:max-content 1fr;gap:8px 14px;align-items:center}
.tools .btn{width:100%}
.tools .hint{margin:0}
.tools-h{grid-column:1/-1;margin:10px 0 0;font-family:var(--label-font);font-size:max(var(--label-size),11px);
  text-transform:uppercase;letter-spacing:max(var(--label-spacing),.06em);color:var(--text-muted)}
.tools-h:first-child{margin-top:0}
@media (max-width:1180px){
  .ready-list{grid-template-columns:1fr 1fr}
}
@media (max-width:780px){
  .tools{grid-template-columns:1fr}
  .tools .hint{margin-bottom:6px}
}

/* ═════════════════════════ дизайн Fragile: общее для трёх типов ═════════ */
body{font-family:var(--font-interface)}
.app{grid-template-rows:auto 1fr}
@media (min-width:781px){
  .topbar{height:calc(var(--header-height) + 14px)}
  .sidebar{top:calc(var(--header-height) + 14px);height:calc(100vh - var(--header-height) - 14px)}
}
.ic{width:18px;height:18px;flex:none}
.btn .ic{width:16px;height:16px}
.btn.big .ic{width:18px;height:18px}
.btn,.seg button,.nav,.vcard,.eng,.ready-it,.tcard,.dtype,.chip,
input,select,textarea,.switch input{transition:background-color var(--transition),
  border-color var(--transition),color var(--transition),box-shadow var(--transition)}
:focus-visible{outline:2px solid var(--interactive-accent);outline-offset:1px}
.nav{align-items:flex-start;color:var(--text-muted)}
.nav .ic{margin-top:1px;color:var(--icon-color)}
.nav:hover .ic,.nav.on .ic{color:var(--icon-color-active)}
.nav-x{display:flex;flex-direction:column;min-width:0;line-height:1.25}
.nav-t{color:var(--text-normal);font-weight:600}
.nav-d{font-size:11.5px;color:var(--text-faint);margin-top:2px;font-weight:400}
.nav.on .nav-d{color:var(--text-muted)}
.chip.live .dot{background:var(--interactive-accent);animation:none}
h2{font-family:var(--label-font);font-size:max(var(--label-size),11px);text-transform:uppercase;
  letter-spacing:max(var(--label-spacing),.06em);color:var(--text-muted)}
label.f{font-family:var(--label-font);color:var(--text-muted)}
:root[data-design="sharp"][data-mono-labels="on"] label.f{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em}
@keyframes av-rise{from{opacity:0;translate:0 6px}to{opacity:1;translate:0 0}}
.av-tip{position:fixed;z-index:200;animation:f-fade-in .12s ease}
.f-tooltip.av-tip{max-width:340px;white-space:normal}

/* --- «Оформление» --- */
.ap-row{display:flex;align-items:center;gap:16px;padding:12px 0;flex-wrap:wrap}
.ap-row + .ap-row,.dtypes + .ap-row,.themes + .ap-row{border-top:1px solid var(--line)}
.ap-text{flex:1 1 260px;min-width:0}
.ap-name{font-weight:600;color:var(--text-normal)}
.ap-desc{font-size:12.5px;color:var(--text-muted);line-height:1.45;margin-top:2px}
.dtypes{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:0 0 14px}
.dtype,.tcard{display:flex;flex-direction:column;gap:6px;text-align:left;cursor:pointer;
  padding:10px;border:1px solid var(--background-modifier-border);border-radius:var(--radius-l);
  background:var(--background-secondary);color:var(--text-normal)}
.dtype small,.tcard small{color:var(--text-muted);font-size:12px;line-height:1.35}
.dtype:hover,.tcard:hover{border-color:var(--background-modifier-border-hover)}
.dtype.on,.tcard.on{border-color:var(--interactive-accent);box-shadow:0 0 0 1px var(--interactive-accent)}
/* мини-окна: как выглядит каждый тип — нарисованы токенами текущей темы */
.dt-prev{position:relative;display:grid;grid-template-columns:28% 1fr;grid-template-rows:14px 1fr;gap:4px;
  height:74px;padding:6px;background:var(--background-primary);border:1px solid var(--background-modifier-border)}
.dt-prev i{display:block;background:var(--background-secondary);border:1px solid var(--background-modifier-border)}
.dt-prev i:first-child{grid-column:1/-1}
.dt-prev i:nth-child(2){grid-row:2}
.dt-sharp{border-radius:0 !important}
.dt-sharp i{border-radius:0 !important}
.dt-sharp i:nth-child(2){box-shadow:inset 2px 0 0 var(--interactive-accent)}
.dt-classic{border-radius:8px !important}
.dt-classic i{border-radius:5px !important;box-shadow:0 2px 6px rgba(0,0,0,.18)}
.dt-classic i:nth-child(2){background:color-mix(in srgb,var(--interactive-accent) 22%,var(--background-secondary))}
.dt-glass{border-radius:12px !important;background:
  radial-gradient(90% 90% at 0% 0%,color-mix(in srgb,var(--interactive-accent) 45%,transparent),transparent 70%),
  radial-gradient(80% 80% at 100% 100%,color-mix(in srgb,var(--color-accent-2) 35%,transparent),transparent 70%),
  var(--background-primary)}
.dt-glass i{border-radius:8px !important;background:color-mix(in srgb,var(--background-primary) 55%,transparent);
  border-color:color-mix(in srgb,var(--text-normal) 16%,transparent);box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-normal) 25%,transparent)}
.themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;padding:0 0 14px}
.tc-bar{display:flex;height:30px;overflow:hidden;border-radius:var(--radius-s);
  border:1px solid var(--background-modifier-border)}
.tc-bar i{flex:1}
input[type=color]{width:46px;height:34px;padding:2px;border:1px solid var(--background-modifier-border);
  border-radius:var(--radius-s);background:var(--background-modifier-form-field);cursor:pointer}
@media (max-width:780px){ .dtypes{grid-template-columns:1fr} .nav-d{display:none} }

/* ═══════════════ ЧЁТКИЙ: прямые углы, полоски акцента вместо заливок ═════ */
:root[data-design="sharp"] .card{box-shadow:none}
[data-design="sharp"] .keep-round{border-radius:50% !important}
[data-design="sharp"] .topbar,[data-design="sharp"] .sidebar{background:var(--background-secondary)}
@media (min-width:781px){ [data-design="sharp"] .sidebar{padding:8px 0;gap:0} }
[data-design="sharp"] .nav{border:0;padding:10px 14px}
[data-design="sharp"] .nav.on{background:var(--background-modifier-active);color:var(--text-normal);
  box-shadow:inset 2px 0 0 var(--interactive-accent);font-weight:600}
[data-design="sharp"] .btn{box-shadow:none;border-color:var(--background-modifier-border-hover)}
[data-design="sharp"] .btn.primary,[data-design="sharp"] .btn.danger{border-color:transparent}
[data-design="sharp"] .btn:active{transform:none;filter:invert(.08)}
[data-design="sharp"] .seg{padding:0;gap:0;background:transparent;border-color:var(--background-modifier-border-hover)}
[data-design="sharp"] .seg button+button{border-left:1px solid var(--background-modifier-border-hover)}
[data-design="sharp"] .seg button.on{background:var(--background-modifier-active);color:var(--text-normal);
  box-shadow:inset 0 -2px 0 var(--interactive-accent)}
[data-design="sharp"] :is(.vcard,.eng,.dtype,.tcard).on{background:var(--background-modifier-active);
  border-color:var(--background-modifier-border-hover);box-shadow:inset 2px 0 0 var(--interactive-accent)}
[data-design="sharp"] .ready-next{box-shadow:inset 2px 0 0 var(--interactive-accent)}
[data-design="sharp"] .ready-next.ok{box-shadow:inset 2px 0 0 var(--color-green)}
[data-design="sharp"] .ready-next.bad{box-shadow:inset 2px 0 0 var(--color-red)}
[data-design="sharp"] .step-n{background:transparent;border:1px solid var(--interactive-accent)}
[data-design="sharp"] .switch input{width:40px;border-color:var(--background-modifier-border-hover)}
[data-design="sharp"] .switch input::after{transition:transform 90ms var(--ease-snap)}
[data-design="sharp"] .switch input:checked::after{transform:translateX(20px)}
[data-design="sharp"] :is(.modal,.toast){box-shadow:var(--shadow-l)}
[data-design="sharp"] .toast{border-left:2px solid var(--interactive-accent)}
[data-design="sharp"] .banner{border-width:0 0 0 2px}
[data-design="sharp"] details.more[open] > summary{box-shadow:inset 2px 0 0 var(--interactive-accent)}
[data-design="sharp"] .chip{background:transparent}
[data-design="sharp"] .vf{box-shadow:inset 2px 0 0 var(--color-green)}
[data-design="sharp"] .vf.no{box-shadow:inset 2px 0 0 var(--color-red)}

/* ═══════════════ КЛАССИЧЕСКИЙ: базовые правила выше (скругления, заливки) ═ */
[data-design="classic"] .card{box-shadow:var(--shadow-s)}
[data-design="classic"] :is(.dtype,.tcard,.vcard):hover{translate:0 -1px}
[data-design="classic"] .btn:not(:disabled):active>*{scale:.92}

/* ═══════════════ СТЕКЛО: панели плавают над цветным фоном из акцента ═════ */
/* цветной фон — отдельный неподвижный слой: при прокрутке его не надо
   перерисовывать (background-attachment:fixed перерисовывал каждый кадр) */
[data-design="glass"] body{background:var(--background-primary)}
[data-design="glass"] body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:
  radial-gradient(60vmax 50vmax at 8% 0%,color-mix(in srgb,var(--interactive-accent) 34%,transparent),transparent 70%),
  radial-gradient(50vmax 45vmax at 100% 100%,color-mix(in srgb,var(--color-accent-2) 26%,transparent),transparent 70%),
  radial-gradient(40vmax 40vmax at 70% 10%,color-mix(in srgb,var(--text-accent) 14%,transparent),transparent 70%),
  var(--background-primary);will-change:transform}
[data-design="glass"] .app{padding:var(--glass-gap);gap:var(--glass-gap)}
[data-design="glass"] .topbar{-webkit-backdrop-filter:blur(var(--glass-blur)) saturate(180%);
  backdrop-filter:blur(var(--glass-blur)) saturate(180%)}
[data-design="glass"] :is(.topbar,.sidebar){background:var(--glass-tint);
  border:1px solid var(--glass-rim);border-radius:var(--radius-l);
  box-shadow:inset 0 1px 0 var(--glass-rim-top),var(--glass-shadow)}
@media (min-width:781px){
  [data-design="glass"] .topbar{top:var(--glass-gap)}
  [data-design="glass"] .sidebar{top:calc(var(--header-height) + 14px + 2 * var(--glass-gap));
    height:calc(100vh - var(--header-height) - 14px - 3 * var(--glass-gap));padding:10px 8px}
}
[data-design="glass"] .main{padding-top:6px}
[data-design="glass"] .nav{border:0;border-radius:12px}
[data-design="glass"] .nav:hover{background:var(--glass-hover)}
[data-design="glass"] .nav.on{background:color-mix(in srgb,var(--interactive-accent) 20%,transparent);color:var(--text-normal)}
/* карточки лежат на плавном цветном фоне: размытие его не меняет, а
   стоит дорого (по замеру — рывки при прокрутке). Стекло — плотнее тинт */
[data-design="glass"] :is(.card,details.more){border-radius:20px;border-color:var(--glass-rim);
  background:color-mix(in srgb,var(--background-secondary) 72%,transparent);
  box-shadow:inset 0 1px 0 var(--glass-rim-top),0 6px 20px -10px rgba(0,0,0,.4)}
[data-design="glass"] .btn{border-radius:999px;border-color:var(--glass-rim);background:var(--glass-tint-strong);
  box-shadow:inset 0 1px 0 var(--glass-rim-top)}
[data-design="glass"] .btn.ghost{background:transparent}
[data-design="glass"] .btn.primary{background:var(--interactive-accent);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 4px 14px -4px color-mix(in srgb,var(--interactive-accent) 70%,transparent)}
[data-design="glass"] .btn.danger:not(:disabled){background:var(--color-red)}
[data-design="glass"] .btn>*{transition:scale .45s var(--ease-spring)}
[data-design="glass"] .btn:not(:disabled):active>*{scale:.93;transition-duration:.12s}
[data-design="glass"] .btn:active{transform:none}
[data-design="glass"] :is(.seg,.seg button,.chip){border-radius:999px}
[data-design="glass"] .seg{background:color-mix(in srgb,var(--text-normal) 8%,transparent);border-color:var(--glass-rim)}
[data-design="glass"] .chip{background:var(--glass-tint-strong);border-color:var(--glass-rim)}
[data-design="glass"] :is(input[type=text],input[type=number],select,textarea){border-radius:12px}
[data-design="glass"] :is(.vcard,.eng,.ready-it,.dtype,.tcard,.vf,.ready-next){border-radius:16px}
[data-design="glass"] .console{border-radius:16px}
[data-design="glass"] .switch input{width:46px;height:28px;border:0;
  background:color-mix(in srgb,var(--text-normal) 18%,transparent);box-shadow:inset 0 0 0 1px var(--glass-rim)}
[data-design="glass"] .switch input::after{top:2px;left:2px;width:24px;height:24px;background:#fff;
  box-shadow:0 2px 6px rgba(0,0,0,.3);transition:transform .5s var(--ease-spring),width .3s var(--ease-spring)}
[data-design="glass"] .switch input:checked{background:var(--interactive-accent)}
[data-design="glass"] .switch input:checked::after{transform:translateX(18px);background:#fff}
[data-design="glass"] .switch input:active::after{width:31px}
[data-design="glass"] .switch input:checked:active::after{transform:translateX(11px)}
[data-design="glass"] .modal{border-radius:22px;border-color:var(--glass-rim);background:var(--glass-sheet);
  -webkit-backdrop-filter:blur(40px) saturate(170%);backdrop-filter:blur(40px) saturate(170%);
  box-shadow:inset 0 1px 0 var(--glass-rim-top),var(--shadow-l)}
[data-design="glass"] .overlay{background:color-mix(in srgb,var(--background-primary) 40%,transparent)}
[data-design="glass"] .toast{border-radius:16px;background:var(--glass-tint-strong);border-color:var(--glass-rim);
  -webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)}
/* уменьшить прозрачность: та же форма, непрозрачные поверхности */
[data-design="glass"][data-reduce-transparency="on"] body,
[data-design="glass"][data-reduce-transparency="on"] body::before{background:var(--background-secondary)}
[data-design="glass"][data-reduce-transparency="on"] :is(.card,details.more){background:var(--background-primary)}
@media (prefers-reduced-transparency:reduce){
  [data-design="glass"] body,[data-design="glass"] body::before{background:var(--background-secondary)}
  [data-design="glass"] :is(.card,details.more){background:var(--background-primary)}
}

/* ═════════════════════ понятные настройки: выбор, голоса, разделы ═══════ */
.opt{padding:14px 0}
.opt + .opt{border-top:1px solid var(--line)}
.opt-t{font-weight:650;color:var(--text-normal)}
.opt-d{font-size:12.5px;color:var(--text-muted);line-height:1.45;margin:3px 0 10px;max-width:76ch}
.choice{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.ch{display:flex;flex-direction:column;gap:4px;text-align:left;cursor:pointer;padding:11px 12px;
  border:1px solid var(--background-modifier-border);border-radius:var(--radius-m);
  background:var(--background-secondary);color:var(--text-normal)}
.ch small{color:var(--text-muted);font-size:12px;line-height:1.35}
.ch:hover{border-color:var(--background-modifier-border-hover)}
.ch.on{border-color:var(--interactive-accent);box-shadow:0 0 0 1px var(--interactive-accent);
  background:color-mix(in srgb,var(--interactive-accent) 9%,var(--background-secondary))}
.ch[data-v="force"].on{border-color:var(--color-red);box-shadow:0 0 0 1px var(--color-red);
  background:color-mix(in srgb,var(--color-red) 9%,var(--background-secondary))}
.ens{display:flex;flex-wrap:wrap;gap:8px}
.ensv{display:flex;align-items:stretch;border:1px solid var(--background-modifier-border);
  border-radius:var(--radius-m);background:var(--background-secondary);overflow:hidden}
.ensv.on{border-color:var(--interactive-accent);box-shadow:0 0 0 1px var(--interactive-accent)}
.ensv.off{opacity:.5}
.ensv-b{display:flex;flex-direction:column;align-items:flex-start;gap:1px;padding:8px 12px;border:0;
  background:transparent;color:var(--text-normal);cursor:pointer;text-align:left}
.ensv-b:disabled{cursor:not-allowed}
.ensv-n{font-weight:600}
.ensv-b small{font-size:11px;color:var(--text-muted)}
.ensv.on .ensv-b small{color:var(--text-accent)}
.ensv-w{display:flex;align-items:center;gap:6px;padding:0 10px 0 4px;color:var(--text-muted);font-size:12px}
.ensv-w input{width:52px;padding:4px 6px;text-align:center}
.switch.is-off{opacity:.55;cursor:not-allowed}
.switch.is-off input{cursor:not-allowed}
#btnAsrGet{margin-top:10px}
.btn.danger:disabled,[data-design] .btn.danger:disabled{background:var(--background-modifier-hover);
  color:var(--text-faint);border-color:var(--background-modifier-border);box-shadow:none;opacity:1}
@media (max-width:780px){ .choice{grid-template-columns:1fr} }
[data-design="sharp"] :is(.ch,.ensv).on{box-shadow:inset 2px 0 0 var(--interactive-accent);
  border-color:var(--background-modifier-border-hover);background:var(--background-modifier-active)}
[data-design="sharp"] .ch[data-v="force"].on{box-shadow:inset 2px 0 0 var(--color-red)}
[data-design="glass"] :is(.ch,.ensv){border-radius:16px;border-color:var(--glass-rim);
  background:color-mix(in srgb,var(--background-primary) 45%,transparent)}

/* ═════════════════════ шапка: всё, что уезжает под неё, размыто и в тени ═ */
.top-shade{display:none}
@media (min-width:781px){
  .top-shade{display:block;position:fixed;top:0;right:0;left:216px;z-index:19;pointer-events:none;
    height:calc(var(--header-height) + 14px + 26px);
    background:linear-gradient(to bottom,
      color-mix(in srgb,var(--background-primary) 88%,transparent) 0%,
      color-mix(in srgb,var(--background-primary) 62%,transparent) 62%,
      transparent 100%);
    -webkit-backdrop-filter:blur(14px) saturate(130%);backdrop-filter:blur(14px) saturate(130%);
    -webkit-mask-image:linear-gradient(to bottom,#000 62%,transparent);
    mask-image:linear-gradient(to bottom,#000 62%,transparent)}
  [data-design="glass"] .top-shade{left:calc(216px + 2 * var(--glass-gap));
    height:calc(var(--header-height) + 14px + 2 * var(--glass-gap) + 30px);
    -webkit-backdrop-filter:blur(18px) saturate(150%) brightness(.82);
    backdrop-filter:blur(18px) saturate(150%) brightness(.82)}
  [data-design="glass"][data-theme="light"] .top-shade{
    -webkit-backdrop-filter:blur(18px) saturate(150%);backdrop-filter:blur(18px) saturate(150%)}
  /* «Уменьшить прозрачность» гасит blur у панелей, но полосу под шапкой
     оставляем размытой: она не делает интерфейс прозрачнее, а прячет
     детали уезжающего текста (так и просили) — плюс плотнее затемнение */
  html[data-reduce-transparency="on"] .top-shade,
  html[data-design="glass"][data-reduce-transparency="on"] .top-shade{
    -webkit-backdrop-filter:blur(16px) brightness(.8) !important;
    backdrop-filter:blur(16px) brightness(.8) !important;
    background:linear-gradient(to bottom,
      color-mix(in srgb,var(--background-primary) 94%,transparent) 0%,
      color-mix(in srgb,var(--background-primary) 70%,transparent) 62%,transparent 100%)}
}

/* ═════════════════════ движение: линза, появление, блик, раскрытие ═══════ */
/* линза: одна фигура выделения переезжает к активному пункту */
.has-lens:not(.sidebar){position:relative}
.has-lens > .lens{position:absolute;left:0;top:0;width:0;height:0;pointer-events:none;z-index:0;
  border-radius:var(--radius-m);background:var(--tint);
  transition:transform var(--lens-dur) var(--lens-ease),width var(--lens-dur) var(--lens-ease),
    height var(--lens-dur) var(--lens-ease),opacity .2s}
.has-lens > :not(.lens){position:relative;z-index:1}
.sidebar.has-lens > .nav.on{background:transparent;border-color:transparent;box-shadow:none}
.seg.has-lens > button.on{background:transparent;box-shadow:none}
.seg.has-lens > .lens{background:var(--interactive-accent);border-radius:6px}
[data-design="sharp"] .sidebar.has-lens > .lens{background:var(--background-modifier-active);
  box-shadow:inset 2px 0 0 var(--interactive-accent)}
[data-design="sharp"] .seg.has-lens > .lens{background:var(--background-modifier-active);
  box-shadow:inset 0 -2px 0 var(--interactive-accent)}
[data-design="sharp"] .seg.has-lens > button.on{color:var(--text-normal)}
[data-design="glass"] .sidebar.has-lens > .lens{border-radius:12px;
  background:color-mix(in srgb,var(--interactive-accent) 22%,transparent);
  box-shadow:inset 0 1px 0 var(--glass-rim-top),0 6px 18px -8px color-mix(in srgb,var(--interactive-accent) 70%,transparent)}
[data-design="glass"] .seg.has-lens > .lens{border-radius:999px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 4px 12px -4px color-mix(in srgb,var(--interactive-accent) 70%,transparent)}
/* стекло: линза в пути «жидкая» — вытягивается и пружинит */
[data-design="glass"] .has-lens > .lens.moving{animation:av-liquid var(--lens-dur) var(--ease-spring)}
@keyframes av-liquid{40%{scale:1.08 .86}}
/* появление раздела: карточки поднимаются по очереди */
.panel.on > :is(.card,details.more,.banner.show){animation:av-rise var(--pop-dur) var(--pop-ease) backwards;
  animation-delay:calc(var(--i,0) * 45ms)}
[data-design="sharp"] .panel.on > :is(.card,details.more,.banner.show){animation-name:f-fade-in}
[data-design="glass"] .panel.on > :is(.card,details.more,.banner.show){animation-duration:.55s}
.panel,.panel.on{animation:none}
/* раскрытие блоков */
details.more[open] > .more-b{animation:av-rise var(--pop-dur) var(--pop-ease)}
details.more > summary::before{transition:transform var(--pop-dur) var(--pop-ease)}
/* точки готовности: короткий «пульс», когда пункт стал зелёным */
.ready-it.pop .rd-dot{animation:av-pop .55s var(--ease-spring)}
@keyframes av-pop{0%{scale:.4}60%{scale:1.6}100%{scale:1}}
/* номер шага превращается в галочку, когда шаг выполнен */
.step-n{transition:background-color var(--transition),color var(--transition),border-color var(--transition)}
.step.done .step-n{background:var(--interactive-accent);color:var(--text-on-accent);border-color:transparent}
.step.done .step-n.flip{animation:av-pop .5s var(--ease-spring)}
/* главная кнопка: блик проходит по ней при наведении (кроме чёткого) */
.btn.primary.big{position:relative;overflow:hidden}
.btn.primary.big::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(105deg,transparent 30%,rgba(255,255,255,.28) 50%,transparent 70%);
  translate:-120% 0}
.btn.primary.big:not(:disabled):hover::after{translate:120% 0;transition:translate .8s var(--ease-out)}
[data-design="sharp"] .btn.primary.big::after{display:none}
/* «Все карточки уже озвучены»: не красная кнопка-тупик, а спокойное «готово» */
html .btn.primary.all-done,html[data-design] .btn.primary.all-done{background:var(--chip)!important;
  color:var(--ok);border:1px solid color-mix(in srgb,var(--ok) 45%,transparent)!important;
  opacity:1;box-shadow:none!important;cursor:default}
.btn.primary.all-done .ic{display:none}
.btn.primary.all-done span::before{content:"\2713\00a0"}
/* выбор (повторная озвучка, голоса) — мягкий отклик */
:is(.ch,.ensv,.tcard,.dtype):active{scale:.985}
[data-design="sharp"] :is(.ch,.ensv,.tcard,.dtype):active{scale:1}
.ensv.on{animation:av-pop-s .35s var(--ease-spring)}
@keyframes av-pop-s{0%{scale:.96}100%{scale:1}}
/* стекло: блик под курсором на карточках */
[data-design="glass"] :is(.card,details.more,.dtype,.tcard,.ch){position:relative}
[data-design="glass"] :is(.card,details.more,.dtype,.tcard,.ch)::after{content:"";position:absolute;inset:0;
  border-radius:inherit;pointer-events:none;opacity:0;transition:opacity .3s;
  background:radial-gradient(220px circle at var(--mx,50%) var(--my,50%),
    color-mix(in srgb,var(--text-normal) 9%,transparent),transparent 70%)}
[data-design="glass"] :is(.card,details.more,.dtype,.tcard,.ch):hover::after{opacity:1}
/* смена оформления: волна нового акцента от места клика */
.av-ink{position:fixed;z-index:300;pointer-events:none;border-radius:50%;width:200px;height:200px;
  contain:strict;
  background:radial-gradient(circle,transparent 0%,
    color-mix(in srgb,var(--interactive-accent) 30%,transparent) 48%,
    color-mix(in srgb,var(--interactive-accent) 60%,transparent) 64%,transparent 71%);
  animation:av-ink 1.1s cubic-bezier(.25,.6,.3,1) forwards;will-change:transform,opacity}
@keyframes av-ink{0%{transform:scale(0);opacity:1}55%{opacity:.9}100%{transform:scale(var(--s,10));opacity:0}}
.toast{transition:opacity .25s var(--ease-out),transform .45s var(--ease-spring)}
/* ансамбль в шаге 2: панель выезжает, голоса появляются по очереди */
.ens-panel{margin-top:12px;padding:14px;border:1px dashed color-mix(in srgb,var(--interactive-accent) 45%,transparent);
  border-radius:var(--radius-m);background:color-mix(in srgb,var(--interactive-accent) 5%,transparent)}
.ens-head{display:flex;flex-direction:column;gap:2px;margin-bottom:10px}
.ens-head span{font-size:12.5px;color:var(--text-muted)}
.ens-panel.ens-in{animation:av-ens .42s var(--ease-out) both}
.ens-panel.ens-in .ensv{animation:av-rise .4s var(--ease-out) both;animation-delay:calc(var(--i,0) * 45ms + 80ms)}
@keyframes av-ens{from{opacity:0;translate:0 -6px;clip-path:inset(0 0 100% 0)}to{opacity:1;translate:0 0;clip-path:inset(0 0 0 0)}}
.ensv-c{flex:none;width:18px;height:18px;border-radius:50%;border:1.5px solid var(--background-modifier-border-hover);
  display:grid;place-items:center;transition:background .2s,border-color .2s}
.ensv-c::after{content:"";width:5px;height:9px;border:solid var(--onaccent);border-width:0 2px 2px 0;
  rotate:45deg;translate:0 -1px;scale:0;transition:scale .28s var(--ease-spring)}
.ensv.on .ensv-c{background:var(--interactive-accent);border-color:var(--interactive-accent)}
.ensv.on .ensv-c::after{scale:1}
.ensv-b{display:grid;grid-template-columns:auto 1fr;align-items:center;column-gap:9px;row-gap:0}
.ensv-b .ensv-c{grid-row:1 / 3}
.ensv-p{min-width:32px;font-variant-numeric:tabular-nums}
.hint.warn{color:var(--color-orange, var(--text-accent))}
/* выбор языка: кнопка с глобусом и всплывающий список с поиском */
.lang-btn{gap:6px}
.lang-btn .lang-chev{width:14px;height:14px;opacity:.7;transition:rotate .25s var(--ease-out)}
.lang-btn[aria-expanded="true"] .lang-chev{rotate:180deg}
.lang-menu{position:fixed;z-index:250;display:flex;flex-direction:column;gap:6px;padding:8px;
  background:var(--background-primary);border:1px solid var(--background-modifier-border);
  border-radius:var(--radius-l);box-shadow:0 18px 44px -12px rgba(0,0,0,.55),0 2px 8px rgba(0,0,0,.25);
  transform-origin:top right}
.lang-menu[hidden]{display:none}
.lang-menu.lm-in{animation:av-lm .22s var(--ease-out) both}
@keyframes av-lm{from{opacity:0;scale:.96;translate:0 -4px}to{opacity:1;scale:1;translate:0 0}}
.lang-menu.lm-in .lang-opt{animation:av-rise .3s var(--ease-out) both;animation-delay:calc(var(--i,0) * 14ms)}
#langFind{flex:none;padding:8px 10px;font-size:13px}
.lang-list{overflow-y:auto;min-height:0;display:flex;flex-direction:column;gap:1px;scrollbar-width:thin}
.lang-opt{display:flex;align-items:baseline;justify-content:space-between;gap:10px;width:100%;padding:8px 10px;
  border:0;border-radius:var(--radius-m);background:transparent;color:var(--text-normal);cursor:pointer;text-align:left;
  font:inherit;transition:background .15s}
.lang-opt:hover,.lang-opt:focus-visible{background:var(--background-modifier-hover);outline:none}
.lang-opt:focus-visible{box-shadow:inset 0 0 0 2px var(--interactive-accent)}
.lang-opt .lang-n{font-weight:600;white-space:nowrap;flex:none}
.lang-opt small{font-size:11.5px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.lang-opt.on{background:color-mix(in srgb,var(--interactive-accent) 14%,transparent)}
.lang-opt.on .lang-n::before{content:"\2713\00a0";color:var(--text-accent)}
.lang-note{font-size:11.5px;color:var(--text-faint);padding:4px 4px 0;border-top:1px solid var(--background-modifier-border)}
[data-design="sharp"] .lang-menu,[data-design="sharp"] .lang-opt{border-radius:0}
[data-design="sharp"] .lang-opt.on{box-shadow:inset 2px 0 0 var(--interactive-accent)}
[data-design="glass"] .lang-menu{border-radius:18px;border-color:var(--glass-rim);
  background:color-mix(in srgb,var(--background-primary) 72%,transparent);
  -webkit-backdrop-filter:blur(var(--glass-blur)) saturate(180%);backdrop-filter:blur(var(--glass-blur)) saturate(180%);
  box-shadow:inset 0 1px 0 var(--glass-rim-top),var(--glass-shadow)}
[data-design="glass"] .lang-opt{border-radius:12px}
html[data-reduce-transparency="on"] .lang-menu{background:var(--background-primary)!important;
  -webkit-backdrop-filter:none!important;backdrop-filter:none!important}
@media (max-width:640px){ .lang-btn #langCur{max-width:9ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap} }

/* «Новый голос»: три способа карточками, шаги с номерами */
.btn[hidden]{display:none}
.nv-sec .tools-h{margin:6px 0 10px}
.nv-empty{margin:-4px 0 0;font-size:13px;color:var(--text-faint)}
.nv-ways{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.nv-way{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:6px;text-align:left;
  padding:16px 16px 14px;border:1px solid var(--background-modifier-border);border-radius:var(--radius-l);
  background:var(--background-secondary);color:var(--text-normal);cursor:pointer;
  transition:border-color .2s,background .2s,translate .25s var(--ease-out),box-shadow .25s}
.nv-way:hover{border-color:var(--background-modifier-border-hover);translate:0 -2px;
  box-shadow:0 10px 24px -14px color-mix(in srgb,var(--interactive-accent) 60%,transparent)}
.nv-way b{font-size:15px}
.nv-way small{font-size:12.5px;line-height:1.4;color:var(--text-muted)}
.nv-way.on{border-color:var(--interactive-accent);box-shadow:0 0 0 1px var(--interactive-accent);
  background:color-mix(in srgb,var(--interactive-accent) 8%,var(--background-secondary))}
.nv-ic{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;margin-bottom:2px;
  background:color-mix(in srgb,var(--interactive-accent) 14%,transparent);color:var(--text-accent);
  transition:scale .35s var(--ease-spring),rotate .35s var(--ease-spring)}
.nv-ic .ic{width:20px;height:20px}
.nv-way:hover .nv-ic{scale:1.08;rotate:-6deg}
.nv-way.on .nv-ic{background:var(--interactive-accent);color:var(--onaccent)}
.nv-tag{position:absolute;top:14px;right:14px;font-size:10.5px;letter-spacing:.04em;text-transform:uppercase;
  color:var(--text-faint);font-family:var(--label-font)}
.nv-way.on .nv-tag{color:var(--text-accent)}
.nv-sec.nv-in{animation:av-rise .45s var(--ease-out) both}
.nv-steps{list-style:none;counter-reset:nv;margin:6px 0 16px;padding:0;display:flex;flex-direction:column;gap:16px}
.nv-steps > li{counter-increment:nv;position:relative;padding-left:42px;line-height:1.5}
.nv-steps > li::before{content:counter(nv);position:absolute;left:0;top:0;width:28px;height:28px;border-radius:50%;
  display:grid;place-items:center;font-weight:700;font-size:13px;background:var(--interactive-accent);color:var(--onaccent)}
[data-design="sharp"] .nv-steps > li::before{border-radius:0}
.nv-sec.nv-in .nv-steps > li{animation:av-rise .4s var(--ease-out) both}
.nv-sec.nv-in .nv-steps > li:nth-child(2){animation-delay:.06s}
.nv-sec.nv-in .nv-steps > li:nth-child(3){animation-delay:.12s}
.nv-sec.nv-in .nv-steps > li:nth-child(4){animation-delay:.18s}
.nv-guide{margin:8px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:6px;color:var(--text-muted);font-size:13px}
.nv-k{display:inline-block;min-width:30px;margin-right:8px;padding:1px 6px;border-radius:6px;text-align:center;
  font-family:var(--font-mono);font-size:12px;color:var(--text-normal);
  background:var(--background-modifier-hover);border:1px solid var(--background-modifier-border)}
.nv-note{margin-top:14px;padding:10px 12px;border-radius:var(--radius-m);font-size:12.5px;color:var(--text-muted);
  background:var(--background-modifier-hover)}
.nv-scan{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding:12px 14px;margin:4px 0 14px;border-radius:var(--radius-m);border:1px dashed var(--background-modifier-border-hover)}
.nv-status{display:none;align-items:center;gap:8px;margin-top:10px;font-size:13px}
.nv-status.on{display:flex;animation:av-rise .3s var(--ease-out) both}
.nv-status .dot.ok{background:var(--ok);box-shadow:0 0 0 3px color-mix(in srgb,var(--ok) 22%,transparent)}
.nv-spin{width:14px;height:14px;border-radius:50%;flex:none;border:2px solid var(--background-modifier-border-hover);
  border-top-color:var(--interactive-accent);animation:av-spin .8s linear infinite}
@keyframes av-spin{to{rotate:360deg}}
[data-design="glass"] .nv-way{border-radius:20px;border-color:var(--glass-rim)}
[data-design="sharp"] .nv-way{border-radius:0}
[data-design="sharp"] .nv-way.on{box-shadow:inset 3px 0 0 var(--interactive-accent);border-color:var(--background-modifier-border-hover)}
[data-design="sharp"] .nv-ic{border-radius:0}
@media (max-width:780px){ .nv-ways{grid-template-columns:1fr} }
@media (prefers-reduced-motion:reduce){
  .nv-sec.nv-in,.nv-sec.nv-in .nv-steps > li,.nv-status.on{animation:none}
  .lang-menu.lm-in,.lang-menu.lm-in .lang-opt{animation:none}
  .nv-way,.nv-ic{transition:none}
  .btn.primary.big:hover::after{transition:none}
  .ens-panel.ens-in,.ens-panel.ens-in .ensv{animation:none}
}
</style>
</head>
<body>
<div class="app">
  <!-- то, что уезжает под шапку, размывается и уходит в тень -->
  <div class="top-shade" aria-hidden="true"></div>

  <div class="topbar">
    <div class="brand"><span class="logo">A</span> <span class="brandname">AnkiVoice</span></div>
    <div class="chips">
      <span class="chip" id="chipAnki"><span class="dot keep-round"></span>Anki: …</span>
      <span class="chip" id="chipTts"><span class="dot keep-round"></span>Движок: …</span>
      <span class="chip" id="chipRun" style="display:none"><span class="dot keep-round"></span>Выполняется</span>
      <button class="btn sm ghost" id="btnTheme" title="Тема, цвета и тип интерфейса"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13.5" cy="6.5" r="1"/><circle cx="17.5" cy="10.5" r="1"/><circle cx="8.5" cy="7.5" r="1"/><circle cx="6.5" cy="12.5" r="1"/><path d="M12 2a10 10 0 0 0 0 20c.9 0 1.6-.7 1.6-1.7 0-.4-.2-.8-.4-1.1-.3-.3-.4-.7-.4-1.1 0-.9.7-1.7 1.7-1.7h2a5.5 5.5 0 0 0 5.5-5.5C22 6 17.5 2 12 2Z"/></svg><span>Оформление</span></button>
      <button class="btn sm ghost lang-btn" id="btnLang" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="langMenu" title="Язык интерфейса"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg><span class="notr" id="langCur"></span><svg class="ic lang-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>
    </div>
  </div>

  <nav class="sidebar">
    <button class="nav on" data-tab="voice"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 10v3"/><path d="M6 6v11"/><path d="M10 3v18"/><path d="M14 8v7"/><path d="M18 5v13"/><path d="M22 10v3"/></svg><span class="nav-x"><span class="nav-t">Озвучка</span><span class="nav-d">выбрать колоду и озвучить</span></span></button>
    <button class="nav" data-tab="anki"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M21 9H3"/><path d="M21 15H3"/><path d="M12 3v18"/></svg><span class="nav-x"><span class="nav-t">Поля колоды</span><span class="nav-d">откуда текст, куда звук</span></span></button>
    <button class="nav" data-tab="sound"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/></svg><span class="nav-x"><span class="nav-t">Голос</span><span class="nav-d">голоса, тест и настройки</span></span></button>
    <button class="nav" data-tab="new"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/></svg><span class="nav-x"><span class="nav-t">Новый голос</span><span class="nav-d">создать или подключить</span></span></button>
    <button class="nav" data-tab="app"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/></svg><span class="nav-x"><span class="nav-t">Приложение</span><span class="nav-d">вид, мастер, обновления</span></span><span class="badge" id="navBadge" style="display:none">!</span></button>
    <div class="side-foot" id="sideFoot">…</div>
  </nav>

  <main class="main">

    <!-- ============================================ ОЗВУЧКА -->
    <section class="panel on" id="p-voice">
      <h1>Озвучка колоды</h1>
      <p class="sub">Выбери колоду и голос, нажми «Начать озвучку» — звук сам ляжет в карточки Anki. Какие поля читать и куда писать звук — во вкладке «Поля колоды».</p>

      <div class="banner" id="voiceBanner"></div>

      <!-- Готовность: что уже работает и что сделать прямо сейчас -->
      <div class="card ready" id="readyCard">
        <div class="ready-list">
          <button class="ready-it" id="rdEngine" type="button" data-go="engine">
            <span class="rd-dot keep-round"></span><span class="rd-t">Движок</span><span class="rd-s">…</span></button>
          <button class="ready-it" id="rdAnki" type="button" data-go="anki">
            <span class="rd-dot keep-round"></span><span class="rd-t">Anki</span><span class="rd-s">…</span></button>
          <button class="ready-it" id="rdVoice" type="button" data-go="voice">
            <span class="rd-dot keep-round"></span><span class="rd-t">Голос</span><span class="rd-s">…</span></button>
          <button class="ready-it" id="rdDeck" type="button" data-go="deck">
            <span class="rd-dot keep-round"></span><span class="rd-t">Колода</span><span class="rd-s">…</span></button>
        </div>
        <div class="ready-next" id="readyNext"></div>
      </div>

      <!-- Движок синтеза: свёрнут, когда папка в порядке (выше выбора колоды) -->
      <details class="card more" id="engineBox">
        <summary>
          <span class="more-t">Движок синтеза</span>
          <span class="hint" id="engineState" style="margin:0"></span>
        </summary>
        <div class="more-b">
          <div class="engines" id="engineCards">
            <button class="eng" data-engine="gpt-sovits" type="button">
              <span class="eng-t">GPT-SoVITS<span class="mark"></span></span>
              <span class="eng-d">Голос — файлы обученной модели. Синтез быстрее, голосов можно много.</span>
            </button>
            <button class="eng" data-engine="indextts" type="button">
              <span class="eng-t">IndexTTS 2.5<span class="mark"></span></span>
              <span class="eng-d">Голос — это одна запись-образец. Японские термины читает точнее, но синтез медленнее.</span>
            </button>
          </div>
          <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:baseline">
            <div class="hint" id="engineHint" style="margin:0"></div>
            <div class="hint" id="enginePort" style="margin:0"></div>
          </div>
          <div class="spacer"></div>
          <label class="f" id="enginePathLabel">Папка движка</label>
          <div class="row">
            <div class="grow"><input type="text" id="gptpath" placeholder="D:\DOWNLOAD\GPT-SoVITS-…"></div>
            <button class="btn sm" id="btnPickGpt">Обзор…</button>
            <button class="btn sm" id="btnCheckPath" hidden>Проверить</button>
            <button class="btn sm" id="btnSavePath">Проверить и сохранить</button>
          </div>
          <div class="hint" id="pathHint"></div>
        </div>
      </details>

      <!-- Главное: три шага и одна кнопка -->
      <div class="card">
        <div class="step">
          <div class="step-n">1</div>
          <div class="step-b">
            <label class="f">Колода</label>
            <div class="row">
              <div class="grow"><select id="deck"></select></div>
              <button class="btn sm" id="btnDecks" title="Перечитать список колод из Anki"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16"/><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/></svg><span>Обновить</span></button>
            </div>
            <div class="hint" id="deckHint">Загружаю колоды из Anki…</div>
          </div>
        </div>

        <div class="step">
          <div class="step-n">2</div>
          <div class="step-b">
            <label class="f" for="voicePick">Голос</label>
            <div class="row">
              <div class="grow"><select id="voicePick" aria-describedby="voiceHint"></select>
                <select id="voice" hidden tabindex="-1" aria-hidden="true"></select></div>
              <button class="btn sm" id="btnHear" title="Синтезировать тестовую фразу выбранным голосом и проиграть её"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg><span>Послушать</span></button>
            </div>
            <div class="hint" id="voiceHint"></div>
            <div class="ens-panel" id="ensPanel" hidden>
              <div class="ens-head">
                <b>Ансамбль: какие голоса участвуют</b>
                <span>Каждая карточка целиком озвучивается одним голосом, голоса чередуются случайно. Отметь хотя бы два.</span>
              </div>
              <div class="ens" id="ensChips"></div>
              <div class="hint" id="ensHint"></div>
              <select id="voices2" multiple hidden></select>
              <input type="hidden" id="ensWeights">
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step-n">3</div>
          <div class="step-b">
            <label class="f">Что озвучить</label>
            <div class="seg" id="segMode">
              <button data-v="both" class="on">слово + предложение</button>
              <button data-v="sentence">предложение</button>
              <button data-v="expression">слово</button>
            </div>
            <div class="row" style="margin-top:12px;align-items:center">
              <label class="f" for="limit" style="margin:0">Не больше карточек за запуск</label>
              <div style="width:110px"><input type="number" id="limit" value="20" min="0" step="1"></div>
              <div class="hint" style="margin:0">Пусто или 0 — все карточки колоды. Считаются только те, что ещё без звука.</div>
            </div>
          </div>
        </div>

        <div class="go">
          <div class="go-sum" id="goSummary"></div>
          <button class="btn primary big" id="btnStart" title="Озвучить выбранную колоду: звук ляжет прямо в карточки Anki"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 4l14 8-14 8Z"/></svg><span>Начать озвучку</span></button>
          <div class="row" style="margin-top:10px">
            <button class="btn" id="btnRetry" style="display:none"
                    title="Ещё раз озвучить карточки, на которых прошлый запуск закончился ошибкой"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg><span>Повторить неудачные</span></button>
            <button class="btn danger" id="btnStop" disabled title="Остановить текущую операцию: уже озвученное сохранится"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"/></svg><span>Остановить</span></button>
          </div>
          <div class="spacer" style="height:14px"></div>
          <div class="prog" id="prog"><i></i></div>
          <div class="prog-meta">
            <span id="progText">Готов к запуску</span>
            <span id="progPct"></span>
          </div>
          <div class="hint" style="margin-top:10px">
            Новый звук записывается прямо в поля карточек Anki — <b>отменить это нельзя</b>,
            но уже озвученные карточки по умолчанию не трогаются (это меняется в
            «Дополнительных настройках»). Всё считается на этом компьютере,
            карточки никуда не отправляются.
          </div>
        </div>
      </div>

      <!-- Дополнительно: всё, что не нужно для первого прогона -->
      <details class="card more" id="advBox">
        <summary>
          <span class="more-t">Дополнительные настройки</span>
          <span class="hint" style="margin:0">повторная озвучка, проверка произношения</span>
        </summary>
        <div class="more-b">
          <section class="opt">
            <div class="opt-t">Карточки, у которых звук уже есть</div>
            <div class="opt-d">Что делать с ними при запуске. По умолчанию их не трогаем.</div>
            <div class="choice" id="redoChoice" role="radiogroup" aria-label="Карточки, у которых звук уже есть">
              <button class="ch" data-v="skip" role="radio" type="button">
                <b>Пропускать</b><small>Озвучиваются только карточки без звука. Самый безопасный вариант.</small></button>
              <button class="ch" data-v="changed" role="radio" type="button">
                <b>Обновить изменённые</b><small>Переозвучит только те, где с прошлого раза поменялся текст или голос.</small></button>
              <button class="ch" data-v="force" role="radio" type="button">
                <b>Переозвучить все</b><small>Заменит звук во всех выбранных карточках. Отменить нельзя.</small></button>
            </div>
            <input type="checkbox" id="force" hidden>
            <input type="checkbox" id="changed" hidden>
          </section>

          <section class="opt">
            <div class="opt-t">Проверка произношения</div>
            <div class="opt-d">После синтеза каждая карточка распознаётся и сверяется с текстом: сомнительные помечаются, решение за тобой. Озвучка идёт примерно в 10 раз дольше.</div>
            <label class="switch" id="verifyPronRow">
              <input type="checkbox" id="verifyPron"> Проверять во время озвучки
            </label>
            <div class="hint" id="pronHint">—</div>
            <button class="btn sm" id="btnAsrGet" type="button" style="display:none">Скачать модель распознавания (~1,5 ГБ)</button>
          </section>
        </div>
      </details>

      <!-- Инструменты: проверки и отчёты, у каждой кнопки — что она делает -->
      <details class="card more" id="toolsBox">
        <summary>
          <span class="more-t">Инструменты и проверки</span>
          <span class="hint" style="margin:0">предпросмотр, новые карточки, проверка качества</span>
        </summary>
        <div class="more-b tools">
          <div class="tools-h">Перед озвучкой</div>
          <button class="btn" id="btnPreview">Предпросмотр</button>
          <div class="hint">Покажет, какой текст уйдёт в озвучку, — без синтеза, ничего не меняет.</div>
          <button class="btn" id="btnNew"
                    title="Озвучить только карточки без тега av_voiced — те, что добавили после прошлого прогона"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="M5 12h14"/></svg><span>Озвучить новые карточки</span></button>
          <div class="hint">Карточки, которые AnkiVoice ещё ни разу не озвучивал, — даже если в них уже есть звук из другого источника (например, AwesomeTTS). Без ограничения по количеству.</div>

          <div class="tools-h">После озвучки</div>
          <button class="btn" id="btnCheck">Проверить звук в карточках</button>
          <div class="hint">Проверит, что у карточек есть звук и файлы лежат в медиа Anki.</div>
          <button class="btn" id="btnMediaCheck">Найти лишние аудиофайлы</button>
          <div class="hint">Найдёт старые файлы озвучки, на которые больше не ссылается ни одна карточка. Только отчёт, ничего не удаляет.</div>
          <button class="btn" id="btnCompress">Сжать звук колоды в .ogg</button>
          <div class="hint">Пережмёт уже записанные .wav-озвучки выбранной колоды в .ogg — примерно в 10 раз легче, на слух разницы нет. Ссылки в карточках поправятся сами, старые .wav уйдут в корзину медиа Anki.</div>

          <div class="tools-h">Проверка качества — по шагам</div>
          <button class="btn" id="btnVerify">1. Проверить уже озвученные</button>
          <div class="hint">Распознает уже озвученные карточки и найдёт, где голос ошибся. Нужна модель распознавания (см. «Дополнительные настройки»).</div>
          <button class="btn" id="btnQCDeck">2. Собрать колоду «Брак»</button>
          <div class="hint">Создаст в Anki колоду «AnkiVoice_Брак» с копиями сомнительных карточек — оригиналы не меняются. Послушай их и в поле «Вердикт» напиши «плохо» (звук испорчен) или «хорошо» (звук в порядке).</div>
          <button class="btn" id="btnVerdicts">3. Итоги проверки</button>
          <div class="hint">Посчитает твои вердикты из колоды «Брак»: как часто проверка права и где она ошибается.</div>

        </div>
      </details>

      <div class="card">
        <div class="log-head">
          <h2>Журнал</h2>
          <div class="sp">
            <label class="switch" title="Держать журнал прокрученным к последней строке"><input type="checkbox" id="follow" checked> Автопрокрутка</label>
            <button class="btn sm ghost" id="btnClear">Очистить</button>
          </div>
        </div>
        <div class="console" id="log"><span class="l-dim">Журнал появится после запуска.</span></div>
      </div>
    </section>

    <!-- ============================================ ПОЛЯ КОЛОДЫ -->
    <section class="panel" id="p-anki">
      <h1>Поля колоды</h1>
      <p class="sub">Что каким полем читать и куда класть звук. Значения подставляются автоматически — поправь, если колода называет поля иначе.</p>

      <div class="banner" id="ankiBanner"></div>

      <div class="card">
        <label class="f">Настраиваем поля для колоды</label>
        <div class="row">
          <div class="grow"><select id="deck2"></select></div>
          <button class="btn sm" id="btnFields" title="Перечитать из Anki список полей этой колоды; твой выбор в таблице сохранится">Перечитать поля из Anki</button>
        </div>
        <div class="hint" id="fieldsHint">Это та же колода, что на главном экране: выбор здесь меняет и её. Поля подставляются сами — проверь их в таблице ниже. «Перечитать поля из Anki» нужна, только если ты добавил поля в Anki уже после открытия программы.</div>
      </div>

      <div class="card">
        <div class="tblwrap">
        <table class="tbl">
          <thead><tr><th style="width:44%">Что</th><th>Поле карточки</th></tr></thead>
          <tbody>
            <tr><td class="k wrap">Откуда брать предложение<div class="ksub">текст, который озвучится целиком</div></td><td><select id="f_sent_src"></select></td></tr>
            <tr><td class="k wrap">Куда записать звук предложения<div class="ksub">пусто — не записывать</div></td><td><select id="f_sent_aud"></select></td></tr>
            <tr><td class="k wrap">Откуда брать слово<div class="ksub">изучаемое слово карточки</div></td><td><select id="f_word_src"></select></td></tr>
            <tr><td class="k wrap">Куда записать звук слова<div class="ksub">пусто — не записывать</div></td><td><select id="f_word_aud"></select></td></tr>
            <tr><td class="k wrap">Поле с фуриганой слова
                <div class="ksub">по нему слово читается точно, как в карточке</div></td>
                <td><select id="f_furi"></select></td></tr>
            <tr><td class="k wrap">Как читать слово
                <div class="ksub">«Авто»: по фуригане, если она есть, иначе движок
                  читает кандзи сам</div></td>
                <td><select id="f_reading"></select></td></tr>
          </tbody>
        </table>
        </div>
        <div class="hint">
          <b>Как это читается.</b> Движок читает иероглифы сам, в контексте
          предложения. Режим <b>«Авто»</b> (по умолчанию) читает основное слово
          строго по строке «Фуригана слова»; если фуриганы нет — кандзи, как
          есть. Режим <b>«Только кандзи»</b> — всегда кандзи: чтение движок
          подбирает сам.
          <br>Режим сохраняется в профиле колоды — у каждой колоды свой.
          <br>Если в строке «Куда записать звук…» выбрать пустое значение — этот звук не записывается.
        </div>
      </div>

      <div class="card">
        <button class="btn primary" id="btnSaveFields" title="Озвучка этой колоды возьмёт поля из этой таблицы">Сохранить настройки полей</button>
        <span class="hint" style="display:inline;margin-left:12px" id="fieldsSaved"></span>
      </div>
    </section>

    <!-- ============================================ ГОЛОС -->
    <section class="panel" id="p-sound">
      <h1>Голос</h1>
      <p class="sub">Нажми на голос — откроются его настройки, и он же станет голосом для озвучки на главном экране. Голос — это три файла: GPT-веса (.ckpt), SoVITS-веса (.pth) и запись-образец на 3–10 секунд с её текстом. Голос с пометкой ✗ озвучивать не сможет — нажми на него, и ниже будет видно, какого файла не хватает.</p>

      <div class="banner" id="voiceBanner2"></div>

      <div class="card">
        <div class="vlist" id="vlist"></div>
        <div class="spacer" style="height:14px"></div>
        <div class="row">
          <button class="btn sm" id="btnTest" title="Синтезировать тестовую фразу выбранным голосом"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg><span>Прослушать тест</span></button>
          <button class="btn sm" id="btnAddVoice" title="Создать свой голос или подключить готовые файлы — вкладка «Новый голос»"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="M5 12h14"/></svg><span>Новый голос…</span></button>
          <button class="btn sm" id="btnScan" title="Найти в папке движка веса, которых ещё нет в списке голосов">Обновить список голосов из папки движка</button>
        </div>
        <div class="hint">«Прослушать» синтезирует тестовую фразу выбранным голосом и сразу её проигрывает.<span id="testFile" hidden></span></div>
      </div>

      <div class="card" id="voiceEdit" style="display:none">
        <h2 id="veName">—</h2>
        <div class="vfiles" id="veFiles"></div>
        <div class="grid2">
          <div>
            <label class="f">Запись-образец голоса (3–10 с)</label>
            <div class="row">
              <div class="grow"><input type="text" id="v_ref" placeholder="файл .wav/.mp3"></div>
              <button class="btn sm" data-pick="v_ref" data-ext="audio">Обзор…</button>
            </div>
            <label class="switch" style="margin-top:12px">
              <input type="checkbox" id="v_noref"> Не знаю, что сказано в записи
            </label>
            <div class="hint">Движок подстроится по одному звучанию. С текстом записи голос получается точнее.</div>
            <div class="spacer"></div>
            <div id="v_gptPrompt">
              <label class="f">Что сказано в записи</label>
              <textarea id="v_prompt" placeholder="дословно, на языке записи"></textarea>
              <div class="row" style="margin-top:10px">
                <div class="grow"><label class="f">Язык записи</label>
                  <select id="v_lang"><option value="ja">японский</option><option value="en">английский</option><option value="zh">китайский</option><option value="ko">корейский</option><option value="yue">кантонский</option></select></div>
                
              </div>
            </div>
          </div>
          <div>
            <div id="v_gptAux">
              <label class="f">Доп. записи для тембра (необязательно)</label>
              <div class="hint" style="margin:0 0 8px">Ещё записи этого же голоса: движок усредняет тембр, звучание стабильнее. Лучше несколько коротких (до 10 с), чем одна длинная: длинную движок разбирает на каждой фразе заново, и видеопамяти может не хватить.</div>
              <div id="auxList" style="display:flex;flex-direction:column;gap:8px"></div>
              <button class="btn sm ghost" id="btnAux">＋ добавить файл</button>
            </div>
            <div class="spacer" style="height:14px"></div>
            <details class="fine" id="v_gptParamsHead">
            <summary><span class="opt-t">Тонкая настройка характера речи</span>
              <span class="hint" style="margin:0">для опытных — обычно трогать не нужно</span></summary>
            <div class="hint" style="margin:6px 0 10px">Двигай по чуть-чуть: «Сохранить голос», затем «Прослушать» — тест звучит с сохранёнными настройками.
              <button class="btn sm ghost" id="btnFineReset" type="button" style="margin-left:6px">Сбросить к стандартным</button></div>
            <div class="sld" style="margin-bottom:10px"><div style="width:140px"><label class="f" title="Одинаковое число — одинаковый результат при повторной озвучке">Зерно случайности (seed)</label>
                  <input type="number" id="v_seed" value="42"></div>
              <div class="hint">одинаковое число — одинаковое звучание при повторной озвучке</div></div>
            <div class="grid2" id="v_gptParams">
              <div class="sld"><label class="f">Живость (temperature)</label>
                <div class="sld-row">
                  <input type="range" id="v_temp_r" min="0" max="2" step="0.01">
                  <input type="number" id="v_temp" step="0.01" min="0" max="2">
                </div>
                <div class="hint">ниже — ровнее и спокойнее, выше — живее, но больше ошибок</div></div>
              <div class="sld"><label class="f">Свобода выбора (top_p)</label>
                <div class="sld-row">
                  <input type="range" id="v_topp_r" min="0" max="1" step="0.01">
                  <input type="number" id="v_topp" step="0.01" min="0" max="1">
                </div>
                <div class="hint">меньше — предсказуемее интонация</div></div>
              <div class="sld"><label class="f">Варианты на шаг (top_k)</label>
                <div class="sld-row">
                  <input type="range" id="v_topk_r" min="0" max="200" step="1">
                  <input type="number" id="v_topk" step="1" min="0" max="200">
                </div>
                <div class="hint">меньше — стабильнее, больше — разнообразнее</div></div>
              <div class="sld"><label class="f">Скорость</label>
                <div class="sld-row">
                  <input type="range" id="v_speed_r" min="0.5" max="2" step="0.05">
                  <input type="number" id="v_speed" step="0.05" min="0.5" max="2">
                </div>
                <div class="hint">1.0 — как в записи-образце</div></div>
            </div>
          </div>
        </div>
        <div class="spacer" style="height:14px"></div>
            </details>
        <button class="btn primary" id="btnSaveVoice">Сохранить голос</button>
        <span class="hint" style="display:inline;margin-left:12px" id="voiceSaved"></span>
      </div>
    </section>

    <!-- ============================================ НОВЫЙ ГОЛОС -->
    <section class="panel" id="p-new">
      <h1>Новый голос</h1>
      <p class="sub">Выбери, с чего начать. Способы идут от самого быстрого к самому точному — готовый голос появится во вкладке «Голос» и в списке шага 2 на главном экране.</p>

      <div class="nv-ways" id="nvWays" role="radiogroup" aria-label="Как получить голос">
        <button class="nv-way" data-v="quick" role="radio" type="button">
          <span class="nv-ic"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg></span>
          <b>Из одной записи</b>
          <small>Без обучения, за минуту. Нужна запись голоса на 3–10 секунд и её текст. Тембр похож, но не идеален.</small>
          <span class="nv-tag">быстро</span></button>
        <button class="nv-way" data-v="weights" role="radio" type="button">
          <span class="nv-ic"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/></svg></span>
          <b>Готовые файлы голоса</b>
          <small>У тебя уже есть веса .ckpt и .pth — скачанные или обученные раньше. Подключаются за минуту.</small>
          <span class="nv-tag">есть файлы</span></button>
        <button class="nv-way" data-v="train" role="radio" type="button">
          <span class="nv-ic"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.9 5.8L20 10l-6.1 1.2L12 17l-1.9-5.8L4 10l6.1-1.2Z"/><path d="M19 17v4"/><path d="M17 19h4"/></svg></span>
          <b>Обучить свой голос</b>
          <small>Самое точное сходство. Нужно 1–10 минут чистых записей и 20–60 минут работы видеокарты.</small>
          <span class="nv-tag">лучше всего</span></button>
      </div>
      <p class="nv-empty" id="nvEmpty">Нажми на способ — ниже появятся шаги.</p>

      <div class="card nv-sec" id="nvQuick" hidden>
        <h2>Голос из одной записи</h2>
        <ol class="nv-steps">
          <li><label class="f" for="q_disp">Как назвать голос</label>
            <input type="text" id="q_disp" placeholder="Например: Мой голос">
            <div class="hint">Так он будет называться в списках.</div></li>
          <li><label class="f" for="q_ref">Запись голоса на 3–10 секунд</label>
            <div class="row"><div class="grow"><input type="text" id="q_ref" placeholder="файл .wav или .mp3"></div>
              <button class="btn sm" id="q_ref_b" type="button">Обзор…</button></div>
            <div class="hint">Одна фраза, один человек, без музыки и шума. Подойдёт кусок из видео или аудиокниги.</div></li>
          <li><label class="f" for="q_txt">Что сказано в записи</label>
            <textarea id="q_txt" placeholder="дословно, на языке записи"></textarea>
            <div class="row" style="margin-top:8px"><div class="grow"><label class="f" for="q_lang">Язык записи</label>
              <select id="q_lang"><option value="ja">японский</option><option value="en">английский</option><option value="zh">китайский</option><option value="ko">корейский</option><option value="yue">кантонский</option></select></div></div>
            <div class="hint">По тексту движок понимает, где какой звук, — без него сходство хуже.</div></li>
        </ol>
        <div class="row">
          <button class="btn primary" id="q_ok" type="button">Создать голос и прослушать</button>
        </div>
        <div class="hint" id="q_err"></div>
        <div class="nv-note">Голос строится на базовых весах движка. Понравится тембр — для точного сходства обучи голос на этих же записях (третий способ).</div>
      </div>

      <div class="card nv-sec" id="nvWeights" hidden>
        <h2>Подключить готовые файлы</h2>
        <div class="nv-scan">
          <div><b>Файлы уже лежат в папке движка?</b>
            <div class="hint" style="margin:2px 0 0">В GPT_weights_… и SoVITS_weights_… — например, после обучения. Тогда достаточно поиска.</div></div>
          <button class="btn sm" id="btnScan2" type="button">Найти голоса в папке движка</button>
        </div>
        <div class="tools-h">или укажи файлы вручную</div>
        <div class="grid2" id="addVoiceCard">
          <div>
            <label class="f" for="a_disp">Как назвать голос</label>
            <input type="text" id="a_disp" placeholder="Кубота Хитоси">
            <div class="spacer"></div>
            <label class="f" for="a_gpt">GPT-веса (.ckpt)</label>
            <div class="row"><div class="grow"><input type="text" id="a_gpt"></div>
              <button class="btn sm" id="a_gpt_b" type="button">Обзор…</button></div>
            <div class="spacer"></div>
            <label class="f" for="a_sov">SoVITS-веса (.pth)</label>
            <div class="row"><div class="grow"><input type="text" id="a_sov"></div>
              <button class="btn sm" id="a_sov_b" type="button">Обзор…</button></div>
          </div>
          <div>
            <label class="f" for="a_ref">Запись-образец голоса (3–10 с)</label>
            <div class="row"><div class="grow"><input type="text" id="a_ref"></div>
              <button class="btn sm" id="a_ref_b" type="button">Обзор…</button></div>
            <div class="spacer"></div>
            <label class="f" for="a_txt">Что сказано в записи</label>
            <textarea id="a_txt" placeholder="дословно, на языке записи"></textarea>
            <div class="spacer"></div>
            <label class="f" for="a_lang">Язык записи</label>
            <select id="a_lang"><option value="ja">японский</option><option value="en">английский</option><option value="zh">китайский</option><option value="ko">корейский</option><option value="yue">кантонский</option></select>
          </div>
        </div>
        <div class="spacer" style="height:14px"></div>
        <button class="btn primary" id="a_ok" type="button">Добавить голос</button>
        <div class="hint" id="a_err"></div>
      </div>

      <div class="card nv-sec" id="nvTrain" hidden>
        <h2>Обучить свой голос</h2>
        <ol class="nv-steps">
          <li><b>Собери записи.</b> 1–10 минут речи одного человека: без музыки, эха и чужих голосов — чем чище, тем точнее голос. Сложи файлы (.wav, .mp3) в одну папку.</li>
          <li><b>Открой студию обучения.</b> Это интерфейс самого GPT-SoVITS, он откроется в браузере.
            <div class="row" style="margin-top:10px">
              <button class="btn primary" id="btnStudio" type="button">Открыть студию обучения</button>
              <button class="btn sm" id="btnStudioStop" type="button" hidden>Закрыть студию</button>
            </div>
            <div class="nv-status" id="studioSt" aria-live="polite"></div>
            <div class="hint">Первый запуск один раз докачает ~250 МБ файлов для обучения. Пока идёт обучение, озвучку лучше не запускать: обоим нужна видеокарта.</div></li>
          <li><b>Пройди в студии вкладки по порядку.</b>
            <ul class="nv-guide">
              <li><span class="nv-k">0</span> подготовка записей: нарежь их на фразы (0b), распознай текст (0c, язык — как в записях), при желании поправь ошибки (0d).</li>
              <li><span class="nv-k">1A</span> придумай имя голоса латиницей и подготовь данные одной кнопкой.</li>
              <li><span class="nv-k">1B</span> обучи сначала SoVITS, потом GPT — значения по умолчанию подходят.</li>
            </ul></li>
          <li><b>Подключи результат.</b> Обученные веса появятся в папке движка — найди их, и голос встанет в список.
            <div class="row" style="margin-top:10px">
              <button class="btn sm" id="btnScan3" type="button">Найти обученные голоса</button>
            </div></li>
        </ol>
      </div>
    </section>

    <!-- ============================================ ПРИЛОЖЕНИЕ -->
    <section class="panel" id="p-app">
      <h1>Приложение</h1>
      <p class="sub">Оформление, мастер настройки, обновление, диагностика и где лежат файлы. Движок синтеза выбирается на главном экране.</p>

      <div class="banner" id="appBanner"></div>

      <!-- Оформление: как в Fragile Notes (тип, плотность, темы, акцент) -->
      <details class="card more" id="appearanceCard">
        <summary>
          <span class="more-t">Оформление</span>
          <span class="hint" style="margin:0">тип интерфейса, тема, акцент, плотность</span>
        </summary>
        <div class="more-b">

        <div class="ap-row">
          <div class="ap-text">
            <div class="ap-name">Тип дизайна</div>
            <div class="ap-desc">Компоновка и форма интерфейса. Цветовая тема и акцент работают с любым типом.</div>
          </div>
        </div>
        <div class="dtypes" id="apDesign" role="radiogroup" aria-label="Тип дизайна">
          <button class="dtype" data-v="sharp" role="radio" type="button">
            <span class="dt-prev dt-sharp" aria-hidden="true"><i></i><i></i><i></i></span>
            <b>Чёткий</b><small>Основной: прямые углы, ясные границы блоков, плотная сетка</small>
          </button>
          <button class="dtype" data-v="classic" role="radio" type="button">
            <span class="dt-prev dt-classic" aria-hidden="true"><i></i><i></i><i></i></span>
            <b>Классический</b><small>Мягкие скругления и плавающие панели, как раньше</small>
          </button>
          <button class="dtype" data-v="glass" role="radio" type="button">
            <span class="dt-prev dt-glass" aria-hidden="true"><i></i><i></i><i></i></span>
            <b>Стекло</b><small>Как в новой iOS: полупрозрачные панели</small>
          </button>
        </div>

        <div class="ap-row">
          <div class="ap-text">
            <div class="ap-name">Плотность</div>
            <div class="ap-desc">Высота строк, вкладок и заголовков панелей.</div>
          </div>
          <div class="seg" id="apDensity">
            <button data-v="compact" type="button">Компактная</button>
            <button data-v="regular" type="button">Обычная</button>
            <button data-v="comfortable" type="button">Просторная</button>
          </div>
        </div>
        <div class="ap-row" id="apMonoRow">
          <div class="ap-text">
            <div class="ap-name">Моноширинные подписи</div>
            <div class="ap-desc">Заголовки разделов, строка состояния и метки — моноширинным шрифтом заглавными.</div>
          </div>
          <label class="switch"><input type="checkbox" id="apMono" aria-label="Моноширинные подписи"></label>
        </div>
        <div class="ap-row" id="apOpaqueRow">
          <div class="ap-text">
            <div class="ap-name">Уменьшить прозрачность</div>
            <div class="ap-desc">Панели станут непрозрачными: проще читать и легче для слабых компьютеров. Включается само, если так настроена система.</div>
          </div>
          <label class="switch"><input type="checkbox" id="apOpaque" aria-label="Уменьшить прозрачность"></label>
        </div>

        <div class="ap-row">
          <div class="ap-text">
            <div class="ap-name">Встроенная тема оформления</div>
            <div class="ap-desc" id="apThemeDesc">—</div>
          </div>
        </div>
        <div class="themes" id="apThemes" role="radiogroup" aria-label="Тема оформления"></div>

        <div class="ap-row">
          <div class="ap-text">
            <div class="ap-name">Цвет акцента</div>
            <div class="ap-desc">Цвет ссылок, кнопок и выделений. Свой цвет перекрывает акцент темы.</div>
          </div>
          <div class="row" style="align-items:center">
            <input type="color" id="apAccent" aria-label="Цвет акцента">
            <button class="btn sm ghost" id="apAccentReset" type="button">Сбросить</button>
          </div>
        </div>
        </div>
      </details>

      <div class="card">
        <div class="log-head">
          <h2>Мастер настройки</h2>
          <span class="hint" id="setupState" style="margin:0"></span>
        </div>
        <div class="hint" id="setupSummary">Проверяю движок, Anki и голоса…</div>
        <div class="spacer" style="height:12px"></div>
        <div class="row">
          <button class="btn primary" id="btnWizard">Открыть мастер</button>
          <button class="btn ghost" id="btnWizardAgain">Пройти заново</button>
        </div>
      </div>

      <div class="card">
        <div class="log-head">
          <h2>Обновление</h2>
        </div>
        <div class="row">
          <button class="btn" id="btnUpdate" title="Сходит в сеть на GitHub и покажет changelog">Проверить обновления</button>
          <a class="btn ghost" id="lnkReleases" href="https://github.com/Daii1414/AnkiVoice/releases"
             target="_blank" rel="noopener">Релизы на GitHub</a>
        </div>
        <div id="updateBox" class="hint">Нажми «Проверить обновления» — покажу список изменений и предложу установщик. Эта кнопка ходит в интернет на GitHub; сама озвучка работает офлайн.</div>
      </div>

      <div class="card">
        <h2>Проверить, всё ли работает</h2>
        <div id="doctor" class="hint">Быстрая проверка без синтеза: папка движка и его Python, связь с Anki, голоса и медиатека Anki. Если что-то не так — здесь будет сказано, что именно и как исправить.</div>
        <div class="spacer" style="height:12px"></div>
        <div class="row">
          <button class="btn" id="btnDoctor">Проверить</button>
          <button class="btn ghost" id="btnSelftest" title="Подробная проверка с чтением японского; итог — в журнале на вкладке «Озвучка»">Подробная проверка</button>
        </div>
      </div>

      <div class="card">
        <h2>Где лежат файлы</h2>
        <table class="tbl">
          <tbody>
            <tr><td class="k">Программа</td><td class="v" id="pCode">—</td></tr>
            <tr><td class="k">Версия</td><td class="v" id="pVersion">—</td></tr>
            <tr><td class="k">Конфиг</td><td class="v" id="pCfg">—</td></tr>
            <tr><td class="k">Медиа Anki (куда падает звук)</td><td class="v" id="pMedia">—</td></tr>
            <tr><td class="k">Журнал и отчёт о сбоях</td><td class="v" id="pLog">—</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="row">
          <button class="btn ghost" id="btnQuit">Закрыть AnkiVoice</button>
          <span class="hint">Закрывает приложение и локальный сервер. Карточки и звук в Anki остаются как есть.</span>
        </div>
      </div>
    
  <div class="card">
    <label class="f">История озвучек</label>
    <div id="histList" class="hint">—</div>
    <pre id="histView" style="display:none;max-height:320px;overflow:auto;
         background:rgba(127,127,127,.08);padding:10px;border-radius:8px;
         white-space:pre-wrap;font-size:12px"></pre>
  </div>
</section>

  </main>
</div>

<!-- мастер первого запуска -->
<div class="overlay" id="wizardOverlay">
  <div class="modal wizard">
    <header><span>Мастер настройки</span>
      <button class="x" id="wzClose">×</button></header>
    <div class="wsteps" id="wzSteps"></div>
    <div class="wbody" id="wzBody"></div>
    <footer>
      <button class="btn sm ghost" id="wzSkip" title="Закрыть мастер — его можно открыть снова во вкладке «Приложение»">Закрыть мастер</button>
      <span class="sp" style="margin-left:auto"></span>
      <button class="btn sm" id="wzPrev">Назад</button>
      <button class="btn sm primary" id="wzNext">Далее</button>
      <button class="btn sm primary" id="wzDone" style="display:none">Готово</button>
    </footer>
  </div>
</div>

<!-- модалка выбора файла/папки -->
<div class="overlay" id="overlay">
  <div class="modal">
    <header><span id="mTitle">Выбор файла</span>
      <button class="x" id="mClose">×</button></header>
    <div class="crumbs" id="mPath">—</div>
    <div class="plist" id="mList"></div>
    <footer>
      <button class="btn sm" id="mUp">↑ Вверх</button>
      <button class="btn sm primary" id="mPick">Выбрать</button>
    </footer>
  </div>
</div>

<!-- свой диалог подтверждения: нативный confirm() блокирует страницу -->
<div class="overlay" id="confirmOverlay">
  <div class="modal" style="width:min(520px,94vw)">
    <header><span>Подтверждение</span>
      <button class="x" id="confirmX">×</button></header>
    <div style="padding:16px 18px;font-size:14px;line-height:1.55" id="confirmText"></div>
    <footer>
      <button class="btn" id="confirmNo">Отмена</button>
      <button class="btn primary" id="confirmOk">Да</button>
    </footer>
  </div>
</div>

<div class="toast" id="toast"></div>
<div class="lang-menu" id="langMenu" role="dialog" aria-label="Язык интерфейса" hidden>
  <input type="search" id="langFind" placeholder="Найти язык" aria-label="Найти язык" autocomplete="off">
  <div class="lang-list notr" id="langList" role="listbox" aria-label="Язык интерфейса"></div>
  <div class="lang-note" id="langNote" hidden>Перевод сделан автоматически — если заметишь ошибку, напиши нам.</div>
</div>

<script>
/*__I18N__*/
/*__THEMES__*/
let LANG = (typeof AV_LANG0 === "string" && AV_LANG0) || "ru";
let I18N_PREFIX = null;
function prefixKeys(){
  // ключи, которыми начинается длинный текст («Проблемы: X», «Код 3»)
  if(I18N_PREFIX) return I18N_PREFIX;
  I18N_PREFIX = Object.keys(I18N)
    .filter(k => k.length >= 6 && /[\s:]$/.test(k))
    .sort((a,b)=>b.length-a.length);
  return I18N_PREFIX;
}
function trText(s){
  if(!I18N) return s;
  const raw = s;
  const key = s.trim();
  if(!key) return s;
  const lead = raw.slice(0, raw.indexOf(key));
  const trail = raw.slice(raw.indexOf(key) + key.length);
  let tr = I18N[key];
  if(tr === undefined) tr = I18N[key.replace(/\u00a0/g, " ")];
  if(tr === undefined) tr = I18N[key.replace(/\u00a0/g, " ").replace(/\s+/g, " ")];
  if(tr === undefined){
    // начало фразы известно, хвост — данные: переводим начало
    const ks = prefixKeys();
    for(let i=0;i<ks.length;i++){
      const k = ks[i];
      if(raw.indexOf(k) === 0){
        return lead + I18N[k] + raw.slice(k.length);
      }
    }
    return s;
  }
  return lead + tr + trail;
}
function translateNode(n){
  if(!n || n.nodeType!==3) return;
  const el = n.parentElement;
  if(el && el.closest(".notr")) return;          // данные и названия языков
  const cur = n.nodeValue;
  // код мог заменить текст после перевода — тогда исходник уже он
  if(n.__ru !== undefined && cur !== n.__tr) n.__ru = undefined;
  const src = n.__ru !== undefined ? n.__ru : cur;
  if(LANG === "ru" || !I18N){
    // возвращаем русский текст, который запомнили при переводе
    if(n.__ru !== undefined){ n.nodeValue = n.__ru; n.__ru = undefined; }
    return;
  }
  const nt = trText(src);
  if(nt !== src){
    n.__ru = src; n.__tr = nt;
    if(cur !== nt) n.nodeValue = nt;
  }else if(n.__ru !== undefined){
    n.nodeValue = src; n.__ru = undefined;
  }
}
// атрибут (подсказка, плейсхолдер, aria-label) — по тому же правилу
function translateAttr(el, attr){
  const cur = el.getAttribute(attr);
  if(cur == null || (el.closest && el.closest(".notr"))) return;
  const k = "__ru_" + attr, kt = "__tr_" + attr;
  if(el[k] !== undefined && cur !== el[kt]) el[k] = undefined;
  const src = el[k] !== undefined ? el[k] : cur;
  if(LANG === "ru" || !I18N){
    if(el[k] !== undefined){ el.setAttribute(attr, el[k]); el[k] = undefined; }
    return;
  }
  const tr = I18N[src] || I18N[src.replace(/\u00a0/g, " ")];
  if(tr){ el[k] = src; el[kt] = tr; if(cur !== tr) el.setAttribute(attr, tr); }
  else if(el[k] !== undefined){ el.setAttribute(attr, src); el[k] = undefined; }
}
function translateDom(root){
  if(!root) return;
  if(root.nodeType===3){ translateNode(root); return; }
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  const nodes = []; let n;
  while((n = w.nextNode())) nodes.push(n);
  for(const x of nodes) translateNode(x);
  if(root.querySelectorAll){
    root.querySelectorAll("[title]").forEach(el=>translateAttr(el, "title"));
    root.querySelectorAll("[placeholder]").forEach(el=>translateAttr(el, "placeholder"));
    root.querySelectorAll("[aria-label]").forEach(el=>translateAttr(el, "aria-label"));
  }
}
const AV_DATA_SEL = "option, script, style, #pCode, #pCfg, #pVersion, #sideFoot, " +
  "#gptpath, #deck, #deck2, #voice, #vlist, #veName, #v_ref, #v_prompt, #auxList, " +
  "#a_disp, " +
  "#a_ref, #a_gpt, #a_sov, #a_txt, #wzPath, #wzText, #testFile, #mPath, #mTitle, " +
  "#voiceHint, #fieldsSaved, #doctor, #updateBox, #log, #progText, " +
  ".vf-p, .rd-s, #goSummary b";
function reportUntranslated(){
  // в английском режиме всё видимое должно быть переведено: что осталось
  // по-русски — пишем в консоль, чтобы это было видно сразу.
  // Данные пользователя (названия колод, пути, имена голосов, лог) не
  // переводятся — их пропускаем.
  const left = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  let n;
  while((n = w.nextNode())){
    const t = (n.nodeValue || "").trim();
    if(!t || !/[\u0410-\u042f\u0430-\u044f\u0401\u0451]/.test(t)) continue;
    const el = n.parentElement;
    if(el && el.closest && el.closest(AV_DATA_SEL)) continue;
    left.push(t.replace(/\s+/g, " ").slice(0, 120));
  }
  if(left.length){
    const uniq = Array.from(new Set(left));
    console.warn("i18n: \u043d\u0435 \u043f\u0435\u0440\u0435\u0432\u0435\u0434\u0435\u043d\u043e ("+uniq.length+"): " + uniq.join(" | "));
  }
}
function langInfo(code){
  return (typeof AV_LANGS !== "undefined" ? AV_LANGS : []).find(l=>l.code === code)
    || {code, name:code, en:code};
}
function applyLang(){
  document.documentElement.lang = LANG;
  const cur = $("langCur");
  if(cur) cur.textContent = langInfo(LANG).name;
  translateDom(document.body);
  translateDom($("langMenu"));
  if(LANG !== "ru") setTimeout(reportUntranslated, 60);
}
try{
  const mo = new MutationObserver(muts=>{
    if(LANG==="ru") return;
    for(const m of muts){
      for(const nd of m.addedNodes){
        if(nd.nodeType===3) translateNode(nd);
        else if(nd.nodeType===1) translateDom(nd);
      }
      if(m.type==="characterData") translateNode(m.target);
    }
  });
  mo.observe(document.body,{childList:true,subtree:true,characterData:true});
}catch(e){}
"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let ST = null;            // последний /api/state
let FIELDS = [];          // поля выбранной колоды
let RUNNING = false;
let NOTHING_TO_DO = false;   // пайплайн сказал «озвучивать нечего»
let STOPPED_BY_USER = false; // остановка по кнопке — это не ошибка
let SSE = null;
let WZ = {open:false, step:0, setup:null, busy:false, timer:null,
          runId:null, path:"", voice:"", text:"", testError:"", serverError:""};
let UPD = {timer:null};

/* ================================================= утилиты */
const AV_TOKEN = "__AVTOKEN__";
async function api(path, body){
  // ключ запуска нужен и GET-запросам: сервер отдаёт /api/* только с ним
  // (раньше GET шли без ключа, и страница не могла загрузить даже состояние)
  const opt = body === undefined ? {headers:{"X-AV-Token": AV_TOKEN}} : {
    method:"POST",
    headers:{"Content-Type":"application/json", "X-AV-Token": AV_TOKEN},
    body: JSON.stringify(body)
  };
  const r = await fetch(path, opt);
  let j = null;
  try{ j = await r.json(); }catch(e){}
  if(!r.ok || (j && j.error)) throw new Error((j && j.error) || ("HTTP "+r.status));
  return j;
}
function toast(msg, kind){
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast on" + (kind ? " " + kind : "");
  clearTimeout(t._h);
  t._h = setTimeout(()=>t.className="toast", 3600);
}
function banner(id, kind, html){
  const el = $(id);
  if(!kind){ el.className = "banner"; el.innerHTML=""; return; }
  el.className = "banner show " + kind;
  el.innerHTML = html;
}

/* ================================================= вкладки */
document.querySelectorAll(".nav").forEach(b=>{
  b.onclick = ()=>{
    document.querySelectorAll(".nav").forEach(x=>x.classList.remove("on"));
    document.querySelectorAll(".panel").forEach(x=>x.classList.remove("on"));
    b.classList.add("on");
    $("p-"+b.dataset.tab).classList.add("on");
    // на телефоне вкладки — лента с прокруткой: активная должна быть видна
    b.scrollIntoView({block:"nearest", inline:"nearest"});
    // на вкладке полей показываем поля колоды сразу, без лишнего клика
    if(b.dataset.tab === "anki" && !FIELDS.length) loadFields();
  };
});
function goTab(name){
  const b = document.querySelector('.nav[data-tab="'+name+'"]');
  if(b) b.click();
}

/* ================================================= тема */
/* ================================================= язык интерфейса */
// выпадающий список в стиле интерфейса: поиск, клавиатура, пометка текущего
function renderLangList(filter){
  const box = $("langList");
  const f = (filter || "").trim().toLowerCase();
  box.innerHTML = "";
  AV_LANGS.filter(l => !f || (l.name + " " + l.en + " " + l.code).toLowerCase().includes(f))
    .forEach((l, i)=>{
      const b = document.createElement("button");
      b.type = "button";
      b.className = "lang-opt" + (l.code === LANG ? " on" : "");
      b.setAttribute("role", "option");
      b.setAttribute("aria-selected", l.code === LANG ? "true" : "false");
      b.setAttribute("lang", l.code);
      b.dataset.code = l.code;
      b.style.setProperty("--i", Math.min(i, 14));
      const nm = document.createElement("span");
      nm.className = "lang-n";
      nm.textContent = l.name;
      b.appendChild(nm);
      if(l.en !== l.name){
        const en = document.createElement("small");
        en.textContent = l.en;
        b.appendChild(en);
      }
      b.onclick = ()=>setLang(l.code);
      box.appendChild(b);
    });
}
function placeLangMenu(){
  const r = $("btnLang").getBoundingClientRect(), m = $("langMenu");
  const w = Math.min(360, innerWidth - 16);
  m.style.width = w + "px";
  m.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + "px";
  m.style.top = (r.bottom + 6) + "px";
  m.style.maxHeight = Math.max(220, innerHeight - r.bottom - 18) + "px";
}
function openLangMenu(){
  const m = $("langMenu");
  renderLangList("");
  $("langFind").value = "";
  $("langNote").hidden = LANG === "ru" || LANG === "en";
  m.hidden = false;
  placeLangMenu();
  m.classList.remove("lm-in"); void m.offsetWidth; m.classList.add("lm-in");
  $("btnLang").setAttribute("aria-expanded", "true");
  const on = m.querySelector(".lang-opt.on");
  if(on) on.scrollIntoView({block:"nearest"});
  setTimeout(()=>$("langFind").focus({preventScroll:true}), 30);
}
function closeLangMenu(focusBtn){
  const m = $("langMenu");
  if(m.hidden) return;
  m.hidden = true;
  $("btnLang").setAttribute("aria-expanded", "false");
  if(focusBtn) $("btnLang").focus();
}
async function setLang(code){
  closeLangMenu(true);
  if(code === LANG) return;
  if(code !== "ru"){
    try{
      const j = await api("/api/i18n?lang=" + encodeURIComponent(code));
      I18N = j.dict;
    }catch(e){ return toast(e.message, "bad"); }
  }
  I18N_PREFIX = null;
  LANG = code;
  const swap = ()=>{
    applyLang();
    // то, что рисуется кодом с учётом языка
    try{ buildThemeGallery(); renderAppearance(); }catch(e){}
    try{ updateReady(); renderEnsemble(); }catch(e){}
  };
  if(typeof withReveal === "function") withReveal(swap); else swap();
  saveCfg({lang:code});
  toast(langInfo(code).name);
}
$("btnLang").onclick = ()=>{ $("langMenu").hidden ? openLangMenu() : closeLangMenu(true); };
$("langFind").oninput = ()=>renderLangList($("langFind").value);
$("langMenu").addEventListener("keydown", e=>{
  const opts = [...$("langList").querySelectorAll(".lang-opt")];
  const i = opts.indexOf(document.activeElement);
  if(e.key === "Escape"){ e.preventDefault(); closeLangMenu(true); }
  else if(e.key === "ArrowDown"){ e.preventDefault(); (opts[i + 1] || opts[0] || {focus(){}}).focus(); }
  else if(e.key === "ArrowUp"){ e.preventDefault(); (i <= 0 ? $("langFind") : opts[i - 1]).focus(); }
  else if(e.key === "Enter" && document.activeElement === $("langFind") && opts[0]){ e.preventDefault(); opts[0].click(); }
});
document.addEventListener("pointerdown", e=>{
  const m = $("langMenu");
  if(!m.hidden && !m.contains(e.target) && !$("btnLang").contains(e.target)) closeLangMenu(false);
});
addEventListener("resize", ()=>{ if(!$("langMenu").hidden) placeLangMenu(); });
addEventListener("scroll", ()=>{ if(!$("langMenu").hidden) placeLangMenu(); }, {passive:true});

/* ================================================= состояние */
async function loadState(){
  try{
    ST = await api("/api/state");
  }catch(e){
    banner("appBanner","bad","<b>Сервер не отвечает:</b> "+esc(e.message));
    return;
  }
  const c = ST.cfg || {};
  // Версию видно в настройках («Где лежат файлы»). В шапке её нет:
  // номер меняется в каждом релизе, а плашка там только отвлекает.
  $("pVersion").textContent = ST.version || "—";

  // статусы
  chip($("chipAnki"), ST.anki, "Anki", ST.anki ? "подключена" : "не подключена");
  chip($("chipTts"),  ST.tts,  "Движок", ST.tts ? "запущен" : "не запущен (запустится сам)");

  $("sideFoot").innerHTML = "Программа<br><b title=\""+esc(ST.code_dir)+"\">"+esc(ST.code_dir)+"</b>";

  // карточка «Где лежат файлы» — заполняем сразу, без нажатия «Диагностика»
  $("pCode").textContent = ST.code_dir || "—";
  $("pCfg").textContent  = ST.config_file || "—";
  $("pMedia").textContent = ST.anki_media || "не нашли";
  $("pLog").textContent = ST.log_file || "—";

  // папка движка
  applyEngineUI();
  $("gptpath").value = ST.path || "";
  if(ST.problems && ST.problems.length){
    banner("appBanner","bad",
      "<b>Папка движка:</b> " + esc(ST.problems.join(" · ")) +
      (ST.auto ? '<div class="acts"><button class="btn sm" id="bAuto">Подставить найденную: '+esc(ST.auto)+'</button></div>' : ""));
    const b = $("bAuto");
    if(b) b.onclick = ()=>{ $("gptpath").value = ST.auto; savePath(); };
    $("navBadge").style.display = "";
    $("pathHint").innerHTML = '<span style="color:var(--err)">Папка не подходит</span>';
  }else{
    banner("appBanner", null);
    $("navBadge").style.display = "none";
    // под полем пути — только результат последней проверки, без дубля статуса
    if(!$("pathHint").textContent) $("pathHint").innerHTML = "";
  }

  // голоса
  renderVoiceList();
  fillVoiceSelect(c.voice);
  const dv = ST.voices && ST.default_voice && ST.voices[ST.default_voice];
  // подпись про голос по умолчанию — только если он и правда выбран,
  // иначе она читается как противоречие («в списке одно, подписано другое»)
  $("voiceHint").innerHTML = (dv && ST.default_voice === $("voice").value)
    ? "Голос по умолчанию: <b>" + esc(dv.display || ST.default_voice) + "</b>"
    : "";

  // колоды не тянем в state (долго) — отдельным вызовом
  if(!$("deck").options.length) loadDecks(c.deck);

  // проверка произношения
  const vpr = $("verifyPron");
  if(vpr) vpr.checked = !!c.verify_pronunciation;
  const pr = (ST && ST.pron) || {};
  if($("pronHint")){
    // недоступна — переключатель серый и рядом сразу кнопка «что сделать»
    vpr.disabled = !pr.ok;
    if(!pr.ok) vpr.checked = false;
    $("verifyPronRow").classList.toggle("is-off", !pr.ok);
    $("pronHint").innerHTML = pr.ok
      ? "Готово к работе, модель: <b>" + esc(pr.msg || "") + "</b>."
      : "Сейчас недоступна: " + esc(pr.msg || "нет данных") + ". " +
        (pr.can_fetch ? "Нажми кнопку ниже — модель скачается один раз. Без неё озвучка работает как обычно."
                      : "Без неё озвучка работает как обычно.");
    $("btnAsrGet").style.display = (!pr.ok && pr.can_fetch) ? "" : "none";
    // шаги проверки качества без модели не работают — так и показываем
    ["btnVerify"].forEach(id=>{
      const b = $(id); if(!b) return;
      b.disabled = !pr.ok;
      b.dataset.tip = pr.ok ? "" : "Недоступно: не скачана модель распознавания речи — кнопка в «Дополнительных настройках».";
    });
  }

  // режим/лимит из конфига
  if(c.mode) setMode(c.mode);
  if(c.limit != null) $("limit").value = c.limit;
  if(c.sentence_src !== undefined){
    ["sentence_src:sent_src","sentence_audio:sent_aud","word_src:word_src",
     "word_audio:word_aud","furigana_src:furi","reading:reading"].forEach(p=>{
      const [k,id] = p.split(":");
      const el = $("f_"+id);
      if(el && c[k] != null) el.dataset.saved = c[k];
    });
  }

  // запущенная операция
  const r = ST.run;
  if(r && r.running) beginRunUI(r);
  else if(ST.last) showLastRun(ST.last);
  updateReady();
}
function chip(el, ok, name, txt){
  el.className = "chip " + (ok ? "good" : "bad");
  el.innerHTML = '<span class="dot keep-round"></span>' + esc(name) + ": " + esc(txt);
}

/* ================================================= колоды */
let DECKS = [];           // [[имя, карточек], …] — из последней загрузки
function deckCount(name){
  const d = DECKS.find(x => x[0] === name);
  return d ? d[1] : 0;
}
function deckHint(){
  const n = deckCount($("deck").value);
  const hint = $("deckHint");
  if(!DECKS.length) return;
  // слова и числа — отдельными узлами: каждая фраза переводится целиком
  hint.innerHTML = "<span>Колод в Anki: </span><b>" + DECKS.length + "</b>. <span>В выбранной:</span> <b>" +
    (n < 0 ? "?" : n) + "</b> <span>карточек</span>" +
    (n > 200 ? " — <b>озвучивать всю колоду долго</b><span>, поставь лимит.</span>" : ".");
  updateReady();
}
async function loadDecks(prefer){
  const hint = $("deckHint");
  hint.textContent = "Читаю колоды из Anki…";
  try{
    const j = await api("/api/decks");
    const decks = j.decks || [];
    DECKS = decks;
    [$("deck"), $("deck2")].forEach(sel=>{
      const prev = sel.value;
      sel.innerHTML = decks.map(d=>
        '<option value="'+esc(d[0])+'">'+esc(d[0])+"  ("+(d[1]<0?"?":d[1])+")</option>").join("");
      if(prefer && decks.some(d=>d[0]===prefer)) sel.value = prefer;
      else if(prev && decks.some(d=>d[0]===prev)) sel.value = prev;
      else{
        const i = decks.findIndex(d=>d[1] > 0);
        if(i >= 0) sel.value = decks[i][0];
      }
    });
    if(!decks.length){
      hint.innerHTML = "Anki не подключена — <b>открой Anki</b> и нажми «Обновить».";
    }else{
      deckHint();
    }
    onDeckPick();
  }catch(e){
    hint.textContent = "Не удалось прочитать колоды: " + e.message;
  }
}
function onDeckPick(){
  const d = $("deck").value;
  if(!d) return;
  saveCfg({deck:d});
  if(d !== $("deck2").value) $("deck2").value = d;
  // поля относятся к конкретной колоде: сменили колоду — перечитать
  clearFieldSelects();
  loadFields();
  deckHint();
}
$("deck").onchange = onDeckPick;
$("deck2").onchange = ()=>{
  if($("deck2").value){
    $("deck").value = $("deck2").value;
    onDeckPick();
  }
};
$("btnDecks").onclick = ()=>loadDecks($("deck").value);

/* ================================================= поля колоды */
const FIELD_IDS = ["sent_src","sent_aud","word_src","word_aud","furi","reading"];
function clearFieldSelects(){
  FIELD_IDS.forEach(id=>{
    const el = $("f_"+id);
    if(el) el.innerHTML = '<option value="">— не используется —</option>';
  });
  $("fieldsSaved").textContent = "";
}
function fillSelect(sel, fields, keep){
  const prev = (keep !== undefined && keep !== null) ? keep : sel.value;
  let html = '<option value="">— не используется —</option>';
  if(sel.id === "f_reading")
    html = '<option value="">Авто: есть фуригана — чтение по ней, нет — кандзи</option>'
          + '<option value="asis">Только кандзи (движок читает сам)</option>';
  // для источника чтения — всего два режима, поля не подставляем
  if(sel.id !== "f_reading")
    html += fields.map(f=>'<option value="'+esc(f)+'">'+esc(f)+"</option>").join("");
  sel.innerHTML = html;
  if(sel.id === "f_reading"){
    // два режима: авто (пусто) и «только кандзи»
    sel.value = (prev === "asis") ? "asis" : "";
    return;
  }
  if(prev && fields.indexOf(prev) >= 0) sel.value = prev;
}
async function loadFields(){
  const deck = $("deck2").value || $("deck").value;
  if(!deck){ banner("ankiBanner","warn","Сначала выбери колоду."); return; }
  $("fieldsHint").textContent = "Читаю поля колоды «"+deck+"»…";
  try{
    const j = await api("/api/fields?deck=" + encodeURIComponent(deck));
    FIELDS = j.fields || [];
    if(!FIELDS.length){
      $("fieldsHint").textContent = "Полей нет — колода пуста или Anki закрыта.";
      banner("ankiBanner","warn","Не удалось прочитать поля колоды «"+esc(deck)+"».");
      return;
    }
    const g = j.guess || {};
    // сначала профиль этой колоды, потом общие значения конфига,
    // иначе — автоподбор по названиям полей
    const c = ST.cfg || {};
    const prof = ((c.profiles) || {})[deck] || {};
    // голос и состав ансамбля на колоду: профиль помнит последний прогон
    if (prof.voice && [...$("voice").options].some(o=>o.value===prof.voice)
        && $("voice").value !== prof.voice){
      // голос из профиля колоды — и сразу во все места, где он виден
      // (раньше плашка и сводка показывали прежний голос, а список — новый)
      $("voice").value = prof.voice;
      markSelected(prof.voice);
      openVoiceEditor(prof.voice);
      renderEnsemble();
      updateReady();
    }
    const sel2 = $("voices2");
    if (sel2){
      // в профиле ансамбль хранится с весами («madara:40») — сравниваем имя
      const want = String(prof.ensemble || "").split(",")
        .map(x=>x.split(":")[0].trim());
      [...sel2.options].forEach(o=>{ o.selected = want.includes(o.value); });
      // доли из профиля («madara:40») — в поле пропорций, порядок как в списке
      const wmap = {};
      String(prof.ensemble || "").split(",").forEach(x=>{
        const [n, w] = x.split(":");
        if(n && w) wmap[n.trim()] = parseInt(w, 10);
      });
      const picked = [...sel2.options].filter(o=>o.selected).map(o=>o.value);
      $("ensWeights").value = picked.length >= 2 && Object.keys(wmap).length
        ? picked.map(v=>wmap[v] || 1).join(",") : "";
      // у колоды сохранён ансамбль — сразу показываем режим «Ансамбль»
      ENS_ON = picked.length >= 2;
      renderEnsemble();
      syncVoicePick();
      updateReady();
    }
    const pick = (key, guess) => {
      if (prof[key] !== undefined && prof[key] !== null && prof[key] !== "")
        return prof[key];
      if (key === "reading"){
        // rezhim chteniya - nastoyka profila kolody; pustoe = avto
        // (furigana est - chtenie po neey, net - kandidzi)
        if (prof.reading === "asis" || prof.reading === "mix") return prof.reading;
        if (c.reading === "asis" || c.reading === "mix") return c.reading;
        return "";
      }
      return (c[key] !== undefined && c[key] !== null && c[key] !== "")
        ? c[key] : (guess || "");
    };
    fillSelect($("f_sent_src"), FIELDS, pick("sentence_src", g.sentence_src));
    fillSelect($("f_sent_aud"), FIELDS, pick("sentence_audio", g.sentence_audio));
    fillSelect($("f_word_src"), FIELDS, pick("word_src", g.word_src));
    fillSelect($("f_word_aud"), FIELDS, pick("word_audio", g.word_audio));
    fillSelect($("f_furi"),     FIELDS, pick("furigana_src", g.furigana_src));
    // режим чтения: профиль колоды, иначе общий, иначе авто
    // (пусто = «авто»: есть фуригана — читаем по ней, нет — кандзи)
    const rprof = prof.reading, rglob = c.reading;
    const readMode = (rprof === "asis") ? "asis"
                   : (rprof === "mix") ? ""      // старое значение — то же, что авто
                   : (rglob === "asis") ? "asis"
                   : (rglob === "mix") ? ""
                   : "";
    fillSelect($("f_reading"),  FIELDS, readMode);
    $("fieldsHint").innerHTML = "Полей в колоде: <b>"+FIELDS.length+"</b>. " +
      "Фуригана: <b>"+esc(g.furigana_src || c.furigana_src || "нет — слово прочитается автоматически")+"</b>.";
    banner("ankiBanner", null);
  }catch(e){
    $("fieldsHint").textContent = "Ошибка: " + e.message;
    banner("ankiBanner","bad","<b>Не удалось прочитать поля:</b> "+esc(e.message));
  }
  updateGoSummary();   // поля известны — можно посчитать, сколько без звука
}
$("btnFields").onclick = loadFields;
FIELD_IDS.forEach(id=>{
  const el = $("f_"+id);
  if(el) el.onchange = ()=>{ $("fieldsSaved").textContent=""; };
});
$("btnSaveFields").onclick = ()=>{
  const g = {};
  FIELD_IDS.forEach(id=>{
    const el = $("f_"+id);
    const key = {sent_src:"sentence_src",sent_aud:"sentence_audio",
      word_src:"word_src",word_aud:"word_audio",furi:"furigana_src",reading:"reading"}[id];
    g[key] = el.value;
  });
  g.deck = $("deck2").value || $("deck").value;
  g.profile_deck = g.deck;          // сохраняем в профиль этой колоды
  saveCfg(g).then(()=>{
    $("fieldsSaved").textContent = "✓ сохранено";
    $("fieldsSaved").style.color = "var(--ok)";
    toast("Настройки полей сохранены","good");
  });
};

/* ================================================= голоса */
function voiceEntries(){
  const v = (ST && ST.voices) || {};
  return Object.keys(v).sort().map(k=>Object.assign({name:k}, v[k]));
}
function renderVoiceList(){
  const list = voiceEntries().sort((a,b)=>(b.ok?1:0)-(a.ok?1:0));
  $("vlist").innerHTML = list.map(v=>{
    const disp = v.display || v.name;
    // ключ голоса (narrator, madara) — внутреннее имя: в карточке его нет,
    // человек видит имя, под которым голос записан в voices.json
    return '<div class="vcard" data-n="'+esc(v.name)+'">'+
      '<div class="nm">'+esc(disp)+'</div>'+
      '<div class="st '+(v.ok?"ok":"no")+'">'+
        (v.ok ? "✓ файлы на месте" : "✗ нет: " + (v.missing || []).map(m => ({gpt:"GPT-весов", sovits:"SoVITS-весов", ref:"записи-образца"})[m.key] || m.key).join(", "))+
      '</div></div>';
  }).join("") || '<div class="empty">Голосов нет — нажми «Добавить голос».</div>';
  document.querySelectorAll(".vcard").forEach(c=>{
    c.onclick = ()=>selectVoice(c.dataset.n);
  });
  const cur = $("voice").value;
  if(cur) markSelected(cur);
}
function markSelected(name){
  document.querySelectorAll(".vcard").forEach(c=>
    c.classList.toggle("on", c.dataset.n === name));
}
function refreshEnsWeightsRow(){ renderEnsemble(); }
/* Несколько голосов: карточки-голоса вместо списка с Ctrl. Данные живут в
   скрытом <select id="voices2"> и поле ensWeights — их читает запуск. */
function ensWeightsMap(){
  const picked = [...$("voices2").selectedOptions].map(o=>o.value);
  const parts = ($("ensWeights").value || "").split(",").map(x=>parseInt(x, 10));
  const m = {};
  picked.forEach((v,i)=>{ m[v] = Number.isFinite(parts[i]) && parts[i] > 0 ? parts[i] : 1; });
  return m;
}
function writeEnsemble(sel, weights){
  const opts = [...$("voices2").options];
  opts.forEach(o=>{ o.selected = sel.has(o.value); });
  const picked = opts.filter(o=>o.selected).map(o=>o.value);
  $("ensWeights").value = picked.length >= 2 ? picked.map(v=>weights[v] || 1).join(",") : "";
  renderEnsemble();
  updateReady();        // плашка «Голос» и сводка показывают состав ансамбля
}
/* Ансамбль — отдельный пункт в списке голосов шага 2. Настройки (кто
   участвует и как часто) видны только в этом режиме; основной голос для
   запуска — первый отмеченный (скрытый #voice), его выбирать не нужно. */
let ENS_ON = false;
const ENS_VAL = "__ensemble__";
function ensPicked(){ return [...$("voices2").selectedOptions].map(o=>o.value); }
function syncVoicePick(){
  const pick = $("voicePick"), src = $("voice");
  if(!pick || !src) return;
  const ok = voiceEntries().filter(v=>v.ok).length;
  pick.innerHTML = [...src.options].map(o=>
      '<option value="'+esc(o.value)+'">'+esc(o.textContent)+"</option>").join("") +
    '<option disabled>──────────</option>' +
    '<option value="'+ENS_VAL+'"'+(ok < 2 ? " disabled" : "")+'>Ансамбль — несколько голосов вперемешку'+
      (ok < 2 ? " (нужно 2 готовых голоса)" : "")+"</option>";
  pick.value = ENS_ON ? ENS_VAL : src.value;
  $("voiceHint").hidden = ENS_ON;       // «голос по умолчанию» к ансамблю не относится
  const panel = $("ensPanel");
  if(panel.hidden === ENS_ON){
    panel.hidden = !ENS_ON;
    if(ENS_ON){ panel.classList.remove("ens-in"); void panel.offsetWidth; panel.classList.add("ens-in"); }
  }
  if(LANG !== "ru") translateDom(pick);
}
function setEnsembleMode(on){
  ENS_ON = !!on;
  if(ENS_ON){
    // вход в ансамбль: текущий голос уже отмечен — остаётся добавить второй
    const cur = new Set(ensPicked());
    if(!cur.size && $("voice").value) cur.add($("voice").value);
    writeEnsemble(cur, ensWeightsMap());
  }else{
    writeEnsemble(new Set(), {});
  }
  syncVoicePick();
  updateReady();
}
function renderEnsemble(){
  const box = $("ensChips");
  if(!box) return;
  const weights = ensWeightsMap();
  const sel = new Set(Object.keys(weights));
  const multi = sel.size >= 2;
  const total = [...sel].reduce((a,v)=>a + (weights[v] || 1), 0) || 1;
  box.innerHTML = "";
  voiceEntries().sort((a,b)=>(b.ok?1:0)-(a.ok?1:0)).forEach((v, i)=>{
    const on = sel.has(v.name);
    const chip = document.createElement("div");
    chip.className = "ensv" + (on ? " on" : "") + (v.ok ? "" : " off");
    chip.style.setProperty("--i", i);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ensv-b";
    btn.disabled = !v.ok;
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    const mark = document.createElement("span");
    mark.className = "ensv-c keep-round";
    mark.setAttribute("aria-hidden", "true");
    const nm = document.createElement("span");
    nm.className = "ensv-n";
    nm.textContent = v.display || v.name;
    const st = document.createElement("small");
    st.textContent = !v.ok ? "нет файлов" : (on ? "участвует" : "не участвует");
    btn.append(mark, nm, st);
    btn.onclick = ()=>{
      const cur = new Set(sel);
      if(cur.has(v.name)) cur.delete(v.name); else cur.add(v.name);
      writeEnsemble(cur, weights);
    };
    chip.appendChild(btn);
    if(on && multi){
      // доля голоса: число и процент от суммы — видно, кто чаще
      const w = document.createElement("label");
      w.className = "ensv-w";
      w.title = "Доля голоса: 2 у одного и 1 у другого — первый звучит вдвое чаще";
      const inp = document.createElement("input");
      inp.type = "number"; inp.min = "1"; inp.max = "100"; inp.step = "1";
      inp.value = weights[v.name] || 1;
      inp.setAttribute("aria-label", "Доля голоса " + (v.display || v.name));
      inp.onchange = ()=>{
        const n = Math.max(1, Math.min(100, parseInt(inp.value, 10) || 1));
        weights[v.name] = n;
        writeEnsemble(sel, weights);
      };
      const pct = document.createElement("span");
      pct.className = "ensv-p";
      pct.textContent = Math.round((weights[v.name] || 1) * 100 / total) + "%";
      w.append(inp, pct);
      chip.appendChild(w);
    }
    box.appendChild(chip);
  });
  // основной голос запуска — первый отмеченный (у него берутся профиль и тест)
  if(ENS_ON && sel.size && !sel.has($("voice").value)){
    const first = [...$("voice").options].find(o=>sel.has(o.value));
    if(first){ $("voice").value = first.value; markSelected(first.value); }
  }
  const hint = $("ensHint");
  if(multi){
    // число — отдельным узлом, чтобы фразы вокруг переводились целиком
    hint.replaceChildren("Голосов:", " " + sel.size + ". ",
                         document.createTextNode("Число у голоса — его доля: 2 и 1 = первый звучит вдвое чаще."));
    hint.classList.remove("warn");
  }else{
    hint.textContent = "Отметь ещё хотя бы один голос — пока все карточки озвучит один.";
    hint.classList.add("warn");
  }
  if(LANG !== "ru") translateDom(box.parentNode);
}
/* «Карточки, у которых звук уже есть»: один выбор вместо двух галочек,
   которые на деле исключали друг друга (скрытые force/changed — для запуска) */
function redoMode(){ return $("force").checked ? "force" : ($("changed").checked ? "changed" : "skip"); }
function setRedo(v){
  $("force").checked = v === "force";
  $("changed").checked = v === "changed";
  document.querySelectorAll("#redoChoice .ch").forEach(b=>{
    const on = b.dataset.v === v;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on ? "true" : "false");
  });
  updateReady();      // баннер и сводка зависят от режима (там же updateGoSummary)
}
document.querySelectorAll("#redoChoice .ch").forEach(b=>{ b.onclick = ()=>setRedo(b.dataset.v); });
setTimeout(()=>setRedo(redoMode()), 0);
function fillVoiceSelect(prefer){
  // готовые голоса — сверху; у неготовых пометка, чтобы было видно, почему
  // озвучка ими не пойдёт (раньше все голоса выглядели одинаково)
  const list = voiceEntries().sort((a,b)=>(b.ok?1:0)-(a.ok?1:0));
  const sel = $("voice");
  const prev = prefer || sel.value;
  sel.innerHTML = list.map(v=>
    '<option value="'+esc(v.name)+'">'+(v.ok ? "" : "✗ ")+esc(v.display || v.name)+
    (v.ok ? "" : " — нет файлов")+"</option>").join("");
  const okv = n => list.some(v=>v.name===n && v.ok);
  const firstOk = (list.find(v=>v.ok) || {}).name;
  // сохранённый выбор берём, только если голос готов; иначе — голос по
  // умолчанию или первый готовый
  if(prev && okv(prev)) sel.value = prev;
  else if(ST.default_voice && okv(ST.default_voice)) sel.value = ST.default_voice;
  else if(firstOk) sel.value = firstOk;
  else if(prev && list.some(v=>v.name===prev)) sel.value = prev;
  if(sel.value) openVoiceEditor(sel.value);
  markSelected(sel.value);
  // ансамбль: тот же список, выбор нескольких (Ctrl/Shift)
  const sel2 = $("voices2");
  if(sel2){
    const chosen = new Set([...sel2.selectedOptions].map(o=>o.value));
    sel2.innerHTML = list.map(v=>
      '<option value="'+esc(v.name)+'">'+esc(v.display || v.name)+"</option>").join("");
    [...sel2.options].forEach(o=>{ if(chosen.has(o.value)) o.selected = true; });
    refreshEnsWeightsRow();
  }
  const selV = list.find(v=>v.name===sel.value);
  $("voiceHint").innerHTML = selV
    ? (selV.ok ? "Файлы весов на месте." : '<span style="color:var(--err)">Не хватает весов (.ckpt и .pth) или записи-образца.</span>')
    : "";
  $("testFile").textContent = "test_" + (sel.value || "…") + ".ogg";
  syncVoicePick();
}
function selectVoice(name){
  if(ENS_ON){
    // в ансамбле карточка голоса только открывает его настройки:
    // состав ансамбля меняется галочками в шаге 2
    markSelected(name);
    openVoiceEditor(name);
    return;
  }
  $("voice").value = name;
  saveCfg({voice:name});
  markSelected(name);
  openVoiceEditor(name);
}
$("voice").onchange = ()=>{
  saveCfg({voice:$("voice").value});
  markSelected($("voice").value);
  openVoiceEditor($("voice").value);
};
// видимый список шага 2: голоса + пункт «Ансамбль»
$("voicePick").onchange = ()=>{
  const val = $("voicePick").value;
  if(val === ENS_VAL) return setEnsembleMode(true);
  if(ENS_ON){ ENS_ON = false; writeEnsemble(new Set(), {}); }
  $("voice").value = val;
  $("voice").dispatchEvent(new Event("change"));
  syncVoicePick();
};

let EDIT = null;   // редактируемый голос
function openVoiceEditor(name){
  const v = (ST.voices||{})[name];
  if(!v){ $("voiceEdit").style.display="none"; return; }
  EDIT = name;
  $("voiceEdit").style.display = "";
  $("veName").textContent = v.display || name;
  const tb = $("btnTest").querySelector("span");
  if(tb){ tb.textContent = "Прослушать: " + (v.display || name); if(LANG !== "ru") translateDom($("btnTest")); }
  renderVoiceFiles(v);
  $("v_ref").value = v.ref || "";
  $("v_prompt").value = v.prompt_text || "";
  $("v_lang").value = v.prompt_lang || "ja";
  $("v_noref").checked = !v.prompt_text;
  $("v_temp").value = v.temperature != null ? v.temperature : 0.6;
  $("v_topp").value = v.top_p != null ? v.top_p : 0.6;
  $("v_topk").value = v.top_k != null ? v.top_k : 20;
  $("v_speed").value = v.speed != null ? v.speed : 1.0;
  $("v_seed").value = v.seed != null ? v.seed : 42;
  ["v_temp","v_topp","v_topk","v_speed"].forEach(syncSlider);
  $("v_prompt").disabled = $("v_noref").checked;
  renderAux(v.aux || []);
}
/* Файлы голоса: что на месте, чего нет (путь — как записан в voices.json) */
function renderVoiceFiles(v){
  const box = $("veFiles");
  if(!box) return;
  const isIndex = engineNow() === "indextts";
  const keys = isIndex ? ["ref"] : ["gpt", "sovits", "ref"];
  const title = {gpt:"GPT-веса (.ckpt)", sovits:"SoVITS-веса (.pth)", ref:"запись-образец"};
  const miss = new Set((v.missing || []).map(m => m.key));
  box.innerHTML = "";
  keys.forEach(k=>{
    const row = document.createElement("div");
    row.className = "vf " + (miss.has(k) ? "no" : "ok");
    const mark = document.createElement("span");
    mark.className = "vf-m";
    mark.textContent = miss.has(k) ? "✗" : "✓";
    const t = document.createElement("span");
    t.className = "vf-t";
    t.textContent = title[k];
    const pth = document.createElement("span");
    pth.className = "vf-p";
    pth.textContent = v[k] || (miss.has(k) ? "не указан" : "");
    pth.title = v[k] || "";
    row.append(mark, t, pth);
    box.appendChild(row);
  });
  if(miss.size){
    // где программа ищет файлы — без этого «не хватает» непонятно
    const where = document.createElement("div");
    where.className = "hint";
    const w1 = document.createElement("span");
    w1.textContent = "Файлы ищутся в папке движка:";
    const w2 = document.createElement("span");
    w2.className = "vf-p";
    w2.textContent = " " + ((ST && ST.path) || "—");
    where.append(w1, w2);
    box.appendChild(where);
    const other = ((v.missing || []).find(m => m.elsewhere) || {}).elsewhere;
    const h = document.createElement("div");
    h.className = "hint";
    if(other){
      h.innerHTML = '<b style="color:var(--warn)"></b> <span class="vf-p"></span>';
      h.firstChild.textContent = "Эти файлы лежат в другом движке — переключись на него:";
      h.lastChild.textContent = other;
    }else{
      h.textContent = isIndex
        ? "Выбери запись-образец ниже и сохрани голос."
        : "Положи недостающие файлы в папку движка (веса — в GPT_weights*/SoVITS_weights*) и нажми «Обновить список голосов из папки движка», либо добавь голос заново кнопкой «Добавить голос».";
    }
    box.appendChild(h);
  }
  if(LANG !== "ru") translateDom(box);
}
/* ползунок <-> поле числа: тянем бегунок — меняется число и наоборот */
function syncSlider(id){
  const n = $(id), r = $(id + "_r");
  if(n && r) r.value = n.value;
}
["v_temp","v_topp","v_topk","v_speed"].forEach(id=>{
  const n = $(id), r = $(id + "_r");
  if(!n || !r) return;
  r.oninput = ()=>{ n.value = r.value; };
  n.oninput = ()=>{ const v = parseFloat(n.value); if(!Number.isNaN(v)) r.value = v; };
});
function renderAux(arr){
  $("auxList").innerHTML = arr.map((p,i)=>
    '<div class="row" data-i="'+i+'"><div class="grow"><input type="text" class="aux" value="'+esc(p)+'"></div>'+
    '<button class="btn sm ghost" data-del="'+i+'">✕</button></div>').join("");
  document.querySelectorAll("#auxList [data-del]").forEach(b=>{
    b.onclick = ()=>{ const a = auxArr(); a.splice(+b.dataset.del,1); renderAux(a); };
  });
}
function auxArr(){
  return Array.from(document.querySelectorAll("#auxList .aux")).map(i=>i.value).filter(x=>x);
}
$("btnAux").onclick = ()=>{ const a = auxArr(); a.push(""); renderAux(a); };
$("v_noref").onchange = ()=>{ $("v_prompt").disabled = $("v_noref").checked; };
$("btnFineReset").onclick = ()=>{
  [["v_temp", .6], ["v_topp", .6], ["v_topk", 20], ["v_speed", 1], ["v_seed", 42]].forEach(([id, v])=>{
    $(id).value = v;
    if($(id + "_r")) syncSlider(id);
  });
  toast("Стандартные значения подставлены — нажми «Сохранить голос»");
};
$("btnSaveVoice").onclick = async ()=>{
  if(!EDIT) return;
  try{
    await api("/api/voice", {
      name:EDIT, ref:$("v_ref").value, prompt_text:$("v_prompt").value,
      noref:$("v_noref").checked, prompt_lang:$("v_lang").value,
      aux:auxArr(), temperature:$("v_temp").value, top_p:$("v_topp").value,
      top_k:$("v_topk").value, speed:$("v_speed").value, seed:$("v_seed").value
    });
    $("voiceSaved").textContent = "✓ сохранено";
    $("voiceSaved").style.color = "var(--ok)";
    toast("Голос сохранён","good");
    await loadState();
  }catch(e){ toast(e.message,"bad"); }
};
$("btnTest").onclick = async ()=>{
  const v = $("voice").value;
  if(!v) return toast("Выбери голос","bad");
  const ok = await runOp({kind:"test", voice:v, text:"既存建築物の改修では、耐火性能と耐震性能の確認が重要です。",
    speed:$("v_speed").value, seed:$("v_seed").value});
  // по готовности звук проигрывается сам (как у «Послушать» на главном)
  if(ok){ HEAR = v; toast("Готовлю пробную фразу… В первый раз движок загружается 1–2 минуты."); }
};
$("btnScan").onclick = ()=>runOp({kind:"scan"});
$("btnAddVoice").onclick = addVoiceDialog;

/* ================================================= запуск операций */
function mode(){ return document.querySelector("#segMode .on").dataset.v; }
function setMode(v){
  document.querySelectorAll("#segMode button").forEach(b=>
    b.classList.toggle("on", b.dataset.v === v));
}
document.querySelectorAll("#segMode button").forEach(b=>{
  b.onclick = ()=>{ setMode(b.dataset.v); saveCfg({mode:b.dataset.v}); };
});

/* Значение поля: сначала то, что выбрано во вкладке «Поля колоды»,
   потом сохранённое в конфиге. Иначе настройка, сохранённая в прошлый
   раз, молча не применялась и озвучка уходила с пустыми полями. */
function fieldVal(id, key){
  const el = $("f_"+id);
  const v = el ? el.value : "";
  if(v) return v;
  const c = (ST && ST.cfg) || {};
  return c[key] || "";
}
function collectVoiceArgs(){
  return {
    kind:"voice", voice:$("voice").value, deck:$("deck").value, mode:mode(),
    voices:(function(){
      const picked = [...$("voices2").selectedOptions].map(o=>o.value);
      if(picked.length < 2) return picked;
      // пропорции: "60,40" -> спецификация "a:60,b:40" (порядок = выбранный)
      const raw = ($("ensWeights") && $("ensWeights").value || "").trim();
      if(!raw) return picked;
      const parts = raw.split(",").map(x=>parseInt(x, 10));
      if(picked.some((_,i)=>!Number.isFinite(parts[i]) || parts[i] < 0))
        return picked;                    // мусор — игнорируем пропорции
      return picked.map((v,i)=>parts[i] ? (v+":"+parts[i]) : v);
    })(),
    sentence_src:fieldVal("sent_src","sentence_src"),
    sentence_audio:fieldVal("sent_aud","sentence_audio"),
    word_src:fieldVal("word_src","word_src"),
    word_audio:fieldVal("word_aud","word_audio"),
    furigana_src:fieldVal("furi","furigana_src"),
    reading:fieldVal("reading","reading"),
    limit:(function(){
      const n = parseInt($("limit").value, 10);
      return (Number.isFinite(n) && n > 0) ? String(n) : "";
    })(), force:$("force").checked, changed:$("changed").checked
  };
}
$("verifyPron").onchange = ()=>{
  saveCfg({verify_pronunciation: $("verifyPron").checked});
  toast($("verifyPron").checked ? "Проверка произношения включена" : "Проверка произношения выключена");
};
$("btnStart").onclick = async ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  if(!$("voice").value) return toast("Сначала выбери голос","bad");
  if(ENS_ON && ensPicked().length < 2)
    return toast("В ансамбле нужно отметить хотя бы два голоса","bad");
  const raw = $("limit").value.trim();
  let lim = 0;
  if(raw !== ""){
    lim = parseInt(raw, 10);
    if(!Number.isFinite(lim) || lim < 0){
      // поле НЕ очищаем: пустое поле означало бы «вся колода»
      return toast("Лимит карточек — целое число не меньше нуля. Пусто или 0 — вся колода","bad");
    }
  }
  // пустой лимит = вся колода: предупреждаем, если она большая
  if(!lim){
    const n = deckCount($("deck").value);
    if(n > 200 && !await askConfirm("Озвучить ВСЮ колоду «"+$("deck").value+"» — "+n+" карточек?\nЭто надолго: с IndexTTS примерно по минуте на карточку.", "Озвучить всё")) return;
  }
  if($("force").checked && !await askConfirm(
      "«Пересобрать всё заново» перезапишет звук в выбранных карточках.\n" +
      "Старые файлы останутся в папке медиа, отмены нет.", "Переозвучить")) return;
  saveCfg({mode:mode(), limit:raw, voice:$("voice").value, deck:$("deck").value});
  await runOp(collectVoiceArgs());
};
$("btnNew").onclick = async ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  if(!$("voice").value) return toast("Сначала выбери голос","bad");
  if(ENS_ON && ensPicked().length < 2)
    return toast("В ансамбле нужно отметить хотя бы два голоса","bad");
  // «новые» лимитом не режем: смысл ровно в том, чтобы добрать добавленное
  const p = collectVoiceArgs();
  p.only_new = true;
  p.limit = "";
  await runOp(p);
};
$("btnRetry").onclick = ()=>runOp({kind:"retry"});
$("limit").onchange = ()=>{ saveCfg({limit:$("limit").value.trim()}); };
$("btnCompress").onclick = async ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  if(!await askConfirm("Сжать .wav-озвучки колоды «"+$("deck").value+"» в .ogg?\n" +
      "Ссылки в карточках заменятся, старые .wav попадут в корзину медиа Anki.", "Сжать")) return;
  runOp({kind:"compress-media", deck:$("deck").value});
};
$("btnMediaCheck").onclick = ()=>{
  runOp({kind:"cleanup-media", deck:$("deck").value || ""});
};
$("btnCheck").onclick = ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  runOp({kind:"check", deck:$("deck").value,
    sentence_audio:fieldVal("sent_aud","sentence_audio"),
    word_audio:fieldVal("word_aud","word_audio")});
};
$("btnSelftest").onclick = async ()=>{
  if(await runOp({kind:"selftest"})){
    goTab("voice");
    setTimeout(()=>$("log").scrollIntoView({behavior:"smooth", block:"center"}), 300);
  }
};
$("btnPreview").onclick = ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  // предпросмотр: движок и голос не нужны, синтеза не будет
  const p = collectVoiceArgs();
  p.kind = "preview";
  runOp(p);
};
$("btnQCDeck").onclick = async ()=>{
  if(!await askConfirm("Собрать колоду «Брак»?\nВ Anki появится новая колода с копиями сомнительных карточек и полем «Вердикт». Оригиналы не меняются.", "Собрать")) return;
  runOp({kind:"qc-deck"});
};
$("btnVerdicts").onclick = ()=>{
  runOp({kind:"verdicts"});
};
$("btnVerify").onclick = ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  if(!(ST && ST.pron && ST.pron.ok)) return toast("Проверка произношения недоступна","bad");
  runOp({kind:"verify", deck:$("deck").value, mode:mode(),
         sentence_audio:fieldVal("sent_aud","sentence_audio"),
         word_audio:fieldVal("word_aud","word_audio")});
};
$("btnStop").onclick = async ()=>{
  STOPPED_BY_USER = true;
  try{
    const j = await api("/api/stop", {});
    toast(j.ok ? "Останавливаю…" : (j.error || "Нечего останавливать"), j.ok?"":"bad");
  }catch(e){ toast(e.message,"bad"); }
};
$("btnClear").onclick = ()=>{ $("log").innerHTML = ""; };
$("follow").onchange = ()=>{ if($("follow").checked) scrollLog(); };
$("voices2") && $("voices2").addEventListener("change", refreshEnsWeightsRow);
$("voice").addEventListener("change", renderEnsemble);
$("btnAsrGet").onclick = async ()=>{
  if(!await askConfirm("Скачать модель распознавания речи faster-whisper (~1,5 ГБ) с HuggingFace?\nОна нужна только для проверки произношения и скачивается один раз.", "Скачать")) return;
  runOp({kind:"fetch-asr"});
};

async function runOp(payload){
  try{
    const j = await api("/api/run", payload);
    beginRunUI(j.run);
    return true;
  }catch(e){
    // если работа уже идёт — баннер не вешаем: он остался бы висеть до конца
    // успешной озвучки и выглядел бы как поломка
    if(!RUNNING){
      banner("voiceBanner","bad","<b>Не запустилось:</b> "+esc(e.message));
      toast(e.message,"bad");
    }else{
      toast(e.message,"bad");
    }
    return false;
  }
}
function beginRunUI(r){
  resetProgress();
  NOTHING_TO_DO = false;
  STOPPED_BY_USER = false;
  RUNNING = true;
  // разрешение на системные уведомления спрашиваем один раз, при старте
  try{ if(window.Notification && Notification.permission === "default")
        Notification.requestPermission(); }catch(e){}
  $("btnStart").disabled = true;
  $("btnCheck").disabled = true;
  $("btnSelftest").disabled = true;
  $("btnStop").disabled = false;
  $("btnTest").disabled = true;
  $("btnHear").disabled = true;
  $("chipRun").style.display = "";
  $("chipRun").className = "chip live";
  $("prog").className = "prog indet";
  $("progText").textContent = r.title || "Выполняется…";
  $("progPct").textContent = "";
  $("voiceBanner") && banner("voiceBanner", null);
  openLog(0);
}
async function loadHistory(){
  try{
    const j = await api("/api/history");
    const HIST = j.runs || [];
    const box = $("histList");
    if(!box) return;
    if(!HIST.length){ box.textContent = "Прогонов пока нет — отчёты появятся после озвучки."; return; }
    box.innerHTML = HIST.map(h=>
      '<div style="cursor:pointer;padding:2px 0" data-f="'+esc(h.file)+'">'
      // готово / ошибок — значками: строка не зависит от языка интерфейса
      + '<b>'+esc(h.at)+'</b> — <span style="color:var(--ok)">✓ '+h.done+'</span> · '
      + '<span style="color:'+(h.failed ? 'var(--err)' : 'var(--sub)')+'">✗ '+h.failed+'</span>'
      + ' ('+esc(String(h.voices || "").replace(/`/g, "").split(/,\s*/).map(
          n => ((ST && ST.voices && ST.voices[n.trim()]) || {}).display || n.trim()).join(", "))+')</div>').join("");
    box.querySelectorAll("[data-f]").forEach(el=>{
      el.onclick = ()=>showReport(el.dataset.f);
    });
  }catch(e){ const b = $("histList"); if(b) b.textContent = "История недоступна: " + e.message; }
}
async function showReport(f){
  const view = $("histView");
  if(!view) return;
  view.style.display = "";
  view.textContent = "Читаю…";
  try{
    const r = await fetch("/api/history?file=" + encodeURIComponent(f),
                          {headers:{"X-AV-Token": AV_TOKEN}});
    view.textContent = await r.text();
  }catch(e){ view.textContent = "Не удалось: " + e.message; }
}
// первичная загрузка истории вместе с состоянием
setTimeout(loadHistory, 1500);
function beep(){
  // короткий сигнал без внешних файлов (страница офлайн)
  try{
    const ctx = new (window.AudioContext||window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.frequency.value = 880; g.gain.value = 0.07;
    o.start(); o.stop(ctx.currentTime + 0.25);
  }catch(e){}
}
function notifyDone(st){
  // системное уведомление, если разрешено; иначе баннер + звук
  try{
    // счётчики ЭТОГО прогона (из журнала): ST.last_run перечитывается
    // только после endRunUI и показывал итоги прошлого запуска
    const bad = PROG_FAIL || 0, okn = PROG_OK || 0;
    const body = "Готово: " + okn + ", ошибок: " + bad +
      (bad ? " — можно перепробовать" : "");
    if(window.Notification && Notification.permission === "granted"){
      const n = new Notification("AnkiVoice: прогон завершён", {body: body});
      n.onclick = ()=>{ try{ window.focus(); }catch(e){} };
    }
    beep();
  }catch(e){}
}
function endRunUI(s){
  RUNNING = false;
  $("btnStart").disabled = false;
  $("btnCheck").disabled = false;
  $("btnSelftest").disabled = false;
  $("btnTest").disabled = false;
  $("btnHear").disabled = false;
  playHeard(s);
  refreshPending(true);
  $("btnStop").disabled = true;
  $("chipRun").style.display = "none";
  const ok = s && s.code === 0;
  $("prog").className = "prog";
  $("prog").firstElementChild.style.width = "100%";
  const stopped = STOPPED_BY_USER;
  $("progText").textContent = (s ? (s.title || "Готово") : "Готово") +
    (stopped ? " — остановлено" :
      (s && s.code != null ? " — код " + s.code : ""));
  // остановка по кнопке — это не ошибка: озвученное до неё сохранено
  $("progPct").textContent = stopped ? "■ остановлено" : (ok ? "✓ завершено" : "✗ есть ошибки");
  $("progPct").style.color = stopped ? "var(--sub)" : (ok ? "var(--ok)" : "var(--err)");
  const t = (s && s.title) || "";
  let done = "";
  if(/Озвучка/.test(t)) done = "Результат записан в колоду.";
  else if(/Проверка произношения/.test(t))
    done = "Проверка завершена — сомнительные в журнале ниже.";
  else if(/Проверка колоды/.test(t)) done = "Проверка колоды завершена.";
  else if(/Предпросмотр/.test(t)) done = "Предпросмотр готов — детали в журнале ниже.";
  else if(/Самопроверка/.test(t)) done = "Проверка окружения завершена.";
  else if(/Тест синтеза/.test(t)) done = "Тестовый звук готов.";
  else if(/Сканирование/.test(t)) done = "Сканирование завершено.";
  if(ok && NOTHING_TO_DO){
    banner("voiceBanner","warn",
      "<b>Озвучивать было нечего.</b> У выбранных карточек уже есть звук " +
      "(или пустой текст). Увеличь лимит карточек или включи " +
      "«Пересобрать всё заново».");
  }else if(STOPPED_BY_USER){
    banner("voiceBanner","warn",
      "<b>Остановлено.</b> Уже озвучённое сохранено, остальное — " +
      "в следующий раз.");
  }else if(!ok && /Проверка колоды/.test(t)){
    banner("voiceBanner","warn",
      "<b>Проверка нашла проблемы.</b> Список карточек — в журнале ниже.");
  }else if(!ok) banner("voiceBanner","bad",
    "<b>Завершилось с ошибкой (код "+(s?s.code:"?")+").</b> Посмотри журнал ниже.");
  else banner("voiceBanner","good", done ? ("<b>Готово.</b> " + done) : "<b>Готово.</b>");
  // уведомление — только про озвучку: предпросмотр/проверки не стоят того
  if(!stopped && /Озвучка|Перепробовать/.test(t)) notifyDone(s);
  try{ if(typeof loadHistory === 'function') loadHistory(); }catch(e){}
}
function showLastRun(s){
  $("prog").className = "prog";
  $("prog").firstElementChild.style.width = s.total ? "100%" : "0%";
  $("progText").textContent = "Прошлая операция: " + (s.title||"") +
    (s.code ? " — код " + s.code : "");
}

/* ================================================= лог (SSE) */
function openLog(since){
  if(SSE){ SSE.close(); SSE = null; }
  const log = $("log");
  if(!since) log.innerHTML = "";
  let lastCount = since || 0;

  SSE = new EventSource("/api/log?since=" + (since||0) + "&t=" + encodeURIComponent(AV_TOKEN));
  SSE.onmessage = ev=>{
    let d;
    try{ d = JSON.parse(ev.data); }catch(e){ return; }
    if(d.line !== undefined){
      appendLine(log, d.line);
      lastCount++;
      updateProgress(d.line, lastCount);
    }
    if(d.done){
      endRunUI(d.done);
      SSE.close(); SSE = null;
      loadState();
    }
  };
  SSE.onerror = ()=>{ /* EventSource сам переподключится */ };
}
function appendLine(log, line){
  const empty = log.querySelector(".l-dim");
  if(empty) empty.remove();
  // пайплайн сообщил, что озвучивать нечего — это не «готово»
  if(/озвучивать нечего|уже озвучено/i.test(line)) NOTHING_TO_DO = true;
  let cls = "";
  if(/^OK\s+\[/.test(line)) cls = "l-ok";
  else if(/^FAIL\s+\[/.test(line)) cls = "l-err";
  else if(line.startsWith("»")) cls = "l-cmd";
  else if(/брак:/.test(line)) cls = "l-brak";
  else if(/^\s*\[/.test(line)) cls = "l-brak";
  else if(/^!!/.test(line)) cls = "l-err";
  const div = document.createElement("div");
  if(cls) div.className = cls;
  div.textContent = line;
  log.appendChild(div);
  while(log.children.length > 3000) log.removeChild(log.firstChild);
  if($("follow").checked) scrollLog();
}
function scrollLog(){ const l=$("log"); l.scrollTop = l.scrollHeight; }

function updateProgress(line, n){
  const m = /К озвучке:\s*\d+\s+\S+\s+в\s+(\d+)/.exec(line);
  if(m) PROG_TOTAL = +m[1];
  // «Карточка 3 из 10 · осталось ~45 с — …»: ETA между числом и тире
  const st = /^Карточка\s+(\d+)\s+из\s+(\d+)[^—]*—\s*(.*)$/.exec(line);
  if(st){ PROG_CUR = +st[1]; PROG_OPS = +st[2]; PROG_STAGE = st[3]; }
  if(/^OK\s+\[(\d+)\]/.test(line)){
    // считаем КАРТОЧКИ, а не операции: в режиме «слово + предложение» на
    // карточку приходится два куска, и старая арифметика давала «25 / 24»
    const okm = /^OK\s+\[(\d+)\]/.exec(line);
    PROG_DONE.add(okm[1]);
    PROG_OK = PROG_DONE.size;
  }
  if(/^FAIL\s+\[/.test(line)) PROG_FAIL++;
  drawProgress(n);
}
let PROG_TOTAL=null, PROG_OK=0, PROG_FAIL=0, PROG_CUR=0, PROG_OPS=0, PROG_STAGE="", PROG_START=0;
let PROG_DONE = new Set();
function resetProgress(){
  PROG_TOTAL=null; PROG_OK=0; PROG_FAIL=0; PROG_CUR=0; PROG_OPS=0; PROG_STAGE="";
  PROG_DONE = new Set();
  PROG_START=Date.now();
}
function fmtSec(s){
  s=Math.max(0,Math.round(s));
  const m=Math.floor(s/60);
  return m ? (m+" мин "+Math.round(s%60)+" с") : (s+" с");
}
function drawProgress(n){
  const el = $("prog"), bar = el.firstElementChild;
  const elapsed = PROG_START ? (Date.now()-PROG_START)/1000 : 0;
  if(PROG_TOTAL){
    el.className = "prog";
    const pct = Math.min(100, Math.round(PROG_OK / PROG_TOTAL * 100));
    bar.style.width = pct + "%";
    $("progPct").textContent = PROG_OK + " / " + PROG_TOTAL +
      (PROG_FAIL ? "  ·  ошибок: " + PROG_FAIL : "");
    $("progPct").style.color = PROG_FAIL ? "var(--err)" : "var(--sub)";
    let txt = "Озвучено карточек: " + PROG_OK;
    // номер операции — из числа операций (в режиме «оба» их вдвое больше
    // карточек; раньше выходило «сейчас 8 из 5»)
    if(PROG_CUR) txt += " · операция " + PROG_CUR + " из " + (PROG_OPS || PROG_TOTAL);
    if(elapsed) txt += " · прошло " + fmtSec(elapsed);
    if(PROG_OK > 0 && PROG_TOTAL > PROG_OK){
      const per = elapsed / PROG_OK;
      txt += " · осталось ≈ " + fmtSec(per * (PROG_TOTAL - PROG_OK));
    }else if(PROG_TOTAL && PROG_CUR && PROG_OK < PROG_TOTAL){
      const slow = (ST && ST.engine === "indextts")
        ? " · с IndexTTS первая карточка идёт до нескольких минут" : "";
      txt += slow;
    }
    if(PROG_STAGE) txt += " · " + PROG_STAGE;
    $("progText").textContent = txt;
  }else{
    el.className = "prog indet";
    $("progText").textContent = "Выполняется… (" + n + " строк журнала)";
  }
}

/* ================================================= свой диалог подтверждения */
/* Нативный confirm() блокирует отрисовку всей страницы и на двойном клике
   появляется дважды. Свой — не блокирует и открыт один раз. */
let CONFIRM_BUSY = false;
function askConfirm(text, okLabel){
  return new Promise(resolve=>{
    if(CONFIRM_BUSY){ resolve(false); return; }
    CONFIRM_BUSY = true;
    const ov = $("confirmOverlay");
    $("confirmText").textContent = text;
    $("confirmOk").textContent = okLabel || "Да";
    ov.classList.add("on");
    const done = (v)=>{
      ov.classList.remove("on");
      $("confirmOk").onclick = null;
      $("confirmNo").onclick = null;
      $("confirmX").onclick = null;
      CONFIRM_BUSY = false;
      resolve(v);
    };
    $("confirmOk").onclick = ()=>done(true);
    $("confirmNo").onclick = ()=>done(false);
    $("confirmX").onclick = ()=>done(false);
  });
}

/* ================================================= конфиг */
async function saveCfg(patch){
  /* /api/config отвечает {ok,problems,auto} — это НЕ состояние.
     Раньше ответ присваивался в ST целиком, поэтому после первой же
     загрузки колод (saveCfg({deck})) из ST пропадали voices, reading_off
     и default_voice — и интерфейс начинал показывать "undefined".
     Сохраняем, а затем перечитываем состояние целиком. */
  try{ await api("/api/config", patch); }
  catch(e){ console.warn(e); return; }
  try{ ST = await api("/api/state"); }catch(e){ console.warn(e); }
}
const AV_ENGINES = {
  "gpt-sovits": {label:"Папка GPT-SoVITS", ph:"D:\\DOWNLOAD\\GPT-SoVITS-…",
                 pick:"Папка GPT-SoVITS",
                 title:"GPT-SoVITS",
                 desc:"Голос — файлы обученной модели. Синтез быстрее, голосов можно много.",
                 hint:"Движок с весами: у каждого голоса свои файлы .ckpt и .pth."},
  "indextts":   {label:"Папка IndexTTS 2.5", ph:"D:\\DOWNLOAD\\index-tts",
                 pick:"Папка IndexTTS",
                 title:"IndexTTS 2.5",
                 desc:"Голос — это одна запись-образец. Японские термины читает точнее, но синтез медленнее.",
                 hint:"Голосу нужна только запись-образец: отдельные веса не нужны, модель общая."}
};
function engineNow(){ return (ST && ST.engine) || "gpt-sovits"; }
function pathKey(){ return engineNow() === "indextts" ? "indextts_path" : "gptsovits_path"; }
function applyEngineUI(){
  const kind = engineNow();
  const e = AV_ENGINES[kind] || AV_ENGINES["gpt-sovits"];
  const isIndex = kind === "indextts";
  // у IndexTTS голос — это один референс: параметров сэмплирования нет
  ["v_gptPrompt","v_gptAux","v_gptParams","v_gptParamsHead"].forEach(id=>{
    const el = $(id); if(el) el.style.display = isIndex ? "none" : "";
  });
  ["a_gpt","a_gpt_b","a_sov","a_sov_b","v_noref"].forEach(id=>{
    const el = $(id); if(el) el.style.display = isIndex ? "none" : "";
  });
  $("enginePathLabel").textContent = e.label;
  $("gptpath").placeholder = e.ph;
  $("btnPickGpt").title = e.pick;
  // под карточками — что важно прямо сейчас: сколько голосов готово и где сервер
  const voices = (ST && ST.voices) ? Object.keys(ST.voices) : [];
  const readyN = voices.filter(v => ST.voices[v] && ST.voices[v].ok).length;
  // числа — отдельными узлами, чтобы слова вокруг переводились целиком
  $("engineHint").replaceChildren("Готовых голосов: ", readyN + " ", "из", " " + voices.length,
    ...(voices.length > readyN ? [" ", "(остальным не хватает файлов — вкладка «Голос»)"] : []));
  $("enginePort").textContent = (ST && ST.tts) ? "Движок: запущен" : "Движок: запустится сам при озвучке";
  $("enginePort").title = isIndex ? "127.0.0.1:9881" : "127.0.0.1:9880";
  // крупный выбор движка — на главном экране
  document.querySelectorAll(".eng[data-engine]").forEach(b=>{
    const on = b.dataset.engine === kind;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
    const mk = b.querySelector(".mark");
    if(mk) mk.textContent = on ? "✓ выбран" : "";
  });
  // статус папки движка — в заголовке карточки
  const st = ST || {};
  const el = $("engineState");
  if(el){
    const probs = st.problems || [];
    let html;
    if(!st.path) html = '<span style="color:var(--err)">папка не указана</span>';
    else if(probs.length) html = '<span style="color:var(--err)">папка не подходит</span>';
    else html = '<span style="color:var(--ok)">папка в порядке ✓</span>';
    el.innerHTML = html;
  }
}
/* Переключение движка: выбор в мастере и крупные карточки на главном экране */
async function setEngine(kind){
  if(!kind || kind === engineNow()){
    applyEngineUI();
    return;
  }
  try{
    await api("/api/config", {engine: kind, engine_confirmed: true});
    ST = await api("/api/state");
    applyEngineUI();
    $("gptpath").value = ST.path || "";
    $("pathHint").textContent = "—";
    try{ await loadSetup(); }catch(e){}
    toast(kind === "indextts" ? "Движок: IndexTTS 2.5" : "Движок: GPT-SoVITS", "good");
  }catch(e){ toast(e.message, "bad"); }
}
async function savePath(){
  const p = $("gptpath").value.trim();
  if(!p) return toast("Укажи папку движка","bad");
  const patch = {}; patch[pathKey()] = p;
  const j = await api("/api/config", patch);
  if(j.problems && j.problems.length){
    banner("appBanner","bad","<b>Проблемы:</b> "+esc(j.problems.join(" · ")));
    $("pathHint").innerHTML = '<span style="color:var(--err)">'+esc(j.problems.join(" · "))+"</span>";
    toast("Папка не подходит — не сохранил","bad");
  }else{
    banner("appBanner", null);
    $("pathHint").innerHTML = '<span style="color:var(--ok)">Папка в порядке ✓</span>';
    toast("Папка сохранена","good");
    await loadState();
    try{ await loadSetup(); }catch(e){}
  }
}
$("btnSavePath").onclick = savePath;
/* «Проверить» ничего не меняет: спрашиваем отдельно, без записи в конфиг */
$("btnCheckPath").onclick = async ()=>{
  const p = $("gptpath").value.trim();
  if(!p) return $("pathHint").innerHTML = '<span style="color:var(--err)">Укажи папку движка</span>';
  banner("appBanner", null);
  const patch = {check_path:true}; patch[pathKey()] = p;
  const j = await api("/api/config", patch);
  $("pathHint").innerHTML = (j.problems && j.problems.length)
    ? '<span style="color:var(--err)">'+esc(j.problems.join(" · "))+"</span>"
    : '<span style="color:var(--ok)">Папка в порядке ✓</span>';
};

$("btnDoctor").onclick = async ()=>{
  $("doctor").textContent = "Проверяю…";
  try{
    const d = await api("/api/doctor");
    const bad = [].concat(d.local_problems||[], d.problems||[]);
    const engLabel = d.engine_label || (d.engine === "indextts" ? "IndexTTS 2.5" : "GPT-SoVITS");
    $("doctor").innerHTML = [
      "Программа: <b>"+esc(d.code_dir)+"</b>",
      "Конфиг: <b>"+esc(d.config_file)+"</b>",
      engLabel+": <b>"+esc(d.engine_path || d.gptsovits_path || "—")+"</b>",
      "Медиа Anki (куда падает звук): <b>"+esc(d.anki_media || "не нашли")+"</b>",
      "Anki: <b>"+(d.anki?"подключена":"НЕ подключена")+"</b>",
      "Сервер: <b>"+(d.tts_server?"запущен":"не запущен")+"</b>",
      d.voices ? "Голосов: <b>"+d.voices.length+"</b> ("+esc(d.voices.join(", "))+")" : "",
      bad.length ? '<span style="color:var(--err)">Проблемы: '+esc(bad.join(" · "))+"</span>"
                 : '<span style="color:var(--ok)">Всё в порядке ✓</span>'
    ].filter(Boolean).map(x=>"<div>"+x+"</div>").join("");
  }catch(e){ $("doctor").textContent = "Ошибка: "+e.message; }
};
$("btnQuit").onclick = async ()=>{
  try{ await api("/api/shutdown", {}); }catch(e){}
  document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;font:16px var(--font);color:var(--sub)">AnkiVoice закрыт. Можно закрыть вкладку.</div>';
};

/* ================================================= модалка файлов */
let PICK = null;   // {input, kind, ext, path}
function openPicker(inputId, kind, ext, title){
  const inp = typeof inputId === "string" ? $(inputId) : inputId;
  PICK = {input:inp, kind:kind, ext:ext||"", path:""};
  $("mTitle").textContent = title || (kind === "dir" ? "Выбор папки" : "Выбор файла");
  $("mPick").style.display = kind === "dir" ? "" : "none";
  $("overlay").classList.add("on");
  fsBrowse("");
}
function joinPath(base, name){
  if(!base) return name;
  return base.replace(/[\\/]+$/, "") + "\\" + name;
}
async function fsBrowse(path){
  $("mPath").textContent = path || "Компьютер";
  $("mList").innerHTML = '<div class="empty">Загрузка…</div>';
  try{
    const j = await api("/api/fs?kind="+encodeURIComponent(PICK.kind)+
      "&ext="+encodeURIComponent(PICK.ext)+
      "&path="+encodeURIComponent(path));
    if(j.error){ $("mList").innerHTML = '<div class="empty">'+esc(j.error)+"</div>"; return; }
    PICK.path = j.path || "";
    PICK.parent = j.parent || "";
    let html = "";
    (j.drives||[]).forEach(d=>{
      html += '<div class="pitem dir" data-go="'+esc(d)+'"><span class="ic">▣</span>'+esc(d)+"</div>";
    });
    if(j.path){
      html += '<div class="pitem dir" data-go="'+esc(j.parent||"")+'"><span class="ic">↰</span>… вверх</div>';
    }
    (j.dirs||[]).forEach(d=>{
      const full = joinPath(j.path, d);
      html += '<div class="pitem dir" data-go="'+esc(full)+'"><span class="ic">📁</span>'+esc(d)+"</div>";
    });
    (j.files||[]).forEach(f=>{
      const full = joinPath(j.path, f);
      html += '<div class="pitem" data-file="'+esc(full)+'"><span class="ic">📄</span>'+esc(f)+"</div>";
    });
    $("mList").innerHTML = html || '<div class="empty">Папка пуста</div>';
    document.querySelectorAll("#mList [data-go]").forEach(el=>{
      el.onclick = ()=>fsBrowse(el.dataset.go);
    });
    document.querySelectorAll("#mList [data-file]").forEach(el=>{
      el.onclick = ()=>{
        if(PICK.kind === "dir") return;
        PICK.input.value = el.dataset.file;
        $("overlay").classList.remove("on");
      };
      el.ondblclick = el.onclick;
    });
  }catch(e){
    $("mList").innerHTML = '<div class="empty">'+esc(e.message)+"</div>";
  }
}
$("mUp").onclick = ()=>fsBrowse(PICK && PICK.parent ? PICK.parent : "");
$("mClose").onclick = ()=> $("overlay").classList.remove("on");
$("mPick").onclick = ()=>{
  if(PICK && PICK.kind === "dir" && PICK.path){
    PICK.input.value = PICK.path;
    $("overlay").classList.remove("on");
  }
};
$("overlay").onclick = e=>{ if(e.target === $("overlay")) $("overlay").classList.remove("on"); };
document.addEventListener("keydown", e=>{
  if(e.key === "Escape") $("overlay").classList.remove("on");
});
document.querySelectorAll("[data-pick]").forEach(b=>{
  b.onclick = ()=>openPicker(b.dataset.pick, "file", b.dataset.ext||"", "Выбор файла");
});
$("btnPickGpt").onclick = ()=>openPicker($("gptpath"), "dir", "",
  (AV_ENGINES[engineNow()] || AV_ENGINES["gpt-sovits"]).pick);
document.querySelectorAll(".eng[data-engine]").forEach(b=>{
  b.onclick = ()=>setEngine(b.dataset.engine);
});

/* ================================================= новый голос */
function addVoiceDialog(){ goTab("new"); }
function showNewWay(v, focus){
  document.querySelectorAll("#nvWays .nv-way").forEach(b=>{
    const on = b.dataset.v === v;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on ? "true" : "false");
  });
  const ids = {quick:"nvQuick", weights:"nvWeights", train:"nvTrain"};
  Object.entries(ids).forEach(([k, id])=>{
    const el = $(id), on = k === v;
    if(el.hidden === !on) return;
    el.hidden = !on;
    if(on){ el.classList.remove("nv-in"); void el.offsetWidth; el.classList.add("nv-in"); }
  });
  $("nvEmpty").hidden = true;
  try{ localStorage.setItem("av-new-way", v); }catch(e){}
  if(v === "train") refreshStudio();
  if(focus){
    const first = $(ids[v]).querySelector("input,textarea,button.primary");
    if(first) setTimeout(()=>first.focus({preventScroll:true}), 60);
    $(ids[v]).scrollIntoView({behavior:"smooth", block:"nearest"});
  }
}
document.querySelectorAll("#nvWays .nv-way").forEach(b=>{ b.onclick = ()=>showNewWay(b.dataset.v, true); });
(function(){
  let v = "";
  try{ v = localStorage.getItem("av-new-way") || ""; }catch(e){}
  if(v) showNewWay(v, false);
})();
function scanVoices(){
  toast("Ищу голоса в папке движка — найденные появятся во вкладке «Голос»");
  runOp({kind:"scan"});
}
$("btnScan2").onclick = scanVoices;
$("btnScan3").onclick = scanVoices;
// после добавления: голос выбран, открыт в «Голосе» и сразу звучит
async function voiceAdded(name){
  await loadState();
  goTab("sound");
  selectVoice(name);
  if(!RUNNING) $("btnTest").click();
}

$("q_ref_b").onclick = ()=>openPicker($("q_ref"),"file","audio","Запись голоса на 3–10 секунд");
$("q_ok").onclick = async ()=>{
  $("q_err").innerHTML = "";
  const btn = $("q_ok");
  btn.disabled = true;
  try{
    const r = await api("/api/voice/add", {
      base:true, display:$("q_disp").value || "Мой голос",
      ref:$("q_ref").value, prompt_text:$("q_txt").value, prompt_lang:$("q_lang").value
    });
    toast("Голос создан — слушаем пробу","good");
    $("q_disp").value = ""; $("q_ref").value = ""; $("q_txt").value = "";
    await voiceAdded(r.name);
  }catch(e){
    $("q_err").innerHTML = '<span style="color:var(--err)">'+esc(e.message)+"</span>";
  }finally{ btn.disabled = false; }
};

$("a_gpt_b").onclick  = ()=>openPicker($("a_gpt"),"file","ckpt","GPT-веса (.ckpt)");
$("a_sov_b").onclick  = ()=>openPicker($("a_sov"),"file","pth","SoVITS-веса (.pth)");
$("a_ref_b").onclick  = ()=>openPicker($("a_ref"),"file","audio","Запись-образец голоса");
$("a_ok").onclick = async ()=>{
  $("a_err").innerHTML = "";
  try{
    const r = await api("/api/voice/add", {
      display:$("a_disp").value,
      gpt:$("a_gpt").value, sovits:$("a_sov").value,
      ref:$("a_ref").value, prompt_text:$("a_txt").value,
      prompt_lang:$("a_lang").value
    });
    toast("Голос добавлен","good");
    $("a_disp").value=""; $("a_gpt").value="";
    $("a_sov").value=""; $("a_ref").value=""; $("a_txt").value="";
    await voiceAdded(r.name);
  }catch(e){
    $("a_err").innerHTML = '<span style="color:var(--err)">'+esc(e.message)+"</span>";
  }
};

// студия обучения GPT-SoVITS: запуск, статус, закрытие
let STUDIO_POLL = null;
function renderStudio(st){
  const el = $("studioSt"), btn = $("btnStudio"), stop = $("btnStudioStop");
  const busy = st.phase === "download" || st.phase === "starting";
  btn.disabled = busy;
  stop.hidden = !st.running;
  btn.textContent = st.running ? "Открыть студию ещё раз" : (busy ? "Запускаю…" : "Открыть студию обучения");
  let html = "";
  if(busy) html = '<span class="nv-spin keep-round" aria-hidden="true"></span>' + esc(st.msg || "Запускаю студию…");
  else if(st.running) html = '<span class="dot ok keep-round" aria-hidden="true"></span>Студия работает: <a href="'+esc(st.url)+'" target="_blank" rel="noopener">'+esc(st.url)+"</a>";
  else if(st.phase === "error") html = '<span style="color:var(--err)">Не запустилась: '+esc(st.error)+"</span>";
  el.innerHTML = html;
  el.className = "nv-status" + (html ? " on" : "");
  if(LANG !== "ru") translateDom(el.parentNode);
}
async function refreshStudio(){
  let st;
  try{ st = await api("/api/studio"); }catch(e){ return; }
  STUDIO_LAST = st;
  renderStudio(st);
  clearTimeout(STUDIO_POLL);
  if(st.phase === "download" || st.phase === "starting")
    STUDIO_POLL = setTimeout(refreshStudio, 1500);
}
// студия сама открывает свою страницу в браузере, когда поднимется
let STUDIO_LAST = null;
$("btnStudio").onclick = async ()=>{
  if(STUDIO_LAST && STUDIO_LAST.running){ window.open(STUDIO_LAST.url, "_blank", "noopener"); return; }
  try{
    await api("/api/studio/start", {lang:LANG});
    refreshStudio();
  }catch(e){ toast(e.message, "bad"); }
};
$("btnStudioStop").onclick = async ()=>{
  await api("/api/studio/stop", {});
  toast("Студия обучения закрыта");
  refreshStudio();
};

/* ================================================= мастер настройки */
const WZ_STEPS = [
  {id:"engine", label:"Движок"},
  {id:"anki",   label:"Связь с Anki"},
  {id:"server", label:"Запуск движка"},
  {id:"test",   label:"Тест голоса"},
];

function setupStepOk(st, i){
  if(!st) return false;
  return !!(st[WZ_STEPS[i].id] && st[WZ_STEPS[i].id].ok);
}
function firstSetupStep(st){
  for(let i=0;i<WZ_STEPS.length;i++) if(!setupStepOk(st,i)) return i;
  return 3;
}
async function loadSetup(){
  WZ.setup = await api("/api/setup");
  renderSetupSummary();
  if(WZ.open) renderWizard();
  return WZ.setup;
}
function renderSetupSummary(){
  const s = WZ.setup;
  if(!s){
    $("setupSummary").textContent = "Не удалось прочитать состояние настройки.";
    return;
  }
  const marks = [
    ["движок", s.engine.ok], ["Anki", s.anki.ok], ["запуск движка", s.server.ok],
    ["голоса", s.voices.ok], ["тест", s.test.ok]
  ];
  // тестовая фраза необязательна: без неё озвучка работает
  const opt = !!(s.core && !s.test.ok);
  $("setupSummary").innerHTML = marks.map(x=>{
    const soft = opt && x[0]==="тест";
    const col = x[1] ? "var(--ok)" : (soft ? "var(--sub)" : "var(--err)");
    const mark = x[1] ? "✓" : (soft ? "—" : "✗");
    return '<span style="color:'+col+'"><b>'+mark+"</b> "+esc(x[0])+
      (soft?" (необязательно)":"")+"</span>";
  }).join(" · ");
  // core — движок, Anki и голоса на месте: этого хватает, чтобы работать.
  // complete — мастер пройден до конца (с тестовой фразой).
  $("setupState").textContent = s.core ? "Готово ✓" : "Требует внимания";
  $("setupState").style.color = s.core ? "var(--ok)" : "var(--err)";
  $("btnWizardAgain").style.display = s.done ? "" : "none";
  if(!s.core) $("navBadge").style.display = "";
  else if(!(ST && ST.problems && ST.problems.length)) $("navBadge").style.display = "none";
}
function hydrateWizard(s){
  if(!WZ.path) WZ.path = s.engine.path || s.engine.auto || "";
  const ready = (s.voices.all || []).filter(v => v.ok);
  if(!WZ.voice || !ready.some(v => v.name === WZ.voice)){
    WZ.voice = ready.some(v => v.name === s.test.voice) ? s.test.voice
      : (ready[0] ? ready[0].name : "");
  }
  if(!WZ.text) WZ.text = s.test.text || "既存建築物の改修では、耐火性能と耐震性能の確認が重要です。";
}
function openWizard(step){
  WZ.open = true;
  WZ.testError = "";
  WZ.serverError = "";
  const s = WZ.setup;
  if(s){
    WZ.path = s.engine.path || s.engine.auto || "";
    hydrateWizard(s);
    WZ.step = step == null ? firstSetupStep(s) : Math.max(0, Math.min(3, step));
    renderWizard();
  }else{
    $("wzBody").innerHTML = '<div class="empty">Проверяю настройку…</div>';
    loadSetup().then(()=>{
      if(!WZ.open) return;
      WZ.path = WZ.setup.engine.path || WZ.setup.engine.auto || "";
      hydrateWizard(WZ.setup);
      WZ.step = step == null ? firstSetupStep(WZ.setup) : Math.max(0, Math.min(3, step));
      renderWizard();
    }).catch(e=>{
      $("wzBody").innerHTML = '<div class="wresult bad">Не удалось прочитать настройку: '+
        esc(e.message)+"</div>";
    });
  }
  $("wizardOverlay").classList.add("on");
}
function closeWizard(){
  WZ.open = false;
  $("wizardOverlay").classList.remove("on");
  markEngineConfirmed();
}
/* Движок спросили один раз: дальше его можно менять на главном экране,
   и мастер больше не пристаёт при каждом запуске. */
function markEngineConfirmed(){
  if(ST && ST.cfg && ST.cfg.engine_confirmed) return;
  api("/api/config", {engine_confirmed: true}).then(()=>{
    try{ if(ST && ST.cfg) ST.cfg.engine_confirmed = true; }catch(e){}
  }).catch(()=>{});
}
function renderWizard(){
  const s = WZ.setup;
  if(!s){ return; }
  hydrateWizard(s);
  $("wzSteps").innerHTML = WZ_STEPS.map((x,i) => {
    const ok = setupStepOk(s,i);
    return '<span class="wstep '+(i===WZ.step?"on ":"")+(ok?"ok":"")+'">'+
      '<span class="n">'+(ok?"✓":(i+1))+"</span>"+esc(x.label)+"</span>";
  }).join("");
  const fn = [engineHtml, ankiHtml, serverHtml, testHtml][WZ.step];
  $("wzBody").innerHTML = fn(s);
  $("wzPrev").disabled = WZ.step === 0 || WZ.busy;
  $("wzNext").style.display = WZ.step < 3 ? "" : "none";
  $("wzNext").disabled = WZ.busy;
  $("wzDone").style.display = WZ.step === 3 ? "" : "none";
  $("wzDone").textContent = s.complete ? "Готово" : "Закрыть";
  $("wzDone").disabled = WZ.busy;
  wireWizard();
}
function engineHtml(s){
  const kind = engineNow();
  const e = AV_ENGINES[kind] || AV_ENGINES["gpt-sovits"];
  const eng = s.engine || {};
  const path = WZ.path || eng.path || eng.auto || "";
  const problems = (eng.problems || []).map(p => "<li>"+esc(p)+"</li>").join("");
  const cards = ["gpt-sovits","indextts"].map(k=>{
    const d = AV_ENGINES[k];
    const on = k === kind;
    return '<button class="eng'+(on?" on":"")+'" type="button" data-w="wzEngine" '+
      'data-kind="'+k+'" aria-pressed="'+(on?"true":"false")+'">'+
      '<span class="eng-t">'+esc(d.title)+(on?'<span class="mark">✓ выбран</span>':"")+'</span>'+
      '<span class="eng-d">'+esc(d.desc)+'</span></button>';
  }).join("");
  return '<h3>1. Движок синтеза</h3>'+
    '<p>Кто будет читать текст. Поменять движок можно в любой момент — в блоке '+
    '«Движок синтеза» на вкладке «Озвучка».</p>'+
    '<div class="engines">'+cards+'</div>'+
    '<div class="spacer"></div>'+
    '<div class="wstate '+(eng.ok?"ok":"bad")+'"><span class="dot keep-round"></span>'+
    (eng.ok ? "Папка проверена: <b>"+esc(eng.path)+"</b>"
            : "Папка не найдена или в ней не хватает файлов")+'</div>'+
    (problems ? '<div class="wcard"><b>Что не так:</b><ul>'+problems+'</ul></div>' : "")+
    '<label class="f">'+esc(e.label)+'</label>'+
    '<div class="row"><div class="grow"><input id="wzPath" type="text" value="'+esc(path)+'"></div>'+
    '<button class="btn sm" data-w="wzBrowse">Обзор…</button>'+
    '<button class="btn sm" data-w="wzSavePath">Проверить и сохранить</button></div>'+
    '<div class="wactions">'+
    (eng.auto ? '<button class="btn sm" data-w="wzAuto" title="'+esc(eng.auto)+'">Подставить найденную</button>' : "")+
    (eng.download_url ? '<a class="btn sm ghost" href="'+esc(eng.download_url)+'" target="_blank" rel="noopener">Скачать движок</a>' : "")+
    '</div>'+
    (eng.ok ? "" : '<div class="wcard"><b>Нет движка?</b> '+esc(eng.hint || "")+'</div>');
}
function ankiHtml(s){
  const a = s.anki;
  return '<h3>2. Связь с Anki (дополнение AnkiConnect)</h3>'+
    '<p>Через AnkiConnect программа читает колоды и записывает звук в карточки. '+
    'Без него озвучка не начнётся.</p>'+
    '<div class="wstate '+(a.ok?"ok":"bad")+'"><span class="dot keep-round"></span>'+
    (a.ok ? "AnkiConnect отвечает — Anki запущена." : "AnkiConnect не отвечает.")+'</div>'+
    (a.ok ? "" :
      '<div class="wcard"><b>Что сделать:</b><ul>'+
      '<li>Открой Anki.</li>'+
      '<li><b>Инструменты → Дополнения → Получить дополнения</b>.</li>'+
      '<li>Вставь код <code>'+esc(a.code)+'</code> и нажми «ОК».</li>'+
      '<li>Перезапусти Anki и вернись сюда.</li></ul>'+
      '<div class="hint">Если Anki не установлена — сначала скачай её.</div></div>')+
    '<div class="wactions">'+
    '<a class="btn sm" href="'+esc(a.url)+'" target="_blank" rel="noopener">Открыть AnkiConnect</a>'+
    '<a class="btn sm ghost" href="https://apps.ankiweb.net/" target="_blank" rel="noopener">Скачать Anki</a>'+
    '<button class="btn sm" data-w="wzRefresh">Проверить снова</button></div>';
}
function serverHtml(s){
  const v = s.server;
  const isIndex = engineNow() === "indextts";
  return '<h3>3. Сервер синтеза</h3>'+
    '<p>'+(isIndex
      ? 'Сервис IndexTTS слушает только <code>127.0.0.1:9881</code>. Первый запуск '+
        'грузит веса и CUDA — это может занять 1–2 минуты.'
      : 'Сервер слушает только <code>127.0.0.1:9880</code>. Первый запуск грузит '+
        'веса и CUDA — это может занять 1–2 минуты.')+'</p>'+
    '<div class="wstate '+(v.ok?"ok":"bad")+'"><span class="dot keep-round"></span>'+
    (v.ok ? "Сервер уже запущен и отвечает." : "Сервер пока не запущен.")+'</div>'+
    (WZ.busy ? '<div class="wcard"><b>Запускаю…</b> не закрывай мастер, первый старт небыстрый.</div>' : "")+
    (WZ.serverError ? '<div class="wresult bad">'+esc(WZ.serverError)+'</div>' : "")+
    '<div class="wactions">'+
    (v.ok ? "" : '<button class="btn sm primary" data-w="wzStartServer" '+(WZ.busy?"disabled":"")+'>Запустить сервер</button>')+
    '<button class="btn sm" data-w="wzRefresh" '+(WZ.busy?"disabled":"")+'>Проверить снова</button>'+
    '<a class="btn sm ghost" href="#" data-w="wzLog">Открыть журнал</a></div>'+
    '<div class="wcard"><b>Можно пропустить.</b> Если сервер ещё не поднят, '+
    'тестовая фраза запустит его автоматически. Этот шаг нужен, чтобы '+
    'заранее увидеть ошибки движка.</div>';
}
function testHtml(s){
  const ready = (s.voices.all || []).filter(v => v.ok);
  if(!ready.length){
    return '<h3>4. Тестовая фраза</h3>'+
      '<div class="wstate bad"><span class="dot keep-round"></span>Нет ни одного голоса с полным набором файлов.</div>'+
      '<p>Открой вкладку «Голос»: добавь голос (GPT .ckpt, SoVITS .pth и запись-образец) '+
      'или нажми «Обновить список голосов из папки движка».</p>'+
      '<div class="wactions"><button class="btn sm primary" data-w="wzSound">Открыть вкладку «Голос»</button>'+
      '<button class="btn sm" data-w="wzRefresh">Проверить снова</button></div>';
  }
  hydrateWizard(s);
  const opts = ready.map(v => '<option value="'+esc(v.name)+'"'+
    (v.name===WZ.voice?" selected":"")+'>'+esc(v.display)+"</option>").join("");
  const text = WZ.text || s.test.text || "";
  return '<h3>4. Тестовая фраза</h3>'+
    '<p>Проверим весь путь: голос → сервер → звук. Это последний шаг мастера.</p>'+
    '<label class="f">Голос</label><select id="wzVoice">'+opts+'</select>'+
    '<div class="spacer"></div>'+
    '<label class="f">Фраза</label><textarea id="wzText" rows="3">'+esc(text)+'</textarea>'+
    '<div class="wactions"><button class="btn sm primary" data-w="wzTest" '+
    (WZ.busy?"disabled":"")+'>'+(WZ.busy?"Синтезирую…":"Синтезировать тестовую фразу")+'</button>'+
    '<button class="btn sm" data-w="wzRefresh" '+(WZ.busy?"disabled":"")+'>Проверить снова</button></div>'+
    (s.test.ok ? '<div class="wresult">Тестовый звук готов ✓'+
      (s.test.voice ? ' <span class="hint">голос: '+esc(s.test.display || s.test.voice)+'</span>' : "")+
      '<audio controls preload="none" src="'+esc(s.test.url)+'&t='+encodeURIComponent(AV_TOKEN)+'"></audio>'+
      (!s.done ? '<div class="hint">Это тест от прошлого запуска. Синтезируй фразу заново, чтобы завершить настройку.</div>' : "")+
      '</div>' : "")+
    (WZ.testError ? '<div class="wresult bad">'+esc(WZ.testError)+'</div>' : "")+
    (s.complete ? '<div class="wstate ok" style="margin-top:14px"><span class="dot keep-round"></span>'+
      'Настройка завершена. Можно закрывать мастер.</div>' : "");
}
function wireWizard(){
  document.querySelectorAll("#wzBody [data-w]").forEach(b=>{
    b.onclick = ev=>{
      if(b.dataset.w === "wzSound" || b.dataset.w === "wzLog") ev.preventDefault();
      onWizardAction(b.dataset.w, b);
    };
  });
  const p = $("wzPath");
  if(p) p.oninput = ()=>{ WZ.path = p.value; };
  const t = $("wzText");
  if(t) t.oninput = ()=>{ WZ.text = t.value; };
  const v = $("wzVoice");
  if(v) v.onchange = ()=>{ WZ.voice = v.value; };
}
async function onWizardAction(a, el){
  if(a === "wzBrowse"){
    const e = AV_ENGINES[engineNow()] || AV_ENGINES["gpt-sovits"];
    openPicker("wzPath", "dir", "", e.pick);
    return;
  }
  if(a === "wzEngine"){
    const kind = el && el.dataset.kind;
    if(!kind || kind === engineNow()) return;
    WZ.busy = true; WZ.serverError = ""; WZ.testError = "";
    renderWizard();
    try{
      await api("/api/config", {engine: kind, engine_confirmed: true});
      await loadState();
      WZ.path = "";
      await loadSetup();
      WZ.path = (WZ.setup.engine && WZ.setup.engine.path) || "";
      toast(kind === "indextts" ? "Движок: IndexTTS 2.5" : "Движок: GPT-SoVITS", "good");
    }catch(e){ toast(e.message, "bad"); }
    finally{ WZ.busy = false; if(WZ.open) renderWizard(); }
    return;
  }
  if(a === "wzSound"){ closeWizard(); goTab("sound"); return; }
  if(a === "wzLog"){ closeWizard(); goTab("voice"); return; }
  if(a === "wzRefresh"){ await refreshWizard(); return; }
  if(WZ.busy) return;
  if(a === "wzAuto"){
    const p = WZ.setup.engine.auto || "";
    if(!p) return toast("Автоматически ничего не нашлось","bad");
    WZ.path = p;
    const el = $("wzPath"); if(el) el.value = p;
    await saveWizardPath(p);
  }else if(a === "wzSavePath"){
    const el = $("wzPath");
    await saveWizardPath(el ? el.value : WZ.path);
  }else if(a === "wzStartServer"){
    await startWizardServer();
  }else if(a === "wzTest"){
    await runWizardTest();
  }
}
async function refreshWizard(){
  if(WZ.busy) return;
  WZ.busy = true; renderWizard();
  try{ await loadSetup(); }
  catch(e){ toast(e.message,"bad"); }
  finally{ WZ.busy = false; if(WZ.open) renderWizard(); }
}
async function saveWizardPath(path){
  const p = String(path || "").trim();
  if(!p) return toast("Укажи папку движка","bad");
  const key = pathKey();
  WZ.path = p; WZ.busy = true; WZ.serverError = ""; WZ.testError = "";
  renderWizard();
  try{
    const j = await api("/api/config", {[key]: p});
    if(j.problems && j.problems.length){
      toast("Папка не подходит","bad");
      await loadSetup();
    }else{
      toast("Папка сохранена","good");
      await loadState();
      await loadSetup();
    }
  }catch(e){ toast(e.message,"bad"); }
  finally{ WZ.busy = false; if(WZ.open) renderWizard(); }
}
function startWizardServer(){
  return new Promise(async resolve=>{
    WZ.busy = true; WZ.serverError = ""; renderWizard();
    let runId = null;
    try{
      const j = await api("/api/setup/server", {});
      if(j.already){
        await loadSetup();
        WZ.busy = false; renderWizard(); toast("Сервер уже работает","good"); resolve(); return;
      }
      runId = j.run && j.run.id; WZ.runId = runId;
      const started = Date.now();
      WZ.timer = setInterval(async ()=>{
        try{
          const st = await api("/api/state");
          const r = st.run;
          if(r && r.id === runId && !r.running){
            clearInterval(WZ.timer); WZ.timer = null; WZ.busy = false;
            await loadSetup();
            if(r.code !== 0) WZ.serverError =
              "Сервер не поднялся (код "+r.code+"). Открой журнал — там причина.";
            else toast("Сервер готов","good");
            if(WZ.open) renderWizard(); resolve();
          }else if(Date.now() - started > 10*60*1000){
            clearInterval(WZ.timer); WZ.timer = null; WZ.busy = false;
            WZ.serverError = "Сервер не поднялся за 10 минут. Посмотри журнал.";
            if(WZ.open) renderWizard(); resolve();
          }
        }catch(e){ /* сеть моргнула — следующий тик */ }
      }, 1500);
    }catch(e){
      WZ.busy = false; WZ.serverError = e.message; renderWizard(); resolve();
    }
  });
}
function runWizardTest(){
  return new Promise(async resolve=>{
    const voice = ($("wzVoice") && $("wzVoice").value) || WZ.voice || "";
    const text = ($("wzText") && $("wzText").value) || WZ.text || "";
    if(!voice){ toast("Сначала выбери голос","bad"); resolve(); return; }
    if(!text.trim()){ toast("Напиши тестовую фразу","bad"); resolve(); return; }
    WZ.voice = voice; WZ.text = text;
    WZ.busy = true; WZ.testError = ""; renderWizard();
    try{
      const j = await api("/api/run", {kind:"test", voice:voice, text:text});
      const runId = j.run && j.run.id; WZ.runId = runId;
      const started = Date.now();
      WZ.timer = setInterval(async ()=>{
        try{
          const st = await api("/api/state");
          const r = st.run;
          if(r && r.id === runId && !r.running){
            clearInterval(WZ.timer); WZ.timer = null; WZ.busy = false;
            if(r.code === 0){
              try{ await api("/api/setup/done", {voice:voice}); }
              catch(e){ WZ.testError = "Звук готов, но отметка мастера не сохранилась: "+e.message; }
              await loadSetup();
              if(!WZ.testError) toast("Тест готов","good");
            }else{
              WZ.testError = "Синтез завершился с ошибкой (код "+r.code+"). "+
                "Открой журнал на вкладке «Озвучка» — там подробности.";
            }
            if(WZ.open) renderWizard(); resolve();
          }else if(Date.now() - started > 5*60*1000){
            clearInterval(WZ.timer); WZ.timer = null; WZ.busy = false;
            WZ.testError = "Тест не закончился за 5 минут. Посмотри журнал.";
            if(WZ.open) renderWizard(); resolve();
          }
        }catch(e){ /* сеть моргнула — следующий тик */ }
      }, 1200);
    }catch(e){
      WZ.busy = false; WZ.testError = e.message; renderWizard(); resolve();
    }
  });
}

/* ================================================= обновления */
function fmtMb(n){
  if(!n) return "—";
  return (n / 1048576).toFixed(n >= 10*1048576 ? 0 : 1) + " МБ";
}
async function checkUpdates(){
  const box = $("updateBox");
  $("btnUpdate").disabled = true;
  box.innerHTML = "Проверяю GitHub…";
  try{
    const j = await api("/api/update/check?force=1");
    renderUpdate(j);
  }catch(e){
    box.innerHTML = '<div class="wresult bad">Не удалось проверить обновления: '+esc(e.message)+
      '<div class="wactions"><a class="btn sm ghost" href="https://github.com/Daii1414/AnkiVoice/releases" '+
      'target="_blank" rel="noopener">Открыть релизы</a></div></div>';
  }finally{ $("btnUpdate").disabled = false; }
}
/* Changelog с GitHub приходит в Markdown — показываем по-человечески:
   без «##», «**» и «`». */
function mdLite(s){
  return String(s || "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/`([^`]+?)`/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/^\s*>\s?/gm, "");
}
function renderUpdate(j){
  const a = j.asset || {};
  let h = '<div>Установлено <b>v'+esc(j.current)+'</b> · последний релиз <b>'+
    esc(j.tag || "—")+'</b></div>';
  if(j.available){
    h += '<div style="margin-top:8px;color:var(--ok)"><b>Доступно обновление '+
      esc(j.tag)+'</b></div>';
    if(j.body) h += '<div class="update-pre">'+esc(mdLite(j.body))+'</div>';
    if(a.name && a.sha256){
      h += '<div class="wactions"><button class="btn sm primary" data-up="dl">Скачать установщик'+
        (a.size ? " ("+fmtMb(a.size)+")" : "")+'</button>'+
        '<a class="btn sm ghost" href="'+esc(a.url)+'" target="_blank" rel="noopener">Скачать вручную</a></div>'+
        '<div class="hint">SHA256 будет проверен после скачивания.</div>';
    }else{
      h += '<div class="wresult bad">В релизе нет установщика или SHA256. '+
        'Скачай вручную со страницы релиза.</div>'+
        '<div class="wactions"><a class="btn sm" href="'+esc(j.url)+'" target="_blank" rel="noopener">Страница релиза</a></div>';
    }
  }else{
    h += '<div style="margin-top:8px;color:var(--ok)">Новых версий нет.</div>';
    if(j.body) h += '<details style="margin-top:10px"><summary>Что нового в '+
      esc(j.tag || "последнем релизе")+'</summary><div class="update-pre">'+esc(mdLite(j.body))+'</div></details>';
  }
  $("updateBox").innerHTML = h;
  const dl = $("updateBox").querySelector('[data-up="dl"]');
  if(dl) dl.onclick = downloadUpdate;
}
async function downloadUpdate(){
  if(UPD.timer) return;
  $("updateBox").innerHTML = '<div>Начинаю скачивание…</div>';
  try{
    await api("/api/update/download", {});
    pollUpdate();
  }catch(e){
    $("updateBox").innerHTML = '<div class="wresult bad">'+esc(e.message)+'</div>';
  }
}
function pollUpdate(){
  if(UPD.timer) clearInterval(UPD.timer);
  const tick = async ()=>{
    try{
      const s = await api("/api/update/status");
      renderUpdateProgress(s);
      if(s.phase === "done" || s.phase === "error"){
        clearInterval(UPD.timer); UPD.timer = null;
      }
    }catch(e){ /* следующий тик */ }
  };
  UPD.timer = setInterval(tick, 900);
  tick();
}
function renderUpdateProgress(s){
  const total = s.total || 0, got = s.received || 0;
  const pct = s.percent || (total ? Math.min(100, Math.round(got*100/total)) : 0);
  let h = "";
  if(s.phase === "checking"){
    h = '<div>Проверяю релиз на GitHub…</div>';
  }else if(s.phase === "downloading" || s.phase === "verifying"){
    h = '<div>Скачиваю установщик…</div>'+
      '<div class="update-bar"><i style="width:'+pct+'%"></i></div>'+
      '<div class="update-meta">'+fmtMb(got)+' из '+fmtMb(total)+' · '+pct+'%</div>';
    if(s.phase === "verifying") h += '<div class="hint">Проверяю SHA256…</div>';
  }else if(s.phase === "done"){
    h = '<div class="wstate ok"><span class="dot keep-round"></span>Скачано, SHA256 совпал ✓</div>'+
      '<div class="hint">'+esc(s.path || "")+'</div>'+
      '<div class="wactions"><button class="btn sm primary" data-up="run">Запустить установщик</button>'+
      '<a class="btn sm ghost" href="https://github.com/Daii1414/AnkiVoice/releases" '+
      'target="_blank" rel="noopener">Страница релиза</a></div>';
  }else if(s.phase === "error"){
    h = '<div class="wresult bad">Скачивание не удалось: '+esc(s.error || "неизвестная ошибка")+'</div>'+
      '<div class="wactions"><button class="btn sm" data-up="retry">Попробовать снова</button></div>';
  }else{
    h = '<div class="hint">Скачивание не запущено.</div>';
  }
  $("updateBox").innerHTML = h;
  const run = $("updateBox").querySelector('[data-up="run"]');
  if(run) run.onclick = runUpdate;
  const retry = $("updateBox").querySelector('[data-up="retry"]');
  if(retry) retry.onclick = downloadUpdate;
}
async function runUpdate(){
  try{
    await api("/api/update/run", {});
    toast("Установщик открыт. Следуй его подсказкам.","good");
  }catch(e){ toast(e.message,"bad"); }
}

$("wzClose").onclick = closeWizard;
$("wzSkip").onclick = ()=>{ markEngineConfirmed(); closeWizard(); };
$("wzPrev").onclick = ()=>{
  if(WZ.step > 0){ WZ.step--; WZ.testError = ""; WZ.serverError = ""; renderWizard(); }
};
$("wzNext").onclick = async ()=>{
  // «Далее» на шаге движка сам проверяет и сохраняет новую папку
  if(WZ.step === 0 && $("wzPath")){
    const p = $("wzPath").value.trim();
    const cur = (WZ.setup && WZ.setup.engine && WZ.setup.engine.path) || "";
    if(p && p !== cur){ await saveWizardPath(p); return; }
  }
  if(WZ.step < 3){ WZ.step++; WZ.testError = ""; WZ.serverError = ""; renderWizard(); }
};
$("wzDone").onclick = ()=>{
  const ok = WZ.setup && WZ.setup.complete;
  closeWizard();
  toast(ok ? "Настройка завершена" : "Мастер можно открыть снова", ok ? "good" : "");
};
$("wizardOverlay").onclick = e=>{ if(e.target === $("wizardOverlay")) closeWizard(); };
document.addEventListener("keydown", e=>{
  if(e.key === "Escape" && WZ.open) closeWizard();
});
$("btnWizard").onclick = ()=>openWizard(0);
$("btnWizardAgain").onclick = async ()=>{
  if(!await askConfirm("Сбросить отметку мастера? Настройки, голоса и файлы останутся.", "Сбросить")) return;
  try{
    await api("/api/setup/reset", {});
    await loadSetup();
    openWizard(0);
  }catch(e){ toast(e.message,"bad"); }
};
$("btnUpdate").onclick = checkUpdates;

/* ================================================= готовность и сводка */
// Плашка вверху главного экрана: четыре условия работы (движок, Anki,
// голос, колода) и ОДНО следующее действие с кнопкой — чтобы было видно,
// куда нажать, без чтения всех настроек подряд.
let ENGINE_BOX_AUTO = false;      // карточку движка раскрываем сами один раз
let HEAR = null;                  // голос, чью пробную фразу ждём проиграть
function readyItem(id, state, text){
  const el = $(id);
  if(!el) return;
  const was = el.classList.contains("ok");
  el.classList.remove("ok", "bad", "warn");
  if(state) el.classList.add(state);
  if(state === "ok" && !was && el.dataset.seen){
    el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop");
  }
  el.dataset.seen = "1";
  el.querySelector(".rd-s").textContent = text;
}
function selectedVoice(){
  const v = $("voice").value;
  return voiceEntries().find(x => x.name === v);
}
function openEngineBox(){
  const b = $("engineBox");
  b.open = true;
  b.scrollIntoView({behavior:"smooth", block:"start"});
}
// как назвать выбранный голос в плашке и сводке (в ансамбле — составом)
function voiceLabel(sv){
  if(ENS_ON){
    const names = ensPicked().map(n=>{ const v = (ST.voices || {})[n]; return (v && v.display) || n; });
    return "ансамбль: " + (names.join(", ") || "голоса не отмечены");
  }
  return sv ? (sv.display || sv.name) : "";
}
function updateReady(){
  if(!ST || !$("readyCard")) return;
  const isIndex = engineNow() === "indextts";
  const engOk = !!ST.path && !(ST.problems || []).length;
  readyItem("rdEngine", engOk ? "ok" : "bad",
    engOk ? (isIndex ? "IndexTTS 2.5" : "GPT-SoVITS")
          : (ST.path ? "папка не подходит" : "не указан"));
  readyItem("rdAnki", ST.anki ? "ok" : "bad", ST.anki ? "подключена" : "не отвечает");
  const readyN = voiceEntries().filter(v => v.ok).length;
  const sv = selectedVoice();
  readyItem("rdVoice", sv && sv.ok ? "ok" : (readyN ? "warn" : "bad"),
    sv ? (voiceLabel(sv) + (sv.ok ? "" : " — нет файлов")) : "не выбран");
  const d = $("deck").value, n = deckCount(d);
  readyItem("rdDeck", d && n !== 0 ? "ok" : (ST.anki ? "warn" : ""),
    d ? (d + " (" + (n < 0 ? "?" : n) + ")") : "не выбрана");

  // что сделать сейчас: первая нерешённая проблема
  let kind = "ok", text = "", btn = "", act = null;
  if(!engOk){
    kind = "bad"; btn = "Настроить движок"; act = openEngineBox;
    text = "Не настроен движок синтеза: укажи папку GPT-SoVITS (в ней лежит api_v2.py).";
  }else if(!ST.anki){
    kind = "bad"; btn = "Проверить снова";
    act = async ()=>{ await loadState(); loadDecks($("deck").value); };
    text = "Anki не отвечает: открой Anki с дополнением AnkiConnect (код 2055492159).";
  }else if(!readyN){
    kind = "bad"; btn = "Открыть «Голос»"; act = ()=>goTab("sound");
    text = "Нет ни одного готового голоса: голосу нужны веса и запись-образец.";
  }else if(!sv || !sv.ok){
    kind = "bad"; btn = "Открыть «Голос»"; act = ()=>goTab("sound");
    text = "У выбранного голоса не хватает файлов — выбери голос без пометки ✗ в шаге 2.";
  }else if(ENS_ON && ensPicked().length < 2){
    kind = "bad";
    text = "В ансамбле отмечен только один голос — отметь в шаге 2 ещё хотя бы один.";
  }else if(!d){
    kind = "bad";
    text = "Выбери колоду в шаге 1.";
  }else if(n === 0){
    kind = "bad";
    text = "В этой колоде нет карточек — выбери другую (число карточек — в скобках).";
  }else{
    text = "Всё готово: проверь шаги ниже и нажми «Начать озвучку». Первый запуск грузит модель 1–2 минуты.";
  }
  const box = $("readyNext");
  box.className = "ready-next " + kind;
  box.innerHTML = '<span class="rn-t"></span>' +
    (btn ? '<button class="btn sm primary" id="rnBtn" type="button"></button>' : "");
  box.querySelector(".rn-t").textContent = text;
  if(btn){ $("rnBtn").textContent = btn; $("rnBtn").onclick = act; }
  if(!engOk && !ENGINE_BOX_AUTO){ ENGINE_BOX_AUTO = true; $("engineBox").open = true; }
  const steps = document.querySelectorAll("#p-voice .step");
  const done = [!!d && n !== 0, !!(sv && sv.ok)];
  done.push(done[0] && done[1]);
  steps.forEach((st, i)=>{
    const num = st.querySelector(".step-n");
    if(!num.dataset.n) num.dataset.n = num.textContent;
    const was = st.classList.contains("done");
    st.classList.toggle("done", !!done[i]);
    num.textContent = num.dataset.n;
    if(done[i] && !was){ num.classList.remove("flip"); void num.offsetWidth; num.classList.add("flip"); }
  });
  updateGoSummary();
  if(LANG !== "ru") translateDom($("readyCard"));
}
// «Что будет озвучено» над главной кнопкой: собирается из кусков, чтобы
// постоянные слова переводились, а данные (колода, голос) оставались как есть
// сколько карточек колоды ещё без звука (спрашиваем сервер, кэш по ключу)
let PENDING = {key:"", n:null, total:null, busy:false};
function pendingKey(){
  const m = mode();
  const sa = (m === "expression") ? "" : fieldVal("sent_aud", "sentence_audio");
  const wa = (m === "sentence") ? "" : fieldVal("word_aud", "word_audio");
  return JSON.stringify([$("deck").value, sa, wa]);
}
async function refreshPending(force){
  const key = pendingKey();
  const [deck, sa, wa] = JSON.parse(key);
  // поля колоды ещё не загружены — без них число будет ложным, ждём
  if(!deck || !(sa || wa) || !(ST && ST.anki)) return;
  if(!force && (PENDING.key === key || PENDING.busy)) return;
  PENDING.busy = true;
  try{
    const j = await api("/api/pending?deck=" + encodeURIComponent(deck) +
                        "&sa=" + encodeURIComponent(sa || "") + "&wa=" + encodeURIComponent(wa || ""));
    PENDING = {key, n: j.pending, total: j.total, busy:false};
  }catch(e){ PENDING = {key, n:null, total:null, busy:false}; }
  updateGoSummary();
}
function updateGoSummary(){
  const el = $("goSummary");
  if(!el) return;
  if(PENDING.key !== pendingKey()) setTimeout(()=>refreshPending(false), 0);
  const d = $("deck").value, sv = selectedVoice();
  const parts = [];
  if(!d || !sv){
    parts.push(["Выбери колоду и голос — здесь будет видно, что именно озвучится.", false]);
  }else{
    const lim = parseInt($("limit").value, 10);
    const hasLim = Number.isFinite(lim) && lim > 0;
    const n = deckCount(d);
    const modeBtn = document.querySelector("#segMode .on");
    const known = PENDING.key === pendingKey() && PENDING.n !== null;
    const redo = redoMode();
    if(known && redo === "skip"){
      // реальное число: сколько без звука и сколько из них озвучится
      const k = hasLim ? Math.min(lim, PENDING.n) : PENDING.n;
      parts.push(["Без звука:", false], [" " + PENDING.n + " ", true], ["из", false],
                 [" " + PENDING.total + ". ", false], ["Будет озвучено:", false],
                 [" " + k + " ", true], ["карточек", false]);
    }else if(known && redo === "force"){
      const k = hasLim ? Math.min(lim, PENDING.total) : PENDING.total;
      parts.push(["Будет переозвучено:", false], [" " + k + " ", true], ["карточек", false]);
    }else{
      parts.push(["Будет озвучено:", false], [" ", false]);
      if(hasLim)
        parts.push(["до", false], [" " + lim + " ", true], ["карточек", false]);
      else
        parts.push(["вся колода", true], [n > 0 ? " (" + n + ")" : "", false]);
    }
    parts.push([" · ", false], ["«" + d + "»", true], [" · ", false],
               [voiceLabel(sv), true], [" · ", false],
               [modeBtn ? modeBtn.textContent : "", true], [". ", false]);
    // в колоде нечего озвучивать: главная кнопка не должна вести в тупик
    const nothing = known && redo === "skip" && PENDING.n === 0;
    const bs = $("btnStart");
    if(bs && !RUNNING){
      bs.disabled = nothing;
      bs.classList.toggle("all-done", nothing);
      bs.querySelector("span").textContent = nothing ? "Все карточки уже озвучены" : "Начать озвучку";
      if(LANG !== "ru") translateDom(bs);
    }
    const rn = $("readyNext");
    if(nothing && rn && rn.classList.contains("ok")){
      rn.querySelector(".rn-t").textContent =
        "Все карточки этой колоды уже озвучены. Чтобы переозвучить — «Дополнительные настройки» → «Переозвучить все», или выбери другую колоду.";
      if(LANG !== "ru") translateDom(rn);
    }
    if($("force").checked) parts.push(["Звук будет перезаписан и у уже озвученных.", false]);
    else if($("changed").checked) parts.push(["Только карточки, изменённые с прошлого раза.", false]);
    else parts.push(["Уже озвученные карточки пропускаются.", false]);
  }
  el.innerHTML = "";
  parts.forEach(([t, bold])=>{
    if(!t) return;
    const s = document.createElement(bold ? "b" : "span");
    s.textContent = t;
    el.appendChild(s);
  });
  if(LANG !== "ru") translateDom(el);
}
["force", "changed"].forEach(id => $(id).addEventListener("change", updateGoSummary));
$("limit").addEventListener("input", updateGoSummary);
document.querySelectorAll("#segMode button").forEach(b =>
  b.addEventListener("click", updateGoSummary));
$("voice").addEventListener("change", updateReady);
document.querySelectorAll(".ready-it").forEach(b=>{
  b.onclick = ()=>{
    const go = b.dataset.go;
    if(go === "engine") openEngineBox();
    else if(go === "anki") loadState().then(()=>loadDecks($("deck").value));
    else if(go === "voice") goTab("sound");
    else if(go === "deck") $("deck").focus();
  };
});
// «Послушать»: пробная фраза выбранным голосом, по готовности — сразу звук
$("btnHear").onclick = async ()=>{
  const v = $("voice").value;
  if(!v) return toast("Сначала выбери голос", "bad");
  const sv = selectedVoice();
  if(sv && !sv.ok) return toast("У голоса не хватает файлов — открой вкладку «Голос»", "bad");
  const ent = (ST && ST.voices && ST.voices[v]) || {};
  const ok = await runOp({kind:"test", voice:v,
    text:"今日はとても良い天気ですね。一緒に散歩に行きましょう。",
    speed: ent.speed || 1.0, seed: ent.seed || 42});
  if(ok){
    HEAR = v;
    toast("Готовлю пробную фразу… В первый раз движок загружается 1–2 минуты.");
  }
};
function playHeard(s){
  const v = HEAR;
  HEAR = null;
  if(!v || !s || s.code !== 0 || !/Тест синтеза/.test(s.title || "")) return;
  const a = new Audio("/api/audio?voice=" + encodeURIComponent(v) +
                      "&t=" + encodeURIComponent(AV_TOKEN) + "&_=" + Date.now());
  a.play().catch(()=>toast("Звук готов, но браузер не дал его проиграть — нажми ещё раз"));
}

/* ================================================= оформление (Fragile) */
// Тип дизайна, плотность, тема, акцент — как в Fragile Notes. Хранится в
// config.json (appearance), сервер подставляет его в <head> до отрисовки.
const AP = Object.assign({colorScheme:"system", builtinTheme:"", builtinScheme:"",
  accentColor:"", designType:"sharp", density:"regular", monoLabels:true,
  reduceTransparency:false}, window.AV_APPEARANCE || {});
const AP_MEDIA = matchMedia("(prefers-color-scheme: light)");
function apTheme(){ return AV_THEMES.find(t => t.id === AP.builtinTheme); }
function applyAppearance(){
  const d = document.documentElement.dataset, t = apTheme();
  if(!t){ AP.builtinTheme = ""; AP.builtinScheme = ""; }
  d.theme = t ? t.scheme : (AP.colorScheme === "system" ? (AP_MEDIA.matches ? "light" : "dark")
                                                         : AP.colorScheme);
  if(t) d.builtinTheme = t.id; else delete d.builtinTheme;
  d.design = AP.designType;
  d.density = AP.density;
  d.monoLabels = AP.monoLabels ? "on" : "off";
  d.reduceTransparency = AP.reduceTransparency ? "on" : "off";
  avAccent(AP.accentColor || "");
  renderAppearance();
}
function saveAppearance(){
  withReveal(applyAppearance);
  saveCfg({appearance: AP});
}
function renderAppearance(){
  if(!$("apDesign")) return;
  document.querySelectorAll("#apDesign .dtype").forEach(b=>{
    const on = b.dataset.v === AP.designType;
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", on ? "true" : "false");
  });
  document.querySelectorAll("#apDensity button").forEach(b=>
    b.classList.toggle("on", b.dataset.v === AP.density));
  $("apMono").checked = !!AP.monoLabels;
  $("apOpaque").checked = !!AP.reduceTransparency;
  $("apMonoRow").style.display = AP.designType === "sharp" ? "" : "none";
  $("apOpaqueRow").style.display = AP.designType === "glass" ? "" : "none";
  const cur = AP.builtinTheme || ("std:" + AP.colorScheme);
  document.querySelectorAll("#apThemes .tcard").forEach(c=>{
    const on = c.dataset.id === cur;
    c.classList.toggle("on", on);
    c.setAttribute("aria-checked", on ? "true" : "false");
  });
  const t = apTheme();
  const desc = $("apThemeDesc");
  // описание темы и пояснение — отдельными узлами: каждый переводится целиком
  desc.replaceChildren(...(t
    ? [themeDesc(t), document.createTextNode(" — "),
       document.createTextNode("схема задаётся темой; смена схемы вернёт стандартную тему.")]
    : [document.createTextNode("Стандартная тема: тёмная, светлая или как в системе.")]));
  // поле цвета показывает текущий акцент (свой или темы)
  const acc = getComputedStyle(document.documentElement)
    .getPropertyValue("--interactive-accent").trim();
  $("apAccent").value = AP.accentColor || toHex(acc) || "#3db6f2";
  $("apAccentReset").style.display = AP.accentColor ? "" : "none";
  if(LANG !== "ru") translateDom($("appearanceCard"));
}
// описание встроенной темы на языке интерфейса (у тем свой ru/en)
function themeDesc(t){
  const d = t.desc || {};
  if(LANG === "ru") return d.ru || "";
  if(LANG === "en") return d.en || d.ru || "";
  return (I18N && I18N[d.ru]) || d.en || d.ru || "";
}
function toHex(css){
  // вычисленный цвет («rgb(…)» или «hsl(…)») -> #rrggbb через canvas
  try{
    const c = document.createElement("canvas").getContext("2d");
    c.fillStyle = css;
    const v = c.fillStyle;
    return /^#[0-9a-f]{6}$/i.test(v) ? v : "";
  }catch(e){ return ""; }
}
function buildThemeGallery(){
  const box = $("apThemes");
  if(!box) return;
  const std = [
    {id:"std:dark", name:"Тёмная", sub:"Стандартная тема", c:[AV_BASE.dark.bg, AV_BASE.dark.side, "#3db6f2", AV_BASE.dark.text]},
    {id:"std:light", name:"Светлая", sub:"Стандартная тема", c:[AV_BASE.light.bg, AV_BASE.light.side, "#3db6f2", AV_BASE.light.text]},
    {id:"std:system", name:"Системная", sub:"Стандартная тема", c:[AV_BASE.dark.bg, AV_BASE.light.bg, "#3db6f2", AV_BASE.dark.text]},
  ];
  const all = std.concat(AV_THEMES.map(t => ({id:t.id, name:t.name + " " + t.kanji,
    sub:themeDesc(t),
    c:[t.bg, t.side, t.accent || t.textAccent || t.text, t.text]})));
  box.innerHTML = "";
  all.forEach(t=>{
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tcard";
    b.dataset.id = t.id;
    b.setAttribute("role", "radio");
    const bar = document.createElement("span");
    bar.className = "tc-bar";
    t.c.forEach(col=>{ const i = document.createElement("i"); i.style.background = col; bar.appendChild(i); });
    const nm = document.createElement("b"); nm.textContent = t.name;
    const sb = document.createElement("small"); sb.textContent = t.sub;
    b.append(bar, nm, sb);
    b.onclick = ()=>{
      if(t.id.startsWith("std:")){
        AP.builtinTheme = ""; AP.builtinScheme = ""; AP.colorScheme = t.id.slice(4);
      }else{
        const th = AV_THEMES.find(x => x.id === t.id);
        AP.builtinTheme = th.id; AP.builtinScheme = th.scheme;
      }
      saveAppearance();
    };
    box.appendChild(b);
  });
}
document.querySelectorAll("#apDesign .dtype").forEach(b=>{
  b.onclick = ()=>{ AP.designType = b.dataset.v; saveAppearance(); };
});
document.querySelectorAll("#apDensity button").forEach(b=>{
  b.onclick = ()=>{ AP.density = b.dataset.v; saveAppearance(); };
});
$("apMono").onchange = ()=>{ AP.monoLabels = $("apMono").checked; saveAppearance(); };
$("apOpaque").onchange = ()=>{ AP.reduceTransparency = $("apOpaque").checked; saveAppearance(); };
$("apAccent").oninput = ()=>{ AP.accentColor = $("apAccent").value; applyAppearance(); };
$("apAccent").onchange = ()=>{ AP.accentColor = $("apAccent").value; saveAppearance(); };
$("apAccentReset").onclick = ()=>{ AP.accentColor = ""; saveAppearance(); };
AP_MEDIA.addEventListener("change", ()=>{ if(!AP.builtinTheme && AP.colorScheme === "system") applyAppearance(); });
$("btnTheme").onclick = ()=>{
  goTab("app");
  $("appearanceCard").open = true;
  setTimeout(()=>$("appearanceCard").scrollIntoView({behavior:"smooth", block:"start"}), 60);
};
buildThemeGallery();
applyAppearance();

/* ================================================= подсказки */
// Одна подсказка за раз и всегда внутри окна (правило Fragile). Системный
// title прячем, пока показана своя: иначе их всплывает две.
(function(){
  let tip = null, cur = null, timer = null;
  function hide(){
    clearTimeout(timer);
    if(tip){ tip.remove(); tip = null; }
    cur = null;
  }
  function show(el){
    const raw = el.dataset.tip;
    if(!raw) return;
    const text = (LANG !== "ru" && I18N && I18N[raw]) || raw;
    tip = document.createElement("div");
    tip.className = "f-tooltip av-tip";
    tip.setAttribute("role", "tooltip");
    tip.textContent = text;
    document.body.appendChild(tip);
    const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
    let x = r.left + r.width / 2 - t.width / 2, y = r.bottom + 8;
    if(y + t.height > innerHeight - 6) y = r.top - t.height - 8;
    x = Math.max(6, Math.min(x, innerWidth - t.width - 6));
    y = Math.max(6, y);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function arm(el){
    if(el === cur) return;
    hide();
    if(el.title){ el.dataset.tip = el.title; el.removeAttribute("title"); }
    if(!el.dataset.tip) return;
    cur = el;
    timer = setTimeout(()=>{ if(cur === el) show(el); }, 350);
  }
  document.addEventListener("mouseover", e=>{
    const el = e.target.closest && e.target.closest("[title],[data-tip]");
    if(el) arm(el); else if(cur) hide();
  });
  document.addEventListener("focusin", e=>{
    const el = e.target.closest && e.target.closest("[title],[data-tip]");
    if(el && e.target.matches(":focus-visible")) arm(el);
  });
  ["mousedown", "keydown", "focusout"].forEach(ev=>
    document.addEventListener(ev, hide, true));
  // прокрутка самой страницы уводит элемент из-под подсказки; прокрутка
  // журнала (он листается сам, пока идёт озвучка) подсказку не трогает
  addEventListener("scroll", hide, {passive:true});
})();

/* ================================================= движение */
// Линза (как в Fragile Notes, lib/motion.ts): одна фигура выделения
// переезжает к активному пункту. Пересчёт только по изменению класса или
// размера — без таймеров и без бесконечных анимаций.
function attachLens(box){
  if(!box || box.__lens) return;
  const lens = document.createElement("i");
  lens.className = "lens";
  lens.setAttribute("aria-hidden", "true");
  box.prepend(lens);
  box.classList.add("has-lens");
  box.__lens = lens;
  let last = null;
  function place(animate){
    const on = box.querySelector(":scope > .on");
    if(!on || !on.offsetWidth){ lens.style.opacity = "0"; last = null; return; }
    lens.style.opacity = "1";
    if(!animate || !last){
      lens.style.transition = "none";
    }
    lens.style.transform = "translate(" + on.offsetLeft + "px," + on.offsetTop + "px)";
    lens.style.width = on.offsetWidth + "px";
    lens.style.height = on.offsetHeight + "px";
    if(!animate || !last){
      void lens.offsetWidth;
      lens.style.transition = "";
    }else if(last !== on){
      lens.classList.remove("moving");
      void lens.offsetWidth;
      lens.classList.add("moving");
    }
    last = on;
  }
  new MutationObserver(muts=>{
    if(muts.some(m => m.target !== lens)) place(true);
  }).observe(box, {attributes:true, attributeFilter:["class"], subtree:true});
  new ResizeObserver(()=>place(false)).observe(box);
  place(false);
}
document.querySelectorAll(".sidebar, #segMode, #apDensity").forEach(attachLens);

// появление раздела: карточкам — порядковый номер для задержки
// (считаем только сами карточки: заголовок и подпись появляются сразу)
document.querySelectorAll(".panel").forEach(p=>{
  [...p.children].filter(c => c.matches(".card,details.more,.banner"))
    .forEach((c, i)=>c.style.setProperty("--i", Math.min(i, 8)));
});

// стекло: блик следует за курсором (координаты — в переменные элемента)
(function(){
  let raf = 0, ev = null;
  document.addEventListener("pointermove", e=>{
    if(document.documentElement.dataset.design !== "glass") return;
    ev = e;
    if(raf) return;
    raf = requestAnimationFrame(()=>{
      raf = 0;
      const el = ev.target.closest && ev.target.closest(".card,details.more,.dtype,.tcard,.ch");
      if(!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", (ev.clientX - r.left) + "px");
      el.style.setProperty("--my", (ev.clientY - r.top) + "px");
    });
  }, {passive:true});
})();

// смена оформления: из места клика расходится волна нового акцента.
// Один слой, который масштабирует видеокарта: по замеру View Transitions
// (снимки всей страницы) шли рывками, волна — ровные 60 к/с
let AV_PTR = {x: innerWidth / 2, y: 0};
document.addEventListener("pointerdown", e=>{ AV_PTR = {x: e.clientX, y: e.clientY}; }, true);
function withReveal(fn){
  fn();
  if(matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = Math.hypot(Math.max(AV_PTR.x, innerWidth - AV_PTR.x),
                       Math.max(AV_PTR.y, innerHeight - AV_PTR.y));
  // слой 200 px, растягиваемый видеокартой: рисуется один раз и маленьким
  // (огромный слой во всю страницу перерисовывался посреди волны)
  const ink = document.createElement("div");
  ink.className = "av-ink keep-round";
  ink.style.left = (AV_PTR.x - 100) + "px";
  ink.style.top = (AV_PTR.y - 100) + "px";
  ink.style.setProperty("--s", (r / 100).toFixed(2));
  document.body.appendChild(ink);
  ink.addEventListener("animationend", ()=>ink.remove());
  setTimeout(()=>ink.remove(), 1800);
}

/* ================================================= старт */
(async function init(){
  await loadState();
  applyLang();
  try{
    await loadSetup();
    // мастер открывается сам, только если чего-то не хватает для работы:
    // нет движка, Anki не отвечает или нет ни одного готового голоса.
    // тестовая фраза необязательна — из-за неё мастер не приставал.
    if(WZ.setup && !WZ.setup.core){
      setTimeout(()=>{ if(!WZ.open) openWizard(); }, 450);
    }else if(!(ST && ST.cfg && ST.cfg.engine_confirmed)){
      // движок ещё ни разу не выбирали — спросим один раз, при первом запуске
      setTimeout(()=>{ if(!WZ.open) openWizard(0); }, 450);
    }
  }catch(e){
    console.warn("setup:", e);
  }
  setInterval(async ()=>{
    try{
      const st = await api("/api/state");
      ST = Object.assign({}, ST, {anki:st.anki, tts:st.tts, run:st.run, last:st.last,
                                  last_run:st.last_run});
      chip($("chipAnki"), st.anki, "Anki", st.anki?"подключена":"не подключена");
      chip($("chipTts"),  st.tts,  "Движок", st.tts?"запущен":"не запущен (запустится сам)");
      // Anki открыли, пока страница висела: подтягиваем колоды и плашку
      if(st.anki && !DECKS.length) loadDecks($("deck").value);
      updateReady();
      // кнопка «Перепробовать»: только когда есть что перепробовать
      const lr = st.last_run || {};
      const nfail = (lr.failed_ids || []).length;
      const rb = $("btnRetry");
      if(rb){
        rb.style.display = (nfail && !RUNNING) ? "" : "none";
        if(nfail){
          rb.querySelector("span").textContent = "Повторить неудачные: " + nfail;
          rb.dataset.tip = "Карточек, которые не озвучились в прошлый запуск" +
            (lr.at ? " (" + lr.at + ")" : "") + ": " + nfail + ". Подробности — в журнале и в «Приложение» → «История озвучек».";
          if(LANG !== "ru") translateDom(rb);
        }
      }
      // если операция кончилась вне нашей сессии (перезалили страницу)
      if(RUNNING && st.run && !st.run.running){
        endRunUI(st.run);
        RUNNING = false;
      }
    }catch(e){}
  }, 4000);
  // восстановление после F5: поднять UI и вернуть лог последнего запуска
  try{
    const st = await api("/api/state");
    if(st.run && st.run.running){
      beginRunUI(st.run);
    }else if(st.last){
      showLastRun(st.last);
      openLog(0);
    }
  }catch(e){
    // раньше тут был пустой catch — ошибка инициализации глоталась молча
    // и страница выглядела «просто пустой» без единой подсказки
    console.error("init:", e);
    toast("Не удалось восстановить состояние: " + e.message, "bad");
  }
})();
</script>
</body>
</html>
"""

# словарь выбранного языка подставляет anki_web.page_html (маркер /*__I18N__*/):
# разметка и динамика переводятся на лету, остальные языки грузятся по /api/i18n

# дизайн Fragile: токены цвета и слой типов интерфейса (вшиты, офлайн) и
# список встроенных тем для галереи «Оформления»
HTML = HTML.replace("/*__FRAGILE_CSS__*/",
                    fragile_assets.THEMES_CSS + "\n" + fragile_assets.DESIGN_CSS)
HTML = HTML.replace("/*__THEMES__*/",
                    "const AV_THEMES = " + json.dumps(fragile_assets.THEMES, ensure_ascii=False)
                    + "; const AV_BASE = " + json.dumps(fragile_assets.BASE) + ";")
