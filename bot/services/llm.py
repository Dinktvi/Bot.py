import requests

from .. import config

SYSTEM_PROMPT = (
    "You are the AI assistant of a Telegram bot that helps users create Telegram bots, "
    "write scenarios and scripts. Answer helpfully, concisely, in the language of the user. "
    "If you cannot help with the question, say so honestly and suggest contacting human support."
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
    return bool(config.LLM_API_KEY)


def ask(prompt, lang):
    if not is_configured():
        return None
    try:
        resp = requests.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT + f" (Reply in {'Russian' if lang=='ru' else 'English'}.)"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 600,
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text
    except Exception as e:
        print(f"[llm] error: {e}")
        return None


def should_escalate(answer):
    if not answer:
        return True
    low = answer.lower()
    return any(m in low for m in ESCALATION_MARKERS)
