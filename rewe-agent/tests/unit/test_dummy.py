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
"""
You can add your unit tests here.
This is where you test your business logic, including agent functionality,
data processing, and other core components of your application.
"""


from app.app_utils.newsletter_template import render_newsletter_html


def test_render_newsletter_html_default() -> None:
    """Test that render_newsletter_html produces valid HTML with default/invented values."""
    html_out = render_newsletter_html()
    assert "<!DOCTYPE html>" in html_out
    assert "Hallo Sanchit," in html_out
    assert "Goldene Kiwi" in html_out
    assert "Angebote bis Samstag bei" in html_out


def test_render_newsletter_html_custom() -> None:
    """Test that render_newsletter_html populates custom placeholders correctly."""
    html_out = render_newsletter_html(
        customer_name="Anna",
        headline="Winter Angebote",
        badge_text="Schöne Feiertage",
        body_text="Tolles Festtagessen bei REWE!",
        products=[
            {"name": "Bio Apfel", "price": "1,99 €", "usage_tip": "Frisch und lecker"},
            {"name": "REWE Brot", "price": "2,49 €"},
        ],
    )
    assert "Hallo Anna," in html_out
    assert "Winter Angebote" in html_out
    assert "Schöne<br>Feiertage" in html_out
    assert "Tolles Festtagessen bei REWE!" in html_out
    assert "Bio Apfel" in html_out
    assert "1,99 €" in html_out
    assert "REWE Brot" in html_out


def test_clean_markdown_in_newsletter() -> None:
    """Test that markdown formatting (bold, italic) is cleaned into HTML tags."""
    html_out = render_newsletter_html(
        headline="**REWE organic summer party snacks**",
        body_text="Enjoy *fresh* food today!",
    )
    assert "<strong>REWE organic summer party snacks</strong>" in html_out
    assert "<em>fresh</em>" in html_out
    assert "**" not in html_out


def test_render_newsletter_a2ui() -> None:
    """Test that render_newsletter_a2ui produces a valid A2UI v0.8 GE-compatible payload."""
    from app.app_utils.newsletter_a2ui import render_newsletter_a2ui

    a2ui_out = render_newsletter_a2ui(
        customer_name="Sanchit",
        headline="**REWE organic summer party snacks**",
        body_text="Enjoy *fresh* food today!",
    )
    assert len(a2ui_out) == 2
    begin_env = a2ui_out[0]
    assert begin_env["version"] == "v0.8"
    assert "beginRendering" in begin_env
    assert begin_env["beginRendering"]["surfaceId"] == "rewe-newsletter-a2ui"

    update_env = a2ui_out[1]
    assert update_env["version"] == "v0.8"
    assert "surfaceUpdate" in update_env
    surface = update_env["surfaceUpdate"]
    assert surface["surfaceId"] == "rewe-newsletter-a2ui"
    assert "components" in surface
    assert len(surface["components"]) > 10
    # Ensure markdown was cleaned
    text_values = []
    for comp in surface["components"]:
        if "Text" in comp.get("component", {}):
            text_values.append(comp["component"]["Text"]["text"].get("literalString", ""))
    assert any("REWE organic summer party snacks" in val for val in text_values)
    assert not any("**" in val for val in text_values)


def test_extract_text_and_a2ui() -> None:
    """Test that extract_text_and_a2ui separates human readable summary text and pure A2UI JSON array."""
    from app.app_utils.newsletter_a2ui import extract_text_and_a2ui

    sample_output = (
        "Here is the personalized blog post and SEO strategy for Sanchit.\n\n"
        "📝 SEO Strategy & Blog Post\nSome great content here.\n\n"
        "📧 Generated A2UI Newsletter Payload\n"
        '[{"version": "v0.8", "beginRendering": {"surfaceId": "rewe-newsletter-a2ui", "root": "root", "catalogId": "https://a2ui.org/specification/v0_8/basic_catalog.json"}}, {"version": "v0.8", "surfaceUpdate": {"surfaceId": "rewe-newsletter-a2ui", "components": []}}]'
    )
    text_part, a2ui_part = extract_text_and_a2ui(sample_output)
    assert "SEO Strategy & Blog Post" in text_part
    assert "Generated A2UI Newsletter Payload" not in text_part
    assert a2ui_part.startswith("[") and a2ui_part.endswith("]")
    assert "rewe-newsletter-a2ui" in a2ui_part


def test_wrap_a2ui_part() -> None:
    """Test that _wrap_a2ui_part formats an A2UI message as an inline_data blob for ADK Dev-UI rendering."""
    from app.app_utils.newsletter_a2ui import _wrap_a2ui_part

    envelope = {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": "rewe-newsletter-a2ui",
            "catalogId": "https://a2ui.org/specification/v0_9/basic_catalog.json",
            "components": [],
        },
    }
    part = _wrap_a2ui_part(envelope)
    assert part.inline_data is not None
    assert part.inline_data.mime_type == "text/plain"
    assert b"<a2a_datapart_json>" in part.inline_data.data
    assert b"rewe-newsletter-a2ui" in part.inline_data.data
