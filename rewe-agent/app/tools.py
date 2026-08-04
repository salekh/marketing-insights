# Copyright 2026 Google LLC
import base64
import json

from google import genai
from google.adk.tools import ToolContext
from google.cloud import bigquery
from google.genai import types

# Configuration
PROJECT_ID = "sa-learning-1"
DATASET_ID = "rewe_marketing"

# Lazy singletons — initialized on first use so ADC is fully resolved
# when running on Agent Runtime (avoids credential errors at import time).
_bq_client: bigquery.Client | None = None
_genai_client: genai.Client | None = None


def _get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        use_vertexai = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ("true", "1")
        if use_vertexai:
            _genai_client = genai.Client(
                vertexai=True,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            )
        else:
            _genai_client = genai.Client(vertexai=False)
    return _genai_client


def get_customer_context(customer_id: str) -> dict:
    """Fetches holistic customer data including demographics, dietary tags, and market context.

    Args:
        customer_id: The unique ID of the customer (e.g., 'CUST001' or 'CUST_NEW_1_1').

    Returns:
        A dictionary containing customer demographics, dietary info, recent history, and current market context.
    """
    print(f"DEBUG: get_customer_context called for {customer_id}")
    # 1. Get Customer Info
    cust_query = f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.customers_360` WHERE customer_id = @cust_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("cust_id", "STRING", customer_id)
        ]
    )
    cust_rows = list(_get_bq_client().query(cust_query, job_config=job_config))

    if not cust_rows:
        print(f"DEBUG: Customer {customer_id} not found")
        return {"error": "Customer not found"}

    customer = dict(cust_rows[0])
    print(f"DEBUG: Found customer: {customer.get('persona_summary')}")

    # Fix: loyalty is a JSON column returned as string — deserialize it
    loyalty_raw = customer.get("loyalty")
    if isinstance(loyalty_raw, str):
        loyalty_data = json.loads(loyalty_raw)
    elif isinstance(loyalty_raw, dict):
        loyalty_data = loyalty_raw
    else:
        loyalty_data = {}

    # 2. Get Recent Interactions
    hist_query = f"SELECT event_type, object_id, timestamp FROM `{PROJECT_ID}.{DATASET_ID}.interaction_history` WHERE customer_id = @cust_id ORDER BY timestamp DESC LIMIT 5"
    history = [
        dict(row) for row in _get_bq_client().query(hist_query, job_config=job_config)
    ]

    # 3. Get Market Context (latest)
    context_query = f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.market_context` ORDER BY timestamp DESC LIMIT 1"
    context_rows = list(_get_bq_client().query(context_query))
    market_context = dict(context_rows[0]) if context_rows else {}

    result = {
        "customer": {
            "persona": customer.get("persona_summary"),
            "dietary_tags": customer.get("dietary_tags"),
            "price_sensitivity": customer.get("price_sensitivity"),
            "loyalty_tier": loyalty_data.get("tier"),
        },
        "recent_history": history,
        "market_context": market_context,
    }
    print(f"DEBUG: Returning result for {customer_id}")
    return result


def generate_seo_keywords(
    blog_theme: str,
    persona_summary: str,
    dietary_tags: list[str],
    language: str = "English",
) -> dict:
    """Uses an LLM to generate SEO-optimized keywords for the blog post, mocking a real SEO API.

    Args:
        blog_theme: The topic or theme of the blog post (e.g., 'summer salads', 'protein-rich breakfasts').
        persona_summary: A short description of the customer persona.
        dietary_tags: A list of dietary tags for the customer (e.g., ['vegan', 'gluten-free']).
        language: The language for generated keywords (default 'English'). Prevents language mixing.

    Returns:
        A dictionary with 'keywords' (list of 3), 'primary_keyword', and 'search_intent'.
    """
    print(f"DEBUG: generate_seo_keywords called for theme='{blog_theme}', language='{language}'")
    dietary_str = ", ".join(dietary_tags) if dietary_tags else "No dietary restrictions"

    prompt = f"""You are a senior SEO analyst for REWE, a leading German grocery retailer.
Generate exactly 3 high-impact, long-tail SEO keywords for a blog post.

Blog Theme: {blog_theme}
Customer Persona: {persona_summary}
Dietary Profile: {dietary_str}

IMPORTANT: ALL keywords MUST be in {language}. Do NOT mix languages.

Rules:
- Keywords must be specific and searchable (e.g., "vegan summer salad recipes" not just "salad")
- Align keywords with the persona's lifestyle and dietary needs
- Think about what this persona would type into Google in {language}
- One keyword should be transactional (buy/shop), one informational (how/what/why), one navigational (REWE branded)
- Every keyword must be entirely in {language} — no German words in English keywords or vice versa

Return ONLY a valid JSON object with this exact structure:
{{"keywords": ["keyword1", "keyword2", "keyword3"], "primary_keyword": "keyword1", "search_intent": "mixed"}}"""

    response = _get_genai_client().models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)
        print(f"DEBUG: SEO keywords generated: {result.get('keywords')}")
        return result
    except json.JSONDecodeError:
        # Graceful fallback
        return {
            "keywords": [blog_theme, f"{blog_theme} recipe", f"REWE {blog_theme}"],
            "primary_keyword": blog_theme,
            "search_intent": "informational",
        }


