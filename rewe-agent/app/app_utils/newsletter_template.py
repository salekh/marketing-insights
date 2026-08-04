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
"""REWE HTML Newsletter template and renderer."""

import html
import json
from typing import Any

DEFAULT_HERO_IMAGE_URL = (
    "https://lh3.googleusercontent.com/aida-public/"
    "AB6AXuDLQ5B3sEqFuWmwb6mJjKyEIgZ69kDIOiq5P1O97mk0PH54n6jJhPuccRP3K7hk37gS4blLkxqmIA_PS-HUBKKket3hwxsgfaHa-E0CdNMeRaWQM3dxsGHSMd1W6CnFBfW8HLatTVD1OIMRJ_q-OD8qGDQt-hhZ2Rf8hPIx7IA9B11DEsWvff8mcUvUQF4CS2_wxp8dewvegBEA95Nad7Y0_5e17tQbCxV8bf77NBK8RBWFxm7v2dytyg"
)

DEFAULT_SECONDARY_HERO_URL = (
    "https://lh3.googleusercontent.com/aida-public/"
    "AB6AXuD873T7cqMSSFWY5gPQagS4-gezDca0KK3t3I56eFy9EdjWrnIwE-VbVmIuEoLIq5ey_q66qIaiIliF4atxP7ufeXFEGZ7YMRzdEEcZFTDJd35GNBEVjFQ1Ih-lDHtfzOeKfuPVBrezm0DwWLsu_zfwmDV9qZ-7HZPo1qIuw5mzxkwVTC03iyMtZAThuDHRT1nhNmvE7phWhcmiBtoWGDOEg-JFg5bgpk56VxGJgZQFCPV-WxccWFH5vA"
)

