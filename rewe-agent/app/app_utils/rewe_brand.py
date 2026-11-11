# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""REWE brand compositor: renders pixel-accurate newsletter artwork with Pillow.

A2UI renderers (incl. Gemini Enterprise) draw native components with the host's
own typography and colour palette, so brand-critical surfaces - the REWE logo
header, the red hero panel with its yellow "Stoerer" badge, the red price tags
and the legal footer - are rendered server-side as images with the real REWE
wordmark and bundled fonts. Body copy, product names and CTAs stay native A2UI
text/buttons so they remain accessible and selectable.

Assets (``app/assets``):
  * ``brand/rewe_logo.png`` - official REWE wordmark (Wikimedia Commons,
    public domain, rasterised from ``rewe_logo.svg``).
  * ``fonts/Barlow*.ttf`` - Barlow / Barlow Condensed (SIL OFL 1.1), the closest
    open match to REWE's bold, compact headline grotesk.
"""

from __future__ import annotations

import functools
import io
import math
import os
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# --------------------------------------------------------------------------- #
# Brand tokens
# --------------------------------------------------------------------------- #
REWE_RED = (204, 7, 30)  # #CC071E - official logo red
REWE_RED_DARK = (160, 0, 20)  # #A00014
REWE_YELLOW = (255, 226, 95)  # #FFE25F - "Stoerer" / highlight yellow
REWE_BONUS = (185, 50, 130)  # #B93282 - REWE Bonus magenta
INK = (27, 28, 28)  # #1B1C1C
INK_SOFT = (93, 63, 61)  # #5D3F3D
GREY_BG = (243, 241, 240)
GREY_LINE = (230, 226, 225)
WHITE = (255, 255, 255)

CANVAS_W = 1200  # 2x of a ~600px newsletter column -> crisp on HiDPI

_ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
_FONT_DIR = os.path.join(_ASSET_DIR, "fonts")
_BRAND_DIR = os.path.join(_ASSET_DIR, "brand")


@functools.cache
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(_FONT_DIR, f"{name}.ttf"), size)


@functools.cache
def _logo() -> Image.Image:
    return Image.open(os.path.join(_BRAND_DIR, "rewe_logo.png")).convert("RGBA")


def logo_at_height(height: int) -> Image.Image:
    logo = _logo()
    w = round(logo.width * height / logo.height)
    return logo.resize((w, height), Image.LANCZOS)


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def to_jpeg_bytes(img: Image.Image, quality: int = 88) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(
        buf, format="JPEG", quality=quality, optimize=True, progressive=True
    )
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def _clean(text: Any) -> str:
    s = re.sub(r"[*_`#]+", "", str(text or ""))
    return re.sub(r"[ \t]+", " ", s).strip()


def _text_w(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    spacing: float = 0.0,
) -> float:
    if not spacing:
        return draw.textlength(text, font=font)
    return sum(draw.textlength(ch, font=font) for ch in text) + spacing * max(
        len(text) - 1, 0
    )


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Any,
    spacing: float,
) -> None:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: float
) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            continue
        cur = words[0]
        for w in words[1:]:
            if draw.textlength(f"{cur} {w}", font=font) <= max_w:
                cur = f"{cur} {w}"
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    max_w: float,
    max_h: float,
    max_size: int,
    min_size: int,
    max_lines: int,
    leading: float = 0.98,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """Largest font size whose wrapped text fits into (max_w x max_h)."""
    for size in range(max_size, min_size - 1, -2):
        font = _font(font_name, size)
        lines = _wrap(draw, text, font, max_w)
        line_h = round(size * leading)
        if (
            len(lines) <= max_lines
            and line_h * len(lines) <= max_h
            and all(draw.textlength(ln, font=font) <= max_w for ln in lines)
        ):
            return font, lines, line_h
    font = _font(font_name, min_size)
    lines = _wrap(draw, text, font, max_w)[:max_lines]
    if lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return font, lines, round(min_size * leading)


def _cover(
    img: Image.Image, size: tuple[int, int], centering: tuple[float, float] = (0.5, 0.5)
) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS, centering=centering)


def _contain(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    im = img.convert("RGBA")
    im.thumbnail(box, Image.LANCZOS)
    return im


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255
    )
    return mask


def _shadow(
    size: tuple[int, int], radius: int, blur: int, opacity: int = 70
) -> Image.Image:
    pad = blur * 3
    sh = Image.new("RGBA", (size[0] + pad * 2, size[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        (pad, pad, pad + size[0], pad + size[1]), radius=radius, fill=(0, 0, 0, opacity)
    )
    return sh.filter(ImageFilter.GaussianBlur(blur))


def _gradient_placeholder(size: tuple[int, int], label: str) -> Image.Image:
    """Branded fallback when no photo is available."""
    w, h = size
    img = Image.new("RGB", size, GREY_BG)
    d = ImageDraw.Draw(img)
    for i in range(h):
        t = i / max(h - 1, 1)
        c = tuple(round(GREY_BG[k] * (1 - t) + GREY_LINE[k] * t) for k in range(3))
        d.line([(0, i), (w, i)], fill=c)
    logo = logo_at_height(max(h // 7, 40))
    img.paste(logo, ((w - logo.width) // 2, h // 2 - logo.height), logo)
    if label:
        font, lines, lh = _fit_lines(
            d, _clean(label), "BarlowCondensed-Bold", w * 0.8, h * 0.3, 54, 28, 2
        )
        y = h // 2 + 24
        for ln in lines:
            d.text(
                ((w - d.textlength(ln, font=font)) / 2, y), ln, font=font, fill=INK_SOFT
            )
            y += lh
    return img


def _trim_white(img: Image.Image, threshold: int = 244, pad: int = 12) -> Image.Image:
    """Crop the near-white studio margin around a packshot."""
    gray = img.convert("L").point(lambda v: 255 if v < threshold else 0)
    bbox = gray.getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    return img.crop(
        (
            max(left - pad, 0),
            max(top - pad, 0),
            min(right + pad, img.width),
            min(bottom + pad, img.height),
        )
    )


def _load(img_bytes: bytes | None) -> Image.Image | None:
    if not img_bytes:
        return None
    try:
        im = Image.open(io.BytesIO(img_bytes))
        im.load()
        return im
    except Exception as e:
        print(f"DEBUG: rewe_brand could not decode image: {e}")
        return None


# --------------------------------------------------------------------------- #
# Newsletter sections
# --------------------------------------------------------------------------- #
def render_header(
    date_label: str = "",
    kicker: str = "Dein Markt",
    subline: str = "Dein persönlicher Newsletter",
) -> bytes:
    """White masthead: REWE wordmark, 'Dein Markt' claim, red rule."""
    w, h = CANVAS_W, 196
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    logo = logo_at_height(104)
    img.paste(logo, (56, 40), logo)
    claim_font = _font("BarlowCondensed-ExtraBold", 54)
    d.text((56 + logo.width + 26, 66), kicker, font=claim_font, fill=REWE_RED)
    if date_label:
        f = _font("Barlow-SemiBold", 26)
        tw = _text_w(d, date_label.upper(), f, 2.5)
        _draw_tracked(d, (w - 56 - tw, 64), date_label.upper(), f, INK_SOFT, 2.5)
        f2 = _font("Barlow-Medium", 26)
        sub = subline
        d.text(
            (w - 56 - d.textlength(sub, font=f2), 104),
            sub,
            font=f2,
            fill=(140, 120, 118),
        )
    d.rectangle((0, h - 12, w, h), fill=REWE_RED)
    return to_png_bytes(img)


def render_hero(
    photo_bytes: bytes | None, headline: str, badge_text: str, kicker: str = ""
) -> bytes:
    """Full-bleed photo, slanted REWE-red headline panel, rotated yellow badge."""
    w, h = CANVAS_W, 760
    photo = _load(photo_bytes)
    base = (
        _cover(photo, (w, h), (0.62, 0.5))
        if photo
        else _gradient_placeholder((w, h), "")
    )
    base = base.convert("RGBA")

    # Red panel with a slanted right edge + subtle drop shadow onto the photo.
    panel_w_top, panel_w_bot = int(w * 0.55), int(w * 0.47)
    poly = [(0, 0), (panel_w_top, 0), (panel_w_bot, h), (0, h)]
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 14, y) for x, y in poly], fill=(0, 0, 0, 90))
    base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(14)))
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(panel).polygon(poly, fill=(*REWE_RED, 255))
    base = Image.alpha_composite(base, panel)

    d = ImageDraw.Draw(base)
    x0, text_w = 64, panel_w_bot - 64 - 40
    y = 78
    if kicker:
        kf = _font("Barlow-Bold", 30)
        k = _clean(kicker).upper()
        tw = _text_w(d, k, kf, 3)
        d.rounded_rectangle((x0 - 2, y - 6, x0 + tw + 26, y + 44), radius=8, fill=WHITE)
        _draw_tracked(d, (x0 + 12, y), k, kf, REWE_RED, 3)
        y += 84

    hl = _clean(headline) or "Frisch. Lecker. Für dich."
    font, lines, lh = _fit_lines(
        d,
        hl,
        "BarlowCondensed-ExtraBold",
        text_w,
        h - y - 170,
        118,
        64,
        4,
        leading=0.95,
    )
    for ln in lines:
        d.text((x0 + 3, y + 4), ln, font=font, fill=REWE_RED_DARK)  # depth
        d.text((x0, y), ln, font=font, fill=WHITE)
        y += lh

    # Small white REWE logo lock-up bottom-left of the panel.
    logo = logo_at_height(64)
    frame = Image.new("RGBA", (logo.width + 8, logo.height + 8), (*WHITE, 255))
    frame.paste(logo, (4, 4), logo)
    base.paste(frame, (x0, h - 64 - frame.height), frame)

    # Yellow rotated "Stoerer" badge straddling the panel edge.
    badge = _clean(badge_text)
    if badge:
        dia = 270
        b = Image.new("RGBA", (dia, dia), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b)
        bd.ellipse((0, 0, dia - 1, dia - 1), fill=(*REWE_YELLOW, 255))
        bd.ellipse((10, 10, dia - 11, dia - 11), outline=(*REWE_RED, 255), width=4)
        bf, blines, blh = _fit_lines(
            bd,
            badge,
            "BarlowCondensed-ExtraBold",
            dia * 0.68,
            dia * 0.6,
            56,
            28,
            4,
            leading=0.95,
        )
        by = (dia - blh * len(blines)) / 2 - 4
        for ln in blines:
            bd.text(
                ((dia - bd.textlength(ln, font=bf)) / 2, by),
                ln,
                font=bf,
                fill=REWE_RED_DARK,
            )
            by += blh
        b = b.rotate(9, resample=Image.BICUBIC, expand=True)
        sh = _shadow((dia, dia), dia // 2, 12, 80)
        # Classic flyer placement: top-right corner of the photo.
        bx = w - b.width - 34
        byy = 30
        base.alpha_composite(
            sh,
            (bx - 36 + (b.width - dia) // 2 + 8, byy - 36 + (b.height - dia) // 2 + 14),
        )
        base.alpha_composite(b, (bx, byy))

    return to_jpeg_bytes(base, quality=90)


def render_section_banner(title: str, subtitle: str = "") -> bytes:
    """Red offers banner, e.g. 'Deine Angebote der Woche' + yellow date pill."""
    w, h = CANVAS_W, 250
    img = Image.new("RGB", (w, h), REWE_RED)
    d = ImageDraw.Draw(img)
    # Diagonal light stripes for the typical REWE flyer texture.
    for x in range(-h, w, 46):
        d.line([(x, h), (x + h, 0)], fill=(212, 24, 46), width=14)
    font, lines, lh = _fit_lines(
        d, _clean(title), "BarlowCondensed-ExtraBold", w - 140, 120, 92, 50, 1
    )
    y = 30
    for ln in lines:
        d.text((60, y), ln, font=font, fill=WHITE)
        y += lh
    y += 14
    if subtitle:
        sf = _font("Barlow-Bold", 32)
        s = _clean(subtitle)
        tw = d.textlength(s, font=sf)
        d.rounded_rectangle(
            (60, y + 14, 60 + tw + 40, y + 66), radius=26, fill=REWE_YELLOW
        )
        d.text((80, y + 20), s, font=sf, fill=REWE_RED_DARK)
    return to_png_bytes(img)


def _split_price(price: str) -> tuple[str, str]:
    s = str(price or "").replace("€", "").replace("EUR", "").strip()
    s = s.replace(",", ".")
    try:
        val = float(re.findall(r"\d+(?:\.\d+)?", s)[0])
    except (IndexError, ValueError):
        return ("1", "99")
    euros, cents = f"{val:.2f}".split(".")
    return euros, cents


def _price_tag(price: str, unit: str = "") -> Image.Image:
    """REWE-style red price tag: big euros, superscript cents, unit line."""
    euros, cents = _split_price(price)
    ef = _font("BarlowCondensed-Black", 210)
    cf = _font("BarlowCondensed-Black", 104)
    uf = _font("Barlow-SemiBold", 38)
    u = _clean(unit)[:16]
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    ebox = probe.textbbox((0, 0), euros, font=ef, anchor="ls")
    cbox = probe.textbbox((0, 0), cents, font=cf, anchor="ls")
    ew, cw = ebox[2] - ebox[0], cbox[2] - cbox[0]
    uw = probe.textlength(u, font=uf) if u else 0
    pad, dot_w = 30, 42
    cap_h = -ebox[1]
    tag_h = cap_h + 2 * pad + 6
    tag_w = int(pad + ew + dot_w + max(cw, uw) + pad)
    tag = Image.new("RGBA", (tag_w, tag_h), (0, 0, 0, 0))
    td = ImageDraw.Draw(tag)
    td.rounded_rectangle((0, 0, tag_w - 1, tag_h - 1), radius=22, fill=(*REWE_RED, 255))
    base_y = tag_h - pad
    td.text((pad - ebox[0], base_y), euros, font=ef, fill=WHITE, anchor="ls")
    dx = pad + ew + 6
    td.ellipse((dx, base_y - 22, dx + 22, base_y), fill=WHITE)
    cx = pad + ew + dot_w
    top = base_y - cap_h
    td.text((cx - cbox[0], top - cbox[1]), cents, font=cf, fill=WHITE, anchor="ls")
    if u:
        td.text((cx, base_y), u, font=uf, fill=(255, 222, 218), anchor="ls")
    return tag


def render_product_tile(
    photo_bytes: bytes | None,
    name: str,
    price: str,
    badge: str = "Aktion",
    discount: str = "",
    bonus: str = "",
    unit: str = "",
) -> bytes:
    """Square offer tile: packshot, AKTION ribbon, Stoerer, REWE price tag.

    Tiles are displayed at roughly 1/3 of their pixel size in a 2-up grid, so
    all labels are drawn large.
    """
    w = h = 900
    img = Image.new("RGBA", (w, h), (*WHITE, 255))
    photo = _load(photo_bytes)
    box_w, box_h, box_top = int(w * 0.80), int(h * 0.66), 120
    if photo is not None:
        floor = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(floor).ellipse(
            (200, box_top + box_h - 40, w - 200, box_top + box_h + 20),
            fill=(0, 0, 0, 34),
        )
        img = Image.alpha_composite(img, floor.filter(ImageFilter.GaussianBlur(22)))
        shot = _contain(_trim_white(photo.convert("RGB")), (box_w, box_h))
        img.paste(shot, ((w - shot.width) // 2, box_top + (box_h - shot.height) // 2))
    else:
        ph = _gradient_placeholder((box_w, box_h - 40), name)
        ph = ph.convert("RGBA")
        img.paste(ph, ((w - ph.width) // 2, box_top), _rounded_mask(ph.size, 24))
    d = ImageDraw.Draw(img)

    if badge:  # AKTION ribbon, top-left
        rf = _font("BarlowCondensed-ExtraBold", 64)
        label = _clean(badge).upper()
        tw = _text_w(d, label, rf, 3)
        d.polygon([(0, 30), (tw + 92, 30), (tw + 62, 112), (0, 112)], fill=REWE_RED)
        _draw_tracked(d, (32, 34), label, rf, WHITE, 3)

    if discount:  # yellow Stoerer, top-right
        dia = 230
        disc = Image.new("RGBA", (dia, dia), (0, 0, 0, 0))
        dd = ImageDraw.Draw(disc)
        dd.ellipse((0, 0, dia - 1, dia - 1), fill=(*REWE_YELLOW, 255))
        df, dl, dlh = _fit_lines(
            dd,
            _clean(discount),
            "BarlowCondensed-Black",
            dia * 0.80,
            dia * 0.62,
            96,
            40,
            2,
        )
        dy = (dia - dlh * len(dl)) / 2 - 6
        for ln in dl:
            dd.text(
                ((dia - dd.textlength(ln, font=df)) / 2, dy), ln, font=df, fill=REWE_RED
            )
            dy += dlh
        disc = disc.rotate(-10, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(
            _shadow((dia, dia), dia // 2, 10, 60), (w - disc.width - 50, 0)
        )
        img.alpha_composite(disc, (w - disc.width - 22, 14))

    tag = _price_tag(price, unit).rotate(3, resample=Image.BICUBIC, expand=True)
    tx, ty = w - tag.width - 26, h - tag.height - 26
    img.alpha_composite(_shadow(tag.size, 22, 12, 70), (tx - 30, ty - 22))
    img.alpha_composite(tag, (tx, ty))

    if bonus:  # REWE Bonus pill, bottom-left
        bf = _font("Barlow-Bold", 44)
        btxt = _clean(bonus)
        tw = d.textlength(btxt, font=bf)
        y0, y1 = h - 128, h - 50
        d.rounded_rectangle((28, y0, 28 + tw + 124, y1), radius=39, fill=REWE_BONUS)
        cx, cy = 28 + 42, (y0 + y1) // 2
        d.ellipse((cx - 28, cy - 28, cx + 28, cy + 28), fill=WHITE)
        ro, ri = 20, 8.5
        d.polygon(
            [
                (
                    cx
                    + (ro if k % 2 == 0 else ri) * math.cos(math.radians(-90 + k * 36)),
                    cy
                    + (ro if k % 2 == 0 else ri) * math.sin(math.radians(-90 + k * 36)),
                )
                for k in range(10)
            ],
            fill=REWE_BONUS,
        )
        d.text((28 + 92, cy), btxt, font=bf, fill=WHITE, anchor="lm")
    return to_jpeg_bytes(img, quality=90)


def render_promo_tile(
    blurb: str = "Mit jedem Einkauf Guthaben sammeln und beim "
    "nächsten Einkauf einlösen.",
    button: str = "Jetzt in der App",
) -> bytes:
    """Brand filler tile (REWE Bonus app promo) to keep the 2-up grid even."""
    w = h = 900
    img = Image.new("RGB", (w, h), REWE_BONUS)
    d = ImageDraw.Draw(img)
    for x in range(-h, w, 60):
        d.line([(x, h), (x + h, 0)], fill=(196, 66, 143), width=18)
    logo = logo_at_height(92)
    frame = Image.new("RGBA", (logo.width + 12, logo.height + 12), (*WHITE, 255))
    frame.paste(logo, (6, 6), logo)
    img.paste(frame, (70, 80), frame)
    f = _font("BarlowCondensed-ExtraBold", 132)
    y = 250
    for ln in ("REWE", "Bonus"):
        d.text((70, y), ln, font=f, fill=WHITE)
        y += 124
    sf = _font("Barlow-SemiBold", 40)
    for ln in _wrap(d, blurb, sf, w - 160):
        d.text((70, y + 40), ln, font=sf, fill=(255, 235, 245))
        y += 52
    bf = _font("Barlow-Bold", 38)
    bw = d.textlength(button, font=bf)
    d.rounded_rectangle(
        (70, h - 150, 70 + bw + 68, h - 74), radius=38, fill=REWE_YELLOW
    )
    d.text((104, h - 136), button, font=bf, fill=REWE_RED_DARK)
    return to_jpeg_bytes(img, quality=90)


def render_footer(
    legal_lines: list[str] | None = None,
    links: str = "Impressum   ·   Datenschutz   ·   Kontakt   ·   "
    "Newsletter abbestellen",
) -> bytes:
    """Grey legal footer with the REWE wordmark."""
    w, h = CANVAS_W, 330
    img = Image.new("RGB", (w, h), (234, 232, 231))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, 10), fill=REWE_RED)
    logo = logo_at_height(70)
    img.paste(logo, ((w - logo.width) // 2, 46), logo)
    lf = _font("Barlow-SemiBold", 28)
    d.text(((w - d.textlength(links, font=lf)) / 2, 146), links, font=lf, fill=INK)
    lines = legal_lines or [
        "REWE Markt GmbH · Domstraße 20 · 50668 Köln",
        "*Angebote gültig in teilnehmenden Märkten. Abgabe nur in haushaltsüblichen "
        "Mengen, solange der Vorrat reicht.",
    ]
    f = _font("Barlow-Regular", 24)
    y = 204
    for ln in lines:
        for sub in _wrap(d, ln, f, w - 160):
            d.text(
                ((w - d.textlength(sub, font=f)) / 2, y),
                sub,
                font=f,
                fill=(110, 100, 98),
            )
            y += 34
    return to_png_bytes(img)
