#!/usr/bin/env node
/* Полный аудит интерфейса AnkiVoice: обходит каждый элемент управления,
   нажимает/меняет его и ловит ошибки консоли и исключения.

   Запуск:
     node web_ui_audit.js http://127.0.0.1:8796

   Опасные действия (реальный синтез, закрытие сервера) пропускаются.
   Конфиг и voices.json снимаются до аудита и возвращаются после.
*/
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CHROME = process.env.CHROME
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9336;
const BASE = process.argv[2] || "http://127.0.0.1:8796";
const REPO = "E:\\TTS-проект";
const CONFIG = path.join(process.env.APPDATA || "", "AnkiVoice", "config.json");
const VOICES = path.join(REPO, "voices.json");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function httpJson(method, url) {
  const r = await fetch(url, { method });
  if (!r.ok) throw new Error(method + " " + url + " -> " + r.status);
  return r.json();
}

function makeCdp(ws) {
  let id = 0;
  const pending = new Map();
  const listeners = [];
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id);
      pending.delete(m.id);
      m.error ? p.rej(new Error(m.error.message)) : p.res(m.result);
      return;
    }
    if (m.method) listeners.forEach((fn) => fn(m));
  });
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
    setTimeout(() => {
      if (pending.has(i)) { pending.delete(i); rej(new Error("CDP таймаут: " + method)); }
    }, 30000);
  });
  send.on = (fn) => listeners.push(fn);
  return send;
}

function openWs(url) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(url);
    ws.addEventListener("open", () => res(ws));
    ws.addEventListener("error", () => rej(new Error("WebSocket ошибка")));
  });
}

async function waitFor(fn, ms, what) {
  const t0 = Date.now();
  for (;;) {
    let v = false;
    try { v = await fn(); } catch (e) { v = false; }
    if (v) return v;
    if (Date.now() - t0 > ms) throw new Error("не дождался: " + what);
    await sleep(250);
  }
}

/* Обход страницы. Выполняется внутри Chrome, возвращает отчёт. */
function auditRunner() {
  return (async function () {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const BLACK_ID = /^(btnStart|btnQuit|btnTest|btnCheck)$/i;
    // btnStart — реальный синтез по колоде; btnTest — синтез образца;
    // btnCheck — запуск проверки колоды; btnQuit — гасит сервер.
    // Аудит должен быть безвредным, поэтому их не трогаем.
    const rep = { tabs: [], elements: [], skipped: [], problems: [] };

    const describe = (el) => {
      const o = { tag: el.tagName.toLowerCase(), id: el.id || "" };
      let t = (el.textContent || "").trim().replace(/\s+/g, " ");
      if (t) o.text = t.slice(0, 42);
      if (el.placeholder) o.ph = el.placeholder;
      if (!t && !el.placeholder && el.id) {
        const lab = document.querySelector('label[for="' + el.id + '"]')
                 || (el.closest && el.closest(".f, .cell, td"));
        if (lab) o.text = (lab.textContent || "").trim().replace(/\s+/g, " ").slice(0, 42);
      }
      return o;
    };

    const closeOverlay = async () => {
      const ov = document.getElementById("overlay");
      if (ov && ov.classList.contains("on")) {
        const x = document.getElementById("mClose");
        if (x) x.click();
        await sleep(80);
      }
    };

    // 1. вкладки
    const navs = Array.from(document.querySelectorAll(".nav"));
    for (const n of navs) {
      n.click();
      await sleep(280);
      const p = document.querySelector(".panel.on");
      rep.tabs.push({
        tab: n.dataset.tab,
        panel: p ? p.id : null,
        chars: p ? p.innerText.trim().length : 0,
        empty: p ? p.innerText.trim().length < 20 : true,
      });
    }
    if (navs[0]) { navs[0].click(); await sleep(200); }

    // 2. голоса (карточки кликаются не через onclick-атрибут)
    const vcards = Array.from(document.querySelectorAll(".vcard, [data-name]"));
    for (const c of vcards.slice(0, 3)) {
      const before = rep.problems.length;
      c.click();
      await sleep(220);
      const ed = document.getElementById("voiceEdit");
      rep.elements.push(Object.assign(describe(c), {
        kind: "vcard",
        openedEditor: !!(ed && ed.style.display !== "none"),
      }));
      if (rep.problems.length > before) rep.problems.push({ el: c.id || c.className, what: "ошибка на карточке голоса" });
    }

    // 3. прочие интерактивные элементы
    const els = Array.from(document.querySelectorAll(
      "button, input, select, textarea, [onclick]"));
    for (const el of els) {
      const d = describe(el);
      if (BLACK_ID.test(d.id)) { d.why = "опасно — пропущено"; rep.skipped.push(d); continue; }
      if (el.disabled) { d.why = "отключён"; rep.skipped.push(d); continue; }

      const errBefore = rep.problems.length;
      try {
        const tag = el.tagName;
        if (tag === "SELECT") {
          d.options = el.options.length;
          if (!el.options.length) rep.problems.push({ el: d.id, what: "select без вариантов" });
          if (el.options.length > 1) {
            el.selectedIndex = Math.min(1, el.options.length - 1);
            el.dispatchEvent(new Event("change", { bubbles: true }));
          }
        } else if (tag === "TEXTAREA") {
          el.dispatchEvent(new Event("input", { bubbles: true }));
        } else if (tag === "INPUT") {
          if (el.type === "checkbox" || el.type === "radio") el.click();
          else {
            if (el.type === "number") {
              const v = parseFloat(el.value);
              if (Number.isNaN(v)) rep.problems.push({ el: d.id, what: "числовое поле с NaN" });
            }
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
          }
        } else el.click();
      } catch (e) {
        d.threw = String((e && e.message) || e);
        rep.problems.push({ el: d.id || d.text, what: "исключение: " + d.threw });
      }
      await sleep(260);   // loadFields/loadDecks ходят в Anki по сети
      await closeOverlay();
      if (rep.problems.length > errBefore) d.flagged = true;
      rep.elements.push(d);
    }

    // 4. сводка по местам, которые должны присутствовать в DOM
    const notes = [];
    ["vlist", "auxList", "doctor", "log"].forEach((id) => {
      const e = document.getElementById(id);
      if (!e) {
        rep.problems.push({ el: id, what: "элемента нет в DOM" });
        return;
      }
      notes.push({ el: id, what: "текст " + e.innerText.trim().length + " симв." });
    });
    rep.notes = notes;

    return rep;
  })();
}

