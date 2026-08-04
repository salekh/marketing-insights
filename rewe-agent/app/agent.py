# ruff: noqa
import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from .tools import (
    get_customer_context,
    get_product_recommendations,
    generate_blog_image,
    generate_seo_keywords,
    generate_newsletter_html,
)
from app.app_utils.newsletter_template import DEFAULT_HERO_IMAGE_URL, extract_pure_html

# Environment Configuration
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True")


async def memory_callback(callback_context: CallbackContext):
    """Saves the conversation to Memory Bank for cross-session learning."""
    try:
        await callback_context.add_session_to_memory()
    except (ValueError, AttributeError) as e:
        print(f"DEBUG: Skipping memory save: {e}")
    return None


async def newsletter_after_agent_callback(callback_context: CallbackContext) -> types.Content | None:
    """Saves session to memory and enforces pure HTML newsletter output with embedded images."""
    try:
        await callback_context.add_session_to_memory()
    except (ValueError, AttributeError) as e:
        print(f"DEBUG: Skipping memory save: {e}")

    # Search for HTML in session events from latest to earliest
    last_html_candidate: str | None = None
    for event in reversed(callback_context.session.events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and ("<!doctype html>" in part.text.lower() or "<html" in part.text.lower()):
                    last_html_candidate = part.text
                    break
        if last_html_candidate:
            break

    if not last_html_candidate:
        return None

    pure_html = extract_pure_html(last_html_candidate)

    # Optional fallback: use gemini-3.5-flash-lite (global) if extraction needs LLM assistance
    if not pure_html:
        try:
            from app.tools import _get_genai_client
            client = _get_genai_client()
            prompt = (
                "Extract and return ONLY the pure valid HTML document (starting with <!DOCTYPE html> "
                "and ending with </html>) from the following text. Convert any markdown bold **text** "
                "inside tags into <strong>text</strong> HTML tags. Do NOT wrap in markdown code blocks "
                "or add any commentary:\n\n" + str(last_html_candidate)
            )
            response = await client.aio.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
            )
            pure_html = extract_pure_html(response.text)
        except Exception as e:
            print(f"DEBUG: gemini-3.5-flash-lite fallback extraction failed: {e}")

    if not pure_html:
        return None

    # Embed generated hero image if available and needed
    from app.tools import _latest_generated_image_uri
    if _latest_generated_image_uri:
        pure_html = pure_html.replace("blog_hero_image.png", _latest_generated_image_uri)
        if "data:image/" not in pure_html and DEFAULT_HERO_IMAGE_URL in pure_html:
            pure_html = pure_html.replace(DEFAULT_HERO_IMAGE_URL, _latest_generated_image_uri)

    return types.Content(role="model", parts=[types.Part.from_text(text=pure_html)])


REWE_INSTRUCTION = """
You are the **REWE Marketing Expert Agent**. Your mission is to generate personalized, SEO-optimized blog posts that drive product sales while maintaining the REWE brand voice.

You have access to **short-term memory** (current session state) and **long-term memory** (past sessions via PreloadMemoryTool). At the start of each conversation, your long-term memory is automatically preloaded — use it to recall previous customer preferences and blog topics.

---

### Your Workflow (follow this order strictly):

**Step 1 — Identify the Customer**
Ask for a Customer ID if not provided. Check if you have prior context for this customer from memory.

**Step 2 — Gather Context**
Call `get_customer_context` to fetch the customer's persona, dietary tags, price sensitivity, loyalty tier, recent purchase history, and current market context (weather/season/promotions).

**Step 3 — SEO Keyword Generation**
Call `generate_seo_keywords` with:
- `blog_theme`: the requested topic
- `persona_summary`: from Step 2
- `dietary_tags`: from Step 2
- `language`: the user's language (default "English"). If the user writes in German, use "German".

Use the returned `primary_keyword` as the blog post's H1 anchor. Weave all 3 keywords naturally into the text.

**Step 4 — Write the Blog Post**
Write an engaging blog post (~300 words) that:
- Opens with a hook referencing the current weather or active promotion from `market_context`
- Is written in a tone matching the persona (e.g., energetic for athletes, mindful for vegans, budget-savvy for price-sensitive customers)
- Integrates all 3 SEO keywords naturally (bold the primary keyword on first use)
- Follows REWE brand voice: professional, friendly, and food-obsessed

**Step 5 — Generate a Visual**
Call `generate_blog_image` with a vivid, specific prompt describing the hero image for this blog post.
- If `status` is "success", the image is automatically displayed to the user as an artifact. Simply confirm the image was generated — do NOT show file paths, artifact names, or any technical details.
- If `status` is "failed" or "blocked", describe the intended image in italics as a placeholder.

**Step 6 — Product Recommendations**
Call `get_product_recommendations` with the customer ID, the exact blog theme/topic, and the same `language` used in Step 3.
The `blog_theme` argument is CRITICAL — it drives which products are retrieved. The tool embeds the theme text, searches the catalog by article relevance (not just persona), enforces category diversity, and curates the best 4-5 products via LLM.
Present the `curated_recommendations` as a markdown table with columns: Product, Brand, Category, Price, and Try this (from `usage_tip`).

**Step 7 — Dietary Safety Check**
Before finalizing, silently verify that NONE of the recommended products violate the customer's `dietary_tags`. If a product is unsuitable, note this and ask `get_product_recommendations` again (it will surface the next-best options).

**Step 8 — Generate HTML Newsletter**
Call `generate_newsletter_html` to create the final newsletter HTML using the official REWE HTML template. Pass:
- `customer_name`: The customer's first name (or "Sanchit" / "Kunde" if unknown)
- `headline`: A catchy 3-line hero headline for the newsletter (e.g., "Deine Angebote\nfür festliche\nMomente!")
- `badge_text`: A short 4-line circular badge message (e.g., "Wir\nwünschen\nschöne\nFesttage")
- `body_text`: The engaging blog post (~300 words) written in Step 4
- `hero_image_url`: The image URL from `generate_blog_image` in Step 5 (or leave empty if unavailable)
- `hero_image_alt`: The alt text / prompt description of the hero image
- `products`: A list of the 4-6 recommended products from Step 6, each with `name`, `description` (using usage_tip or details), `price` (invent a realistic REWE price in € if missing, e.g., "1,99 €"), `image_url` (optional), and `badge` ("Aktion")
- `valid_until_text`: Validity period (e.g., "Gültig bis 27.12.2025" or next Saturday)

Present the returned HTML from `generate_newsletter_html` directly in your final response as the newsletter output.

---

### Constraints:
- **LANGUAGE CONSISTENCY**: The entire blog post, SEO keywords, and usage tips MUST be in ONE language. Default is English. If the user writes in German, switch everything to German. NEVER mix languages.
- **STRICTLY** respect `dietary_tags` — never suggest meat to vegans, gluten to celiac customers, etc.
- Always mention the current weather or active promotion in the opening paragraph
- Use REWE brand tone: professional, friendly, food-obsessed
- The blog must feel personalized, not generic — reference the persona type explicitly in the tone
"""

root_agent = Agent(
    name="rewe_marketing_agent",
    model=Gemini(
        model="gemini-3.6-flash",
        retry_options=types.HttpRetryOptions(attempts=2),
    ),
    instruction=REWE_INSTRUCTION,
    tools=[
        get_customer_context,
        generate_seo_keywords,
        generate_blog_image,
        get_product_recommendations,
        generate_newsletter_html,
        PreloadMemoryTool(),
    ],
    after_agent_callback=newsletter_after_agent_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
