#!/usr/bin/env python3
"""Собирает сайт: оборачивает фрагменты из src/ в общий шаблон и кладёт в site/.

Каждый фрагмент начинается со строки-заголовка:
<!-- title: Заголовок | description: Описание | body: sheet | listen: no -->
- body: sheet — режим шпаргалки для печати;
- listen: no — не добавлять блок «Послушать».

Что ещё делает сборка:
- копирует src/style.css, src/a11y.js и записи диктора src/audio/*.mp3;
- добавляет шапку с меню, панель «Для слабовидящих» и подвал;
- на страницах уроков добавляет «путь по урокам» сверху, кнопки «Послушать»
  и «Шпаргалка», карточку «Следующий урок» снизу;
- заменяет {{icon:имя}} на встроенную SVG-иконку (без внешних файлов);
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

# Иконки в стиле Feather: 24×24, обводка currentColor
ICONS = {
    "arrow": '<path d="M5 12h14M13 5l7 7-7 7"/>',
    "back": '<path d="M19 12H5M11 19l-7-7 7-7"/>',
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>',
    "printer": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>',
    "book": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "chat": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "pen": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    "alert": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/>',
    "star": '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
}


def icon(name: str, cls: str = "icon") -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        f"{ICONS[name]}</svg>"
    )


# Уроки по порядку: файл, полное название, короткое (для «пути»), иконка, время
LESSONS = [
    ("urok-1", "Первый разговор с ИИ", "Первый разговор", "chat", "40 минут"),
    ("urok-2", "ИИ понимает фотографии", "Фотографии", "camera", "40 минут"),
    ("urok-3", "Можно ли верить ИИ. Мошенники", "Проверка и мошенники", "shield", "50 минут"),
    ("urok-4", "ИИ в повседневных делах", "Повседневные дела", "pen", "50 минут"),
]

NAV = [
    ("index.html#uroki", "Уроки", "book"),
    ("pomoshchniku.html", "Учу родителей", "users"),
    ("instrumenty.html", "Какой ИИ выбрать", "grid"),
]

# Применяет сохранённые настройки до отрисовки, чтобы страница не «мигала»
PRELOAD = (
    "<script>(function(){try{var d=document.documentElement;"
    "['size','contrast','spacing'].forEach(function(k){var v=localStorage.getItem('a11y-'+k);"
    "if(v)d.setAttribute('data-'+k,v);});}catch(e){}})();</script>"
)

A11Y_PANEL = """<div id="a11y-panel" class="a11y-panel" hidden>
  <div class="inner">
    <div class="a11y-grid">
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
    </div>
    <button type="button" class="link-btn" id="a11y-reset">Вернуть как было</button>
  </div>
</div>"""

LISTEN_BAR = """<section class="listen-bar" aria-labelledby="listen-title" data-tts="skip">
  <h2 id="listen-title">{volume} {heading}</h2>
{audio}  <div class="tts-controls" hidden>
    <button type="button" class="btn {play_cls}" id="tts-play" data-label="{play_label}">▶ {play_label}</button>
    <button type="button" class="btn secondary" id="tts-rate" aria-pressed="false">Медленнее</button>
    <button type="button" class="btn secondary" id="tts-stop" hidden>С начала</button>
  </div>
  <p class="tts-status meta" role="status" aria-live="polite"></p>
</section>"""

AUDIO = """  <audio controls preload="none" src="audio/{name}.mp3">Ваш браузер не воспроизводит аудио.</audio>
  <p class="listen-hint">Или пусть телефон читает вслух и подсвечивает текст:</p>
"""

TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="theme-color" content="#1f5fa8">
{preload}
<link rel="stylesheet" href="style.css">
<script src="a11y.js" defer></script>
</head>
<body{body_class}>
<a class="skip-link" href="#content">Перейти к содержанию</a>
<div class="topbar">
  <div class="inner">
    <button type="button" id="a11y-toggle" class="topbar-btn" aria-expanded="false" aria-controls="a11y-panel">{eye} Версия для слабовидящих</button>
  </div>
</div>
{panel}
<header class="site-header">
  <div class="inner">
    <a class="logo" href="index.html" aria-label="{site_name} — на главную"><span class="logo-mark" aria-hidden="true">ИИ</span><span class="logo-text">это просто</span></a>
    <nav class="site-nav" aria-label="Разделы">
{nav}
    </nav>
  </div>
</header>
<main id="content" tabindex="-1">
{content}
</main>
<footer class="site-footer">
  <div class="inner">
    <nav class="footer-nav" aria-label="Разделы внизу страницы">
      <a href="index.html">Главная</a>
      <a href="index.html#uroki">Уроки</a>
      <a href="pomoshchniku.html">Учу родителей</a>
      <a href="instrumenty.html">Какой ИИ выбрать</a>
    </nav>
    <p>{site_name} — бесплатные уроки по ИИ для людей старшего возраста и их близких. Материалы можно свободно печатать и раздавать.</p>
  </div>
</footer>
</body>
</html>
"""

HEADER_RE = re.compile(r"^<!--(.*?)-->\s*", re.S)
ICON_RE = re.compile(r"\{\{icon:([a-z]+)\}\}")


