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
"""A2UI rendering of the REWE newsletter for Gemini Enterprise (GE).

How GE renders A2UI from an ADK agent on Agent Engine (``adkAgentDefinition``):
Dolphin forwards the ADK event unchanged and the GE planner turns every
``inline_data`` part that matches *exactly* the following into a UI event::

    mime_type = "text/plain"
    data      = b'<a2a_datapart_json>{"data": <ONE A2UI message>,
                  "metadata": {"mimeType": "application/json+a2ui"}}</a2a_datapart_json>'

Constraints from the GE planner (ui_event_utils.cc): no whitespace around the
tags, mime ``application/json+a2ui`` (NOT ``application/a2ui+json``), one A2UI
message per part (no arrays), <= 1 MiB per part, nesting depth <= 64. The same
envelope is also what ADK's A2A part converter turns into a proper A2A
``DataPart`` - so the agent renders identically if it is registered as an A2A
agent instead.

Spec versions: GE supports A2UI v0.9 (Angular renderer, Basic/Material/Custom
catalogs, ``theme.primaryColor`` honoured) and v0.8 (Lit renderer, maintenance
mode). We emit v0.9 + Basic catalog by default; set ``A2UI_VERSION=v0.8`` to
emit the v0.8 Standard catalog instead (e.g. for older ADK Web builds).

Layout strategy: brand-critical artwork (masthead, hero, offer banner, price
tags, footer) is rendered as images by :mod:`app.app_utils.rewe_brand` with
the real REWE wordmark and bundled fonts; copy, product names and CTAs are
native A2UI components so they stay accessible, selectable and themeable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

A2UI_MIME_TYPE = "application/json+a2ui"  # the only mime GE accepts
_BLOB_START = b"<a2a_datapart_json>"
_BLOB_END = b"</a2a_datapart_json>"
_PENDING_KEY = "temp:a2ui_pending"
_MAX_PART_BYTES = 900 * 1024  # GE hard limit is 1 MiB per part

V09_BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
V08_STANDARD_CATALOG_ID = (
    "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
)

REWE_PRIMARY_HEX = "#CC071E"


def a2ui_version() -> str:
    v = os.environ.get("A2UI_VERSION", "v0.9").strip().lower()
    return "v0.8" if v in ("v0.8", "0.8") else "v0.9"


# --------------------------------------------------------------------------- #
# Version-neutral component tree
# --------------------------------------------------------------------------- #
@dataclass
class Node:
    id: str
    kind: str  # Text | Image | Column | Row | Card | Button | Divider
    props: dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    child: str | None = None
    weight: float | None = None


class Surface:
    """Collects nodes and serialises them to A2UI v0.9 or v0.8 messages."""

    def __init__(
        self, surface_id: str, display_name: str = "", icon_url: str = ""
    ) -> None:
        self.surface_id = surface_id
        self.display_name = display_name
        self.icon_url = icon_url
        self.nodes: dict[str, Node] = {}

    # -- builders ---------------------------------------------------------- #
    def add(self, node: Node) -> str:
        self.nodes[node.id] = node
        return node.id

    def text(
        self, id: str, text: str, variant: str = "body", weight: float | None = None
    ) -> str:
        return self.add(
            Node(id, "Text", {"text": text, "variant": variant}, weight=weight)
        )

    def image(
        self,
        id: str,
        url: str,
        alt: str = "",
        fit: str = "contain",
        variant: str = "mediumFeature",
        weight: float | None = None,
    ) -> str:
        return self.add(
            Node(
                id,
                "Image",
                {"url": url, "alt": alt, "fit": fit, "variant": variant},
                weight=weight,
            )
        )

    def column(
        self,
        id: str,
        children: list[str],
        align: str = "stretch",
        justify: str = "start",
        weight: float | None = None,
    ) -> str:
        return self.add(
            Node(
                id,
                "Column",
                {"align": align, "justify": justify},
                children=children,
                weight=weight,
            )
        )

    def row(
        self,
        id: str,
        children: list[str],
        align: str = "stretch",
        justify: str = "start",
        weight: float | None = None,
    ) -> str:
        return self.add(
            Node(
                id,
                "Row",
                {"align": align, "justify": justify},
                children=children,
                weight=weight,
            )
        )

    def card(self, id: str, child: str, weight: float | None = None) -> str:
        return self.add(Node(id, "Card", child=child, weight=weight))

    def divider(self, id: str) -> str:
        return self.add(Node(id, "Divider"))

    def link_button(
        self,
        id: str,
        label: str,
        url: str,
        primary: bool = True,
        weight: float | None = None,
    ) -> str:
        label_id = self.text(f"{id}_label", label, "body")
        return self.add(
            Node(
                id,
                "Button",
                {"url": url, "primary": primary},
                child=label_id,
                weight=weight,
            )
        )

    # -- serialisation ----------------------------------------------------- #
    def _v09_component(self, n: Node) -> dict[str, Any]:
        c: dict[str, Any] = {"id": n.id, "component": n.kind}
        p = n.props
        if n.kind == "Text":
            c["text"] = p["text"]
            c["variant"] = p.get("variant", "body")
        elif n.kind == "Image":
            c["url"] = p["url"]
            if p.get("alt"):
                c["description"] = p["alt"]
            c["fit"] = {"scale-down": "scaleDown"}.get(p["fit"], p["fit"])
            c["variant"] = p.get("variant", "mediumFeature")
        elif n.kind in ("Column", "Row"):
            c["children"] = list(n.children)
            c["align"] = p.get("align", "stretch")
            c["justify"] = p.get("justify", "start")
        elif n.kind == "Card":
            c["child"] = n.child
        elif n.kind == "Button":
            c["child"] = n.child
            c["variant"] = "primary" if p.get("primary") else "default"
            c["action"] = {
                "functionCall": {
                    "call": "openUrl",
                    "args": {"url": p["url"]},
                    "returnType": "void",
                }
            }
        elif n.kind == "Divider":
            c["axis"] = "horizontal"
        if n.weight is not None:
            c["weight"] = n.weight
        return c

    def _v08_component(self, n: Node) -> dict[str, Any]:
        p = n.props
        body: dict[str, Any]
        if n.kind == "Text":
            body = {
                "text": {"literalString": p["text"]},
                "usageHint": p.get("variant", "body"),
            }
        elif n.kind == "Image":
            body = {
                "url": {"literalString": p["url"]},
                "fit": {"scaleDown": "scale-down"}.get(p["fit"], p["fit"]),
            }
            if p.get("alt"):
                body["altText"] = {"literalString": p["alt"]}
        elif n.kind in ("Column", "Row"):
            body = {
                "children": {"explicitList": list(n.children)},
                "alignment": p.get("align", "stretch"),
                "distribution": p.get("justify", "start")
                if p.get("justify") != "stretch"
                else "start",
            }
        elif n.kind == "Card":
            body = {"child": n.child}
        elif n.kind == "Button":
            body = {
                "child": n.child,
                "primary": bool(p.get("primary")),
                "action": {
                    "name": "open_url",
                    "context": [{"key": "url", "value": {"literalString": p["url"]}}],
                },
            }
        else:
            body = {"axis": "horizontal"}
        c: dict[str, Any] = {"id": n.id, "component": {n.kind: body}}
        if n.weight is not None:
            c["weight"] = n.weight
        return c

    def _chunks(self, comps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Greedy-pack components so each message part stays < 1 MiB."""
        out: list[list[dict[str, Any]]] = [[]]
        size = 0
        for c in comps:
            s = len(json.dumps(c, ensure_ascii=False).encode("utf-8"))
            if out[-1] and size + s > _MAX_PART_BYTES:
                out.append([])
                size = 0
            out[-1].append(c)
            size += s
        return out

    def messages(self, version: str | None = None) -> list[dict[str, Any]]:
        version = version or a2ui_version()
        if version == "v0.8":
            comps = [self._v08_component(n) for n in self.nodes.values()]
            msgs: list[dict[str, Any]] = [
                {"surfaceUpdate": {"surfaceId": self.surface_id, "components": ch}}
                for ch in self._chunks(comps)
            ]
            msgs.append(
                {
                    "beginRendering": {
                        "surfaceId": self.surface_id,
                        "root": "root",
                        "styles": {"primaryColor": REWE_PRIMARY_HEX, "font": "Barlow"},
                    }
                }
            )
            return msgs

        theme: dict[str, Any] = {"primaryColor": REWE_PRIMARY_HEX}
        if self.display_name:
            theme["agentDisplayName"] = self.display_name
        if self.icon_url.startswith("https://"):
            theme["iconUrl"] = self.icon_url
        comps = [self._v09_component(n) for n in self.nodes.values()]
        msgs = [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": self.surface_id,
                    "catalogId": V09_BASIC_CATALOG_ID,
                    "theme": theme,
                },
            }
        ]
        msgs.extend(
            {
                "version": "v0.9",
                "updateComponents": {"surfaceId": self.surface_id, "components": ch},
            }
            for ch in self._chunks(comps)
        )
        return msgs


