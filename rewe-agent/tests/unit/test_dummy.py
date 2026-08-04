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
    """Test that render_newsletter_a2ui produces a valid A2UI v0.9 createSurface payload."""
    from app.app_utils.newsletter_a2ui import render_newsletter_a2ui

    a2ui_out = render_newsletter_a2ui(
        customer_name="Sanchit",
        headline="**REWE organic summer party snacks**",
        body_text="Enjoy *fresh* food today!",
    )
    assert len(a2ui_out) == 1
    envelope = a2ui_out[0]
    assert envelope["version"] == "v0.9"
    assert "createSurface" in envelope
    surface = envelope["createSurface"]
    assert surface["surfaceId"] == "rewe-newsletter-a2ui"
    assert "components" in surface
    assert len(surface["components"]) > 10
    # Ensure markdown was cleaned
    text_values = [
        comp.get("text", "")
        for comp in surface["components"]
        if comp.get("component") == "Text"
    ]
    assert any("REWE organic summer party snacks" in val for val in text_values)
    assert not any("**" in val for val in text_values)
