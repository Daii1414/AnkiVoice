# -*- coding: utf-8 -*-
"""anki_web_page.py — HTML/CSS/JS веб-интерфейса AnkiVoice (одним файлом).

Отдельный модуль, чтобы anki_web.py остался читаемым: сервер — про HTTP
и запуск пайплайна, здесь — только вид. Никаких внешних библиотек и CDN:
страница полностью работает офлайн (сырьё — system-ui/Segoe UI).

Виджеты повторяют tkinter-окно (Голос / Anki / Финализация), но живут в
браузере: вкладки, карточки, живой лог потоком (SSE), полоса прогресса,
модальный выбор файлов вместо системного диалога.
"""

HTML = r"""<!doctype html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnkiVoice</title>
<style>
:root{
  --r:12px; --r-s:8px;
  --font:"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:"Cascadia Code","Consolas","SF Mono",ui-monospace,Menlo,monospace;
}
html[data-theme="dark"]{
  --page:#0F1319; --card:#171C25; --border:#262E3B; --line:#212936;
  --text:#E7ECF5; --sub:#97A1B3;
  --accent:#8B9BFF; --accent-h:#A6B2FF; --tint:#26304E; --onaccent:#10141C;
  --ok:#4CD797; --ok-t:#123024; --warn:#FFC46B; --warn-t:#33290F;
  --err:#FF7B7C; --err-t:#331A1C;
  --chip:#1E2531; --input:#212A37; --hover:#232C3A;
  --console:#0C0F14; --console-fg:#D8DEE9;
  --disabled:#5C6675; --accent-dis:#39436B;
  --shadow:0 1px 2px rgba(0,0,0,.35),0 10px 30px rgba(0,0,0,.28);
}
html[data-theme="light"]{
  --page:#F1F3F8; --card:#FFFFFF; --border:#E3E7EF; --line:#EDF0F5;
  --text:#1B2233; --sub:#6E7789;
  --accent:#4F46E5; --accent-h:#4338CA; --tint:#EEF0FF; --onaccent:#FFFFFF;
  --ok:#12A150; --ok-t:#E6F7EF; --warn:#B46A00; --warn-t:#FFF3E0;
  --err:#E5484D; --err-t:#FDECEC;
  --chip:#F2F4F8; --input:#FFFFFF; --hover:#E9EDF4;
  --console:#12161C; --console-fg:#D8DEE9;
  --disabled:#9AA3B2; --accent-dis:#B6B1F5;
  --shadow:0 1px 2px rgba(20,28,45,.06),0 8px 24px rgba(20,28,45,.08);
}
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
  background:linear-gradient(135deg,var(--accent),#6D5CF5);
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
  text-align:left;width:100%;transition:.14s}
.nav:hover{background:var(--hover);color:var(--text)}
.nav.on{background:var(--tint);color:var(--accent);border-color:color-mix(in srgb,var(--accent) 30%,transparent);font-weight:600}
.nav .ic{width:18px;text-align:center;font-size:15px}
.nav .badge{margin-left:auto;background:var(--err);color:#fff;border-radius:999px;
  font-size:11px;padding:1px 6px;font-weight:700}
.side-foot{margin-top:auto;font-size:11.5px;color:var(--sub);
  border-top:1px solid var(--line);padding-top:10px;word-break:break-all}

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
@media(max-width:900px){.grid2,.grid3{grid-template-columns:1fr}
  .app{grid-template-columns:1fr}.sidebar{display:none}}

label.f{display:block;font-size:12.5px;color:var(--sub);margin-bottom:6px;font-weight:600}
.row{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap}
.row>*{min-width:0}
.grow{flex:1 1 180px}
input[type=text],input[type=number],select,textarea{
  width:100%;background:var(--input);border:1px solid var(--border);
  border-radius:var(--r-s);padding:9px 11px;outline:none;transition:.14s}
input:focus,select:focus,textarea:focus{border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent)}
input:disabled{color:var(--disabled);background:var(--chip)}
textarea{resize:vertical;min-height:76px;line-height:1.6}
select{cursor:pointer}
.hint{font-size:12px;color:var(--sub);margin-top:6px}
.hint b{color:var(--text);font-weight:600}

.btn{display:inline-flex;align-items:center;gap:8px;justify-content:center;
  background:var(--hover);border:1px solid var(--border);color:var(--text);
  border-radius:var(--r-s);padding:9px 15px;cursor:pointer;transition:.14s;
  font-weight:550;white-space:nowrap}
.btn:hover{border-color:color-mix(in srgb,var(--text) 25%,transparent)}
.btn:active{transform:translateY(1px)}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.btn.primary{background:var(--accent);border-color:transparent;color:var(--onaccent);font-weight:650}
.btn.primary:hover{background:var(--accent-h)}
.btn.danger{background:var(--err);border-color:transparent;color:#fff;font-weight:650}
.btn.ghost{background:transparent}
.btn.sm{padding:7px 11px;font-size:13px}
.btn.big{padding:13px 22px;font-size:15px;width:100%}

.seg{display:inline-flex;background:var(--chip);border:1px solid var(--border);
  border-radius:var(--r-s);padding:3px;gap:3px;flex-wrap:wrap}
.seg button{background:none;border:0;padding:7px 13px;border-radius:6px;
  cursor:pointer;color:var(--sub);transition:.14s;font-weight:550}
.seg button:hover{color:var(--text)}
.seg button.on{background:var(--accent);color:var(--onaccent);font-weight:650}

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
  font-size:13.5px;display:none;border:1px solid}
.banner.show{display:block}
.banner.bad{background:var(--err-t);border-color:color-mix(in srgb,var(--err) 38%,transparent);color:var(--err)}
.banner.warn{background:var(--warn-t);border-color:color-mix(in srgb,var(--warn) 38%,transparent);color:var(--warn)}
.banner.good{background:var(--ok-t);border-color:color-mix(in srgb,var(--ok) 38%,transparent);color:var(--ok)}
.banner b{font-weight:700}
.banner .acts{margin-top:9px;display:flex;gap:8px}

.prog{height:8px;border-radius:999px;background:var(--chip);overflow:hidden;
  border:1px solid var(--border);position:relative}
.prog i{display:block;height:100%;width:0;border-radius:999px;
  background:linear-gradient(90deg,var(--accent),#6D5CF5);transition:width .4s ease}
.prog.indet i{width:32%;animation:slide 1.3s ease-in-out infinite}
@keyframes slide{0%{margin-left:-32%}100%{margin-left:100%}}
.prog-meta{display:flex;justify-content:space-between;font-size:12.5px;
  color:var(--sub);margin-top:7px}

/* ---------------------------------------------------------- лог */
.console{background:var(--console);border:1px solid var(--border);
  border-radius:var(--r);height:340px;overflow:auto;padding:12px 14px;
  font:12.5px/1.65 var(--mono);color:var(--console-fg);white-space:pre-wrap;
  word-break:break-word;scroll-behavior:smooth}
.console .l-ok{color:#7AE2A8}
.console .l-err{color:#FF8A80}
.console .l-cmd{color:#8AB4F8}
.console .l-brak{color:#FFC46B}
.console .l-dim{color:#6E7789}
.console::-webkit-scrollbar{width:10px}
.console::-webkit-scrollbar-thumb{background:#2A3242;border-radius:99px;border:2px solid var(--console)}
.log-head{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.log-head h2{margin:0}
.log-head .sp{margin-left:auto;display:flex;gap:8px;align-items:center}

/* ---------------------------------------------------------- голоса */
.vlist{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:10px}
.vcard{background:var(--input);border:1px solid var(--border);border-radius:var(--r-s);
  padding:12px 13px;cursor:pointer;transition:.14s;position:relative}
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
.tbl .v{font-weight:600}

/* ---------------------------------------------------------- модалка файлов */
.overlay{position:fixed;inset:0;background:rgba(6,9,14,.62);backdrop-filter:blur(3px);
  display:none;place-items:center;z-index:50;padding:20px}
.overlay.on{display:grid}
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
.spacer{height:6px}
</style>
</head>
<body>
<div class="app">

  <div class="topbar">
    <div class="brand"><span class="logo">A</span> AnkiVoice</div>
    <div class="chips">
      <span class="chip" id="chipAnki"><span class="dot"></span>Anki: …</span>
      <span class="chip" id="chipTts"><span class="dot"></span>Сервер: …</span>
      <span class="chip" id="chipRun" style="display:none"><span class="dot"></span>Выполняется</span>
      <button class="btn sm ghost" id="btnTheme" title="Сменить тему">◐ Тема</button>
    </div>
  </div>

  <nav class="sidebar">
    <button class="nav on" data-tab="voice"><span class="ic">▶</span> Озвучка</button>
    <button class="nav" data-tab="anki"><span class="ic">▤</span> Поля колоды</button>
    <button class="nav" data-tab="sound"><span class="ic">♪</span> Голос</button>
    <button class="nav" data-tab="app"><span class="ic">⚙</span> Приложение<span class="badge" id="navBadge" style="display:none">!</span></button>
    <div class="side-foot" id="sideFoot">…</div>
  </nav>

  <main class="main">

    <!-- ============================================ ОЗВУЧКА -->
    <section class="panel on" id="p-voice">
      <h1>Озвучка колоды</h1>
      <p class="sub">Основное слово читается строго по фуригане, всё остальное — автоматически.</p>

      <div class="banner" id="voiceBanner"></div>

      <div class="card">
        <div class="grid2">
          <div>
            <label class="f">Колода</label>
            <div class="row">
              <div class="grow"><select id="deck"></select></div>
              <button class="btn sm" id="btnDecks">⟳ Обновить</button>
            </div>
            <div class="hint" id="deckHint">Загружаю колоды из Anki…</div>
          </div>
          <div>
            <label class="f">Голос</label>
            <select id="voice"></select>
            <div class="hint" id="voiceHint"></div>
          </div>
        </div>

        <div class="spacer"></div>
        <label class="f">Что озвучивать</label>
        <div class="seg" id="segMode">
          <button data-v="both" class="on">слово + предложение</button>
          <button data-v="sentence">предложение</button>
          <button data-v="expression">слово</button>
        </div>

        <div class="spacer"></div>
        <div class="row">
          <div style="width:130px">
            <label class="f">Лимит карточек</label>
            <input type="number" id="limit" value="0" min="0">
          </div>
          <div class="hint" style="align-self:center;padding-bottom:10px">0 = все</div>
          <label class="switch" style="align-self:center;padding-bottom:12px">
            <input type="checkbox" id="force"> Пересобрать всё заново
          </label>
        </div>
      </div>

      <div class="card">
        <div class="row">
          <button class="btn primary big" id="btnStart">▶&nbsp; Начать озвучку</button>
          <button class="btn danger" id="btnStop" disabled>■&nbsp; Остановить</button>
          <button class="btn" id="btnCheck">Проверить колоду</button>
          <button class="btn" id="btnSelftest">Самопроверка</button>
        </div>

        <div class="spacer" style="height:16px"></div>
        <div class="prog indet" id="prog"><i></i></div>
        <div class="prog-meta">
          <span id="progText">Готов к запуску</span>
          <span id="progPct"></span>
        </div>
      </div>

      <div class="card">
        <div class="log-head">
          <h2>Журнал</h2>
          <div class="sp">
            <label class="switch"><input type="checkbox" id="follow" checked> Следить</label>
            <button class="btn sm ghost" id="btnClear">Очистить</button>
          </div>
        </div>
        <div class="console" id="log"><span class="l-dim">Лог появится после запуска.</span></div>
      </div>
    </section>

    <!-- ============================================ ПОЛЯ КОЛОДЫ -->
    <section class="panel" id="p-anki">
      <h1>Поля колоды</h1>
      <p class="sub">Что каким полем читать и куда класть звук. Значения подставляются автоматически — поправь, если колода называет поля иначе.</p>

      <div class="banner" id="ankiBanner"></div>

      <div class="card">
        <label class="f">Колода</label>
        <div class="row">
          <div class="grow"><select id="deck2"></select></div>
          <button class="btn sm" id="btnFields">Поля выбранной колоды</button>
        </div>
        <div class="hint" id="fieldsHint">Выбери колоду и нажми «Поля выбранной колоды».</div>
      </div>

      <div class="card">
        <table class="tbl">
          <thead><tr><th style="width:44%">Роль</th><th>Поле карточки</th></tr></thead>
          <tbody>
            <tr><td class="k">Текст предложения</td><td><select id="f_sent_src"></select></td></tr>
            <tr><td class="k">Звук предложения →</td><td><select id="f_sent_aud"></select></td></tr>
            <tr><td class="k">Основное слово</td><td><select id="f_word_src"></select></td></tr>
            <tr><td class="k">Звук слова →</td><td><select id="f_word_aud"></select></td></tr>
            <tr><td class="k">Фуригана слова ← поле</td><td><select id="f_furi"></select></td></tr>
            <tr><td class="k">Источник чтения</td><td><select id="f_reading"></select></td></tr>
          </tbody>
        </table>
        <div class="hint">Пустой выбор в колонке «→» = звук не записывать. Пустая фуригана = слово прочитается автоматически.</div>
      </div>

      <div class="card">
        <button class="btn primary" id="btnSaveFields">Сохранить настройки полей</button>
        <span class="hint" style="display:inline;margin-left:12px" id="fieldsSaved"></span>
      </div>
    </section>

    <!-- ============================================ ГОЛОС -->
    <section class="panel" id="p-sound">
      <h1>Голос</h1>
      <p class="sub">Референс, текст промпта и параметры чтения выбранного голоса.</p>

      <div class="banner" id="voiceBanner2"></div>

      <div class="card">
        <div class="vlist" id="vlist"></div>
        <div class="spacer" style="height:14px"></div>
        <div class="row">
          <button class="btn sm" id="btnTest">▶&nbsp; Прослушать тест</button>
          <button class="btn sm" id="btnAddVoice">➕ Добавить голос</button>
          <button class="btn sm" id="btnScan">Обновить веса в движке</button>
        </div>
        <div class="hint">Тест играет <span class="l-cmd" id="testFile">—</span></div>
      </div>

      <div class="card" id="voiceEdit" style="display:none">
        <h2 id="veName">—</h2>
        <div class="grid2">
          <div>
            <label class="f">Референс 3–10 с</label>
            <div class="row">
              <div class="grow"><input type="text" id="v_ref" placeholder="файл .wav/.mp3"></div>
              <button class="btn sm" data-pick="v_ref" data-ext="audio">Обзор…</button>
            </div>
            <label class="switch" style="margin-top:12px">
              <input type="checkbox" id="v_noref"> Без текста референса
            </label>
            <div class="spacer"></div>
            <label class="f">Текст референса</label>
            <textarea id="v_prompt" placeholder="что говорит голос в референсе"></textarea>
            <div class="row" style="margin-top:10px">
              <div class="grow"><label class="f">Язык промпта</label>
                <input type="text" id="v_lang" value="ja"></div>
              <div style="width:110px"><label class="f">Seed</label>
                <input type="number" id="v_seed" value="42"></div>
            </div>
          </div>
          <div>
            <label class="f">Доп. файлы (aux)</label>
            <div id="auxList" style="display:flex;flex-direction:column;gap:8px"></div>
            <button class="btn sm ghost" id="btnAux">＋ добавить файл</button>
            <div class="spacer" style="height:14px"></div>
            <div class="grid2">
              <div><label class="f">Температура</label>
                <input type="number" id="v_temp" step="0.01" min="0" max="2"></div>
              <div><label class="f">top_p</label>
                <input type="number" id="v_topp" step="0.01" min="0" max="1"></div>
              <div><label class="f">top_k</label>
                <input type="number" id="v_topk" step="1" min="0" max="200"></div>
              <div><label class="f">Скорость</label>
                <input type="number" id="v_speed" step="0.05" min="0.5" max="2"></div>
            </div>
          </div>
        </div>
        <div class="spacer" style="height:14px"></div>
        <button class="btn primary" id="btnSaveVoice">Сохранить голос</button>
        <span class="hint" style="display:inline;margin-left:12px" id="voiceSaved"></span>
      </div>
      <div class="card" id="addVoiceCard" style="display:none">
        <h2>Новый голос</h2>
        <div class="grid2">
          <div>
            <label class="f">Имя (латиницей)</label>
            <input type="text" id="a_name" placeholder="kubota">
            <div class="spacer"></div>
            <label class="f">Как показывать</label>
            <input type="text" id="a_disp" placeholder="Кубота Хитоси">
            <div class="spacer"></div>
            <label class="f">GPT .ckpt</label>
            <div class="row"><div class="grow"><input type="text" id="a_gpt"></div>
              <button class="btn sm" id="a_gpt_b">…</button></div>
            <div class="spacer"></div>
            <label class="f">SoVITS .pth</label>
            <div class="row"><div class="grow"><input type="text" id="a_sov"></div>
              <button class="btn sm" id="a_sov_b">…</button></div>
          </div>
          <div>
            <label class="f">Референс 3–10 с</label>
            <div class="row"><div class="grow"><input type="text" id="a_ref"></div>
              <button class="btn sm" id="a_ref_b">…</button></div>
            <div class="spacer"></div>
            <label class="f">Текст референса</label>
            <textarea id="a_txt" placeholder="что говорит голос в референсе"></textarea>
            <div class="spacer"></div>
            <label class="f">Язык промпта</label>
            <input type="text" id="a_lang" value="ja">
          </div>
        </div>
        <div class="spacer" style="height:14px"></div>
        <div class="row">
          <button class="btn primary" id="a_ok">Добавить</button>
          <button class="btn" id="a_cancel">Отмена</button>
        </div>
        <div class="hint" id="a_err"></div>
      </div>
    </section>

    <!-- ============================================ ПРИЛОЖЕНИЕ -->
    <section class="panel" id="p-app">
      <h1>Приложение</h1>
      <p class="sub">Папка движка, диагностика и внешний вид.</p>

      <div class="banner" id="appBanner"></div>

      <div class="card">
        <label class="f">Папка GPT-SoVITS</label>
        <div class="row">
          <div class="grow"><input type="text" id="gptpath" placeholder="D:\DOWNLOAD\GPT-SoVITS-…"></div>
          <button class="btn sm" id="btnPickGpt">Обзор…</button>
          <button class="btn sm" id="btnCheckPath">Проверить</button>
        </div>
        <div class="hint" id="pathHint">—</div>
        <div class="spacer"></div>
        <button class="btn primary" id="btnSavePath">Сохранить папку</button>
      </div>

      <div class="card">
        <h2>Диагностика</h2>
        <div id="doctor" class="hint">Нажми «Запустить диагностику».</div>
        <div class="spacer" style="height:12px"></div>
        <div class="row">
          <button class="btn" id="btnDoctor">Запустить диагностику</button>
          <button class="btn ghost" id="btnQuit">Закрыть AnkiVoice</button>
        </div>
      </div>

      <div class="card">
        <h2>Где лежат файлы</h2>
        <table class="tbl">
          <tbody>
            <tr><td class="k">Программа</td><td class="v" id="pCode">—</td></tr>
            <tr><td class="k">Конфиг</td><td class="v" id="pCfg">—</td></tr>
            <tr><td class="k">Версия</td><td class="v" id="pVer">—</td></tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>
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

<div class="toast" id="toast"></div>

<script>
"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let ST = null;            // последний /api/state
let FIELDS = [];          // поля выбранной колоды
let RUNNING = false;
let SSE = null;

/* ================================================= утилиты */
async function api(path, body){
  const opt = body === undefined ? {} : {
    method:"POST", headers:{"Content-Type":"application/json"},
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
  };
});

/* ================================================= тема */
$("btnTheme").onclick = ()=>{
  const nx = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = nx;
  saveCfg({theme:nx});
};

/* ================================================= состояние */
async function loadState(){
  try{
    ST = await api("/api/state");
  }catch(e){
    banner("appBanner","bad","<b>Сервер не отвечает:</b> "+esc(e.message));
    return;
  }
  const c = ST.cfg || {};
  if(c.theme) document.documentElement.dataset.theme = c.theme;

  // статусы
  chip($("chipAnki"), ST.anki, "Anki", ST.anki ? "подключена" : "не подключена");
  chip($("chipTts"),  ST.tts,  "Сервер", ST.tts ? "запущен" : "не запущен (поднимется сам)");

  $("sideFoot").innerHTML = "Программа<br><b>"+esc(ST.code_dir)+"</b>";

  // папка движка
  $("gptpath").value = ST.path || "";
  if(ST.problems && ST.problems.length){
    banner("appBanner","bad",
      "<b>Папка GPT-SoVITS:</b> " + esc(ST.problems.join(" · ")) +
      (ST.auto ? '<div class="acts"><button class="btn sm" id="bAuto">Подставить найденную: '+esc(ST.auto)+'</button></div>' : ""));
    const b = $("bAuto");
    if(b) b.onclick = ()=>{ $("gptpath").value = ST.auto; savePath(); };
    $("navBadge").style.display = "";
  }else{
    banner("appBanner", null);
    $("navBadge").style.display = "none";
    $("pathHint").innerHTML = "Папка в порядке.";
  }

  // голоса
  renderVoiceList();
  fillVoiceSelect(c.voice);
  const dv = ST.voices && ST.default_voice && ST.voices[ST.default_voice];
  $("voiceHint").innerHTML = dv
    ? "Голос по умолчанию: <b>" + esc(dv.display || ST.default_voice) + "</b>"
    : "";

  // колоды не тянем в state (долго) — отдельным вызовом
  if(!$("deck").options.length) loadDecks(c.deck);

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
}
function chip(el, ok, name, txt){
  el.className = "chip " + (ok ? "good" : "bad");
  el.innerHTML = '<span class="dot"></span>' + esc(name) + ": " + esc(txt);
}

/* ================================================= колоды */
async function loadDecks(prefer){
  const hint = $("deckHint");
  hint.textContent = "Читаю колоды из Anki…";
  try{
    const j = await api("/api/decks");
    const decks = j.decks || [];
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
      hint.innerHTML = "Колод в Anki: <b>" + decks.length + "</b>. Заметок в выбранной: <b>" +
        (decks.find(d=>d[0]===$("deck").value)||[,"?"])[1] + "</b>.";
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
}
$("deck").onchange = onDeckPick;
$("deck2").onchange = ()=>{ if($("deck2").value) $("deck").value = $("deck2").value; };
$("btnDecks").onclick = ()=>loadDecks($("deck").value);

/* ================================================= поля колоды */
const FIELD_IDS = ["sent_src","sent_aud","word_src","word_aud","furi","reading"];
function fillSelect(sel, fields, keep){
  const prev = keep || sel.value;
  let html = '<option value="">— не используется —</option>';
  if(sel.id === "f_reading")
    html = '<option value="">'+ (ST ? ST.reading_off : "Не подставлять") +'</option>';
  html += fields.map(f=>'<option value="'+esc(f)+'">'+esc(f)+"</option>").join("");
  sel.innerHTML = html;
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
    // значения по умолчанию из конфига, иначе — автоподбор
    const c = ST.cfg || {};
    const pick = (key, guess) => (c[key] !== undefined && c[key] !== null && c[key] !== "")
      ? c[key] : (guess || "");
    fillSelect($("f_sent_src"), FIELDS, pick("sentence_src", g.sentence_src));
    fillSelect($("f_sent_aud"), FIELDS, pick("sentence_audio", g.sentence_audio));
    fillSelect($("f_word_src"), FIELDS, pick("word_src", g.word_src));
    fillSelect($("f_word_aud"), FIELDS, pick("word_audio", g.word_audio));
    fillSelect($("f_furi"),     FIELDS, pick("furigana_src", g.furigana_src));
    fillSelect($("f_reading"),  FIELDS, c.reading && c.reading !== (ST?ST.reading_off:"")
                                        ? c.reading : "");
    $("fieldsHint").innerHTML = "Полей в колоде: <b>"+FIELDS.length+"</b>. " +
      "Фуригана: <b>"+(g.furigana_src || c.furigana_src || "нет — слово прочитается автоматически")+"</b>.";
    banner("ankiBanner", null);
  }catch(e){
    $("fieldsHint").textContent = "Ошибка: " + e.message;
    banner("ankiBanner","bad","<b>Не удалось прочитать поля:</b> "+esc(e.message));
  }
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
  if(!g.reading) g.reading = (ST && ST.reading_off) || "Не подставлять (движок сам)";
  g.deck = $("deck2").value || $("deck").value;
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
  const list = voiceEntries();
  $("vlist").innerHTML = list.map(v=>{
    const disp = v.display || v.name;
    return '<div class="vcard" data-n="'+esc(v.name)+'">'+
      '<div class="nm">'+esc(disp)+'</div>'+
      '<div class="st '+(v.ok?"ok":"no")+'">'+(v.ok?"✓ файлы на месте":"✗ нет gpt/sovits/ref")+'</div>'+
      '<div class="st">'+esc(v.name)+'</div></div>';
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
function fillVoiceSelect(prefer){
  const list = voiceEntries();
  const sel = $("voice");
  const prev = prefer || sel.value;
  sel.innerHTML = list.map(v=>
    '<option value="'+esc(v.name)+'">'+esc(v.display || v.name)+"</option>").join("");
  if(prev && list.some(v=>v.name===prev)) sel.value = prev;
  else if(ST.default_voice && list.some(v=>v.name===ST.default_voice)) sel.value = ST.default_voice;
  if(sel.value) openVoiceEditor(sel.value);
  markSelected(sel.value);
  const selV = list.find(v=>v.name===sel.value);
  $("voiceHint").innerHTML = selV
    ? (selV.ok ? "Файлы весов на месте." : '<span style="color:var(--err)">У голоса не найдены файлы gpt/sovits/ref.</span>')
    : "";
  $("testFile").textContent = "test_" + (sel.value || "…") + ".ogg";
}
function selectVoice(name){
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

let EDIT = null;   // редактируемый голос
function openVoiceEditor(name){
  const v = (ST.voices||{})[name];
  if(!v){ $("voiceEdit").style.display="none"; return; }
  EDIT = name;
  $("voiceEdit").style.display = "";
  $("veName").textContent = (v.display || name) + "  ·  " + name;
  $("v_ref").value = v.ref || "";
  $("v_prompt").value = v.prompt_text || "";
  $("v_lang").value = v.prompt_lang || "ja";
  $("v_noref").checked = !v.prompt_text;
  $("v_temp").value = v.temperature != null ? v.temperature : 0.6;
  $("v_topp").value = v.top_p != null ? v.top_p : 0.6;
  $("v_topk").value = v.top_k != null ? v.top_k : 20;
  $("v_speed").value = v.speed != null ? v.speed : 1.0;
  $("v_seed").value = v.seed != null ? v.seed : 42;
  $("v_prompt").disabled = $("v_noref").checked;
  renderAux(v.aux || []);
}
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
  const ok = await runOp({kind:"test", voice:v, text:"こんにちは、テストです。",
    speed:$("v_speed").value, seed:$("v_seed").value});
  if(ok) setTimeout(()=>{ $("log").scrollIntoView({behavior:"smooth"}); }, 300);
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

function collectVoiceArgs(){
  return {
    kind:"voice", voice:$("voice").value, deck:$("deck").value, mode:mode(),
    sentence_src:$("f_sent_src").value, sentence_audio:$("f_sent_aud").value,
    word_src:$("f_word_src").value, word_audio:$("f_word_aud").value,
    furigana_src:$("f_furi").value, reading:$("f_reading").value,
    limit:$("limit").value, force:$("force").checked
  };
}
$("btnStart").onclick = async ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  if(!$("voice").value) return toast("Сначала выбери голос","bad");
  saveCfg({mode:mode(), limit:$("limit").value, voice:$("voice").value, deck:$("deck").value});
  await runOp(collectVoiceArgs());
};
$("btnCheck").onclick = ()=>{
  if(!$("deck").value) return toast("Сначала выбери колоду","bad");
  runOp({kind:"check", deck:$("deck").value,
    sentence_audio:$("f_sent_aud").value, word_audio:$("f_word_aud").value});
};
$("btnSelftest").onclick = ()=>runOp({kind:"selftest"});
$("btnStop").onclick = async ()=>{
  try{
    const j = await api("/api/stop", {});
    toast(j.ok ? "Останавливаю…" : (j.error || "Нечего останавливать"), j.ok?"":"bad");
  }catch(e){ toast(e.message,"bad"); }
};
$("btnClear").onclick = ()=>{ $("log").innerHTML = ""; };
$("follow").onchange = ()=>{ if($("follow").checked) scrollLog(); };

async function runOp(payload){
  try{
    const j = await api("/api/run", payload);
    beginRunUI(j.run);
    return true;
  }catch(e){
    banner("voiceBanner","bad","<b>Не запустилось:</b> "+esc(e.message));
    toast(e.message,"bad");
    return false;
  }
}
function beginRunUI(r){
  resetProgress();
  RUNNING = true;
  $("btnStart").disabled = true;
  $("btnCheck").disabled = true;
  $("btnSelftest").disabled = true;
  $("btnStop").disabled = false;
  $("btnTest").disabled = true;
  $("chipRun").style.display = "";
  $("chipRun").className = "chip live";
  $("prog").className = "prog indet";
  $("progText").textContent = r.title || "Выполняется…";
  $("progPct").textContent = "";
  $("voiceBanner") && banner("voiceBanner", null);
  openLog(0);
}
function endRunUI(s){
  RUNNING = false;
  $("btnStart").disabled = false;
  $("btnCheck").disabled = false;
  $("btnSelftest").disabled = false;
  $("btnTest").disabled = false;
  $("btnStop").disabled = true;
  $("chipRun").style.display = "none";
  const ok = s && s.code === 0;
  $("prog").className = "prog";
  $("prog").firstElementChild.style.width = "100%";
  $("progText").textContent = (s ? (s.title || "Готово") : "Готово") +
    (s && s.code != null ? " — код " + s.code : "");
  $("progPct").textContent = ok ? "✓ завершено" : "✗ есть ошибки";
  $("progPct").style.color = ok ? "var(--ok)" : "var(--err)";
  if(!ok) banner("voiceBanner","bad",
    "<b>Завершилось с ошибкой (код "+(s?s.code:"?")+").</b> Посмотри журнал ниже.");
  else banner("voiceBanner","good","<b>Готово.</b> Результат записан в колоду.");
}
function showLastRun(s){
  $("prog").className = "prog";
  $("prog").firstElementChild.style.width = s.total ? "100%" : "0%";
  $("progText").textContent = "Прошлая операция: " + (s.title||"") + " — код " + s.code;
}

/* ================================================= лог (SSE) */
function openLog(since){
  if(SSE){ SSE.close(); SSE = null; }
  const log = $("log");
  if(!since) log.innerHTML = "";
  let lastCount = since || 0;

  SSE = new EventSource("/api/log?since=" + (since||0));
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
  const m = /К озвучке:\s*(\d+)/.exec(line);
  if(m) PROG_TOTAL = +m[1];
  if(/^OK\s+\[/.test(line)) PROG_OK++;
  if(/^FAIL\s+\[/.test(line)) PROG_FAIL++;
  drawProgress(n);
}
let PROG_TOTAL = null, PROG_OK = 0, PROG_FAIL = 0;
function resetProgress(){ PROG_TOTAL=null; PROG_OK=0; PROG_FAIL=0; }
function drawProgress(n){
  const el = $("prog"), bar = el.firstElementChild;
  if(PROG_TOTAL){
    el.className = "prog";
    const pct = Math.min(100, Math.round(PROG_OK / PROG_TOTAL * 100));
    bar.style.width = pct + "%";
    $("progPct").textContent = PROG_OK + " / " + PROG_TOTAL +
      (PROG_FAIL ? "  ·  ошибок: " + PROG_FAIL : "");
    $("progPct").style.color = PROG_FAIL ? "var(--err)" : "var(--sub)";
    $("progText").textContent = "Озвучено карточек: " + PROG_OK;
  }else{
    el.className = "prog indet";
    $("progText").textContent = "Выполняется… (" + n + " строк журнала)";
  }
}

/* ================================================= конфиг */
async function saveCfg(patch){
  try{ ST = await api("/api/config", patch); }catch(e){ console.warn(e); }
}
async function savePath(){
  const p = $("gptpath").value.trim();
  const j = await api("/api/config", {gptsovits_path:p});
  if(j.problems && j.problems.length){
    banner("appBanner","bad","<b>Проблемы:</b> "+esc(j.problems.join(" · ")));
    $("pathHint").innerHTML = '<span style="color:var(--err)">'+esc(j.problems.join(" · "))+"</span>";
    toast("Папка не подходит","bad");
  }else{
    banner("appBanner", null);
    $("pathHint").innerHTML = '<span style="color:var(--ok)">Папка в порядке ✓</span>';
    toast("Папка сохранена","good");
    await loadState();
  }
}
$("btnSavePath").onclick = savePath;
$("btnCheckPath").onclick = async ()=>{
  const p = $("gptpath").value.trim();
  const j = await api("/api/config", {gptsovits_path:p});
  $("pathHint").innerHTML = (j.problems && j.problems.length)
    ? '<span style="color:var(--err)">'+esc(j.problems.join(" · "))+"</span>"
    : '<span style="color:var(--ok)">Папка в порядке ✓</span>';
};

$("btnDoctor").onclick = async ()=>{
  $("doctor").textContent = "Проверяю…";
  try{
    const d = await api("/api/doctor");
    const bad = [].concat(d.local_problems||[], d.problems||[]);
    $("doctor").innerHTML = [
      "Программа: <b>"+esc(d.code_dir)+"</b>",
      "Конфиг: <b>"+esc(d.config_file)+"</b>",
      "GPT-SoVITS: <b>"+esc(d.gptsovits_path||"—")+"</b>",
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
$("btnPickGpt").onclick = ()=>openPicker($("gptpath"), "dir", "", "Папка GPT-SoVITS");

/* ================================================= добавление голоса */
function addVoiceDialog(){
  $("addVoiceCard").style.display = "";
  $("addVoiceCard").scrollIntoView({behavior:"smooth", block:"center"});
  $("a_name").focus();
}
$("a_cancel").onclick = ()=>{ $("addVoiceCard").style.display = "none"; $("a_err").innerHTML=""; };
$("a_gpt_b").onclick  = ()=>openPicker($("a_gpt"),"file","ckpt","GPT-веса (.ckpt)");
$("a_sov_b").onclick  = ()=>openPicker($("a_sov"),"file","pth","SoVITS-веса (.pth)");
$("a_ref_b").onclick  = ()=>openPicker($("a_ref"),"file","audio","Файл референса");
$("a_ok").onclick = async ()=>{
  $("a_err").innerHTML = "";
  try{
    await api("/api/voice/add", {
      name:$("a_name").value, display:$("a_disp").value,
      gpt:$("a_gpt").value, sovits:$("a_sov").value,
      ref:$("a_ref").value, prompt_text:$("a_txt").value,
      prompt_lang:$("a_lang").value
    });
    toast("Голос добавлен","good");
    $("addVoiceCard").style.display = "none";
    await loadState();
    selectVoice($("a_name").value.trim());
    $("a_name").value=""; $("a_disp").value=""; $("a_gpt").value="";
    $("a_sov").value=""; $("a_ref").value=""; $("a_txt").value="";
  }catch(e){
    $("a_err").innerHTML = '<span style="color:var(--err)">'+esc(e.message)+"</span>";
  }
};

/* ================================================= старт */
(async function init(){
  await loadState();
  setInterval(async ()=>{
    try{
      const st = await api("/api/state");
      ST = Object.assign({}, ST, {anki:st.anki, tts:st.tts, run:st.run, last:st.last});
      chip($("chipAnki"), st.anki, "Anki", st.anki?"подключена":"не подключена");
      chip($("chipTts"),  st.tts,  "Сервер", st.tts?"запущен":"не запущен (поднимется сам)");
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
