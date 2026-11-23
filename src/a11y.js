/* Версия для слабовидящих и чтение страницы вслух.
   Работает без внешних сервисов: голос берётся из телефона или компьютера (Web Speech API).
   Правила, что читать, совпадают с tts.py (озвучка диктором через ElevenLabs). */
(function () {
  "use strict";
  var root = document.documentElement;

  /* ---------- Версия для слабовидящих ---------- */
  function store(key, value) {
    try {
      if (value) localStorage.setItem("a11y-" + key, value);
      else localStorage.removeItem("a11y-" + key);
    } catch (e) { /* приватный режим: настройки просто не запомнятся */ }
  }
  function apply(key, value) {
    if (value) root.setAttribute("data-" + key, value);
    else root.removeAttribute("data-" + key);
    store(key, value);
  }

  var toggle = document.getElementById("a11y-toggle");
  var panel = document.getElementById("a11y-panel");
  if (toggle && panel) {
    var options = panel.querySelectorAll("button[data-set]");
    var sync = function () {
      options.forEach(function (b) {
        var current = root.getAttribute("data-" + b.dataset.set) || "";
        b.setAttribute("aria-pressed", String(current === (b.dataset.value || "")));
      });
    };
    toggle.addEventListener("click", function () {
      var open = panel.hidden;
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      if (open) { var first = panel.querySelector("button"); if (first) first.focus(); }
    });
    options.forEach(function (b) {
      b.addEventListener("click", function () { apply(b.dataset.set, b.dataset.value || ""); sync(); });
    });
    var reset = document.getElementById("a11y-reset");
    if (reset) reset.addEventListener("click", function () {
      ["size", "contrast", "spacing"].forEach(function (k) { apply(k, ""); });
      sync();
    });
    sync();
  }

  /* ---------- Чтение вслух ---------- */
  var bar = document.querySelector(".listen-bar");
  if (!bar) return;
  var controls = bar.querySelector(".tts-controls");
  var status = bar.querySelector(".tts-status");
  if (!("speechSynthesis" in window) || !controls) return;
  var synth = window.speechSynthesis;
  controls.hidden = false;

  var BLOCKS = "h1,h2,h3,p,li,.prompt,.box,[data-say]";
  var SKIP = ".helper,.no-print,.pager,.listen-bar,[data-tts='skip'],table,.table-wrap:not([data-say])";
  /* \b в JavaScript не понимает кириллицу, поэтому границы слова задаём явно */
  var PRONOUNCE = [["ИИ", "И-И"], ["ЖКХ", "жэ-ка-ха"], ["СМС", "эс-эм-эс"],
    ["VPN", "ви-пи-эн"], ["УК", "у-ка"], ["A4", "А-четыре"]].map(function (p) {
    return [new RegExp("(^|[^0-9A-Za-zА-Яа-яЁё])" + p[0] + "(?=$|[^0-9A-Za-zА-Яа-яЁё])", "g"), "$1" + p[1]];
  });
  var SYMBOLS = /[←-⇿☀-➿⬀-⯿️＋★☐]|[\uD83C-\uDBFF][\uDC00-\uDFFF]/g;

  function ownText(el) {
    if (el.hasAttribute("data-say")) return el.getAttribute("data-say");
    var out = "";
    el.childNodes.forEach(function (n) {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1 && !n.matches(BLOCKS) && !n.matches(SKIP)) out += ownText(n);
    });
    return out;
  }
  function speakable(text) {
    text = text.replace(SYMBOLS, " ").replace(/\s·\s/g, ", ");
    PRONOUNCE.forEach(function (p) { text = text.replace(p[0], p[1]); });
    return text.replace(/\s+/g, " ").replace(/ ([,.:;!?])/g, "$1").trim();
  }
  function collect() {
    var main = document.querySelector("main");
    var list = [];
    main.querySelectorAll(BLOCKS).forEach(function (el) {
      if (el.closest(SKIP)) return;
      if (el.parentElement.closest("[data-say]")) return;
      var text = speakable(ownText(el));
      if (text && el.classList.contains("prompt")) text = "«" + text + "»";
      else if (text && !/[.!?:»;]$/.test(text)) text += ".";
      if (text) list.push({ el: el, text: text });
    });
    return list;
  }

  var playBtn = document.getElementById("tts-play");
  var stopBtn = document.getElementById("tts-stop");
  var rateBtn = document.getElementById("tts-rate");
  var blocks = [], index = 0, playing = false, slow = false, voice = null;

  function pickVoice() {
    var voices = synth.getVoices();
    var ru = voices.filter(function (v) { return /^ru/i.test(v.lang); });
    voice = ru.find(function (v) { return v.localService; }) || ru[0] || null;
    if (voices.length && !voice) {
      status.textContent = "На этом устройстве не найден русский голос. Его можно включить в настройках телефона: «Синтез речи» или «Озвучивание текста».";
    }
  }
  pickVoice();
  if (typeof synth.onvoiceschanged !== "undefined") synth.onvoiceschanged = pickVoice;

  function mark(i) {
    blocks.forEach(function (b) { b.el.classList.remove("tts-reading"); });
    if (blocks[i]) {
      blocks[i].el.classList.add("tts-reading");
      blocks[i].el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }
  function setButtons() {
    playBtn.textContent = playing ? "⏸ Пауза" : (index > 0 ? "▶ Продолжить" : "▶ Слушать страницу");
    playBtn.setAttribute("aria-pressed", String(playing));
    stopBtn.hidden = !(playing || index > 0);
  }
  function speakNext() {
    if (!playing) return;
    if (index >= blocks.length) { stop(); status.textContent = "Страница прочитана до конца."; return; }
    var u = new SpeechSynthesisUtterance(blocks[index].text);
    u.lang = "ru-RU";
    if (voice) u.voice = voice;
    u.rate = slow ? 0.75 : 0.95;
    u.onend = function () { if (playing) { index += 1; speakNext(); } };
    u.onerror = function (e) {
      if (e.error === "interrupted" || e.error === "canceled") return;
      playing = false; setButtons();
      status.textContent = "Не получилось прочитать вслух на этом устройстве.";
    };
    mark(index);
    synth.speak(u);
  }
  function play() {
    if (!blocks.length) blocks = collect();
    status.textContent = "";
    playing = true; setButtons();
    synth.cancel();
    speakNext();
  }
  function pause() {
    /* «Пауза» = остановить и запомнить место: так надёжнее, чем synth.pause() на Android */
    playing = false; synth.cancel(); setButtons();
  }
  function stop() {
    playing = false; synth.cancel(); index = 0; mark(-1); setButtons();
  }

  playBtn.addEventListener("click", function () { playing ? pause() : play(); });
  stopBtn.addEventListener("click", function () { stop(); status.textContent = ""; });
  rateBtn.addEventListener("click", function () {
    slow = !slow;
    rateBtn.setAttribute("aria-pressed", String(slow));
    rateBtn.textContent = slow ? "🐢 Медленно: включено" : "🐢 Медленнее";
    if (playing) { synth.cancel(); speakNext(); }
  });
  /* Если на странице есть запись диктора, не даём двум голосам звучать одновременно */
  var audio = bar.querySelector("audio");
  if (audio) {
    audio.addEventListener("play", function () { if (playing) pause(); });
    playBtn.addEventListener("click", function () { if (!audio.paused) audio.pause(); });
  }
  window.addEventListener("pagehide", function () { synth.cancel(); });
  setButtons();
})();
