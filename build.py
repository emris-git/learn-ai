#!/usr/bin/env python3
"""Собирает сайт: оборачивает фрагменты из src/ в общий шаблон и кладёт в site/.
Стили берутся из src/style.css.

Каждый фрагмент начинается со строки-заголовка:
<!-- title: Заголовок страницы | description: Описание | body: sheet -->
Поле body необязательно (sheet — режим шпаргалки для печати).

Запуск: python3 build.py
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).parent
SRC = ROOT / "src"
OUT = ROOT / "site"
SITE_NAME = "ИИ — это просто"

TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="style.css">
</head>
<body{body_class}>
<header class="site-header">
  <div class="inner">
    <a class="logo" href="index.html">{site_name}</a>
    <nav class="site-nav" aria-label="Разделы">
      <a href="pomoshchniku.html">Для помощника</a>
      <a href="index.html#uroki">Уроки</a>
      <a href="instrumenty.html">Инструменты</a>
    </nav>
  </div>
</header>
<main>
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


def build() -> None:
    OUT.mkdir(exist_ok=True)
    shutil.copy(SRC / "style.css", OUT / "style.css")
    count = 0
    for src in sorted(SRC.glob("*.html")):
        text = src.read_text(encoding="utf-8")
        match = HEADER_RE.match(text)
        if not match:
            raise SystemExit(f"{src.name}: нет строки-заголовка <!-- title: ... -->")
        meta = parse_meta(match.group(1))
        title = meta.get("title", SITE_NAME)
        full_title = title if title == SITE_NAME else f"{title} — {SITE_NAME}"
        body = meta.get("body")
        html = TEMPLATE.format(
            title=full_title,
            description=meta.get("description", ""),
            body_class=f' class="{body}"' if body else "",
            site_name=SITE_NAME,
            content=text[match.end():].rstrip(),
        )
        (OUT / src.name).write_text(html, encoding="utf-8")
        count += 1
    print(f"Собрано страниц: {count} → {OUT}")


if __name__ == "__main__":
    build()