DEFAULT_PRODUCTS = [
    {
        "name": "Goldene Kiwi",
        "description": "Herkunft: Italien, Kl. I, je St.",
        "price": "0,55 €",
        "badge": "Aktion",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuBOCstsgytUC8TxPsnWoT0jF8xftplpXs7e3cc0Pcko2GKtfd5i3u1bvxcwCVVHTeVfxxKtJIbiKVPd8ZbBi8PRGg84TT5pFT31pj5mRsbJVA5if5LLNhoC83c6oCsCaq472IYcLLvl1tp0Pke1w3Ha6sq37kmPaJGCotvbts8k42o2mNRzn-n4Ba3CX-VXKgH05jSMWva0ah_DHFFqoxnm2QMTqZnJCwGsHP-diGGyzyMH-JSI6oEbrA"
        ),
        "alt_text": "Three golden kiwis on a white background. One is cut in half, revealing bright yellow flesh and black seeds. The other two are whole with fuzzy brown skin.",
    },
    {
        "name": "Neuburger",
        "description": "österreichische Spezialität, je 100 g",
        "price": "1,79 €",
        "badge": "Aktion",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuAcL4rWAGhWlI6H1oHLR1TXttm2ZDKGQGFs0vLt1lAxkQ7fUa_zCrSPi7wXdWg1aowhbwf8OgPiaxsAivdDw8apREGC6OGMmQoBloJ_N18wUop61e30kez2AAAASbzmGRcpIvb6vlMi_vyqkMlsNd1mfY73Un37c0h9sJFS1RIz21-JcYaFgM4tkkXxVckNGthEwc2_OQAJI8IFySMUM0skfzHAI9llubt2MGES5_Ua8sF4u_TvD5t47g"
        ),
        "alt_text": "A block of Neuburger meat loaf, sliced on one side, presented with a few slices folded neatly in front. Garnished with a sprig of parsley and a cucumber slice, on a white background.",
    },
    {
        "name": "Bonduelle Kidney Bohne",
        "description": "250-g-Abtropfgew., je 400-g-Dose (1 kg = 4.44) oder Goldmais 285-g-Abtropfgew., je 300-g-Dose (1 kg = 3.89)",
        "price": "1,11 €",
        "badge": "Aktion",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuDEq5jsJTC0cut2oYf19biMg3yNiUCvmmQbhlT7VijaB9tP4xDKJ87Ym7aiRn2b5G0p-xOSpBm5LxxmSkCrU7os_OL7A0WT6Qrp8XHSDQlXE0pYYuOL3GPp3DJ_9JcwhHgvWuSebdz6i12k3dxfNzDzh3jVmTqXKBPXRJ5FeXS77oe70DmpK1W5HM6wBEQMdPxsyPt58x6nI8JkjkS7Vh1Bn5-ToT6TiwVJk5ROZPZHhGBWWJzXtPSduQ"
        ),
        "alt_text": "Two cans of Bonduelle vegetables. One is a taller can of Kidney Beans, the other is a shorter can of Goldmais (sweet corn). Both cans are open at the top, showing the contents inside. White background.",
    },
    {
        "name": "Jack Daniel's Tennessee Whiskey",
        "description": "40% Vol., je 0,7-l-Fl. (1 l = 21.41)",
        "price": "14,99 €",
        "badge": "Aktion",
        "discount_pill": "1,00 €",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuA4Jzk8uxNHsvi25oYiNqGSa7d6B1x5lBXcTVflIw8G274QYK3OzZCmG8KZ7FPy26QU_HlGAcFWgK2kSP2RZ4JmA6I6kDWFB7vPlKIISfBFEEz3p3Ry9dl4T3PYaZwCHNp6dtkAZaiQMKW_Qyi59mTFcgPwqE5Bg06bcYx8E6c9Ij-oObqMgVmgXiDMRE2p8YQW2eTWbUYSosIItCP06n-RXMiKC-Gp8I4Gca7SytaWvE2wIIA_oVbPAQ"
        ),
        "alt_text": "A glass bottle of Jack Daniel's Tennessee Whiskey (Old No. 7 brand) standing upright against a light green background.",
    },
    {
        "name": "Coppenrath & Wiese Unsere Goldstücke 6",
        "description": "tiefgefroren, je 420-g-Btl. (1 kg = 4.74)",
        "price": "1,99 €",
        "badge": "Aktion",
        "discount_pill": "0,20 €",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuAsNOz7ERvGSr1BY9mx5QvbwhvWE8KnVz1HJZDgBayRy4j4GSdzVUKicZvlNYfEAUomDXpIQCN0LrahoUB2n4jx4RoA_94NoOwpmpi1wq5azcd7w1fr4QXVhPO8g3CKxvFUK7BafKXNCqIizZysHhP1FFcrrxhMXN345qrvIEE4p3-riNghK875x7QBkyrRN3Nf_os6SwenDklG99FEsupWmScfZjVn9xIyoc7cWHiB-uSuX2UKBaaI6g"
        ),
        "alt_text": "A bag of frozen Coppenrath & Wiese 'Unsere Goldstücke' bread rolls. The packaging shows golden brown rolls and the number 6. Light green background.",
    },
    {
        "name": "Leerdammer Käsescheiben",
        "description": "versch. Sorten, je 140-g-Pckg. (1 kg = 10.64)",
        "price": "1,49 €",
        "badge": "Aktion",
        "image_url": (
            "https://lh3.googleusercontent.com/aida-public/"
            "AB6AXuC_0ILm4i-fU-a6IwEuZ5IQmltP8wjPXgkvZb02z4AIPAc564wJ7t5zjoSqUne8oTss9BGQLJKiBNRMmE02MWO70USMpIrGUD7HzC10C7B2cJG9fQSM0EXXClBnvkmoDTLAJEWUsYz3Wzg67XyB59P1dyMczFZjZhHE-_eA8EVy_KAEm53riMR_l-4AnO2crTau78UA4TB5RCMjf5iEyQnuTFB0tyD8bhqWGXdrhb8EShRlyNG3e7-EXg"
        ),
        "alt_text": "A package of Leerdammer Original cheese slices. The yellow packaging features the brand logo and a picture of a cheese sandwich. White background.",
    },
]


def _format_price(price_val: Any, default_val: str = "1,99 €") -> str:
    """Formats a price value into German euro string (e.g., '1,99 €')."""
    if price_val is None or price_val == "":
        return default_val
    if isinstance(price_val, (int, float)):
        formatted = f"{price_val:.2f}".replace(".", ",")
        return f"{formatted} €"
    s = str(price_val).strip()
    if not s.endswith("€"):
        s = f"{s} €"
    return s