async function main() {
  const snap = {};
  for (const [k, p] of [["config", CONFIG], ["voices", VOICES]]) {
    try { snap[k] = { p, raw: fs.readFileSync(p) }; } catch (e) { snap[k] = null; }
  }

  const prof = fs.mkdtempSync(path.join(os.tmpdir(), "avaudit-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--disable-extensions", "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + prof, "--window-size=1440,1200", "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  let ws = null;
  try {
    await waitFor(() => httpJson("GET", "http://127.0.0.1:" + PORT + "/json/version")
      .then(() => true).catch(() => false), 15000, "старт Chrome");

    let target;
    try { target = await httpJson("PUT", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }
    catch (e) { target = await httpJson("GET", "http://127.0.0.1:" + PORT + "/json/new?about:blank"); }

    ws = await openWs(target.webSocketDebuggerUrl);
    const send = makeCdp(ws);

    const consoleErrors = [];
    const exceptions = [];
    send.on((m) => {
      if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
        consoleErrors.push(m.params.args.map((a) => a.value || a.description || "").join(" "));
      }
      if (m.method === "Runtime.exceptionThrown") {
        const d = m.params.exceptionDetails;
        exceptions.push((d.exception && (d.exception.description || d.exception.value))
                        || d.text || "исключение");
      }
    });

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Page.navigate", { url: BASE + "/" });
    await waitFor(async () => (await send("Runtime.evaluate",
      { expression: "document.readyState", returnByValue: true })).result.value === "complete",
      20000, "загрузка страницы");
    await waitFor(async () => (await send("Runtime.evaluate",
      { expression: "document.querySelectorAll('#deck option').length>0", returnByValue: true }))
      .result.value === true, 25000, "загрузка колод");

    const r = await send("Runtime.evaluate",
      { expression: "(" + auditRunner.toString() + ")()", awaitPromise: true, returnByValue: true });

    const rep = r.result.value || {};
    rep.consoleErrors = consoleErrors;
    rep.exceptions = exceptions;

    console.log(JSON.stringify(rep, null, 2));
  } finally {
    if (ws) try { ws.close(); } catch (e) { /* ignore */ }
    try { chrome.kill(); } catch (e) { /* ignore */ }
    await sleep(400);
    try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) { /* ignore */ }
    for (const k of Object.keys(snap)) {
      if (snap[k]) { try { fs.writeFileSync(snap[k].p, snap[k].raw); } catch (e) { /* ignore */ } }
    }
    console.error("конфиг и voices.json возвращены");
  }
}

main().catch((e) => { console.error("ОШИБКА: " + e.message); process.exit(1); });