def parse_meta(raw: str) -> dict:
    meta = {}
    for part in raw.split("|"):
        if ":" in part:
            key, value = part.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def section_of(page: str) -> str:
    if page.startswith(("urok-", "shpargalka-")):
        return "index.html#uroki"
    return page


def nav_html(page: str) -> str:
    current_href = section_of(page)
    items = []
    for href, label, ico in NAV:
        current = ' aria-current="page"' if href == current_href else ""
        items.append(f'      <a href="{href}"{current}>{icon(ico)}<span>{label}</span></a>')
    return "\n".join(items)


def stepper(index: int) -> str:
    items = []
    for i, (name, _title, short, _ico, _time) in enumerate(LESSONS):
        state = "current" if i == index else ("before" if i < index else "after")
        current = ' aria-current="step"' if i == index else ""
        items.append(
            f'    <li class="{state}"><a href="{name}.html"{current}>'
            f'<span class="step-num">{i + 1}</span><span class="step-title">{short}</span></a></li>'
        )
    _name, _title, _short, _ico, time = LESSONS[index]
    return (
        '<nav class="stepper" aria-label="Уроки по порядку" data-tts="skip">\n'
        '  <ol>\n' + "\n".join(items) + "\n  </ol>\n</nav>\n"
        f'<p class="lesson-badge" data-tts="skip">{icon("clock")} Урок {index + 1} из {len(LESSONS)} · {time}</p>\n'
    )


def next_lesson(index: int) -> str:
    links = []
    if index + 1 < len(LESSONS):
        name, title, _short, ico, _time = LESSONS[index + 1]
        card = (
            f'<a class="next-card" href="{name}.html"><span class="next-icon">{icon(ico)}</span>'
            f'<span class="next-body"><span class="next-label">Следующий урок</span>'
            f"<strong>Урок {index + 2}. {title}</strong></span>{icon('arrow', 'icon next-arrow')}</a>"
        )
    else:
        card = (
            f'<a class="next-card" href="index.html#uroki"><span class="next-icon">{icon("check")}</span>'
            f'<span class="next-body"><span class="next-label">Вы прошли все 4 урока</span>'
            f"<strong>Вернуться к списку уроков</strong></span>{icon('arrow', 'icon next-arrow')}</a>"
        )
    if index > 0:
        prev = LESSONS[index - 1]
        links.append(f'<a href="{prev[0]}.html">{icon("back")} Урок {index}. {prev[2]}</a>')
    links.append(f'<a href="index.html#uroki">{icon("book")} Все уроки</a>')
    return (
        '<nav class="next-lesson" aria-label="Дальше" data-tts="skip">\n'
        f"  {card}\n  <div class=\"lesson-links\">{' '.join(links)}</div>\n</nav>"
    )


def build() -> None:
    OUT.mkdir(exist_ok=True)
    for asset in ("style.css", "a11y.js"):
        shutil.copy(SRC / asset, OUT / asset)
    if (SRC / "audio").is_dir():
        shutil.copytree(SRC / "audio", OUT / "audio", dirs_exist_ok=True)

    lesson_index = {name: i for i, (name, *_rest) in enumerate(LESSONS)}
    count = 0
    for src in sorted(SRC.glob("*.html")):
        text = src.read_text(encoding="utf-8")
        match = HEADER_RE.match(text)
        if not match:
            raise SystemExit(f"{src.name}: нет строки-заголовка <!-- title: ... -->")
        meta = parse_meta(match.group(1))
        name = src.stem
        content = text[match.end():].rstrip()
        content = content.replace("<th>", '<th scope="col">')

        body = meta.get("body")
        idx = lesson_index.get(name)
        if body != "sheet" and meta.get("listen") != "no":
            has_audio = (SRC / "audio" / f"{name}.mp3").exists()
            bar = LISTEN_BAR.format(
                volume=icon("volume"),
                heading="Послушать урок" if idx is not None else "Послушать страницу",
                audio=AUDIO.format(name=name) if has_audio else "",
                play_cls="secondary" if has_audio else "",
                play_label="Читать голосом телефона" if has_audio else "Слушать страницу",
            )
            if idx is not None:
                bar += (
                    f'\n<div class="lesson-actions" data-tts="skip"><a class="btn secondary" '
                    f'href="shpargalka-{idx + 1}.html">{icon("printer")} Шпаргалка для печати</a></div>'
                )
            content = content.replace("</h1>", "</h1>\n" + bar, 1)
        if idx is not None:
            content = stepper(idx) + content + "\n\n" + next_lesson(idx)

        content = ICON_RE.sub(lambda m: icon(m.group(1)), content)
        title = meta.get("title", SITE_NAME)
        html = TEMPLATE.format(
            title=title if title == SITE_NAME else f"{title} — {SITE_NAME}",
            description=meta.get("description", ""),
            preload=PRELOAD,
            body_class=f' class="{body}"' if body else "",
            site_name=SITE_NAME,
            eye=icon("eye"),
            nav=nav_html(src.name),
            panel=A11Y_PANEL,
            content=content,
        )
        (OUT / src.name).write_text(html, encoding="utf-8")
        count += 1
    print(f"Собрано страниц: {count} → {OUT}")


if __name__ == "__main__":
    build()
