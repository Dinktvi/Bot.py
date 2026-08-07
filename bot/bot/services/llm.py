import re
import time
import urllib.parse
from pathlib import Path

import requests

from .. import config

SYSTEM_PROMPT = (
    "You are the AI assistant of a Telegram bot that helps users create Telegram bots, "
    "write scenarios, scripts and deploy bots to hosting. "
    "You remember the whole conversation history.\n"
    "RULES:\n"
    "1. When the user asks for a script/bot code, produce the COMPLETE, ready-to-run file "
    "in a single fenced code block (```python ... ```). The code block will be saved to a file "
    "and sent to the user automatically, so put the full code there.\n"
    "2. IMPORTANT: In follow-up messages do NOT repeat the whole script again. "
    "Only reply with the changed parts / snippets / fixes. If nothing changed in code, "
    "just explain in words.\n"
    "3. You can also help with DEPLOYING a bot to hosting: explain step-by-step how to run "
    "a Telegram bot on Termux (Android), a VPS, Railway, Render, Oracle Cloud Free, serv00.com, "
    "or the user's own computer. Give concrete commands and config examples in code blocks.\n"
    "4. Answer helpfully, concisely, in the language of the user. "
    "If you cannot help with the question, say so honestly and suggest contacting human support.\n"
    "5. Before your real answer write a short status line on its own line that describes "
    "what you are doing right now and an estimate, e.g. "
    "\"⚙️ Пишу готовый код бота... ~10 сек\" or \"⚙️ Объясняю шаги деплоя... ~5 сек\". "
    "Then put the actual answer on the next lines. Do not invent exact timings, use a rough estimate.\n"
    "6. WEB BROWSING TOOL. You can browse the internet yourself. "
    "If the user asks about something that needs up-to-date info, a specific website, prices, "
    "docs, news or verification, use this tool BEFORE answering: write on its own line "
    "exactly the tag [FETCH:https://example.com/path] and keep your answer short. "
    "The page text will be inserted into the conversation automatically and you can then "
    "finish your real answer. Only fetch real, public, safe URLs. Never fetch telegram links "
    "that require login, never guess internal IPs.\n"
    "7. IMAGE GENERATION TOOL. You can generate images. "
    "If the user asks for a picture, logo, avatar, meme, illustration, diagram or any image, "
    "write exactly [IMAGE:detailed english prompt describing the image] on its own line. "
    "Be very specific: style, colors, objects, composition. Keep the prompt in English.\n"
)

ESCALATION_MARKERS = [
    "can't help",
    "cannot help",
    "не могу помочь",
    "не смогу",
    "не знаю",
    "обратитесь",
    "contact support",
    "contact an admin",
    "свяжитесь с",
    "не удалось",
]

FETCH_RE = re.compile(r"\[FETCH:(https?://[^\]]+)\]", re.IGNORECASE)
IMAGE_RE = re.compile(r"\[IMAGE:([^\]]+)\]", re.IGNORECASE)


def is_configured():
    return any(p["api_key"] for p in config.AI_PROVIDERS.values())


def available_providers():
    return [pid for pid, p in config.AI_PROVIDERS.items() if p["api_key"]]


def get_provider(provider=None):
    p = config.AI_PROVIDERS.get(provider or config.DEFAULT_AI_PROVIDER)
    if p and p["api_key"]:
        return p
    return config.AI_PROVIDERS["groq"]


def fetch_url(url, max_chars=None):
    """Fetch a public URL and return readable text (HTML stripped)."""
    max_chars = max_chars or config.WEB_FETCH_MAX_CHARS
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Host247Bot/1.0; +https://t.me/Host_24_7_Bot)"
            },
            timeout=config.WEB_FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type.lower():
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
                tag.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            text = soup.get_text("\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return (f"Title: {title}\n{text}")[:max_chars]
        return resp.text[:max_chars]
    except Exception as e:
        return f"FETCH ERROR: {e}"


def generate_image(prompt):
    """Generate an image via Pollinations (free, no key). Returns local file path."""
    try:
        prompt = (prompt or "").strip()
        if not prompt:
            return None
        safe = urllib.parse.quote(prompt[:500])
        url = f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024&nologo=true&model=flux"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        if "image" not in resp.headers.get("Content-Type", ""):
            return None
        name = f"img_{int(time.time() * 1000)}.jpg"
        path = Path(config.IMAGES_DIR) / name
        path.write_bytes(resp.content)
        return str(path)
    except Exception as e:
        print(f"[llm:image] error: {e}")
        return None


def _chat(messages, p):
    resp = requests.post(
        f"{p['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {p['api_key']}"},
        json={
            "model": p["model"],
            "messages": messages,
            "max_tokens": 1600,
            "temperature": 0.7,
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def ask(prompt, lang, history=None, max_fetches=3):
    """Run the assistant. The model may request web fetches and image generation.

    Returns (answer_text, elapsed, image_paths).
    """
    if not is_configured():
        return None, 0.0, []
    p = get_provider()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f" (Reply in {'Russian' if lang == 'ru' else 'English'}.)"},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    image_paths = []
    t0 = time.time()
    for turn in range(max_fetches + 1):
        try:
            text = _chat(messages, p)
        except Exception as e:
            if turn == 0:
                print(f"[llm:{p['model']}] error: {e}")
                return None, time.time() - t0, []
            break

        fetches = FETCH_RE.findall(text)
        images = IMAGE_RE.findall(text)

        if fetches and turn < max_fetches:
            text_no_tag = FETCH_RE.sub("", text).strip()
            for url in fetches[:2]:
                page = fetch_url(url)
                messages.append({"role": "user", "content": f"[Page content of {url}]\n{page}"})
                messages.append({"role": "assistant", "content": text_no_tag or "..."})
            continue

        if images:
            text = IMAGE_RE.sub("", text).strip()
            for img_prompt in images[:2]:
                path = generate_image(img_prompt)
                if path:
                    image_paths.append(path)

        elapsed = time.time() - t0
        return text, elapsed, image_paths

    elapsed = time.time() - t0
    return text, elapsed, image_paths


def should_escalate(answer):
    if not answer:
        return True
    low = answer.lower()
    return any(m in low for m in ESCALATION_MARKERS)
