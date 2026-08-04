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

A2UI_VERSION = "v0.8"
A2UI_BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_8/basic_catalog.json"
_A2UI_BLOB_MARKER = b"<a2a_datapart_json>"


def _wrap_a2ui_part(a2ui_message: dict[str, Any]) -> Any:
    """Wrap an A2UI message dict as an inline-data blob for ADK Dev-UI / A2UI client rendering."""
    import json as _json
    from google.genai import types

    datapart_json = _json.dumps({
        "kind": "data",
        "metadata": {"mimeType": "application/json+a2ui"},
        "data": a2ui_message,
    })
    blob_data = (
        _A2UI_BLOB_MARKER
        + datapart_json.encode("utf-8")
        + b"</a2a_datapart_json>"
    )
    return types.Part(
        inline_data=types.Blob(data=blob_data, mime_type="text/plain")
    )


_A2UI_PENDING_KEY = "temp:a2ui_pending"
_latest_a2ui_stash: list[dict[str, Any]] | None = None


def _stash_latest_a2ui(envelope_list: list[dict[str, Any]]) -> None:
    global _latest_a2ui_stash
    _latest_a2ui_stash = envelope_list


def _before_model_callback(callback_context: Any, llm_request: Any) -> None:
    """Strip echoed A2UI blobs from history so the model doesn't regurgitate."""
    from google.genai import types

    if not getattr(llm_request, "contents", None):
        return None

    for content in llm_request.contents:
        if not getattr(content, "parts", None):
            continue
        clean_parts = [
            types.Part.from_text(text="[A2UI component rendered]")
            if (
                getattr(p, "inline_data", None)
                and p.inline_data.mime_type == "text/plain"
                and _A2UI_BLOB_MARKER in (p.inline_data.data or b"")
            )
            else p
            for p in content.parts
        ]
        content.parts[:] = clean_parts

    return None


def _after_model_callback(callback_context: Any, llm_response: Any) -> Any:
    """Inject pending A2UI inline_data blobs into the model response with a2a metadata."""
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    global _latest_a2ui_stash
    pending = None
    if callback_context and hasattr(callback_context, "state") and _A2UI_PENDING_KEY in callback_context.state:
        pending = callback_context.state.get(_A2UI_PENDING_KEY)
        callback_context.state[_A2UI_PENDING_KEY] = None

    if not pending and _latest_a2ui_stash:
        pending = _latest_a2ui_stash
        _latest_a2ui_stash = None

    if not pending:
        return None

    blob_parts = [_wrap_a2ui_part(msg) for msg in pending]

    existing_parts = []
    if llm_response and getattr(llm_response, "content", None) and getattr(llm_response.content, "parts", None):
        existing_parts = list(llm_response.content.parts)

    all_parts = existing_parts + blob_parts

    return LlmResponse(
        content=types.Content(role="model", parts=all_parts),
        custom_metadata={"a2a:response": True},
    )

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

    # Helper builders for A2UI v0.8 (GE-compatible)
    def _text(comp_id: str, text: str, usage_hint: str = "body") -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {
                "Text": {
                    "text": {"literalString": str(text)},
                    "usageHint": usage_hint,
                }
            },
        }

    def _image(comp_id: str, url: str, fit: str = "cover") -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {
                "Image": {
                    "url": {"literalString": str(url)},
                    "fit": fit,
                }
            },
        }

    def _divider(comp_id: str) -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {"Divider": {}},
        }

    def _button(comp_id: str, label_id: str) -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {
                "Button": {
                    "child": label_id,
                }
            },
        }

    def _card(comp_id: str, child_id: str) -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {
                "Card": {
                    "child": child_id,
                }
            },
        }

    def _column(comp_id: str, children_ids: list[str]) -> dict[str, Any]:
        return {
            "id": comp_id,
            "component": {
                "Column": {
                    "children": {
                        "explicitList": children_ids,
                    }
                }
            },
        }

    # Build A2UI v0.8 components list
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

    components.append(_column("root", root_children))

    # Header components
    components.extend([
        _text("header_title", "REWE Newsletter • Dein Markt", "h2"),
        _divider("header_divider"),
        _image("hero_image", str(hero_image_url), "cover"),
        _text("hero_headline", headline, "h1"),
        _text("hero_badge", badge_text, "caption"),
        _text("hero_greeting", f"Hallo {customer_name},", "h2"),
        _text("hero_body", body_text, "body"),
        _button("cta_button", "cta_button_label"),
        _text("cta_button_label", cta_button_text, "body"),
        _divider("offers_divider"),
        _text("offers_heading", "Unsere aktuellen REWE Angebote", "h1"),
        _text("offers_subheading", valid_until_text, "caption"),
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
            _card(card_id, col_id),
            _column(col_id, [img_id, badge_id, title_id, desc_id]),
            _image(img_id, p_img, "contain"),
            _text(badge_id, badge_price_str, "caption"),
            _text(title_id, p_name, "h2"),
            _text(desc_id, p_desc, "body"),
        ])

    surface_id = "rewe-newsletter-a2ui"
    return [
        {
            "version": A2UI_VERSION,
            "beginRendering": {
                "surfaceId": surface_id,
                "root": "root",
                "catalogId": A2UI_BASIC_CATALOG_ID,
            },
        },
        {
            "version": A2UI_VERSION,
            "surfaceUpdate": {
                "surfaceId": surface_id,
                "components": components,
            },
        },
    ]