def _render_product_card(idx: int, p: dict[str, Any], default_p: dict[str, Any]) -> str:
    """Renders a single product card HTML snippet."""
    p_name = html.escape(str(p.get("name") or default_p["name"]))
    p_desc_val = (
        p.get("usage_tip")
        or p.get("description")
        or p.get("marketing_copy")
        or default_p["description"]
    )
    p_desc = html.escape(str(p_desc_val))
    p_price = html.escape(_format_price(p.get("price") or p.get("price_current"), default_p["price"]))
    p_badge = html.escape(str(p.get("badge") or default_p.get("badge") or "Aktion"))
    p_img = html.escape(str(p.get("image_url") or default_p["image_url"]))
    p_alt = html.escape(str(p.get("alt_text") or default_p["alt_text"]))
    p_discount = p.get("discount_pill") or default_p.get("discount_pill")

    if p_discount:
        discount_str = html.escape(str(p_discount))
        return f"""<div class="bg-[#eaf1ec] border border-[#d1e0d7] rounded-xl p-stack-md flex flex-col h-full hover:shadow-md transition-shadow relative">
<div class="absolute top-2 left-2 bg-[#1b5e40] text-white font-label-bold text-[11px] px-2 py-1 rounded-full flex items-center gap-1 z-10">
<span class="material-symbols-outlined text-[#b93282] text-[14px]" style="font-variation-settings: 'FILL' 1;">stars</span>
          {discount_str}
        </div>
<div class="aspect-square mb-stack-sm relative flex items-center justify-center">
<img class="object-contain w-[70%] h-[90%]" data-alt="{p_alt}" src="{p_img}">
</div>
<div class="flex-1 flex flex-col">
<h4 class="font-headline-md text-[16px] text-on-surface mb-1">{p_name}</h4>
<p class="font-label-sm text-on-surface-variant mb-stack-md line-clamp-2 flex-1">{p_desc}</p>
<div class="flex justify-end mt-auto">
<div class="flex rounded-full overflow-hidden text-[12px] font-bold shadow-sm">
<div class="bg-tertiary-fixed text-on-tertiary-fixed px-2 py-1">{p_badge}</div>
<div class="bg-primary text-on-primary px-2 py-1">{p_price}</div>
</div>
</div>
</div>
</div>"""

    return f"""<div class="bg-surface-container-lowest border border-outline-variant rounded-xl p-stack-md flex flex-col h-full hover:shadow-md transition-shadow">
<div class="aspect-square mb-stack-sm relative flex items-center justify-center">
<img class="object-contain w-[80%] h-[80%]" data-alt="{p_alt}" src="{p_img}">
</div>
<div class="flex-1 flex flex-col">
<h4 class="font-headline-md text-[16px] text-on-surface mb-1">{p_name}</h4>
<p class="font-label-sm text-on-surface-variant mb-stack-md line-clamp-2 flex-1">{p_desc}</p>
<div class="flex justify-end mt-auto">
<div class="flex rounded-full overflow-hidden text-[12px] font-bold shadow-sm">
<div class="bg-tertiary-fixed text-on-tertiary-fixed px-2 py-1">{p_badge}</div>
<div class="bg-primary text-on-primary px-2 py-1">{p_price}</div>
</div>
</div>
</div>
</div>"""