def get_product_recommendations(
    customer_id: str, blog_theme: str = "", language: str = "English"
) -> dict:
    """Article-aware product recommendations with category diversity and LLM curation.

    3-step pipeline:
      1. Fetch customer profile (dietary tags, price sensitivity, persona).
      2. Embed the blog_theme text via ML.GENERATE_EMBEDDING and use it as the
         VECTOR_SEARCH query — this finds products relevant to the **article**, not
         just the persona. A category-diverse window (max 3 per category_path)
         prevents homogeneous results like "5 types of pasta".
      3. An LLM curator selects 4-5 products from ~15 diverse candidates, weighing
         article fit, dietary safety, price sensitivity, and variety.

    Falls back to persona-embedding search if topic-embedding fails.

    Args:
        customer_id: The unique ID of the customer.
        blog_theme: The blog post topic — this drives the product selection.
        language: Language for usage_tips (default 'English'). Prevents language mixing.

    Returns:
        A dict with 'curated_recommendations' (4-5 products with reasoning),
        'candidate_count' (how many were considered), and 'blog_theme'.
    """
    print(
        f"DEBUG: get_product_recommendations called for {customer_id}, theme='{blog_theme}'"
    )

    cust_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("cust_id", "STRING", customer_id)
        ]
    )

    # --- Step 1: Fetch customer profile for curation context ---
    profile_query = f"""
    SELECT persona_summary, dietary_tags, price_sensitivity
    FROM `{PROJECT_ID}.{DATASET_ID}.customers_360`
    WHERE customer_id = @cust_id
    LIMIT 1
    """
    profile_rows = list(
        _get_bq_client().query(profile_query, job_config=cust_job_config)
    )
    customer_profile = dict(profile_rows[0]) if profile_rows else {}
    persona_summary = customer_profile.get("persona_summary", "General customer")
    dietary_tags = customer_profile.get("dietary_tags") or []
    price_sensitivity = customer_profile.get("price_sensitivity", "medium")

    # --- Step 2: Topic-seeded VECTOR_SEARCH with category diversity ---
    # Embed the blog theme and search by article relevance, not persona similarity.
    # ROW_NUMBER() PARTITION BY category_path enforces max 3 products per category.
    topic_search_query = f"""
    WITH topic_embedding AS (
        SELECT ml_generate_embedding_result AS embedding
        FROM ML.GENERATE_EMBEDDING(
            MODEL `{PROJECT_ID}.{DATASET_ID}.embedding_model`,
            (SELECT @blog_theme AS content),
            STRUCT(TRUE AS flatten_json_output, 768 AS output_dimensionality)
        )
    ),
    ranked AS (
        SELECT
            base.name,
            base.brand,
            base.category_path,
            base.price_current,
            base.marketing_copy,
            distance,
            ROW_NUMBER() OVER (
                PARTITION BY base.category_path ORDER BY distance ASC
            ) AS cat_rank
        FROM VECTOR_SEARCH(
            TABLE `{PROJECT_ID}.{DATASET_ID}.product_catalog`,
            'product_embedding',
            (SELECT embedding FROM topic_embedding),
            top_k => 200,
            distance_type => 'COSINE'
        )
    )
    SELECT name, brand, category_path, price_current, marketing_copy
    FROM ranked
    WHERE cat_rank <= 3
    ORDER BY distance ASC
    LIMIT 15
    """

    theme_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "blog_theme",
                "STRING",
                blog_theme or "popular REWE grocery products",
            )
        ]
    )

    try:
        candidates = [
            dict(row)
            for row in _get_bq_client().query(
                topic_search_query, job_config=theme_job_config
            )
        ]
        print(
            f"DEBUG: Topic-seeded search returned {len(candidates)} diverse candidates"
        )
    except Exception as e:
        print(f"DEBUG: Topic search failed ({e}), falling back to persona-based search")
        # Fallback: use persona_embedding with category diversity
        fallback_query = f"""
        WITH ranked AS (
            SELECT
                base.name, base.brand, base.category_path,
                base.price_current, base.marketing_copy, distance,
                ROW_NUMBER() OVER (
                    PARTITION BY base.category_path ORDER BY distance ASC
                ) AS cat_rank
            FROM VECTOR_SEARCH(
                TABLE `{PROJECT_ID}.{DATASET_ID}.product_catalog`,
                'product_embedding',
                (
                    SELECT persona_embedding
                    FROM `{PROJECT_ID}.{DATASET_ID}.customers_360`
                    WHERE customer_id = @cust_id LIMIT 1
                ),
                top_k => 200,
                distance_type => 'COSINE'
            )
        )
        SELECT name, brand, category_path, price_current, marketing_copy
        FROM ranked WHERE cat_rank <= 3
        ORDER BY distance ASC LIMIT 15
        """
        candidates = [
            dict(row)
            for row in _get_bq_client().query(
                fallback_query, job_config=cust_job_config
            )
        ]
        print(f"DEBUG: Persona fallback returned {len(candidates)} candidates")

    if not candidates:
        return {
            "curated_recommendations": [],
            "candidate_count": 0,
            "blog_theme": blog_theme,
        }

    # --- Step 3: LLM curation — select best 4-5 from diverse candidates ---
    candidates_text = "\n".join(
        f"{i + 1}. {c['name']} | Brand: {c['brand']} | "
        f"Category: {c['category_path']} | "
        f"Price: €{c['price_current']:.2f} | {c['marketing_copy']}"
        for i, c in enumerate(candidates)
    )
    dietary_str = ", ".join(dietary_tags) if dietary_tags else "No dietary restrictions"

    curation_prompt = f"""You are a REWE product curator for a blog article. Select the BEST 4-5 products that a reader of this specific article would actually want to buy.

ARTICLE TOPIC: {blog_theme or "General REWE products"}

CUSTOMER PROFILE:
- Persona: {persona_summary}
- Dietary restrictions: {dietary_str}
- Price sensitivity: {price_sensitivity}

CANDIDATE PRODUCTS (pre-filtered by article relevance with category diversity):
{candidates_text}

CURATION RULES:
1. ARTICLE FIT is the #1 priority — every product MUST make sense for a reader of this article
2. STRICTLY exclude products violating dietary restrictions (no meat/dairy for vegans, no gluten for celiac)
3. MAXIMIZE CATEGORY DIVERSITY — select from different category_path values; never pick 2+ near-identical products
4. Weight price sensitivity: "high" → prefer affordable, "low" → premium is fine
5. Each product should serve a different role in the article context (e.g., main ingredient, side, drink, snack)

For each product, write a "usage_tip" that is a PRACTICAL, ACTIONABLE suggestion tied to the article theme.
IMPORTANT: ALL usage_tips MUST be written in {language}. Do NOT mix languages.
Good usage_tips: "Toss with olive oil and grill for 3 min per side — perfect summer asparagus", "Blend with frozen berries for a post-workout smoothie", "Melt into a warm fondue as a cozy winter dessert"
Bad usage_tips: "Great for vegans", "Fits your healthy lifestyle", "A good match for this article"
The tip should read like advice from a friend — a mini recipe idea, a seasonal preparation method, or a creative pairing.

Return ONLY a valid JSON array with 4-5 objects:
[
  {{
    "name": "product name",
    "brand": "brand",
    "category_path": "category",
    "price_current": 0.00,
    "marketing_copy": "copy",
    "usage_tip": "1-2 sentence practical recipe idea or preparation tip tied to the article theme"
  }}
]"""

    try:
        curation_response = _get_genai_client().models.generate_content(
            model="gemini-3.6-flash",
            contents=curation_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        curated = json.loads(curation_response.text)
        # Defensive unwrap: some models return dict wrapper instead of bare array
        if isinstance(curated, dict):
            for key in (
                "recommendations",
                "products",
                "curated",
                "items",
                "results",
            ):
                if key in curated and isinstance(curated[key], list):
                    curated = curated[key]
                    break
            else:
                curated = [curated]
        print(
            f"DEBUG: LLM curated {len(curated)} products from {len(candidates)} candidates"
        )
    except Exception as e:
        print(f"DEBUG: LLM curation failed ({e}), returning top-5 candidates")
        curated = candidates[:5]

    return {
        "curated_recommendations": curated,
        "candidate_count": len(candidates),
        "blog_theme": blog_theme,
    }


async def generate_blog_image(
    prompt: str,
    tool_context: ToolContext,
    aspect_ratio: str = "16:9",
    image_size: str = "2K",
) -> dict:
    """Generates an AI marketing image and saves it as an ADK artifact.

    The image is saved via ToolContext.save_artifact() so the ADK web UI
    renders it inline automatically. The raw bytes never appear in the tool
    response (which would cause a 400 INVALID_ARGUMENT from the Gemini API).

    Args:
        prompt: A vivid description of the hero image for the blog post.
        tool_context: Injected by ADK — used to save the image as an artifact.
        aspect_ratio: Output aspect ratio (default "16:9").
        image_size: Output resolution (default "2K").

    Returns:
        A dict with 'status', 'alt_text', and 'artifact_filename'.
    """
    print(
        f"DEBUG: generate_blog_image called — {aspect_ratio} {image_size}: {prompt[:80]}..."
    )

    marketing_prompt = (
        f"Create a vibrant, high-quality marketing photograph for a REWE grocery retailer "
        f"blog post: {prompt}. "
        f"Style: professional food photography, bright natural lighting, appetizing composition, "
        f"retail-ready aesthetic. No text overlays."
    )

    response = await _get_genai_client().aio.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=marketing_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                output_mime_type="image/png",
            ),
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL,
            ),
        ),
    )

    # Check for content policy / finish errors before parsing
    candidate = response.candidates[0] if response.candidates else None
    if candidate is None:
        print("DEBUG: No candidates in response")
        return {"status": "failed", "alt_text": prompt, "reason": "No candidates"}

    if candidate.finish_reason != types.FinishReason.STOP:
        reason = candidate.finish_reason
        print(f"DEBUG: Image generation blocked — finish_reason: {reason}")
        return {"status": "blocked", "alt_text": prompt, "reason": str(reason)}

    # Extract image bytes — skip thought parts
    image_bytes = None
    alt_text = prompt
    parts = candidate.content.parts if candidate.content else []

    for part in parts:
        if part.thought:
            continue
        if part.inline_data is not None:
            raw = part.inline_data.data
            image_bytes = raw if isinstance(raw, bytes) else base64.b64decode(raw)
            print(
                f"DEBUG: Image extracted ({image_size}, {aspect_ratio}, {len(image_bytes)} bytes)"
            )
            break
        elif part.text:
            alt_text = part.text.strip()

    if image_bytes is None:
        print("DEBUG: No inline_data in response — generation may have been filtered")
        return {"status": "failed", "alt_text": alt_text, "reason": "No image in response"}

    # Save as ADK artifact — rendered inline by the ADK web UI.
    # Uses GcsArtifactService in production, InMemoryArtifactService locally.
    artifact_filename = "blog_hero_image.png"
    image_artifact = types.Part(
        inline_data=types.Blob(
            mime_type="image/png",
            data=image_bytes,
        )
    )
    version = await tool_context.save_artifact(
        filename=artifact_filename, artifact=image_artifact
    )
    print(
        f"DEBUG: Image saved as artifact '{artifact_filename}' v{version} "
        f"({len(image_bytes)} bytes)"
    )

    return {
        "status": "success",
        "alt_text": alt_text,
        "artifact_filename": artifact_filename,
    }