def extract_text_and_a2ui(full_output: str) -> tuple[str, str]:
    """Extracts (readable_text, pure_a2ui_json) from a combined model response string."""
    if not full_output:
        return ("", "")

    import re

    match = re.search(r"\[\s*\{\s*(?:\"version\"|\"createSurface\"|\"beginRendering\"|\"surfaceUpdate\")", full_output)
    if not match:
        return ("", "")

    idx = match.start()
    text_part = full_output[:idx].strip()
    a2ui_candidate = full_output[idx:].strip()
    r_idx = a2ui_candidate.rfind("]")
    if r_idx != -1:
        a2ui_candidate = a2ui_candidate[:r_idx + 1]
        try:
            parsed = json.loads(a2ui_candidate)
            if isinstance(parsed, list) and len(parsed) > 0 and ("createSurface" in parsed[0] or "beginRendering" in parsed[0] or "surfaceUpdate" in parsed[0] or "version" in parsed[0]):
                lines = text_part.splitlines()
                while lines and (
                    "Generated A2UI" in lines[-1]
                    or "```" in lines[-1]
                    or not lines[-1].strip()
                ):
                    lines.pop()
                clean_text = "\n".join(lines).strip()
                clean_a2ui = json.dumps(parsed, indent=2, ensure_ascii=False)
                return (clean_text, clean_a2ui)
        except Exception:
            pass

    return ("", "")