# --------------------------------------------------------------------------- #
# Newsletter layout
# --------------------------------------------------------------------------- #
def build_newsletter_surfaces(
    *,
    surface_id: str,
    urls: dict[str, str],
    customer_name: str,
    body_text: str,
    cta_text: str,
    cta_url: str,
    products: list[dict[str, Any]],
    product_urls: list[str],
    hero_alt: str = "",
    insights: dict[str, Any] | None = None,
    logo_url: str = "",
    strings: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Returns the full A2UI message list (newsletter + optional insights)."""
    t = strings or {}
    s = Surface(surface_id, display_name="REWE Newsletter", icon_url=logo_url)

    root_children: list[str] = []
    root_children.append(
        s.image(
            "masthead",
            urls["header"],
            t.get("masthead_alt", "REWE – Dein Markt"),
            fit="contain",
        )
    )
    root_children.append(
        s.image(
            "hero",
            urls["hero"],
            hero_alt or t.get("hero_alt", "Newsletter"),
            fit="contain",
        )
    )

    # Personal letter (native text so it stays readable/selectable).
    greeting = s.text(
        "greeting",
        t.get("greeting", "Hallo {name},").format(name=customer_name)
        if customer_name
        else t.get("greeting_anon", "Hallo,"),
        "h2",
    )
    body = s.text("body", body_text.strip(), "body")
    signoff = s.text("signoff", t.get("signoff", "**REWE**"), "body")
    cta = s.link_button("cta", cta_text, cta_url, primary=True)
    app_btn = s.link_button(
        "cta_app",
        t.get("cta2", "Prospekt ansehen"),
        "https://www.rewe.de/angebote/",
        primary=False,
    )
    cta_row = s.row("cta_row", [cta, app_btn], align="center", justify="start")
    letter_col = s.column("letter_col", [greeting, body, signoff, cta_row])
    root_children.append(s.card("letter", letter_col))

    root_children.append(
        s.image("offers_banner", urls["banner"], t.get("banner", ""), fit="contain")
    )

    # 2-up product grid.
    tiles: list[str] = []
    for i, (p, url) in enumerate(zip(products, product_urls, strict=False)):
        name = s.text(f"p{i}_name", p["display_name"], "h4")
        parts = [
            s.image(f"p{i}_img", url, p.get("alt") or p["display_name"], fit="contain"),
            name,
        ]
        if p.get("tip"):
            parts.append(s.text(f"p{i}_tip", p["tip"], "body"))
        if p.get("meta"):
            parts.append(s.text(f"p{i}_meta", p["meta"], "caption"))
        col = s.column(f"p{i}_col", parts)
        tiles.append(s.card(f"p{i}_card", col, weight=1))
    for r in range(0, len(tiles), 2):
        root_children.append(
            s.row(f"grid_{r // 2}", tiles[r : r + 2], align="stretch", justify="start")
        )

    root_children.append(
        s.image("footer", urls["footer"], "REWE Markt GmbH", fit="contain")
    )
    s.column("root", root_children)
    # Ensure the root is emitted first for renderers that build top-down.
    s.nodes = {"root": s.nodes.pop("root"), **s.nodes}
    messages = s.messages()

    if insights:
        messages.extend(
            _build_insights_surface(f"{surface_id}-insights", insights, logo_url, t)
        )
    return messages


def _build_insights_surface(
    surface_id: str, insights: dict[str, Any], logo_url: str, t: dict[str, str]
) -> list[dict[str, Any]]:
    """Compact 'campaign brief' card for the marketer (keywords, persona...)."""
    s = Surface(surface_id, display_name=t.get("ins_name", "REWE"), icon_url=logo_url)
    rows: list[str] = [s.text("title", t.get("ins_title", "Brief"), "h3")]

    def kv(key: str, label: str, value: str) -> None:
        if not value:
            return
        k = s.text(f"{key}_k", label, "caption", weight=1)
        v = s.text(f"{key}_v", value, "body", weight=3)
        rows.append(s.row(f"{key}_row", [k, v], align="start"))

    kws = insights.get("seo_keywords") or []
    if kws:
        primary = insights.get("primary_keyword") or kws[0]
        kv(
            "kw",
            t.get("ins_kw", "SEO"),
            "  \n".join(
                f"**{k}** ({t.get('ins_primary', 'primary')})" if k == primary else k
                for k in kws
            ),
        )
    kv("persona", t.get("ins_persona", "Persona"), insights.get("persona", ""))
    tags = insights.get("dietary_tags") or []
    kv(
        "diet",
        t.get("ins_diet", "Diet"),
        t.get("ins_diet_ok", "{tags}").format(tags=", ".join(tags))
        if tags
        else t.get("ins_diet_none", "-"),
    )
    kv("hook", t.get("ins_hook", "Hook"), insights.get("market_hook", ""))
    kv(
        "products",
        t.get("ins_products", "Products"),
        str(insights.get("product_count", "")),
    )
    s.column("insights_col", rows)
    s.card("root_card", "insights_col")
    s.column("root", ["root_card"])
    s.nodes = {"root": s.nodes.pop("root"), **s.nodes}
    return s.messages()


# --------------------------------------------------------------------------- #
# Envelope + ADK callbacks
# --------------------------------------------------------------------------- #
def wrap_a2ui_part(message: dict[str, Any]):
    """Wraps ONE A2UI message in the exact inline_data envelope GE expects."""
    from google.genai import types

    payload = json.dumps(
        {"data": message, "metadata": {"mimeType": A2UI_MIME_TYPE}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return types.Part(
        inline_data=types.Blob(
            data=_BLOB_START + payload + _BLOB_END, mime_type="text/plain"
        )
    )


def is_a2ui_part(part: Any) -> bool:
    blob = getattr(part, "inline_data", None)
    return bool(
        blob is not None
        and blob.mime_type == "text/plain"
        and (blob.data or b"").startswith(_BLOB_START)
    )


def stash_pending(state: Any, messages: list[dict[str, Any]]) -> None:
    pending = list(state.get(_PENDING_KEY) or [])
    pending.extend(messages)
    state[_PENDING_KEY] = pending


def before_model_callback(callback_context: Any, llm_request: Any) -> None:
    """Replaces rendered A2UI blobs in history with a short placeholder.

    Keeps the prompt small and stops the model from echoing UI JSON.
    """
    from google.genai import types

    for content in getattr(llm_request, "contents", None) or []:
        parts = getattr(content, "parts", None)
        if not parts:
            continue
        if any(is_a2ui_part(p) for p in parts):
            cleaned = [p for p in parts if not is_a2ui_part(p)]
            cleaned.append(
                types.Part.from_text(
                    text="[REWE newsletter rendered for the user as an A2UI widget]"
                )
            )
            content.parts[:] = cleaned
    return None


def after_model_callback(callback_context: Any, llm_response: Any) -> Any:
    """Appends pending A2UI parts to the final (non-tool-call) model turn."""
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    if getattr(llm_response, "partial", False):
        return None
    state = getattr(callback_context, "state", None)
    if state is None:
        return None
    pending = state.get(_PENDING_KEY)
    if not pending:
        return None
    content = getattr(llm_response, "content", None)
    parts = list(getattr(content, "parts", None) or [])
    if any(getattr(p, "function_call", None) for p in parts):
        return None  # model is still working; inject on the final answer
    state[_PENDING_KEY] = None

    # Drop anything that looks like hand-written UI JSON from the model text.
    text_parts = [
        p
        for p in parts
        if not (
            getattr(p, "text", None)
            and ("createSurface" in p.text or "beginRendering" in p.text)
        )
    ]
    ui_parts = [wrap_a2ui_part(m) for m in pending]
    return LlmResponse(
        content=types.Content(role="model", parts=text_parts + ui_parts),
        usage_metadata=getattr(llm_response, "usage_metadata", None),
    )


# Backwards-compatible aliases (older agent.py imports).
_before_model_callback = before_model_callback
_after_model_callback = after_model_callback
a2ui_callback = after_model_callback
