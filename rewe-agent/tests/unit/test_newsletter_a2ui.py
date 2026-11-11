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
"""Contract tests for the REWE A2UI newsletter (GE wire format + A2UI schema)."""

import json

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.app_utils import rewe_brand
from app.app_utils.newsletter_a2ui import (
    A2UI_MIME_TYPE,
    after_model_callback,
    before_model_callback,
    build_newsletter_surfaces,
    stash_pending,
    wrap_a2ui_part,
)

_URLS = {
    k: f"https://storage.googleapis.com/b/{k}.png"
    for k in ("header", "hero", "banner", "footer", "logo")
}
_PRODUCTS = [
    {"display_name": f"Produkt {i}", "tip": "Tipp **fett**", "meta": "REWE · 1,99 €"}
    for i in range(4)
]


def _messages(version: str, monkeypatch) -> list[dict]:
    monkeypatch.setenv("A2UI_VERSION", version)
    return build_newsletter_surfaces(
        surface_id="s1",
        urls=_URLS,
        customer_name="Anna",
        body_text="Hallo **Welt**",
        cta_text="Los",
        cta_url="https://www.rewe.de/",
        products=_PRODUCTS,
        product_urls=[f"https://storage.googleapis.com/b/p{i}.jpg" for i in range(4)],
        insights={
            "seo_keywords": ["a", "b", "c"],
            "primary_keyword": "a",
            "persona": "Veganer",
            "dietary_tags": ["vegan"],
            "market_hook": "Sonne",
            "product_count": 4,
        },
        logo_url=_URLS["logo"],
    )


def _by_surface(msgs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for m in msgs:
        body = next(v for k, v in m.items() if k != "version")
        out.setdefault(body["surfaceId"], []).append(m)
    return out


@pytest.mark.parametrize("version,spec", [("v0.9", "0.9"), ("v0.8", "0.8")])
def test_messages_validate_against_a2ui_schema(version, spec, monkeypatch):
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.manager import A2uiSchemaManager

    catalog = A2uiSchemaManager(
        version=spec, catalogs=[BasicCatalog.get_config(spec)]
    ).get_selected_catalog()
    surfaces = _by_surface(_messages(version, monkeypatch))
    assert len(surfaces) == 2  # newsletter + campaign brief
    for msgs in surfaces.values():
        catalog.validator.validate(msgs)


def test_v09_sets_rewe_theme_and_root(monkeypatch):
    msgs = _messages("v0.9", monkeypatch)
    create = msgs[0]["createSurface"]
    assert msgs[0]["version"] == "v0.9"
    assert create["theme"]["primaryColor"] == "#CC071E"
    comps = msgs[1]["updateComponents"]["components"]
    assert comps[0]["id"] == "root"
    images = [c for c in comps if c["component"] == "Image"]
    assert all(c["url"].startswith("https://") for c in images)


def test_v08_has_no_version_field(monkeypatch):
    msgs = _messages("v0.8", monkeypatch)
    assert all("version" not in m for m in msgs)
    assert "beginRendering" in msgs[1]


def test_envelope_matches_ge_planner_contract(monkeypatch):
    for m in _messages("v0.9", monkeypatch):
        part = wrap_a2ui_part(m)
        assert part.inline_data.mime_type == "text/plain"
        data = part.inline_data.data
        assert data.startswith(b"<a2a_datapart_json>")
        assert data.endswith(b"</a2a_datapart_json>")
        inner = json.loads(
            data[len(b"<a2a_datapart_json>") : -len(b"</a2a_datapart_json>")]
        )
        assert (
            inner["metadata"]["mimeType"] == A2UI_MIME_TYPE == "application/json+a2ui"
        )
        assert isinstance(inner["data"], dict)  # one message per part, never a list
        assert len(data) < 1024 * 1024


class _Ctx:
    def __init__(self):
        self.state: dict = {}


def test_after_model_callback_injects_only_on_final_turn(monkeypatch):
    ctx = _Ctx()
    stash_pending(ctx.state, _messages("v0.9", monkeypatch))

    tool_turn = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(name="x", args={}))],
        )
    )
    assert after_model_callback(ctx, tool_turn) is None
    assert ctx.state["temp:a2ui_pending"]

    final = LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text="Hier ist dein Newsletter.")]
        )
    )
    out = after_model_callback(ctx, final)
    assert out.content.parts[0].text == "Hier ist dein Newsletter."
    assert len(out.content.parts) == 1 + 4
    assert not ctx.state["temp:a2ui_pending"]


def test_before_model_callback_strips_ui_blobs(monkeypatch):
    msg = _messages("v0.9", monkeypatch)[0]

    class _Req:
        def __init__(self):
            self.contents = [
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="hi"), wrap_a2ui_part(msg)],
                )
            ]

    req = _Req()
    before_model_callback(None, req)
    parts = req.contents[0].parts
    assert all(p.inline_data is None for p in parts)
    assert "A2UI" in parts[-1].text


def test_brand_renderers_produce_images():
    assert rewe_brand.render_header("KW 1").startswith(b"\x89PNG")
    assert (
        rewe_brand.render_hero(None, "Headline", "Badge", "Für dich")[:2] == b"\xff\xd8"
    )
    assert (
        rewe_brand.render_product_tile(
            None, "Tofu", "1.99", "Aktion", "-20%", "10% Bonus", "je 200 g"
        )[:2]
        == b"\xff\xd8"
    )
    assert rewe_brand.render_section_banner("Angebote", "bis Sa.").startswith(
        b"\x89PNG"
    )
    assert rewe_brand.render_promo_tile()[:2] == b"\xff\xd8"
    assert rewe_brand.render_footer().startswith(b"\x89PNG")