def render_newsletter_html(
    customer_name: str = "Sanchit",
    headline: str = "",
    badge_text: str = "",
    body_text: str = "",
    hero_image_url: str = "",
    hero_image_alt: str = "",
    cta_button_text: str = "",
    valid_until_text: str = "",
    products: list[Any] | None = None,
) -> str:
    """Renders the REWE marketing newsletter HTML using the official REWE template.

    Automatically populates the template placeholders based on generated image, blog text,
    and product recommendations. If any content is missing, invents realistic REWE defaults.
    """
    if not customer_name:
        customer_name = "Sanchit"

    if not headline:
        headline_html = "Deine Angebote<br>für festliche<br>Momente!"
    else:
        if "<br>" in headline or "<BR>" in headline:
            headline_html = headline
        elif "\n" in headline:
            headline_html = headline.replace("\n", "<br>")
        else:
            headline_html = headline

    if not badge_text:
        badge_html = "Wir<br>wünschen<br>schöne<br>Festtage"
    else:
        if "<br>" in badge_text or "<BR>" in badge_text:
            badge_html = badge_text
        elif "\n" in badge_text:
            badge_html = badge_text.replace("\n", "<br>")
        else:
            badge_html = "<br>".join(badge_text.split()[:4])

    if not body_text:
        body_text = (
            "Feste feiern & genießen! Ob Weihnachtsdinner oder Silvesterabend – "
            "entdecke unsere Top-Angebote für genussvolle Momente mit Familie und Freunden."
        )

    if not hero_image_url or not str(hero_image_url).startswith("http"):
        hero_image_url = DEFAULT_HERO_IMAGE_URL

    if not hero_image_alt:
        hero_image_alt = (
            "A festive feast on a dark wooden table. A bowl of creamy orange soup is in the foreground, "
            "alongside rustic croutons in a wooden bowl. Fresh green peas and other colorful side dishes "
            "are scattered around. Warm, golden string lights and candles create a cozy, holiday atmosphere."
        )

    if not cta_button_text:
        cta_button_text = "Jetzt zugreifen & sparen"

    if not valid_until_text:
        valid_until_text = "Gültig bis 27.12.2025"

    # Normalize products list
    if products is None:
        products = []
    elif isinstance(products, str):
        try:
            products = json.loads(products)
        except Exception:
            products = []
    elif not isinstance(products, list):
        products = list(products)

    normalized_products: list[dict[str, Any]] = []
    for item in products:
        if isinstance(item, dict):
            normalized_products.append(item)
        elif hasattr(item, "model_dump"):
            normalized_products.append(item.model_dump())
        elif hasattr(item, "__dict__"):
            normalized_products.append(item.__dict__)
        else:
            normalized_products.append({"name": str(item)})

    # Ensure 6 cards for the grid by padding with default products if necessary
    grid_cards: list[str] = []
    for i in range(6):
        default_p = DEFAULT_PRODUCTS[i % len(DEFAULT_PRODUCTS)]
        p = normalized_products[i] if i < len(normalized_products) else default_p
        grid_cards.append(_render_product_card(i, p, default_p))

    products_grid_html = "\n<!-- Product -->\n".join(grid_cards)

    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta content="width=device-width, initial-scale=1.0" name="viewport"><style>@layer base{{html,body{{margin:0;padding:0;}}body{{overscroll-behavior:none;}}main>:first-child{{margin-top:0!important;}}main>:last-child{{margin-bottom:0!important;}}}}::-webkit-scrollbar{{display:none;}}</style><script src="https://cdn.tailwindcss.com"></script><script id="tailwind-config">tailwind.config={{theme:{{extend:{{"colors":{{"tertiary-fixed":"#ffe25f","tertiary-container":"#c7aa00","primary-fixed":"#ffdad6","on-error-container":"#93000a","surface-container-lowest":"#ffffff","surface-container-low":"#f6f3f2","on-tertiary-fixed-variant":"#534600","on-surface-variant":"#5d3f3d","secondary-container":"#c3e4fe","background":"#fbf9f8","error-container":"#ffdad6","outline-variant":"#e6bdb9","on-secondary-fixed":"#001e2f","on-secondary-container":"#47667c","surface-bright":"#fbf9f8","surface-variant":"#e4e2e1","inverse-surface":"#303030","on-error":"#ffffff","on-primary-container":"#ffdcd8","on-primary":"#ffffff","on-primary-fixed-variant":"#930011","surface-tint":"#c0001a","primary":"#a00014","error":"#ba1a1a","inverse-primary":"#ffb3ad","secondary-fixed":"#c8e6ff","tertiary-fixed-dim":"#e6c500","surface-container-high":"#eae8e7","secondary-fixed-dim":"#abcae4","on-primary-fixed":"#410003","on-background":"#1b1c1c","inverse-on-surface":"#f3f0f0","primary-fixed-dim":"#ffb3ad","tertiary":"#6e5d00","on-secondary":"#ffffff","on-tertiary":"#ffffff","outline":"#916f6b","secondary":"#436278","on-tertiary-fixed":"#221b00","surface-container-highest":"#e4e2e1","primary-container":"#cc071e","surface-container":"#f0eded","surface-dim":"#dcd9d9","on-secondary-fixed-variant":"#2b4a5f","surface":"#fbf9f8","on-tertiary-container":"#4b3f00","on-surface":"#1b1c1c"}},"borderRadius":{{"DEFAULT":"0.25rem","lg":"0.5rem","xl":"0.75rem","full":"9999px"}},"spacing":{{"container-max":"600px","margin-x":"20px","stack-sm":"8px","stack-lg":"24px","gutter":"16px","stack-md":"16px"}},"fontFamily":{{"label-sm":["Work Sans"],"body-lg":["Work Sans"],"label-bold":["Hanken Grotesk"],"body-md":["Work Sans"],"headline-lg-mobile":["Hanken Grotesk"],"headline-xl":["Hanken Grotesk"],"headline-lg":["Hanken Grotesk"],"headline-md":["Hanken Grotesk"]}},"fontSize":{{"label-sm":["12px",{{"lineHeight":"1.2","fontWeight":"400"}}],"body-lg":["16px",{{"lineHeight":"1.5","fontWeight":"400"}}],"label-bold":["14px",{{"lineHeight":"1.0","fontWeight":"700"}}],"body-md":["14px",{{"lineHeight":"1.4","fontWeight":"400"}}],"headline-lg-mobile":["22px",{{"lineHeight":"1.2","fontWeight":"700"}}],"headline-xl":["32px",{{"lineHeight":"1.1","fontWeight":"800"}}],"headline-lg":["24px",{{"lineHeight":"1.2","fontWeight":"700"}}],"headline-md":["20px",{{"lineHeight":"1.2","fontWeight":"700"}}]}}}}}}}}</script>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@100..900&amp;family=Work+Sans:wght@100..900&amp;display=swap" rel="stylesheet"></head><body class="bg-surface-container-low font-body-md text-on-surface"><div class="max-w-[600px] mx-auto bg-surface min-h-screen shadow-[0_2px_12px_rgba(0,0,0,0.04)]"><header class="w-full bg-surface border-b border-outline-variant"><div class="h-20 flex items-center justify-between px-margin-x"><div class="flex items-center gap-2"><div class="w-12 h-12 flex items-center justify-center"><img src="https://lh3.googleusercontent.com/aida-public/AB6AXuDwvhQkMGxmytgYB2N7uIn6Rf0SSDf4qgzJbB53JheUH5xKLJk7_8BbT4Rg85M2j2wyu9xk0UL-xpUG3_YSZrqCKYze2BmECsuDG1aZwuAJ5hkpN2qA_kwbWr6TAto4bnkGZo59Lkclil91F_t7cWH80fHoQSJZzqPnX5lt_0RfQqiwd1aNfGfVPYnLMNNhoxDGKuUbg6I1C_JUdOc9xaMAG0nK9pbtA0MXP7PqqPEBofL2wlgCjrk50IKsqiCUnN5qMUw" alt="REWE Logo" class="w-full h-full object-contain"></div></div><nav class="flex items-center gap-stack-lg" data-active-classes="text-primary font-label-bold"><a class="font-label-sm text-on-surface-variant hover:text-primary transition-colors underline decoration-outline-variant underline-offset-4" data-path="newsletter-profil" href="#">Newsletter-Profil</a></nav></div></header><main class="w-full bg-surface"><div class="flex flex-col w-full">
