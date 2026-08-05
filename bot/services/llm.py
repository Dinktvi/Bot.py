import time

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
    "Then put the actual answer on the next lines. Do not invent exact timings, use a rough estimate."
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


def is_configured():
    return any(p["api_key"] for p in config.AI_PROVIDERS.values())


def available_providers():
    return [pid for pid, p in config.AI_PROVIDERS.items() if p["api_key"]]


def get_provider(provider):
    p = config.AI_PROVIDERS.get(provider)
    if p and p["api_key"]:
        return p
    return config.AI_PROVIDERS[config.DEFAULT_AI_PROVIDER]


def ask(prompt, lang, history=None, provider=None):
    if not is_configured():
        return None, 0.0
    p = get_provider(provider or config.DEFAULT_AI_PROVIDER)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f" (Reply in {'Russian' if lang=='ru' else 'English'}.)"},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    last_err = None
    t0 = time.time()
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{p['base_url'].rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {p['api_key']}"},
                json={
                    "model": p["model"],
                    "messages": messages,
                    "max_tokens": 1200,
                    "temperature": 0.7,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            elapsed = time.time() - t0
            return text, elapsed
        except Exception as e:
            last_err = e
            print(f"[llm:{p['model']}] attempt {attempt + 1} error: {e}")
            time.sleep(1 + attempt)
    print(f"[llm:{p['model']}] giving up: {last_err}")
    return None, time.time() - t0


def should_escalate(answer):
    if not answer:
        return True
    low = answer.lower()
    return any(m in low for m in ESCALATION_MARKERS)
