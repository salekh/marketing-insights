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
"""A2UI format renderer for personalized REWE marketing newsletters.

Based on the basic catalog primitives from a2ui_starter (v0.9 A2UI envelope format).
"""

from __future__ import annotations
import json
from typing import Any
from app.app_utils.newsletter_template import (
    DEFAULT_HERO_IMAGE_URL,
    _format_price,
)

A2UI_VERSION = "v0.9"
A2UI_BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"

DEFAULT_PRODUCTS = [
    {
        "name": "Neuburger",
        "price": "1,79 €",
        "badge": "Aktion",
        "description": "österreichische Spezialität, je 100 g",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuAcL4rWAGhWlI6H1oHLR1TXttm2ZDKGQGFs0vLt1lAxkQ7fUa_zCrSPi7wXdWg1aowhbwf8OgPiaxsAivdDw8apREGC6OGMmQoBloJ_N18wUop61e30kez2AAAASbzmGRcpIvb6vlMi_vyqkMlsNd1mfY73Un37c0h9sJFS1RIz21-JcYaFgM4tkkXxVckNGthEwc2_OQAJI8IFySMUM0skfzHAI9llubt2MGES5_Ua8sF4u_TvD5t47g",
    },
    {
        "name": "Bonduelle Kidney Bohne",
        "price": "1,11 €",
        "badge": "Aktion",
        "description": "250-g-Abtropfgew., je 400-g-Dose (1 kg = 4.44) oder Goldmais 285-g-Abtropfgew., je 300-g-Dose",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDEq5jsJTC0cut2oYf19biMg3yNiUCvmmQbhlT7VijaB9tP4xDKJ87Ym7aiRn2b5G0p-xOSpBm5LxxmSkCrU7os_OL7A0WT6Qrp8XHSDQlXE0pYYuOL3GPp3DJ_9JcwhHgvWuSebdz6i12k3dxfNzDzh3jVmTqXKBPXRJ5FeXS77oe70DmpK1W5HM6wBEQMdPxsyPt58x6nI8JkjkS7Vh1Bn5-ToT6TiwVJk5ROZPZHhGBWWJzXtPSduQ",
    },
    {
        "name": "Jack Daniel's Tennessee Whiskey",
        "price": "14,99 €",
        "badge": "Aktion",
        "discount_pill": "1,00 €",
        "description": "40% Vol., je 0,7-l-Fl. (1 l = 21.41)",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuA4Jzk8uxNHsvi25oYiNqGSa7d6B1x5lBXcTVflIw8G274QYK3OzZCmG8KZ7FPy26QU_HlGAcFWgK2kSP2RZ4JmA6I6kDWFB7vPlKIISfBFEEz3p3Ry9dl4T3PYaZwCHNp6dtkAZaiQMKW_Qyi59mTFcgPwqE5Bg06bcYx8E6c9Ij-oObqMgVmgXiDMRE2p8YQW2eTWbUYSosIItCP06n-RXMiKC-Gp8I4Gca7SytaWvE2wIIA_oVbPAQ",
    },
    {
        "name": "Coppenrath & Wiese Unsere Goldstücke 6",
        "price": "1,99 €",
        "badge": "Aktion",
        "discount_pill": "0,20 €",
        "description": "tiefgefroren, je 420-g-Btl. (1 kg = 4.74)",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuAsNOz7ERvGSr1BY9mx5QvbwhvWE8KnVz1HJZDgBayRy4j4GSdzVUKicZvlNYfEAUomDXpIQCN0LrahoUB2n4jx4RoA_94NoOwpmpi1wq5azcd7w1fr4QXVhPO8g3CKxvFUK7BafKXNCqIizZysHhP1FFcrrxhMXN345qrvIEE4p3-riNghK875x7QBkyrRN3Nf_os6SwenDklG99FEsupWmScfZjVn9xIyoc7cWHiB-uSuX2UKBaaI6g",
    },
    {
        "name": "Leerdammer Käsescheiben",
        "price": "1,49 €",
        "badge": "Aktion",
        "description": "versch. Sorten, je 140-g-Pckg. (1 kg = 10.64)",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuC_0ILm4i-fU-a6IwEuZ5IQmltP8wjPXgkvZb02z4AIPAc564wJ7t5zjoSqUne8oTss9BGQLJKiBNRMmE02MWO70USMpIrGUD7HzC10C7B2cJG9fQSM0EXXClBnvkmoDTLAJEWUsYz3Wzg67XyB59P1dyMczFZjZhHE-_eA8EVy_KAEm53riMR_l-4AnO2crTau78UA4TB5RCMjf5iEyQnuTFB0tyD8bhqWGXdrhb8EShRlyNG3e7-EXg",
    },
    {
        "name": "Kiwi Gold",
        "price": "0,69 €",
        "badge": "Aktion",
        "description": "Klasse I, aus Neuseeland, je Stück",
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDLQ5B3sEqFuWmwb6mJjKyEIgZ69kDIOiq5P1O97mk0PH54n6jJhPuccRP3K7hk37gS4blLkxqmIA_PS-HUBKKket3hwxsgfaHa-E0CdNMeRaWQM3dxsGHSMd1W6CnFBfW8HLatTVD1OIMRJ_q-OD8qGDQt-hhZ2Rf8hPIx7IA9B11DEsWvff8mcUvUQF4CS2_wxp8dewvegBEA95Nad7Y0_5e17tQbCxV8bf77NBK8RBWFxm7v2dytyg",
    },
]