<!-- Hero Section -->
<div class="px-margin-x pt-stack-sm pb-stack-lg">
<div class="rounded-xl overflow-hidden bg-secondary-fixed-variant shadow-sm relative">
<div class="relative w-full h-[280px]">
<div class="absolute inset-0 bg-cover bg-right h-full w-[60%] left-[40%]" data-alt="{html.escape(hero_image_alt)}" style="background-image: url('{html.escape(hero_image_url)}')"></div>
<div class="absolute inset-0 bg-gradient-to-r from-[#47667c] via-[#47667c] to-transparent w-[70%]"></div>
<div class="relative z-10 p-stack-lg flex flex-col justify-center h-full w-[65%]">
<h1 class="font-headline-xl text-on-primary font-bold leading-tight drop-shadow-md">
            {headline_html}
          </h1>
</div>
<div class="absolute right-1/2 top-[55%] translate-x-[70%] -translate-y-1/2 bg-tertiary-fixed text-on-tertiary-fixed-variant w-[110px] h-[110px] rounded-full flex items-center justify-center text-center leading-tight shadow-md rotate-[-5deg] z-20">
<span class="font-headline-md font-bold text-[18px]">{badge_html}</span>
</div>
</div>
<div class="bg-[#47667c] p-stack-lg text-on-primary">
<h2 class="font-headline-lg font-bold mb-stack-md">Hallo {html.escape(customer_name)},</h2>
<p class="font-body-lg mb-stack-lg leading-relaxed">
          {html.escape(body_text)}
        </p>
<div class="font-body-md mb-stack-lg">
<p class="">Herzliche Grüße</p>
<p class="">dein <span class="bg-tertiary-fixed text-on-tertiary-fixed-variant font-bold px-1 rounded-sm">REWE</span> Team</p>
</div>
<button class="w-full bg-surface text-secondary font-label-bold py-3 rounded-lg shadow-sm hover:bg-surface-container transition-colors">
          {html.escape(cta_button_text)}
        </button>
