# ruff: noqa: RUF001
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
"""End-to-end builder for the REWE A2UI newsletter.

Pipeline (all I/O parallelised):
  1. Load the hero photo saved by ``generate_blog_image`` (ADK artifact).
  2. Fetch/generate one e-commerce packshot per product (Gemini image model,
     cached in GCS by product so repeat runs are instant).
  3. Composite brand artwork with :mod:`rewe_brand` (CPU, worker threads).
  4. Publish every image to GCS and get browser-loadable signed URLs.
  5. Build A2UI messages (:mod:`newsletter_a2ui`) and stash them in temp state;
     ``after_model_callback`` appends them to the agent's final answer.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import os
import re
from typing import Any

from google.genai import types

from app.app_utils import image_host, rewe_brand
from app.app_utils.newsletter_a2ui import build_newsletter_surfaces, stash_pending

_PACKSHOT_MODEL = os.environ.get("PACKSHOT_MODEL", "gemini-3.1-flash-image")
_PACKSHOT_TIMEOUT_S = float(os.environ.get("PACKSHOT_TIMEOUT_S", "75"))
_HERO_ARTIFACT = "blog_hero_image.png"
_WEEKDAYS = {
    "de": ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "header_date": "KW {kw} · {date}",
        "header_sub": "Dein persönlicher Newsletter",
        "kicker": "Für dich, {name}",
        "banner": "Deine Angebote der Woche",
        "valid_until": "Gültig bis {wd} {date}",
        "greeting": "Hallo {name},",
        "greeting_anon": "Hallo,",
        "signoff": "Herzliche Grüße  \n**dein REWE Team**",
        "cta": "Jetzt Angebote entdecken",
        "cta2": "Prospekt ansehen",
        "promo_blurb": "Mit jedem Einkauf Guthaben sammeln und beim nächsten "
        "Einkauf einlösen.",
        "promo_button": "Jetzt in der App",
        "promo_tip": "Bei jedem Einkauf Guthaben sammeln – einfach in der "
        "REWE App aktivieren.",
        "promo_meta": "Exklusiv für REWE Bonus-Kund:innen",
        "footer_links": "Impressum   ·   Datenschutz   ·   Kontakt   ·   "
        "Newsletter abbestellen",
        "footer_legal": "*Angebote gültig in teilnehmenden Märkten. Abgabe nur "
        "in haushaltsüblichen Mengen, solange der Vorrat reicht.",
        "badge_default": "Aktion",
        "ins_title": "Kampagnen-Steckbrief",
        "ins_kw": "SEO-Keywords",
        "ins_primary": "primär",
        "ins_persona": "Persona",
        "ins_diet": "Ernährung",
        "ins_diet_ok": "✅ Alle Produkte geprüft: {tags}",
        "ins_diet_none": "Keine Einschränkungen",
        "ins_hook": "Aufhänger",
        "ins_products": "Produkte",
        "ins_name": "REWE Kampagnen-Insights",
        "hero_alt": "Newsletter-Titelbild",
        "masthead_alt": "REWE – Dein Markt",
    },
    "en": {
        "header_date": "Week {kw} · {date}",
        "header_sub": "Your personal newsletter",
        "kicker": "Just for you, {name}",
        "banner": "Your deals of the week",
        "valid_until": "Valid until {wd} {date}",
        "greeting": "Hi {name},",
        "greeting_anon": "Hi there,",
        "signoff": "Warm regards,  \n**your REWE team**",
        "cta": "Discover this week's deals",
        "cta2": "View the flyer",
        "promo_blurb": "Collect credit with every purchase and redeem it on "
        "your next shop.",
        "promo_button": "Get it in the app",
        "promo_tip": "Collect credit with every shop – just activate it in the "
        "REWE app.",
        "promo_meta": "Exclusive for REWE Bonus members",
        "footer_links": "Imprint   ·   Privacy   ·   Contact   ·   Unsubscribe",
        "footer_legal": "*Offers valid in participating stores while stocks last. "
        "Household quantities only.",
        "badge_default": "Deal",
        "ins_title": "Campaign brief",
        "ins_kw": "SEO keywords",
        "ins_primary": "primary",
        "ins_persona": "Persona",
        "ins_diet": "Diet",
        "ins_diet_ok": "✅ All products checked: {tags}",
        "ins_diet_none": "No restrictions",
        "ins_hook": "Hook",
        "ins_products": "Products",
        "ins_name": "REWE campaign insights",
        "hero_alt": "Newsletter hero image",
        "masthead_alt": "REWE – Dein Markt",
    },
}


def _lang_key(language: str) -> str:
    return "en" if str(language or "").strip().lower().startswith("en") else "de"


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _plain(s: Any) -> str:
    return re.sub(r"[*_`#]+", "", _clean(s))


def _price_str(p: dict[str, Any]) -> str:
    raw = p.get("price") or p.get("price_current")
    if raw in (None, ""):
        return "1.99"
    if isinstance(raw, (int, float)):
        return f"{raw:.2f}"
    return str(raw)


def _de_price(p: str) -> str:
    try:
        return (
            f"{float(re.findall(r'[0-9]+(?:[.,][0-9]+)?', p)[0].replace(',', '.')):.2f}".replace(
                ".", ","
            )
            + "\u00a0€"
        )
    except (IndexError, ValueError):
        return p


def _next_saturday(today: datetime.date | None = None) -> datetime.date:
    today = today or datetime.date.today()
    return today + datetime.timedelta(days=(5 - today.weekday()) % 7 or 7)


def _normalise_products(products: Any) -> list[dict[str, Any]]:
    import json

    if isinstance(products, str):
        try:
            products = json.loads(products)
        except Exception:
            products = []
    out: list[dict[str, Any]] = []
    for item in products or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if isinstance(item, dict) and item.get("name"):
            out.append(dict(item))
    return out[:6]


# --------------------------------------------------------------------------- #
# Image sources
# --------------------------------------------------------------------------- #
async def _load_hero(tool_context: Any) -> bytes | None:
    try:
        part = await tool_context.load_artifact(_HERO_ARTIFACT)
    except Exception as e:
        print(f"DEBUG: newsletter: could not load hero artifact: {e}")
        return None
    blob = getattr(part, "inline_data", None) if part else None
    if not blob or not blob.data:
        return None
    data = blob.data
    return data if isinstance(data, bytes) else base64.b64decode(data)


def _packshot_cache_key(p: dict[str, Any]) -> str:
    ident = f"{_plain(p.get('brand'))}|{_plain(p.get('name'))}".lower()
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()[:32]


def _cache_get(key: str) -> bytes | None:
    bucket = image_host._bucket_name()
    if not bucket:
        return None
    try:
        blob = image_host._storage_client().bucket(bucket).blob(f"packshots/{key}.png")
        return blob.download_as_bytes() if blob.exists() else None
    except Exception as e:
        print(f"DEBUG: packshot cache read failed: {e}")
        return None


def _cache_put(key: str, data: bytes) -> None:
    bucket = image_host._bucket_name()
    if not bucket:
        return
    try:
        image_host._storage_client().bucket(bucket).blob(
            f"packshots/{key}.png"
        ).upload_from_string(data, content_type="image/png")
    except Exception as e:
        print(f"DEBUG: packshot cache write failed: {e}")


async def _generate_packshot(p: dict[str, Any]) -> bytes | None:
    key = _packshot_cache_key(p)
    cached = await asyncio.to_thread(_cache_get, key)
    if cached:
        return cached

    from app.tools import _get_genai_client

    name, brand = _plain(p.get("name")), _plain(p.get("brand"))
    category = _plain(p.get("category_path")).split(">")[-1].strip()
    prompt = (
        f"Professional e-commerce packshot of a German supermarket product: "
        f"'{name}'"
        + (f" by {brand}" if brand else "")
        + (f" (category: {category})" if category else "")
        + ". "
        "Single product, front view, centred, filling ~75% of the frame, on a "
        "seamless pure white (#FFFFFF) studio background with a very soft "
        "natural contact shadow. Realistic retail packaging or the fresh "
        "product itself as sold at REWE, crisp focus, high-key lighting, "
        "photorealistic. No extra props, no hands, no price tags, no watermark."
    )
    try:
        resp = await asyncio.wait_for(
            _get_genai_client().aio.models.generate_content(
                model=_PACKSHOT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1",
                        image_size="1K",
                        output_mime_type="image/png",
                    ),
                ),
            ),
            timeout=_PACKSHOT_TIMEOUT_S,
        )
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else []) or []:
                if part.inline_data is not None and not part.thought:
                    raw = part.inline_data.data
                    data = raw if isinstance(raw, bytes) else base64.b64decode(raw)
                    await asyncio.to_thread(_cache_put, key, data)
                    return data
    except Exception as e:
        print(f"DEBUG: packshot generation failed for '{name}': {e}")
    return None


async def _fetch_url(url: str) -> bytes | None:
    import urllib.request

    def _get() -> bytes | None:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rewe-agent/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read()
        except Exception as e:
            print(f"DEBUG: could not fetch product image {url[:80]}: {e}")
            return None

    return await asyncio.to_thread(_get)


async def _product_photo(p: dict[str, Any]) -> bytes | None:
    url = str(p.get("image_url") or "")
    if url.startswith("https://"):
        data = await _fetch_url(url)
        if data:
            return data
    return await _generate_packshot(p)


# --------------------------------------------------------------------------- #
# Public entry point (called by the ADK tool in app/tools.py)
# --------------------------------------------------------------------------- #
async def build_and_stash_newsletter(
    tool_context: Any,
    *,
    customer_name: str,
    headline: str,
    badge_text: str,
    body_text: str,
    hero_image_alt: str,
    cta_button_text: str,
    valid_until_text: str,
    products: Any,
    seo_keywords: list[str] | None,
    primary_keyword: str,
    persona: str,
    dietary_tags: list[str] | None,
    market_hook: str,
    language: str = "German",
) -> dict[str, Any]:
    lk = _lang_key(language)
    t = STRINGS[lk]
    customer_name = _plain(customer_name)
    items = _normalise_products(products)
    today = datetime.date.today()
    sat = _next_saturday(today)
    date_fmt = "%d.%m.%Y" if lk == "de" else "%d %b %Y"
    valid_until = _plain(valid_until_text) or t["valid_until"].format(
        wd=_WEEKDAYS[lk][sat.weekday()], date=sat.strftime(date_fmt)
    )
    kw = today.isocalendar().week

    hero_task = asyncio.create_task(_load_hero(tool_context))
    photo_tasks = [asyncio.create_task(_product_photo(p)) for p in items]
    hero_bytes = await hero_task
    photos = await asyncio.gather(*photo_tasks)

    # --- composite artwork (CPU bound -> threads) --------------------------
    first = customer_name.split()[0] if customer_name else ""
    jobs: dict[str, Any] = {
        "header": asyncio.to_thread(
            rewe_brand.render_header,
            t["header_date"].format(kw=kw, date=today.strftime(date_fmt)),
            "Dein Markt",
            t["header_sub"],
        ),
        "hero": asyncio.to_thread(
            rewe_brand.render_hero,
            hero_bytes,
            _plain(headline),
            _plain(badge_text),
            t["kicker"].format(name=first) if first else "",
        ),
        "banner": asyncio.to_thread(
            rewe_brand.render_section_banner, t["banner"], valid_until
        ),
        "footer": asyncio.to_thread(
            rewe_brand.render_footer,
            ["REWE Markt GmbH · Domstraße 20 · 50668 Köln", t["footer_legal"]],
            t["footer_links"],
        ),
        "logo": asyncio.to_thread(
            lambda: rewe_brand.to_png_bytes(rewe_brand.logo_at_height(96))
        ),
    }
    tile_jobs = []
    for p, photo in zip(items, photos, strict=False):
        tile_jobs.append(
            asyncio.to_thread(
                rewe_brand.render_product_tile,
                photo,
                _plain(p.get("name")),
                _price_str(p),
                _plain(p.get("badge") or t["badge_default"]),
                _plain(p.get("discount_pill") or p.get("discount") or ""),
                _plain(p.get("bonus") or ""),
                _plain(p.get("unit") or ""),
            )
        )
    if len(items) % 2 == 1:
        tile_jobs.append(
            asyncio.to_thread(
                rewe_brand.render_promo_tile, t["promo_blurb"], t["promo_button"]
            )
        )

    keys = list(jobs)
    rendered = await asyncio.gather(*jobs.values())
    images = dict(zip(keys, rendered, strict=True))
    tiles = await asyncio.gather(*tile_jobs)

    # --- publish -----------------------------------------------------------
    def _mime(b: bytes) -> str:
        return "image/png" if b[:4] == b"\x89PNG" else "image/jpeg"

    pub = [
        asyncio.to_thread(image_host.publish_image, b, _mime(b))
        for b in [*images.values(), *tiles]
    ]
    urls_flat = await asyncio.gather(*pub)
    urls = dict(zip(keys, urls_flat[: len(keys)], strict=True))
    tile_urls = list(urls_flat[len(keys) :])

    view_products: list[dict[str, Any]] = []
    for p in items:
        brand, name = _plain(p.get("brand")), _plain(p.get("name"))
        display = name
        meta_bits = [
            b
            for b in (brand, _plain(p.get("category_path")).split(">")[-1].strip())
            if b
        ]
        view_products.append(
            {
                "display_name": display,
                "tip": _clean(
                    p.get("usage_tip")
                    or p.get("description")
                    or p.get("marketing_copy")
                ),
                "meta": " · ".join(meta_bits),
                "alt": f"{display} – {_de_price(_price_str(p))}",
            }
        )
    if len(items) % 2 == 1:
        view_products.append(
            {
                "display_name": "REWE Bonus",
                "tip": t["promo_tip"],
                "meta": t["promo_meta"],
                "alt": "REWE Bonus App",
            }
        )

    surface_id = f"rewe-newsletter-{getattr(tool_context, 'function_call_id', '') or os.urandom(4).hex()}"
    surface_id = re.sub(r"[^a-zA-Z0-9_-]", "", surface_id)[:60]
    messages = build_newsletter_surfaces(
        surface_id=surface_id,
        urls=urls,
        customer_name=first,
        body_text=str(body_text or "").strip(),
        cta_text=_plain(cta_button_text) or t["cta"],
        cta_url="https://www.rewe.de/angebote/",
        products=view_products,
        product_urls=tile_urls,
        hero_alt=_plain(hero_image_alt),
        insights={
            "seo_keywords": [_plain(k) for k in (seo_keywords or []) if _plain(k)],
            "primary_keyword": _plain(primary_keyword),
            "persona": _plain(persona),
            "dietary_tags": [_plain(t) for t in (dietary_tags or []) if _plain(t)],
            "market_hook": _plain(market_hook),
            "product_count": len(items),
        },
        logo_url=urls.get("logo", ""),
        strings=t,
    )
    stash_pending(tool_context.state, messages)

    signed = sum(1 for u in urls_flat if u.startswith("https://"))
    return {
        "status": "rendered",
        "surface_id": surface_id,
        "a2ui_messages": len(messages),
        "images_published": f"{signed}/{len(urls_flat)} via HTTPS",
        "product_photos_generated": sum(1 for x in photos if x),
        "instructions_for_final_answer": (
            "The complete newsletter (and a campaign brief card) is ALREADY "
            "displayed to the user as an interactive A2UI widget attached to "
            "your next message. Reply with ONE or TWO short sentences in the "
            "user's language introducing it. Do NOT repeat the blog text, the "
            "product list, any JSON, HTML or markdown tables."
        ),
    }