def _strip_markdown_for_a2ui(text: str) -> str:
    """Strip markdown symbols so text looks clean in A2UI Text components."""
    if not text:
        return ""
    s = str(text)
    s = s.replace("**", "").replace("*", "")
    return s.strip()


def render_newsletter_a2ui(
    customer_name: str = "Sanchit",
    headline: str = "",
    badge_text: str = "",
    body_text: str = "",
    hero_image_url: str = "",
    hero_image_alt: str = "",
    cta_button_text: str = "",
    valid_until_text: str = "",
    products: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Renders the REWE marketing newsletter as an A2UI v0.9 createSurface payload.

    Reflects the exact layout, sections, and styling of the HTML newsletter using A2UI basic catalog primitives.
    """
    if not headline:
        headline = "Deine Angebote für festliche Momente!"
    headline = _strip_markdown_for_a2ui(headline)

    if not badge_text:
        badge_text = "Wir wünschen schöne Festtage"
    badge_text = _strip_markdown_for_a2ui(badge_text)

    if not body_text:
        body_text = (
            "Feste feiern & genießen! Ob Weihnachtsdinner oder Silvesterabend – "
            "entdecke unsere Top-Angebote für genussvolle Momente mit Familie und Freunden."
        )
    body_text = _strip_markdown_for_a2ui(body_text)

    from app.tools import _latest_generated_image_uri

    if not hero_image_url or (
        not str(hero_image_url).startswith("http")
        and not str(hero_image_url).startswith("data:image/")
    ):
        if _latest_generated_image_uri:
            hero_image_url = _latest_generated_image_uri
        else:
            hero_image_url = DEFAULT_HERO_IMAGE_URL

    if not cta_button_text:
        cta_button_text = "Jetzt zugreifen & sparen"

    if not valid_until_text:
        valid_until_text = "Gültig bis 27.12.2025"

    # Normalize products
    if products is None:
        products = []
    elif isinstance(products, str):
        try:
            products = json.loads(products)
        except Exception:
            products = []

    final_products: list[dict[str, Any]] = []
    for idx in range(6):
        if idx < len(products) and isinstance(products[idx], dict):
            final_products.append(products[idx])
        else:
            final_products.append(DEFAULT_PRODUCTS[idx % len(DEFAULT_PRODUCTS)])

    # Build A2UI components list
    components: list[dict[str, Any]] = []

    # Root Column
    root_children = [
        "header_title",
        "header_divider",
        "hero_image",
        "hero_headline",
        "hero_badge",
        "hero_greeting",
        "hero_body",
        "cta_button",
        "offers_divider",
        "offers_heading",
        "offers_subheading",
    ]
    for idx in range(6):
        root_children.append(f"prod_card_{idx}")

    components.append({
        "id": "root",
        "component": "Column",
        "children": root_children,
    })

    # Header components
    components.extend([
        {
            "id": "header_title",
            "component": "Text",
            "text": "REWE Newsletter • Dein Markt",
            "variant": "title",
        },
        {
            "id": "header_divider",
            "component": "Divider",
        },
        {
            "id": "hero_image",
            "component": "Image",
            "url": str(hero_image_url),
            "fit": "cover",
            "accessibility": {"label": hero_image_alt or "REWE Hero Image"},
        },
        {
            "id": "hero_headline",
            "component": "Text",
            "text": headline,
            "variant": "headline",
        },
        {
            "id": "hero_badge",
            "component": "Text",
            "text": badge_text,
            "variant": "caption",
        },
        {
            "id": "hero_greeting",
            "component": "Text",
            "text": f"Hallo {customer_name},",
            "variant": "title",
        },
        {
            "id": "hero_body",
            "component": "Text",
            "text": body_text,
            "variant": "body",
        },
        {
            "id": "cta_button",
            "component": "Button",
            "child": "cta_button_label",
        },
        {
            "id": "cta_button_label",
            "component": "Text",
            "text": cta_button_text,
            "variant": "button",
        },
        {
            "id": "offers_divider",
            "component": "Divider",
        },
        {
            "id": "offers_heading",
            "component": "Text",
            "text": "Unsere aktuellen REWE Angebote",
            "variant": "headline",
        },
        {
            "id": "offers_subheading",
            "component": "Text",
            "text": valid_until_text,
            "variant": "caption",
        },
    ])

    # Product cards
    for idx, p in enumerate(final_products):
        def_p = DEFAULT_PRODUCTS[idx % len(DEFAULT_PRODUCTS)]
        p_name = _strip_markdown_for_a2ui(p.get("name") or def_p["name"])
        p_desc_val = (
            p.get("usage_tip")
            or p.get("description")
            or p.get("marketing_copy")
            or def_p["description"]
        )
        p_desc = _strip_markdown_for_a2ui(str(p_desc_val))
        p_price = _format_price(
            p.get("price") or p.get("price_current"), def_p["price"]
        )
        p_badge = str(p.get("badge") or def_p.get("badge") or "Aktion")
        p_img = str(p.get("image_url") or def_p["image_url"])

        badge_price_str = f"{p_badge} • {p_price}"
        if p.get("discount_pill"):
            badge_price_str += f" (Rabatt: {p.get('discount_pill')})"

        card_id = f"prod_card_{idx}"
        col_id = f"prod_col_{idx}"
        img_id = f"prod_img_{idx}"
        badge_id = f"prod_badge_{idx}"
        title_id = f"prod_title_{idx}"
        desc_id = f"prod_desc_{idx}"

        components.extend([
            {
                "id": card_id,
                "component": "Card",
                "child": col_id,
            },
            {
                "id": col_id,
                "component": "Column",
                "children": [img_id, badge_id, title_id, desc_id],
            },
            {
                "id": img_id,
                "component": "Image",
                "url": p_img,
                "fit": "contain",
                "accessibility": {"label": p_name},
            },
            {
                "id": badge_id,
                "component": "Text",
                "text": badge_price_str,
                "variant": "caption",
            },
            {
                "id": title_id,
                "component": "Text",
                "text": p_name,
                "variant": "title",
            },
            {
                "id": desc_id,
                "component": "Text",
                "text": p_desc,
                "variant": "body",
            },
        ])

    envelope = {
        "version": A2UI_VERSION,
        "createSurface": {
            "surfaceId": "rewe-newsletter-a2ui",
            "catalogId": A2UI_BASIC_CATALOG_ID,
            "components": components,
        },
    }
    return [envelope]