</div>
</div>
</div>
<!-- Secondary Hero -->
<div class="px-margin-x pb-stack-lg">
<div class="rounded-xl overflow-hidden shadow-sm h-[160px]">
<img class="w-full h-full object-cover" data-alt="A person holding a large brown paper REWE grocery bag filled with fresh produce, including red bell peppers, leafy greens, and packaged goods like 'ja!' brand items. The background shows a cozy home kitchen setting with wooden shelves and jars. The lighting is bright and natural." src="{DEFAULT_SECONDARY_HERO_URL}">
</div>
</div>
<!-- Offers Header -->
<div class="px-margin-x pb-stack-md">
<h3 class="font-headline-lg text-on-surface mb-1">
      Angebote bis Samstag bei <span class="bg-tertiary-fixed text-on-tertiary-fixed-variant px-1 rounded-sm">REWE</span>*
    </h3>
<p class="font-body-md text-on-surface-variant">{html.escape(valid_until_text)}</p>
</div>
<!-- Category Navigation -->
<div class="px-margin-x pb-stack-lg">
<div class="flex items-stretch border border-outline-variant rounded-lg overflow-hidden bg-surface relative">
<!-- Left Arrow -->
<button class="w-8 flex items-center justify-center bg-surface-container-lowest border-r border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors shrink-0">
<span class="material-symbols-outlined text-[20px]">chevron_left</span>
</button>
<!-- Nav Items -->
<div class="flex flex-1 overflow-x-auto no-scrollbar snap-x">
<div class="flex-1 min-w-[80px] p-2 flex flex-col items-center justify-center gap-1 border-r border-outline-variant border-b-2 border-b-primary snap-start bg-surface-container-lowest cursor-pointer">
<span class="material-symbols-outlined text-primary text-[24px]" style="font-variation-settings: 'FILL' 1;">stars</span>
<span class="font-label-sm font-bold text-primary text-center leading-none text-[10px]">Topangebote</span>
</div>
<div class="flex-1 min-w-[80px] p-2 flex flex-col items-center justify-center gap-1 border-r border-outline-variant border-b-2 border-b-transparent snap-start hover:bg-surface-container-lowest transition-colors cursor-pointer">
<span class="material-symbols-outlined text-[#b93282] text-[24px]" style="font-variation-settings: 'FILL' 1;">stars</span>
<span class="font-label-sm font-bold text-on-surface text-center leading-none text-[10px]"><span class="text-tertiary-container">REWE</span> Bonus</span>
</div>
<div class="flex-1 min-w-[80px] p-2 flex flex-col items-center justify-center gap-1 border-r border-outline-variant border-b-2 border-b-transparent snap-start hover:bg-surface-container-lowest transition-colors cursor-pointer">
<span class="material-symbols-outlined text-on-surface-variant text-[24px]">nutrition</span>
<span class="font-label-sm font-bold text-on-surface text-center leading-none text-[10px]">Obst &amp; Gemüse</span>
</div>
<div class="flex-1 min-w-[80px] p-2 flex flex-col items-center justify-center gap-1 border-b-2 border-b-transparent snap-start hover:bg-surface-container-lowest transition-colors cursor-pointer">
<span class="material-symbols-outlined text-on-surface-variant text-[24px]">kitchen</span>
<span class="font-label-sm font-bold text-on-surface text-center leading-none text-[10px]">Frische &amp; Kühlung</span>
</div>
</div>
<!-- Right Arrow -->
<button class="w-8 flex items-center justify-center bg-surface-container-lowest border-l border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors shrink-0">
<span class="material-symbols-outlined text-[20px]">chevron_right</span>
</button>
</div>
</div>
<!-- Product Grid -->
<div class="px-margin-x pb-stack-lg">
<div class="grid grid-cols-2 gap-stack-md">
{products_grid_html}
</div>
</div>
</div></main><footer class="w-full bg-surface-container-highest py-stack-lg border-t border-outline-variant mt-stack-lg"><div class="px-margin-x flex flex-col items-center gap-stack-md"><div class="flex gap-stack-lg"><a class="font-label-sm text-on-surface-variant hover:text-on-surface" data-path="impressum" href="#">Impressum</a><a class="font-label-sm text-on-surface-variant hover:text-on-surface" data-path="datenschutz" href="#">Datenschutz</a><a class="font-label-sm text-on-surface-variant hover:text-on-surface" data-path="kontakt" href="#">Kontakt</a></div><p class="font-label-sm text-on-surface-variant opacity-70">© 2024 REWE Markt GmbH. Alle Rechte vorbehalten.</p></div></footer></div>

</body></html>"""
