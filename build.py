#!/usr/bin/env python3
"""Собирает сайт: оборачивает фрагменты из src/ в общий шаблон и кладёт в site/.

Каждый фрагмент начинается со строки-заголовка:
<!-- title: Заголовок страницы | description: Описание | body: sheet -->
Поле body необязательно (sheet — режим шпаргалки для печати).

Что ещё делает сборка:
- копирует src/style.css, src/a11y.js и записи диктора src/audio/*.mp3;
- добавляет панель «Для слабовидящих» и блок «Прослушать страницу»
  (если есть src/audio/<страница>.mp3, в блоке появится запись диктора);
- проставляет scope у заголовков таблиц и aria-current у текущего пункта меню.

Запуск: python3 build.py
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = ROOT / "site"
SITE_NAME = "ИИ — это просто"

NAV = [
    ("pomoshchniku.html", "Для помощника"),
    ("index.html#uroki", "Уроки"),
    ("instrumenty.html", "Инструменты"),
]

# Применяет сохранённые настройки до отрисовки, чтобы страница не «мигала»
PRELOAD = (
    "<script>(function(){try{var d=document.documentElement;"
    "['size','contrast','spacing'].forEach(function(k){var v=localStorage.getItem('a11y-'+k);"
    "if(v)d.setAttribute('data-'+k,v);});}catch(e){}})();</script>"
)

A11Y_PANEL = """<div id="a11y-panel" class="a11y-panel" hidden>
  <div class="inner">
    <fieldset>
      <legend>Размер текста</legend>
      <div class="option-row">
        <button type="button" class="option" data-set="size" data-value="">А</button>
        <button type="button" class="option size-2" data-set="size" data-value="2" aria-label="А плюс, крупнее">А+</button>
        <button type="button" class="option size-3" data-set="size" data-value="3" aria-label="А два плюса, самый крупный">А++</button>
      </div>
    </fieldset>
    <fieldset>
      <legend>Цвета</legend>
      <div class="option-row">
        <button type="button" class="option" data-set="contrast" data-value="">Обычные</button>
        <button type="button" class="option c-bw" data-set="contrast" data-value="bw">Чёрным по белому</button>
        <button type="button" class="option c-wb" data-set="contrast" data-value="wb">Белым по чёрному</button>
        <button type="button" class="option c-blue" data-set="contrast" data-value="blue">Синим по голубому</button>
      </div>
    </fieldset>
    <fieldset>
      <legend>Расстояние между буквами</legend>
      <div class="option-row">
        <button type="button" class="option" data-set="spacing" data-value="">Обычное</button>
        <button type="button" class="option" data-set="spacing" data-value="wide">Увеличенное</button>
      </div>
    </fieldset>
    <button type="button" class="option" id="a11y-reset">Вернуть как было</button>
  </div>
</div>"""

LISTEN_BAR = """<section class="listen-bar" aria-labelledby="listen-title">
  <h2 id="listen-title">🔊 Прослушать</h2>
{audio}  <div class="tts-controls" hidden>
    <button type="button" class="btn" id="tts-play">▶ Слушать страницу</button>
    <button type="button" class="btn secondary" id="tts-stop" hidden>■ С начала</button>
    <button type="button" class="btn secondary" id="tts-rate" aria-pressed="false">🐢 Медленнее</button>
  </div>
  <p class="tts-status meta" role="status" aria-live="polite"></p>
</section>"""

AUDIO = """  <p class="meta">Запись диктора:</p>
  <audio controls preload="none" src="audio/{name}.mp3">Ваш браузер не воспроизводит аудио.</audio>
  <p class="meta">Или голосом вашего телефона, с подсветкой текста:</p>
"""

TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
{preload}
<link rel="stylesheet" href="style.css">
<script src="a11y.js" defer></script>
</head>
<body{body_class}>
<a class="skip-link" href="#content">Перейти к содержанию</a>
<header class="site-header">
  <div class="inner">
    <a class="logo" href="index.html">{site_name}</a>
    <nav class="site-nav" aria-label="Разделы">
{nav}
    </nav>
    <button type="button" id="a11y-toggle" class="a11y-toggle" aria-expanded="false" aria-controls="a11y-panel"><span aria-hidden="true">👁</span> Для слабовидящих</button>
  </div>
</header>
{panel}
<main id="content" tabindex="-1">
{content}
</main>
<footer class="site-footer">
  <div class="inner">
    {site_name} — бесплатные уроки по ИИ для людей старшего возраста и их близких.
    Материалы можно свободно печатать и раздавать.
  </div>
</footer>
</body>
</html>
"""

HEADER_RE = re.compile(r"^<!--(.*?)-->\s*", re.S)


def parse_meta(raw: str) -> dict:
    meta = {}
    for part in raw.split("|"):
        if ":" in part:
            key, value = part.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def nav_html(page: str) -> str:
    items = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == page else ""
        items.append(f'      <a href="{href}"{current}>{label}</a>')
    return "\n".join(items)


def build() -> None:
    OUT.mkdir(exist_ok=True)
    for asset in ("style.css", "a11y.js"):
        shutil.copy(SRC / asset, OUT / asset)
    if (SRC / "audio").is_dir():
        shutil.copytree(SRC / "audio", OUT / "audio", dirs_exist_ok=True)

    count = 0
    for src in sorted(SRC.glob("*.html")):
        text = src.read_text(encoding="utf-8")
        match = HEADER_RE.match(text)
        if not match:
            raise SystemExit(f"{src.name}: нет строки-заголовка <!-- title: ... -->")
        meta = parse_meta(match.group(1))
        content = text[match.end():].rstrip()
        content = content.replace("<th>", '<th scope="col">')

        body = meta.get("body")
        if body != "sheet":
            name = src.stem
            audio = AUDIO.format(name=name) if (SRC / "audio" / f"{name}.mp3").exists() else ""
            bar = LISTEN_BAR.format(audio=audio)
            content = content.replace("</h1>", "</h1>\n" + bar, 1)

        title = meta.get("title", SITE_NAME)
        html = TEMPLATE.format(
            title=title if title == SITE_NAME else f"{title} — {SITE_NAME}",
            description=meta.get("description", ""),
            preload=PRELOAD,
            body_class=f' class="{body}"' if body else "",
            site_name=SITE_NAME,
            nav=nav_html(src.name),
            panel=A11Y_PANEL,
            content=content,
        )
        (OUT / src.name).write_text(html, encoding="utf-8")
        count += 1
    print(f"Собрано страниц: {count} → {OUT}")


if __name__ == "__main__":
    build()
