import os

from PIL import Image, ImageDraw, ImageFont

from . import config


def _font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _gradient_bg(w, h, top, bottom):
    base = Image.new("RGB", (w, h))
    top = top or (18, 18, 30)
    bottom = bottom or (40, 26, 80)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(0, w, 4):
            base.paste(color, (x, y, x + 4, y + 1))
    return base


def _add_stars(draw, w, h, count=40):
    import random

    rng = random.Random(42)
    for _ in range(count):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(1, 2)
        draw.ellipse((x, y, x + r, y + r), fill=(255, 255, 255, 80))


def _draw_card(img, w, y, h, color, radius=18):
    draw = ImageDraw.Draw(img, "RGBA")
    overlay = Image.new("RGBA", (w, h + 80), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((20, y, w - 20, y + h), radius=radius, fill=color)
    return overlay, od


def generate_main_image():
    """Main menu header banner."""
    w, h = 900, 480
    img = _gradient_bg(w, h, (16, 16, 34), (64, 24, 110))
    draw = ImageDraw.Draw(img, "RGBA")
    _add_stars(draw, w, h)

    f_big = _font(64)
    f_mid = _font(32)

    title = "AI HELPER BOT"
    tw = draw.textlength(title, font=f_big)
    draw.text(((w - tw) / 2, 150), title, font=f_big, fill=(255, 255, 255))

    sub = "Bots \u00b7 Scenarios \u00b7 Scripts"
    sw = draw.textlength(sub, font=f_mid)
    draw.text(((w - sw) / 2, 260), sub, font=f_mid, fill=(200, 170, 255))

    btn = "SUBSCRIPTION"
    bw = draw.textlength(btn, font=f_mid)
    draw.rounded_rectangle(((w - bw) / 2 - 40, 330, (w + bw) / 2 + 40, 400), radius=24, fill=(120, 60, 220))
    btw = draw.textlength(btn, font=f_mid)
    draw.text(((w - btw) / 2, 343), btn, font=f_mid, fill=(255, 255, 255))

    path = os.path.join(config.ASSETS_DIR, "main.png")
    img.save(path)
    return path


def generate_plans_image():
    w, h = 900, 480
    img = _gradient_bg(w, h, (20, 26, 46), (40, 60, 120))
    draw = ImageDraw.Draw(img, "RGBA")
    _add_stars(draw, w, h)
    f_big = _font(56)
    f_mid = _font(30)

    title = "SUBSCRIPTION PLANS"
    tw = draw.textlength(title, font=f_big)
    draw.text(((w - tw) / 2, 60), title, font=f_big, fill=(255, 255, 255))

    cards = [
        ("STANDARD", "75 \u2b50 / month", (70, 110, 200)),
        ("PRO", "150 \u2b50 / month", (200, 120, 60)),
    ]
    cw = (w - 40 - 20) // 2
    for i, (name, price, color) in enumerate(cards):
        x0 = 20 + i * (cw + 20)
        card = Image.new("RGBA", (cw, 300), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, cw, 300), radius=24, fill=(color[0], color[1], color[2], 200))
        nt = draw.textlength(name, font=f_mid)
        cd.text(((cw - nt) / 2, 60), name, font=f_mid, fill=(255, 255, 255))
        pt = draw.textlength(price, font=_font(40))
        cd.text(((cw - pt) / 2, 150), price, font=_font(40), fill=(255, 255, 255))
        cd.text((0, 0), "", font=_font(1), fill=(0, 0, 0))
        img.paste(card, (x0, 120), card)

    path = os.path.join(config.ASSETS_DIR, "plans.png")
    img.save(path)
    return path


def generate_assistant_image():
    w, h = 900, 480
    img = _gradient_bg(w, h, (10, 30, 40), (20, 80, 90))
    draw = ImageDraw.Draw(img, "RGBA")
    _add_stars(draw, w, h)
    f_big = _font(60)
    f_mid = _font(30)
    title = "AI ASSISTANT"
    tw = draw.textlength(title, font=f_big)
    draw.text(((w - tw) / 2, 170), title, font=f_big, fill=(255, 255, 255))
    sub = "Ask anything about bots, scenarios, scripts"
    sw = draw.textlength(sub, font=f_mid)
    draw.text(((w - sw) / 2, 280), sub, font=f_mid, fill=(170, 230, 235))
    path = os.path.join(config.ASSETS_DIR, "assistant.png")
    img.save(path)
    return path


def generate_auction_image():
    w, h = 900, 480
    img = _gradient_bg(w, h, (40, 24, 12), (120, 70, 20))
    draw = ImageDraw.Draw(img, "RGBA")
    _add_stars(draw, w, h)
    f_big = _font(60)
    f_mid = _font(30)
    title = "AUCTION"
    tw = draw.textlength(title, font=f_big)
    draw.text(((w - tw) / 2, 170), title, font=f_big, fill=(255, 255, 255))
    sub = "Bid in Telegram Stars"
    sw = draw.textlength(sub, font=f_mid)
    draw.text(((w - sw) / 2, 280), sub, font=f_mid, fill=(250, 220, 180))
    path = os.path.join(config.ASSETS_DIR, "auction.png")
    img.save(path)
    return path


def generate_all():
    files = [
        generate_main_image(),
        generate_plans_image(),
        generate_assistant_image(),
        generate_auction_image(),
    ]
    return files


if __name__ == "__main__":
    print(generate_all())
