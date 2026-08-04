# Telegram Bot Project Context (don't lose this!)

This file preserves the project spec so it survives between sessions. Read it first when working on this project.

## What is this project
A Telegram bot (shop/helper) for a bot-building service. It sells subscriptions in Telegram Stars and includes:
- An assistant that helps create bots, scenarios, and writes scripts
- A storefront with subscription tiers
- Admin panel
- AI support chat

## Bot token
```
8703346061:AAHK0-QBCy4UlAaGOtli7qpmHGVjC5pWKv4
```
(Telegram bot token, provided by the owner. Store in `config` / `.env`, never expose in chat logs.)

## Global admin (main admin)
```
6382264272
```

## Pricing (Telegram Stars)
Standard ("Обычный"):
- 1 month: 75 stars
- 3 months: 125 stars
- 6 months: 250 stars
- 12 months (year): 500 stars

Pro:
- 1 month: 150 stars
- 3 months: 300 stars
- 6 months: 600 stars
- 12 months (year): 1250 stars

## Features (spec)
- At start: language selection — English or Russian (EN/RU), nice non-ugly UI
- Bot itself generates the menu photos/images
- Admin panel opened with command `/console`
  - Add subscription promo code
  - Add discounts
  - Add auction (аукцион)
  - Broadcast/mailing (рассылка)
  - Add sponsors
- AI assistant for user support: answers questions; if the AI can't handle it ("плохо"), escalate to admins
- Complaint/support channel to admins
- AI assistant creates scripts as files (data/scripts/script_<uid>_*.py) and sends them as documents;
  does not repeat full code in follow-ups; helps with hosting deployment guides
- Profile menu (main menu → Start → Profile): shows GitHub link status, script count, AI requests
- GitHub OAuth connect/disconnect, My Files list (download/delete), push scripts to GitHub
  (creates repo `my-bot-scripts`, uploads via GitHub Contents API, base64)
- Admin "Grant subscription" (выдать подписку): by ID or @username, plan+period, notifies the user

## Tech decisions
- Python 3.11 + aiogram 3.x
- SQLite for persistence (users, subscriptions, codes, discounts, auction, sponsors, tickets,
  chat_history, github_accounts)
- Telegram Stars payments via `send_invoice` with currency `XTR`
- Images generated with Pillow (no external image APIs)
- LLM for assistant must use `USER_LLM_API_KEY` / `USER_LLM_BASE_URL` / `USER_LLM_MODEL` env vars (user-provided key, NOT the agent environment key)
- GitHub OAuth: aiohttp server (bot/oauth_server.py, port 8080), redirect URI must match
  github.com/settings/developers OAuth App; preview URL changes per session → update .env + GitHub app

## Previous session note
The user previously lost context ("потерял чат") — this file exists so the spec survives.
