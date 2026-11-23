#!/usr/bin/env python3
"""Озвучка уроков диктором через ElevenLabs.

Текст для озвучки берётся из src/*.html по тем же правилам, что и кнопка
«Слушать страницу» на сайте (src/a11y.js): блоки для помощника, таблицы и
кнопки пропускаются, у таблиц читается версия из атрибута data-say.

Примеры:
  python3 tts.py --text                 # только выгрузить тексты в audio-text/ и посчитать символы
  python3 tts.py --voices               # список голосов в аккаунте
  python3 tts.py --voice VOICE_ID       # записать уроки 1–4 в src/audio/*.mp3
  python3 tts.py --voice VOICE_ID urok-2 # записать один урок

Ключ: переменная окружения ELEVENLABS_API_KEY. В облачной сессии Claude ключ
подставляет сетевой прокси, переменная не нужна.
После записи запустите python3 build.py: плеер появится на странице урока.
"""
from html.parser import HTMLParser
from pathlib import Path
import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = Path(__file__).parent
SRC = ROOT / "src"
TEXT_OUT = ROOT / "audio-text"
AUDIO_OUT = SRC / "audio"
DEFAULT_PAGES = ["urok-1", "urok-2", "urok-3", "urok-4"]
API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"
CHUNK = 2500  # символов в одном запросе

VOID = {"br", "hr", "img", "meta", "link", "input", "source"}
BLOCK_TAGS = {"h1", "h2", "h3", "p", "li"}
SKIP_CLASSES = {"helper", "no-print", "pager", "listen-bar"}
PRONOUNCE = [
    (r"\bИИ\b", "И-И"), (r"\bЖКХ\b", "жэ-ка-ха"), (r"\bСМС\b", "эс-эм-эс"),
    (r"\bVPN\b", "ви-пи-эн"), (r"\bУК\b", "у-ка"), (r"\bA4\b", "А-четыре"),
]
SYMBOLS = re.compile(
    "[←-⇿☀-➿⬀-⯿️＋★☐\U0001F000-\U0001FAFF]"
)


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []
        self.classes = set((self.attrs.get("class") or "").split())


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [], None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def is_block(n):
    return n.tag in BLOCK_TAGS or "prompt" in n.classes or "box" in n.classes or "data-say" in n.attrs


def is_skip(n):
    return (
        bool(n.classes & SKIP_CLASSES)
        or n.attrs.get("data-tts") == "skip"
        or n.tag == "table"
        or ("table-wrap" in n.classes and "data-say" not in n.attrs)
    )


def own_text(n):
    if "data-say" in n.attrs:
        return n.attrs["data-say"]
    out = []
    for c in n.children:
        if isinstance(c, str):
            out.append(c)
        elif not is_block(c) and not is_skip(c):
            out.append(own_text(c))
    return "".join(out)


def speakable(text):
    text = SYMBOLS.sub(" ", text).replace(" · ", ", ")
    for pattern, repl in PRONOUNCE:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r" ([,.:;!?])", r"\1", text).strip()


def narration(page: str) -> list[str]:
    html = (SRC / f"{page}.html").read_text(encoding="utf-8")
    tree = Tree()
    tree.feed(html)
    blocks = []

    def walk(n, skipped, in_say):
        for c in n.children:
            if isinstance(c, str):
                continue
            skip = skipped or is_skip(c)
            if is_block(c) and not skip and not in_say:
                text = speakable(own_text(c))
                if text:
                    if "prompt" in c.classes:
                        text = f"«{text}»"
                    elif not text.endswith((".", "!", "?", ":", "»", ";")):
                        text += "."
                    blocks.append(text)
            walk(c, skip, in_say or "data-say" in c.attrs)

    walk(tree.root, False, False)
    return blocks


def chunks(blocks: list[str]) -> list[str]:
    out, cur = [], ""
    for b in blocks:
        if cur and len(cur) + len(b) + 1 > CHUNK:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{b}" if cur else b
    if cur:
        out.append(cur)
    return out


def request(method, path, body=None, accept="application/json"):
    key = os.environ.get("ELEVENLABS_API_KEY", "proxy-injected")
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": accept},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def list_voices():
    data = json.loads(request("GET", "/voices"))
    for v in data.get("voices", []):
        labels = v.get("labels") or {}
        print(f"{v['voice_id']}  {v['name']:<20} {labels.get('gender', '')} {labels.get('accent', '')} {labels.get('language', '')}")


def synthesize(page: str, voice: str, speed: float):
    parts = chunks(narration(page))
    audio = b""
    for i, text in enumerate(parts):
        body = {
            "text": text,
            "model_id": MODEL,
            "voice_settings": {"stability": 0.6, "similarity_boost": 0.75, "style": 0.0, "speed": speed},
        }
        if i > 0:
            body["previous_text"] = parts[i - 1][-500:]
        if i + 1 < len(parts):
            body["next_text"] = parts[i + 1][:500]
        audio += request(
            "POST", f"/text-to-speech/{voice}?output_format=mp3_44100_64", body, accept="audio/mpeg"
        )
        print(f"  {page}: часть {i + 1}/{len(parts)}")
    AUDIO_OUT.mkdir(exist_ok=True)
    (AUDIO_OUT / f"{page}.mp3").write_bytes(audio)
    print(f"  → src/audio/{page}.mp3 ({len(audio) // 1024} КБ)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pages", nargs="*", default=DEFAULT_PAGES)
    ap.add_argument("--text", action="store_true", help="только выгрузить тексты и посчитать символы")
    ap.add_argument("--voices", action="store_true", help="показать голоса аккаунта")
    ap.add_argument("--voice", help="ID голоса ElevenLabs")
    ap.add_argument("--speed", type=float, default=0.9, help="скорость речи, 0.7–1.2 (по умолчанию 0.9)")
    args = ap.parse_args()

    if args.voices:
        list_voices()
        return

    TEXT_OUT.mkdir(exist_ok=True)
    total = 0
    for page in args.pages:
        text = "\n".join(narration(page))
        (TEXT_OUT / f"{page}.txt").write_text(text + "\n", encoding="utf-8")
        total += len(text)
        print(f"{page}: {len(text)} символов")
    print(f"Всего: {total} символов (столько кредитов ElevenLabs уйдёт на запись)")

    if args.text:
        return
    if not args.voice:
        sys.exit("Укажите голос: --voice VOICE_ID (список: python3 tts.py --voices)")
    for page in args.pages:
        synthesize(page, args.voice, args.speed)


if __name__ == "__main__":
    main()