async def _async_extract_text_and_a2ui(full_output: str) -> tuple[str, str]:
    """Extracts (readable_text, pure_a2ui_json) with fallback to gemini-3.5-flash-lite (global)."""
    text_part, a2ui_part = extract_text_and_a2ui(full_output)
    if a2ui_part:
        return (text_part, a2ui_part)

    try:
        from app.tools import _get_genai_client
        client = _get_genai_client()
        prompt = (
            "You are an expert parser. Separate the following content into two clean parts:\n"
            "1) 'text': The human-readable text (blog post, SEO strategy, product recommendations) WITHOUT any A2UI JSON array or code block.\n"
            "2) 'a2ui_json': The exact, pure JSON array string starting with [ and ending with ] that contains the A2UI createSurface envelope.\n"
            "Return ONLY a valid JSON object with keys 'text' and 'a2ui_json':\n\n" + str(full_output)
        )
        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
        )
        raw_res = response.text.strip()
        if raw_res.startswith("```json"):
            raw_res = raw_res[7:]
        if raw_res.startswith("```"):
            raw_res = raw_res[3:]
        if raw_res.endswith("```"):
            raw_res = raw_res[:-3]
        parsed_res = json.loads(raw_res.strip())
        t_res = parsed_res.get("text", "").strip()
        a_res = parsed_res.get("a2ui_json", "").strip()
        parsed_array = json.loads(a_res)
        if isinstance(parsed_array, list) and len(parsed_array) > 0 and ("createSurface" in parsed_array[0] or "beginRendering" in parsed_array[0] or "surfaceUpdate" in parsed_array[0] or "version" in parsed_array[0]):
            return (t_res, json.dumps(parsed_array, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"DEBUG: gemini-3.5-flash-lite A2UI split fallback failed: {e}")

    return ("", "")


def _strip_a2a_wrappers(text: str) -> str:
    import re
    return re.sub(
        r"<a2a_datapart_json>.*?</a2a_datapart_json>", "", text, flags=re.DOTALL
    )


def _extract_a2ui_json(text: str) -> str | None:
    import re
    tag_match = re.search(r"<a2ui-json>(.*?)</a2ui-json>", text, re.DOTALL)
    if tag_match:
        return tag_match.group(1).strip()

    fence_match = re.search(r"```(?:json)?\s*([\[\{].*?)\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    clean_text = _strip_a2a_wrappers(text).strip()

    json_start = -1
    for i, ch in enumerate(clean_text):
        if ch in ("[", "{"):
            json_start = i
            break

    json_end = -1
    for i, ch in enumerate(reversed(clean_text)):
        if ch in ("]", "}"):
            json_end = len(clean_text) - i
            break

    if json_start != -1 and json_end != -1 and json_start < json_end:
        return clean_text[json_start:json_end]

    return None


def _sanitize_json(text: str) -> str:
    text = text.replace("\u201c", '\\"').replace("\u201d", '\\"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text


def _parse_json_greedy(text: str) -> list:
    decoder = json.JSONDecoder()
    results = []
    idx = 0
    text = text.strip()
    while idx < len(text):
        while idx < len(text) and text[idx] in " \t\n\r":
            idx += 1
        if idx >= len(text):
            break
        if text[idx] not in '[{"tfn0123456789-':
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            break
        if isinstance(obj, list):
            results.extend(obj)
        else:
            results.append(obj)
        idx = end
    if not results:
        raise json.JSONDecodeError("No valid JSON found", text, 0)
    return results


def _repair_json(text: str) -> list | None:
    opens = {"{": "}", "[": "]"}
    closes = {"}", "]"}
    stack = []
    in_string = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in opens:
            stack.append(opens[ch])
        elif ch in closes:
            if stack and stack[-1] == ch:
                stack.pop()

    if not stack:
        try:
            result = json.loads(text)
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            return None

    suffix = '"' if in_string else ""
    repaired = text + suffix + "".join(reversed(stack))
    try:
        result = json.loads(repaired)
        return result if isinstance(result, list) else [result]
    except json.JSONDecodeError:
        return None


def before_model_callback(callback_context: Any, llm_request: Any) -> None:
    from google.genai import types

    if not getattr(llm_request, "contents", None):
        return None

    for content in llm_request.contents:
        if not getattr(content, "parts", None):
            continue
        clean_parts = [
            types.Part.from_text(text="[A2UI component rendered]")
            if (
                getattr(p, "inline_data", None)
                and p.inline_data.mime_type == "text/plain"
                and _A2UI_BLOB_MARKER in (p.inline_data.data or b"")
            )
            else p
            for p in content.parts
        ]
        content.parts[:] = clean_parts

    return None


def a2ui_callback(callback_context: Any, llm_response: Any) -> Any:
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    if not getattr(llm_response, "content", None) or not getattr(llm_response.content, "parts", None):
        return None

    a2ui_keys = {
        "beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface",
        "surfaceId", "components",
    }

    new_parts = []
    found_a2ui = False

    for part_idx, part in enumerate(llm_response.content.parts):
        if not getattr(part, "text", None):
            new_parts.append(part)
            continue

        text = part.text.strip()

        if "<a2a_datapart_json>" in text:
            stripped = _strip_a2a_wrappers(text).strip()
            if not stripped:
                continue
            text = stripped

        if not any(k in text for k in a2ui_keys):
            new_parts.append(types.Part.from_text(text=text))
            continue

        json_text = _extract_a2ui_json(text)
        if json_text is None:
            new_parts.append(types.Part.from_text(text=text))
            continue

        json_text = _sanitize_json(json_text)

        try:
            parsed = _parse_json_greedy(json_text)
        except json.JSONDecodeError:
            parsed = _repair_json(json_text)
            if parsed is None:
                new_parts.append(types.Part.from_text(text=text))
                continue

        if not isinstance(parsed, list):
            parsed = [parsed]

        wrapped_keys = {"beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface"}
        normalized: list[dict] = []
        for m in parsed:
            if not isinstance(m, dict):
                continue
            if any(k in m for k in wrapped_keys):
                normalized.append(m)
            elif "surfaceId" in m and "components" in m:
                surface_id = m["surfaceId"]
                components = m["components"]
                if components and isinstance(components, list) and isinstance(components[0], dict):
                    root_id = components[0].get("id", surface_id)
                    normalized.append(
                        {"beginRendering": {"surfaceId": surface_id, "root": root_id}}
                    )
                normalized.append(
                    {"surfaceUpdate": {"surfaceId": surface_id, "components": components}}
                )
            elif "surfaceId" in m:
                normalized.append(m)

        msgs = normalized
        if not msgs:
            new_parts.append(types.Part.from_text(text=text))
            continue

        has_begin = any("beginRendering" in m for m in msgs)
        if not has_begin:
            for m in msgs:
                if "surfaceUpdate" in m:
                    surface_id = m["surfaceUpdate"].get("surfaceId")
                    components = m["surfaceUpdate"].get("components", [])
                    if surface_id and components:
                        msgs.insert(
                            0,
                            {
                                "beginRendering": {
                                    "surfaceId": surface_id,
                                    "root": components[0]["id"],
                                }
                            },
                        )
                    break

        new_parts.extend([_wrap_a2ui_part(m) for m in msgs])
        found_a2ui = True

    global _latest_a2ui_stash
    pending = None
    if callback_context and hasattr(callback_context, "state") and _A2UI_PENDING_KEY in callback_context.state:
        pending = callback_context.state.get(_A2UI_PENDING_KEY)
        callback_context.state[_A2UI_PENDING_KEY] = None

    if not pending and _latest_a2ui_stash:
        pending = _latest_a2ui_stash
        _latest_a2ui_stash = None

    if pending:
        new_parts.extend([_wrap_a2ui_part(msg) for msg in pending])
        found_a2ui = True

    if not found_a2ui:
        return None

    return LlmResponse(
        content=types.Content(role="model", parts=new_parts),
        custom_metadata={"a2a:response": True},
    )
