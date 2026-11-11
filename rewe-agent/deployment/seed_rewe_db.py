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
"""Rebuilds and multiplies the ``sa-learning-1.rewe_marketing`` BigQuery dataset.

Targets:
  * ``product_catalog``:     5,200 unique products (up from 433 / 193 distinct IDs)
  * ``customers_360``:       2,000 unique customers (up from 202 / 151 distinct IDs)
  * ``interaction_history``: 20,000 events (up from 1,211), 100% referentially &
                             dietarily consistent over the past 90 days
  * ``market_context``:      all 16 German federal states with current Autumn 2026
                             weather & promotions

All 768-dim embeddings are computed in BigQuery via ``ML.GENERATE_EMBEDDING``
using ``rewe_marketing.embedding_model`` (``text-embedding-004``). Tables are
built and verified in ``_staging_*`` tables before replacing production, and a
COSINE vector index is created on ``product_catalog(product_embedding)``.

Usage:
    uv run python deployment/seed_rewe_db.py
"""

from __future__ import annotations

import datetime
import json
import os
import random
import time
from typing import Any

from google.cloud import bigquery

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "sa-learning-1")
DATASET_ID = "rewe_marketing"
FULL_DS = f"{PROJECT_ID}.{DATASET_ID}"
TARGET_PRODUCTS = 5200
TARGET_CUSTOMERS = 2000
TARGET_INTERACTIONS = 20000
NOW = datetime.datetime(2026, 11, 11, 12, 0, 0, tzinfo=datetime.UTC)

# --------------------------------------------------------------------------- #
# German geography (16 Bundesländer, real cities & PLZs)
# --------------------------------------------------------------------------- #
REGIONS: list[dict[str, Any]] = [
    {
        "region": "Berlin",
        "cities": [
            ("Berlin", "10115"),
            ("Berlin", "10243"),
            ("Berlin", "10437"),
            ("Berlin", "12047"),
            ("Berlin", "13355"),
        ],
        "weather": "Crisp & Cloudy, 7°C",
        "promo": "Herbstküche Berlin: Bio-Kürbis, Suppen & Vorratskammer -20%",
    },
    {
        "region": "Bavaria",
        "cities": [
            ("München", "80331"),
            ("München", "80802"),
            ("Nürnberg", "90402"),
            ("Augsburg", "86150"),
            ("Regensburg", "93047"),
        ],
        "weather": "Clear & Cool, 6°C",
        "promo": "Bayerische Herbstküche: Regionales Wurzelgemüse & Bio-Genuss -20%",
    },
    {
        "region": "North Rhine-Westphalia",
        "cities": [
            ("Köln", "50667"),
            ("Düsseldorf", "40210"),
            ("Dortmund", "44135"),
            ("Essen", "45127"),
            ("Bonn", "53111"),
        ],
        "weather": "Light Rain, 9°C",
        "promo": "Gemütlich durch den November: Heißgetränke, Suppen & Gebäck",
    },
    {
        "region": "Baden-Württemberg",
        "cities": [
            ("Stuttgart", "70173"),
            ("Karlsruhe", "76133"),
            ("Freiburg", "79098"),
            ("Heidelberg", "69115"),
            ("Ulm", "89073"),
        ],
        "weather": "Partly Cloudy, 8°C",
        "promo": "Herbstgenuss aus der Region: Äpfel, Kürbis & Pasta-Vielfalt",
    },
    {
        "region": "Hamburg",
        "cities": [
            ("Hamburg", "20095"),
            ("Hamburg", "22765"),
            ("Hamburg", "20249"),
            ("Hamburg", "22083"),
        ],
        "weather": "Breezy, 8°C",
        "promo": "Nordische Wohlfühlwoche: Tee, Fisch & Bio-Backwaren",
    },
    {
        "region": "Hesse",
        "cities": [
            ("Frankfurt am Main", "60311"),
            ("Wiesbaden", "65183"),
            ("Kassel", "34117"),
            ("Darmstadt", "64283"),
        ],
        "weather": "Mild Autumn, 9°C",
        "promo": "Genuss-Herbst: Feine Welt Käse, Wein & Ofengemüse",
    },
    {
        "region": "Saxony",
        "cities": [("Dresden", "01067"), ("Leipzig", "04109"), ("Chemnitz", "09111")],
        "weather": "Crisp & Sunny, 7°C",
        "promo": "Sächsische Back- & Kürbiswoche: 15% auf Mehl, Nüsse & Bio-Gemüse",
    },
    {
        "region": "Lower Saxony",
        "cities": [
            ("Hannover", "30159"),
            ("Braunschweig", "38100"),
            ("Oldenburg", "26122"),
            ("Osnabrück", "49074"),
        ],
        "weather": "Overcast, 8°C",
        "promo": "Familien-Vorratswoche: Große Ja! & Beste Wahl Sparpacks",
    },
    {
        "region": "Rhineland-Palatinate",
        "cities": [("Mainz", "55116"), ("Koblenz", "56068"), ("Trier", "54290")],
        "weather": "Partly Cloudy, 9°C",
        "promo": "Wein & Herbstküche: Regionale Spezialitäten im Angebot",
    },
    {
        "region": "Schleswig-Holstein",
        "cities": [("Kiel", "24103"), ("Lübeck", "23552"), ("Flensburg", "24937")],
        "weather": "Fresh Breeze, 7°C",
        "promo": "Küsten-Herbst: Heiße Suppen, Haferdrinks & Frühstücks-Highlights",
    },
    {
        "region": "Brandenburg",
        "cities": [("Potsdam", "14467"), ("Cottbus", "03046")],
        "weather": "Crisp, 6°C",
        "promo": "Regional aus Brandenburg: Kartoffeln, Kürbis & Äpfel",
    },
    {
        "region": "Saxony-Anhalt",
        "cities": [("Magdeburg", "39104"), ("Halle", "06108")],
        "weather": "Cool & Dry, 7°C",
        "promo": "Herbst-Preishits: Jeden Tag günstig mit Ja! & REWE Bonus",
    },
    {
        "region": "Thuringia",
        "cities": [("Erfurt", "99084"), ("Jena", "07743")],
        "weather": "Chilly, 5°C",
        "promo": "Thüringer Herzhaft-Woche: Eintöpfe, Brot & Grill-Klassiker",
    },
    {
        "region": "Mecklenburg-Vorpommern",
        "cities": [("Rostock", "18055"), ("Schwerin", "19053")],
        "weather": "Windy, 7°C",
        "promo": "Ostsee-Herbst: Tee-Vielfalt, Vollkorn & Bio-Snacks",
    },
    {
        "region": "Saarland",
        "cities": [("Saarbrücken", "66111")],
        "weather": "Mild, 9°C",
        "promo": "Savoir-Vivre im Herbst: Feinkost, Baguette & Rotwein",
    },
    {
        "region": "Bremen",
        "cities": [("Bremen", "28195"), ("Bremerhaven", "27568")],
        "weather": "Light Breeze, 8°C",
        "promo": "Kaffee- & Genusswoche: Fairtrade Röstungen & Kekse",
    },
]

# --------------------------------------------------------------------------- #
# Product generator definitions
# --------------------------------------------------------------------------- #
# Each department defines:
#   category_path, brands, bases (base_name, eng_hint, recipe_tag, unit_opts),
#   variants, price_range, nutrition_template, dietary flags
DEPARTMENTS: list[dict[str, Any]] = [
    {
        "cat": "Food > Produce > Vegetables",
        "brands": ["REWE Bio", "REWE Regional", "REWE Beste Wahl", "Ja!"],
        "bases": [
            ("Hokkaido Kürbis", "pumpkin soup, oven-roasted pumpkin", "REC_HERBST"),
            ("Butternut Kürbis", "creamy roasted squash", "REC_HERBST"),
            ("Muskatkürbis", "spiced autumn stew", "REC_HERBST"),
            ("Süßkartoffeln", "baked sweet potato fries & mash", "REC_HERBST"),
            (
                "Speisekartoffeln festkochend",
                "classic German potato salad & pan-fried potatoes",
                "REC_CLASSIC",
            ),
            (
                "Speisekartoffeln mehligkochend",
                "velvety mashed potatoes & soups",
                "REC_CLASSIC",
            ),
            ("Karotten", "fresh crunch for salads, soups, and snacking", "REC_SOUP"),
            (
                "Pastinaken",
                "sweet nutty root vegetable for autumn roasting",
                "REC_HERBST",
            ),
            (
                "Rote Bete",
                "earthy beetroot for bowls, salads, and roasting",
                "REC_SALAD",
            ),
            ("Brokkoli", "tender florets for stir-fries and steaming", "REC_FIT"),
            (
                "Blumenkohl",
                "versatile cauliflower for curries and oven bakes",
                "REC_VEG",
            ),
            ("Zucchini", "juicy summer & grill zucchini", "REC_GRILL"),
            ("Aubergine", "mediterranean grilled eggplant & ratatouille", "REC_GRILL"),
            (
                "Paprika Mix",
                "colorful bell peppers for salads and fajitas",
                "REC_SALAD",
            ),
            (
                "Strauchtomaten",
                "aromatic vine tomatoes for sauces and bruschetta",
                "REC_PASTA",
            ),
            (
                "Cherrytomaten",
                "sweet cherry tomatoes for snacking and pasta",
                "REC_SALAD",
            ),
            ("Salatgurke", "crisp cucumber for fresh salads and tzatziki", "REC_SALAD"),
            ("Spinat jung", "tender baby spinach for smoothies and pasta", "REC_FIT"),
            ("Grünkohl", "classic winter kale for hearty bowls", "REC_WINTER"),
            ("Rosenkohl", "roasted Brussels sprouts for autumn & winter", "REC_WINTER"),
            (
                "Champignons braun",
                "earthy brown mushrooms for pan dishes & risottos",
                "REC_HERBST",
            ),
            (
                "Kräuterseitlinge",
                "meaty king oyster mushrooms for plant-based grilling",
                "REC_VEGAN",
            ),
            (
                "Lauch / Porree",
                "aromatic leek for classic potato leek soup",
                "REC_SOUP",
            ),
            (
                "Zwiebeln gelb",
                "essential kitchen staple for every savory recipe",
                "REC_CLASSIC",
            ),
            (
                "Rote Zwiebeln",
                "mild sweet red onions for salads and burgers",
                "REC_GRILL",
            ),
            (
                "Knoblauch",
                "aromatic garlic bulbs for Mediterranean cooking",
                "REC_PASTA",
            ),
            ("Spargel grün", "tender green asparagus for pan & grill", "REC_SPRING"),
            ("Fenchel", "fresh anise-noted fennel for roasting and salads", "REC_MED"),
            (
                "Sellerieknolle",
                "hearty celeriac for winter broths and puree",
                "REC_SOUP",
            ),
            (
                "Avocado Hass",
                "creamy ripe Hass avocado for toast and guacamole",
                "REC_BREAKFAST",
            ),
        ],
        "variants": [
            "frisch",
            "vom Feld",
            "aromatisch",
            "Klasse I",
            "erntefrisch",
            "aus eigenem Anbau",
            "knackig",
            "saisonal",
        ],
        "units": ["500g", "750g", "1kg", "1,5kg", "2kg", "250g", "Stück", "2er Pack"],
        "price": (0.89, 4.99),
        "nutri": {
            "nutriscore": "A",
            "calories": 34,
            "protein_g": 1.8,
            "carbs_g": 5.5,
            "fat_g": 0.3,
            "sugar_g": 2.4,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Produce > Fruits",
        "brands": [
            "REWE Bio",
            "REWE Regional",
            "REWE Beste Wahl",
            "Ja!",
            "REWE Feine Welt",
        ],
        "bases": [
            (
                "Äpfel Elstar",
                "crisp sweet-tart apples for baking and snacking",
                "REC_BAKE",
            ),
            (
                "Äpfel Braeburn",
                "crunchy aromatic apples from German orchards",
                "REC_SNACK",
            ),
            (
                "Birnen Conference",
                "juicy sweet pears for autumn desserts & cheese boards",
                "REC_HERBST",
            ),
            (
                "Bananen",
                "creamy energy-rich bananas for smoothies & bowls",
                "REC_BREAKFAST",
            ),
            (
                "Orangen Saftorangen",
                "vitamin-rich sweet oranges for fresh juice",
                "REC_BREAKFAST",
            ),
            ("Clementinen", "easy-peel winter citrus fruit", "REC_WINTER"),
            (
                "Zitronen unbehandelt",
                "zesty organic lemons for cooking, baking, and tea",
                "REC_CLASSIC",
            ),
            ("Trauben kernlos hell", "crisp seedless white grapes", "REC_SNACK"),
            (
                "Trauben kernlos dunkel",
                "sweet dark grapes for snacking and cheese platters",
                "REC_GOURMET",
            ),
            ("Erdbeeren", "sweet summer strawberries", "REC_SUMMER"),
            (
                "Heidelbeeren",
                "antioxidant-rich blueberries for oatmeal & yogurt",
                "REC_BREAKFAST",
            ),
            ("Himbeeren", "aromatic raspberries for desserts", "REC_SUMMER"),
            (
                "Zwetschgen",
                "late-summer plums for traditional Pflaumenkuchen",
                "REC_BAKE",
            ),
            ("Mango essreif", "sweet tropical mango for curries and bowls", "REC_BOWL"),
            ("Kiwi Gold", "vitamin C-packed golden kiwis", "REC_BREAKFAST"),
            ("Granatapfel", "ruby pomegranate seeds for salads and bowls", "REC_SALAD"),
            (
                "Feigen frisch",
                "sweet Mediterranean figs for autumn salads",
                "REC_GOURMET",
            ),
            (
                "Cranberries frisch",
                "tart festive berries for sauces & baking",
                "REC_WINTER",
            ),
        ],
        "variants": [
            "aromatisch",
            "süß",
            "saftig",
            "Klasse I",
            "handverlesen",
            "sonnengereift",
            "aus der Region",
        ],
        "units": ["250g", "300g", "500g", "750g", "1kg", "1,5kg", "2er", "4er"],
        "price": (1.29, 5.49),
        "nutri": {
            "nutriscore": "A",
            "calories": 52,
            "protein_g": 0.7,
            "carbs_g": 12.1,
            "fat_g": 0.2,
            "sugar_g": 9.8,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Produce > Salad & Herbs",
        "brands": ["REWE Bio", "REWE Regional", "REWE Beste Wahl"],
        "bases": [
            (
                "Feldsalat",
                "nutty lamb's lettuce for autumn & winter salads",
                "REC_SALAD",
            ),
            ("Rucola", "peppery arugula for pizza, pasta, and bowls", "REC_PASTA"),
            (
                "Eisbergsalat",
                "crisp iceberg lettuce for burgers and bowls",
                "REC_GRILL",
            ),
            (
                "Romanasalat Herzen",
                "crunchy romaine hearts for Caesar salad",
                "REC_SALAD",
            ),
            ("Babysalat Mix", "washed ready-to-eat tender greens", "REC_SALAD"),
            (
                "Basilikum im Topf",
                "fresh aromatic basil for caprese & pesto",
                "REC_PASTA",
            ),
            (
                "Petersilie glatt",
                "fresh flat-leaf parsley for soups and garnishes",
                "REC_SOUP",
            ),
            (
                "Rosmarin frisch",
                "fragrant rosemary for roasted potatoes and veggies",
                "REC_HERBST",
            ),
            (
                "Koriander frisch",
                "bright fresh coriander for curries and tacos",
                "REC_ASIAN",
            ),
            (
                "Schnittlauch Bund",
                "crisp chives for quark, eggs, and soups",
                "REC_BREAKFAST",
            ),
            (
                "Ingwerwurzel",
                "spicy fresh ginger for autumn teas and stir-fries",
                "REC_ASIAN",
            ),
            (
                "Kurkumawurzel",
                "golden turmeric root for immunity shots & curries",
                "REC_VEGAN",
            ),
        ],
        "variants": ["gewaschen", "im Topf", "Bund", "aromatisch", "küchenfertig"],
        "units": ["75g", "100g", "125g", "150g", "200g", "1 Topf"],
        "price": (0.99, 2.99),
        "nutri": {
            "nutriscore": "A",
            "calories": 21,
            "protein_g": 2.1,
            "carbs_g": 2.4,
            "fat_g": 0.3,
            "sugar_g": 0.8,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Dairy Alternatives",
        "brands": ["REWE Bio", "Oatly", "Alpro", "Alnatura", "REWE Beste Wahl"],
        "bases": [
            (
                "Haferdrink Barista",
                "creamy oat milk that froths like cafe latte art",
                "REC_COFFEE",
            ),
            (
                "Haferdrink Natur",
                "everyday unsweetened oat drink for muesli and baking",
                "REC_BREAKFAST",
            ),
            (
                "Sojadrink Natur",
                "protein-rich plant milk for cooking and shakes",
                "REC_FIT",
            ),
            (
                "Mandeldrink Ungesüßt",
                "nutty low-calorie almond drink for smoothies",
                "REC_VEGAN",
            ),
            (
                "Kokosdrink",
                "silky coconut drink for curries and iced coffee",
                "REC_ASIAN",
            ),
            (
                "Hafer Cuisine Kochcreme",
                "plant-based cooking cream for pumpkin soup & pasta",
                "REC_HERBST",
            ),
            (
                "Soja Joghurt Natur",
                "creamy probiotic soy yogurt with live cultures",
                "REC_BREAKFAST",
            ),
            (
                "Hafer Joghurt Vanille",
                "smooth oat yogurt for fruit bowls",
                "REC_BREAKFAST",
            ),
            ("Kokos Joghurt Mango", "tropical plant-based dessert snack", "REC_SNACK"),
            (
                "Vegane Butter Alternative",
                "plant-based spreadable butter for baking and toast",
                "REC_BAKE",
            ),
            (
                "Veganer Reibeschmelz",
                "meltable plant-based cheese for pizza & gratins",
                "REC_VEGAN",
            ),
            (
                "Veganer Feta Genuss",
                "tangy plant-based Greek-style block for salads",
                "REC_SALAD",
            ),
        ],
        "variants": [
            "ungesüßt",
            "Barista",
            "Calcium-Plus",
            "ohne Zuckerzusatz",
            "cremig",
            "klassisch",
        ],
        "units": ["200ml", "250g", "400g", "500g", "1L", "6x1L"],
        "price": (1.19, 3.79),
        "nutri": {
            "nutriscore": "A",
            "calories": 48,
            "protein_g": 2.8,
            "carbs_g": 4.9,
            "fat_g": 1.8,
            "sugar_g": 1.5,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Meat Alternatives",
        "brands": [
            "REWE Bio",
            "Rügenwalder Mühle",
            "Garden Gourmet",
            "REWE Beste Wahl",
            "Alnatura",
        ],
        "bases": [
            (
                "Tofu Natur",
                "firm organic tofu for marinating, grilling, and curries",
                "REC_VEGAN",
            ),
            (
                "Räuchertofu",
                "smoky wood-fired tofu with rich umami flavor",
                "REC_HERBST",
            ),
            (
                "Tofu Grillsteaks",
                "seasoned plant-based grill steaks rich in protein",
                "REC_GRILL",
            ),
            (
                "Veganes Hack",
                "juicy plant-based mince for bolognese and chili",
                "REC_PASTA",
            ),
            (
                "Vegane Bratwurst",
                "hearty plant-based sausages for grill & pan",
                "REC_GRILL",
            ),
            ("Vegane Burger Patties", "thick plant-based burger patties", "REC_GRILL"),
            (
                "Veganes Mühlen Cordon Bleu",
                "crispy plant-based schnitzel style cutlet",
                "REC_CLASSIC",
            ),
            (
                "Falafel Bällchen",
                "oriental chickpea balls with cumin and parsley",
                "REC_BOWL",
            ),
            ("Tempeh mariniert", "fermented protein-packed soy tempeh", "REC_FIT"),
            (
                "Seitan Geschnetzeltes",
                "tender plant-based strips for stir-fries",
                "REC_FIT",
            ),
            (
                "Vegane Chicken Chunks",
                "crispy plant-based bites for salads and wraps",
                "REC_BOWL",
            ),
            (
                "Linsen-Bolognese Basis",
                "ready-to-simmer protein-rich lentil ragu",
                "REC_PASTA",
            ),
        ],
        "variants": [
            "Natur",
            "Kräuter",
            "Mediterran",
            "Smoky BBQ",
            "Paprika",
            "Classic",
            "High Protein",
        ],
        "units": ["160g", "180g", "200g", "250g", "300g", "400g"],
        "price": (1.79, 4.49),
        "nutri": {
            "nutriscore": "A",
            "calories": 168,
            "protein_g": 17.5,
            "carbs_g": 6.2,
            "fat_g": 8.1,
            "sugar_g": 1.1,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": True,
    },
    {
        "cat": "Food > Meat & Poultry",
        "brands": ["REWE Regional", "REWE Beste Wahl", "Ja!", "REWE Feine Welt"],
        "bases": [
            (
                "Rindersteak Hüfte",
                "tender beef sirloin steak for pan or BBQ",
                "REC_GRILL",
            ),
            (
                "Rinderhackfleisch",
                "lean ground beef for burgers & bolognese",
                "REC_PASTA",
            ),
            (
                "Hähnchenbrustfilet",
                "lean high-protein chicken breast fillets",
                "REC_FIT",
            ),
            (
                "Hähnchenschenkel gewürzt",
                "juicy seasoned chicken drumsticks for oven & grill",
                "REC_GRILL",
            ),
            (
                "Putenbrust Geschnetzeltes",
                "lean turkey strips for quick stir-fries",
                "REC_FIT",
            ),
            (
                "Schweinefilet",
                "tender pork tenderloin for Sunday roasts",
                "REC_GOURMET",
            ),
            (
                "Nürnberger Rostbratwürstchen",
                "classic German grilled sausages",
                "REC_GRILL",
            ),
            (
                "Rindergulasch",
                "slow-cook diced beef for hearty autumn stews",
                "REC_HERBST",
            ),
            ("Kalbsschnitzel", "fine veal cutlets for Wiener Schnitzel", "REC_GOURMET"),
            (
                "Lammkoteletts Kräuter",
                "herb-marinated lamb chops for grilling",
                "REC_GRILL",
            ),
        ],
        "variants": [
            "Natur",
            "BBQ-mariniert",
            "Kräuter-Knoblauch",
            "Haltungsform 4",
            "aus der Region",
            "Extra Mager",
        ],
        "units": ["250g", "300g", "400g", "500g", "600g", "1kg"],
        "price": (2.99, 12.99),
        "nutri": {
            "nutriscore": "B",
            "calories": 155,
            "protein_g": 22.5,
            "carbs_g": 0.4,
            "fat_g": 6.8,
            "sugar_g": 0.2,
        },
        "vegan": False,
        "veg": False,
        "gf": True,
        "lf": True,
        "hp": True,
    },
    {
        "cat": "Food > Seafood",
        "brands": ["REWE Beste Wahl", "REWE Bio", "REWE Feine Welt", "Iglo", "Frosta"],
        "bases": [
            ("Lachsfilet ASC", "omega-3 rich Atlantic salmon fillet", "REC_FIT"),
            ("Wildlachsfilet", "tender wild Pacific salmon fillets", "REC_FIT"),
            (
                "Garnelen Riesengarnelen",
                "succulent king prawns for garlic pasta & grill",
                "REC_MED",
            ),
            (
                "Kabeljau Rückenfilet",
                "flaky white cod loin for oven baking",
                "REC_GOURMET",
            ),
            (
                "Forellenfilet geräuchert",
                "smoked German trout fillet for light dinners",
                "REC_CLASSIC",
            ),
            (
                "Räucherlachs schottisch",
                "delicate cold-smoked salmon slices",
                "REC_GOURMET",
            ),
            (
                "Thunfischfilets in Olivenöl",
                "protein-rich tuna fillets for salads",
                "REC_FIT",
            ),
            (
                "Matjesfilets nordisch",
                "traditional Nordic pickled herring fillets",
                "REC_CLASSIC",
            ),
            (
                "Schollenfilet",
                "mild European plaice fillet for pan-frying",
                "REC_CLASSIC",
            ),
        ],
        "variants": [
            "naturbelassen",
            "mit Kräutern",
            "über Buchenholz geräuchert",
            "MSC-zertifiziert",
            "küchenfertig",
        ],
        "units": ["150g", "200g", "250g", "300g", "400g"],
        "price": (2.79, 9.99),
        "nutri": {
            "nutriscore": "A",
            "calories": 148,
            "protein_g": 20.4,
            "carbs_g": 0.2,
            "fat_g": 7.2,
            "sugar_g": 0.0,
        },
        "vegan": False,
        "veg": False,
        "gf": True,
        "lf": True,
        "hp": True,
    },
    {
        "cat": "Food > Dairy & Eggs",
        "brands": [
            "Weihenstephan",
            "REWE Bio",
            "REWE Regional",
            "Ehrmann",
            "Arla",
            "Kerrygold",
            "Ja!",
        ],
        "bases": [
            (
                "Frische Vollmilch 3,5%",
                "creamy fresh whole milk from Bavarian pastures",
                "REC_BREAKFAST",
            ),
            (
                "Fettarme H-Milch 1,5%",
                "long-life low-fat milk for coffee and baking",
                "REC_CLASSIC",
            ),
            (
                "Laktosefreie Milch 1,5%",
                "gentle lactose-free milk with natural sweetness",
                "REC_BREAKFAST",
            ),
            (
                "Naturjoghurt 3,8%",
                "creamy mild yogurt for breakfast bowls & dressings",
                "REC_BREAKFAST",
            ),
            (
                "Griechischer Joghurt 10%",
                "thick authentic Greek-style yogurt for tzatziki",
                "REC_MED",
            ),
            (
                "Skyr Natur High Protein",
                "Icelandic-style low-fat high-protein yogurt",
                "REC_FIT",
            ),
            (
                "Speisequark Magerstufe",
                "protein-packed low-fat quark for fitness & baking",
                "REC_FIT",
            ),
            (
                "Schlagsahne",
                "rich whipping cream for autumn soups and cakes",
                "REC_BAKE",
            ),
            (
                "Crème fraîche",
                "velvety French-style cream for Flammkuchen & pumpkin soup",
                "REC_HERBST",
            ),
            (
                "Deutsche Markenbutter",
                "golden pasture butter for baking & toast",
                "REC_BAKE",
            ),
            (
                "Freilandeier 6er",
                "fresh free-range eggs from regional farms",
                "REC_BREAKFAST",
            ),
            (
                "Körniger Frischkäse",
                "high-protein cottage cheese for salads and snacks",
                "REC_FIT",
            ),
            (
                "High Protein Pudding Schoko",
                "creamy 20g protein dessert with low sugar",
                "REC_FIT",
            ),
        ],
        "variants": [
            "Classic",
            "Laktosefrei",
            "Weidehaltung",
            "Cremig",
            "Mild",
            "Natur",
        ],
        "units": ["150g", "200g", "250g", "400g", "500g", "1L", "6er", "10er"],
        "price": (0.79, 3.99),
        "nutri": {
            "nutriscore": "B",
            "calories": 112,
            "protein_g": 6.4,
            "carbs_g": 4.5,
            "fat_g": 7.1,
            "sugar_g": 4.2,
        },
        "vegan": False,
        "veg": True,
        "gf": True,
        "lf": False,
        "hp": False,
    },
    {
        "cat": "Food > Cheese & Deli",
        "brands": [
            "REWE Feine Welt",
            "REWE Bio",
            "REWE Beste Wahl",
            "Arla",
            "Kerrygold",
            "Ja!",
        ],
        "bases": [
            (
                "Gouda jung in Scheiben",
                "mild creamy Dutch Gouda slices for sandwiches",
                "REC_CLASSIC",
            ),
            (
                "Bergkäse gereift",
                "aged Alpine mountain cheese for Käsespätzle",
                "REC_HERBST",
            ),
            (
                "Mozzarella Kugel",
                "soft Italian mozzarella for caprese and pizza",
                "REC_PASTA",
            ),
            (
                "Parmigiano Reggiano 24 Monate",
                "aged authentic Parmesan for pasta and risotto",
                "REC_PASTA",
            ),
            (
                "Feta g.U. Schafskäse",
                "tangy Greek sheep's milk feta for salads & oven bakes",
                "REC_MED",
            ),
            (
                "Halloumi Grillkäse",
                "squeaky Cypriot grilling cheese that holds its shape",
                "REC_GRILL",
            ),
            (
                "Camembert französisch",
                "bloomy-rind creamy Camembert for cheese boards",
                "REC_GOURMET",
            ),
            (
                "Ziegenkäse Rolle",
                "mild goat cheese for honey-walnut autumn salads",
                "REC_HERBST",
            ),
            (
                "Cheddar irisch würzig",
                "sharp aged Irish cheddar for burgers",
                "REC_GRILL",
            ),
            (
                "Hummus Classic",
                "velvety chickpea dip with tahini and lemon",
                "REC_VEGAN",
            ),
            (
                "Hummus Kürbis-Curry",
                "seasonal pumpkin-curry chickpea dip",
                "REC_HERBST",
            ),
            (
                "Tzatziki nach griechischer Art",
                "cool cucumber garlic yogurt dip for BBQ",
                "REC_GRILL",
            ),
            (
                "Guacamole frisch",
                "chunky avocado lime dip for bowls and nachos",
                "REC_VEGAN",
            ),
        ],
        "variants": [
            "Natur",
            "Kräuter",
            "Chili",
            "extra würzig",
            "laktosefrei",
            "gereift",
        ],
        "units": ["140g", "150g", "175g", "200g", "250g", "400g"],
        "price": (1.29, 5.49),
        "nutri": {
            "nutriscore": "C",
            "calories": 285,
            "protein_g": 18.2,
            "carbs_g": 2.1,
            "fat_g": 22.4,
            "sugar_g": 1.0,
        },
        "vegan": False,
        "veg": True,
        "gf": True,
        "lf": False,
        "hp": True,
    },
    {
        "cat": "Food > Bakery & Bread",
        "brands": [
            "REWE Bio",
            "REWE Beste Wahl",
            "REWE Regional",
            "Ja!",
            "Coppenrath & Wiese",
        ],
        "bases": [
            (
                "Dinkel-Vollkornbrot",
                "hearty spelt wholegrain bread rich in fiber",
                "REC_BREAKFAST",
            ),
            (
                "Bauernbrot Sauerteig",
                "crusty sourdough farmhouse loaf for soups & cheese",
                "REC_HERBST",
            ),
            (
                "Eiweißbrot Mehrkorn",
                "low-carb high-protein seed bread for athletes",
                "REC_FIT",
            ),
            (
                "Ciabatta zum Aufbacken",
                "crispy Italian bread for grilling and bruschetta",
                "REC_GRILL",
            ),
            (
                "Laugenbrezeln 6er",
                "Bavarian-style pretzel rolls for warm oven baking",
                "REC_CLASSIC",
            ),
            (
                "Burger Brioche Buns",
                "soft golden brioche buns for gourmet burgers",
                "REC_GRILL",
            ),
            (
                "Glutenfreies Mehrkornbrot",
                "certified gluten-free seeded loaf",
                "REC_GF",
            ),
            (
                "Butter-Croissants",
                "flaky French-style croissants for Sunday breakfast",
                "REC_BREAKFAST",
            ),
            (
                "Vollkorn-Wraps 6er",
                "soft wholewheat tortillas for quick lunch wraps",
                "REC_BOWL",
            ),
            ("Kürbiskernbrötchen 4er", "crusty pumpkin seed rolls", "REC_HERBST"),
            (
                "Zimtschnecken skandinavisch",
                "soft spiced cinnamon rolls for cozy afternoons",
                "REC_WINTER",
            ),
        ],
        "variants": [
            "Vollkorn",
            "Dinkel",
            "mit Saaten",
            "zum Aufbacken",
            "frisch gebacken",
            "glutenfrei",
        ],
        "units": ["250g", "300g", "400g", "500g", "750g", "4er", "6er"],
        "price": (0.99, 4.29),
        "nutri": {
            "nutriscore": "B",
            "calories": 248,
            "protein_g": 9.1,
            "carbs_g": 43.0,
            "fat_g": 3.4,
            "sugar_g": 2.9,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Pantry > Pasta & Grains",
        "brands": [
            "Barilla",
            "De Cecco",
            "REWE Bio",
            "Ja!",
            "REWE Beste Wahl",
            "Alnatura",
        ],
        "bases": [
            ("Spaghetti Nr. 5", "al dente Italian durum wheat spaghetti", "REC_PASTA"),
            (
                "Penne Rigate",
                "ridged tubes that catch chunky tomato and veggie sauces",
                "REC_PASTA",
            ),
            ("Fusilli Vollkorn", "high-fiber wholegrain spiral pasta", "REC_FIT"),
            (
                "Rote Linsen Fusilli",
                "gluten-free high-protein red lentil pasta",
                "REC_GF",
            ),
            (
                "Kichererbsen Penne",
                "plant-protein chickpea pasta for fitness meals",
                "REC_GF",
            ),
            (
                "Tagliatelle Nestchen",
                "classic ribbon pasta for mushroom & truffle sauces",
                "REC_HERBST",
            ),
            (
                "Basmati Reis",
                "fragrant long-grain rice for curries and bowls",
                "REC_ASIAN",
            ),
            (
                "Risotto Reis Arborio",
                "creamy Italian rice for pumpkin & mushroom risotto",
                "REC_HERBST",
            ),
            (
                "Quinoa Tri-Color",
                "protein-rich Andean superfood grain for salads",
                "REC_GF",
            ),
            (
                "Couscous mittelgrob",
                "quick-steaming couscous for warm Mediterranean bowls",
                "REC_BOWL",
            ),
            (
                "Rote Linsen",
                "quick-cooking lentils for warming autumn dal & soups",
                "REC_SOUP",
            ),
            (
                "Beluga Linsen",
                "firm nutty black lentils for gourmet salads",
                "REC_VEGAN",
            ),
            (
                "Kichererbsen vorgekocht",
                "ready-to-use chickpeas for hummus and curries",
                "REC_VEGAN",
            ),
            (
                "Polenta Maisgrieß",
                "golden Italian cornmeal for creamy polenta",
                "REC_GF",
            ),
        ],
        "variants": [
            "Hartweizen",
            "Vollkorn",
            "Glutenfrei",
            "Express",
            "100% Hülsenfrüchte",
            "Tradizionale",
        ],
        "units": ["250g", "400g", "500g", "750g", "1kg", "2kg"],
        "price": (0.79, 4.49),
        "nutri": {
            "nutriscore": "A",
            "calories": 348,
            "protein_g": 12.8,
            "carbs_g": 68.0,
            "fat_g": 1.8,
            "sugar_g": 2.6,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Pantry > Oils, Vinegars & Spices",
        "brands": [
            "REWE Bio",
            "REWE Feine Welt",
            "Bertolli",
            "Kühne",
            "Alnatura",
            "REWE Beste Wahl",
        ],
        "bases": [
            (
                "Olivenöl Extra Vergine",
                "cold-pressed Mediterranean olive oil for salads & roasting",
                "REC_MED",
            ),
            (
                "Steirisches Kürbiskernöl",
                "rich dark roasted pumpkin seed oil for autumn soups",
                "REC_HERBST",
            ),
            (
                "Rapsöl kaltgepresst",
                "regional cold-pressed canola oil for everyday cooking",
                "REC_CLASSIC",
            ),
            (
                "Kokosöl nativ",
                "aromatic organic coconut oil for curries and baking",
                "REC_ASIAN",
            ),
            (
                "Sesamöl geröstet",
                "nutty toasted sesame oil for Asian wok dishes",
                "REC_ASIAN",
            ),
            (
                "Aceto Balsamico di Modena",
                "aged sweet-tart balsamic vinegar for caprese",
                "REC_MED",
            ),
            (
                "Apfelessig naturtrüb",
                "raw unfiltered apple cider vinegar for dressings",
                "REC_SALAD",
            ),
            (
                "Meersalz grob",
                "pure sea salt crystals for kitchen grinders",
                "REC_CLASSIC",
            ),
            (
                "Schwarzer Pfeffer Tellicherry",
                "aromatic whole black peppercorns",
                "REC_CLASSIC",
            ),
            (
                "Kurkuma & Curry Gewürzmischung",
                "warming spice blend for pumpkin soup & dal",
                "REC_HERBST",
            ),
            (
                "Zimt Ceylon gemahlen",
                "fragrant sweet Ceylon cinnamon for porridge & baking",
                "REC_WINTER",
            ),
            (
                "Gemüsebrühe ohne Hefeextrakt",
                "clean aromatic vegetable stock for soups",
                "REC_SOUP",
            ),
        ],
        "variants": [
            "kaltgepresst",
            "nativ extra",
            "gereift",
            "gemahlen",
            "aromatisch",
            "aus Italien",
            "aus Österreich",
        ],
        "units": ["45g", "100ml", "250ml", "500ml", "750ml", "1L"],
        "price": (1.29, 9.49),
        "nutri": {
            "nutriscore": "C",
            "calories": 820,
            "protein_g": 0.0,
            "carbs_g": 0.5,
            "fat_g": 91.0,
            "sugar_g": 0.2,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Pantry > Sauces & Canned",
        "brands": [
            "Mutti",
            "REWE Bio",
            "REWE Beste Wahl",
            "Knorr",
            "Kühne",
            "Hengstenberg",
            "Ja!",
        ],
        "bases": [
            (
                "Passierte Tomaten",
                "sun-ripened Italian tomato passata for pasta & soups",
                "REC_PASTA",
            ),
            (
                "Polpa Tomatenstücke",
                "chunky diced Italian tomatoes in juice",
                "REC_PASTA",
            ),
            (
                "Kokosmilch cremig",
                "rich 60% coconut milk for Thai curries & pumpkin soup",
                "REC_HERBST",
            ),
            (
                "Kürbissuppe Bio im Glas",
                "ready-to-heat creamy organic Hokkaido pumpkin soup",
                "REC_HERBST",
            ),
            ("Tomatensuppe mediterran", "velvety tomato basil soup", "REC_SOUP"),
            ("Pesto alla Genovese", "fragrant basil pesto with pine nuts", "REC_PASTA"),
            (
                "Pesto Rosso getrocknete Tomate",
                "intense sun-dried tomato pesto",
                "REC_PASTA",
            ),
            (
                "Kidneybohnen",
                "tender red kidney beans for chili sin carne",
                "REC_VEGAN",
            ),
            (
                "Zuckermais knackig",
                "sweet crisp corn kernels for salads and wraps",
                "REC_SALAD",
            ),
            (
                "BBQ Sauce Smoky",
                "hickory-smoked grill sauce for ribs, tofu, and burgers",
                "REC_GRILL",
            ),
            (
                "Senf mittelscharf",
                "classic German medium mustard for bratwurst & dressings",
                "REC_GRILL",
            ),
            ("Sojasauce Tamari", "gluten-free naturally brewed soy sauce", "REC_GF"),
            (
                "Tahini Sesammus",
                "silky roasted sesame paste for hummus & dressings",
                "REC_VEGAN",
            ),
            (
                "Erdnussmus 100% Crunch",
                "pure roasted peanut butter with no added sugar",
                "REC_FIT",
            ),
        ],
        "variants": [
            "klassisch",
            "ohne Zuckerzusatz",
            "scharf",
            "cremig",
            "naturbelassen",
            "italienisch",
        ],
        "units": ["190g", "250ml", "350g", "400g", "500ml", "680g", "720ml"],
        "price": (0.89, 4.49),
        "nutri": {
            "nutriscore": "B",
            "calories": 95,
            "protein_g": 3.4,
            "carbs_g": 9.8,
            "fat_g": 4.2,
            "sugar_g": 4.1,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Breakfast & Cereal",
        "brands": ["REWE Bio", "Alnatura", "REWE Beste Wahl", "Ja!", "Seeberger"],
        "bases": [
            (
                "Haferflocken zart",
                "fine organic rolled oats for warm autumn porridge",
                "REC_BREAKFAST",
            ),
            (
                "Haferflocken kernig",
                "hearty coarse oats for overnight oats and baking",
                "REC_BREAKFAST",
            ),
            (
                "Knusper-Granola Beeren",
                "crunchy oven-baked oat clusters with freeze-dried berries",
                "REC_BREAKFAST",
            ),
            (
                "Protein Müsli Schoko-Nuss",
                "high-protein crunchy muesli with soy crisps & nuts",
                "REC_FIT",
            ),
            (
                "Glutenfreie Haferflocken",
                "certified gluten-free wholegrain oats",
                "REC_GF",
            ),
            (
                "Chiasamen",
                "omega-3 rich chia seeds for puddings and smoothies",
                "REC_VEGAN",
            ),
            (
                "Leinsamen geschrotet",
                "ground flaxseeds for digestion and bread baking",
                "REC_VEGAN",
            ),
            (
                "Blütenhonig cremig",
                "golden regional blossom honey for tea and toast",
                "REC_BREAKFAST",
            ),
            (
                "Ahornsirup Grad A",
                "pure Canadian maple syrup for pancakes & roasted squash",
                "REC_VEGAN",
            ),
            (
                "Fruchtaufstrich Erdbeere 75%",
                "extra-fruity strawberry jam",
                "REC_BREAKFAST",
            ),
            (
                "Schoko-Haselnuss-Creme vegan",
                "palm-oil-free vegan hazelnut cocoa spread",
                "REC_VEGAN",
            ),
        ],
        "variants": [
            "ohne Zuckerzusatz",
            "zart",
            "kernig",
            "High Protein",
            "mit Nüssen",
            "glutenfrei",
        ],
        "units": ["200g", "300g", "350g", "400g", "500g", "750g", "1kg"],
        "price": (1.19, 5.99),
        "nutri": {
            "nutriscore": "B",
            "calories": 368,
            "protein_g": 12.2,
            "carbs_g": 59.0,
            "fat_g": 7.4,
            "sugar_g": 9.5,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Baking & Desserts",
        "brands": ["Dr. Oetker", "REWE Bio", "Alnatura", "REWE Beste Wahl", "Ja!"],
        "bases": [
            (
                "Dinkelmehl Type 630",
                "versatile organic spelt flour for cakes & waffles",
                "REC_BAKE",
            ),
            (
                "Weizenmehl Type 405",
                "classic baking flour for cookies and pastries",
                "REC_BAKE",
            ),
            (
                "Mandelmehl entölt",
                "low-carb gluten-free almond flour for baking",
                "REC_GF",
            ),
            (
                "Backkakao schwach entölt",
                "rich dark cocoa powder for brownies & hot chocolate",
                "REC_WINTER",
            ),
            (
                "Vanilleschoten Bourbon",
                "whole aromatic Madagascar vanilla pods",
                "REC_BAKE",
            ),
            (
                "Mandeln gemahlen",
                "finely ground almonds for winter Stollen & cookies",
                "REC_WINTER",
            ),
            (
                "Haselnüsse gehackt",
                "crunchy roasted hazelnuts for toppings & cakes",
                "REC_BAKE",
            ),
            (
                "Kuvertüre Zartbitter 70%",
                "fine dark couverture chocolate for glazing",
                "REC_VEGAN",
            ),
            ("Rohrohrzucker", "unrefined golden cane sugar", "REC_BAKE"),
            (
                "Backpulver Weinstein",
                "organic cream-of-tartar baking powder",
                "REC_BAKE",
            ),
        ],
        "variants": [
            "fein gemahlen",
            "geröstet",
            "Bourbon",
            "extra dunkel",
            "klassisch",
        ],
        "units": ["100g", "200g", "250g", "500g", "1kg"],
        "price": (0.89, 4.99),
        "nutri": {
            "nutriscore": "C",
            "calories": 375,
            "protein_g": 9.8,
            "carbs_g": 62.0,
            "fat_g": 8.5,
            "sugar_g": 12.0,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Frozen",
        "brands": [
            "Frosta",
            "Iglo",
            "Coppenrath & Wiese",
            "REWE Bio",
            "REWE Beste Wahl",
            "Ja!",
        ],
        "bases": [
            (
                "Unsere Goldstücke Brötchen",
                "crispy oven-fresh breakfast rolls from freezer",
                "REC_BREAKFAST",
            ),
            (
                "Pfannengemüse Toskana",
                "mediterranean frozen veggies ready in 8 minutes",
                "REC_VEGAN",
            ),
            (
                "Bami Goreng Pfannengericht",
                "quick Asian noodle skillet meal",
                "REC_ASIAN",
            ),
            ("Rahm-Spinat mit Blub", "creamy chopped spinach classic", "REC_CLASSIC"),
            ("Erbsen & Möhren jung", "flash-frozen sweet peas and carrots", "REC_SOUP"),
            (
                "Himbeeren tiefgefroren",
                "vitamin-locked frozen raspberries for smoothies",
                "REC_BREAKFAST",
            ),
            (
                "Mango Würfel tiefgefroren",
                "sweet frozen mango chunks for lassi & bowls",
                "REC_BOWL",
            ),
            (
                "Kräuter-Mischung 8-Kräuter",
                "chopped garden herbs ready for soups & dressings",
                "REC_SOUP",
            ),
            (
                "Steinofen Pizza Margherita",
                "crispy wood-fired Italian Margherita pizza",
                "REC_CLASSIC",
            ),
            (
                "Vegane Bowl Sweet Chili",
                "balanced frozen quinoa & edamame meal bowl",
                "REC_VEGAN",
            ),
            (
                "Apfelstrudel mit Rosinen",
                "warm Viennese apple strudel dessert",
                "REC_WINTER",
            ),
        ],
        "variants": [
            "ohne Zusatzstoffe",
            "ofenfrisch",
            "küchenfertig",
            "klassisch",
            "vegan",
            "mediterran",
        ],
        "units": ["250g", "300g", "420g", "450g", "500g", "750g", "1kg"],
        "price": (1.49, 4.99),
        "nutri": {
            "nutriscore": "B",
            "calories": 142,
            "protein_g": 5.2,
            "carbs_g": 21.0,
            "fat_g": 3.8,
            "sugar_g": 4.2,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Food > Snacks & Sweets",
        "brands": [
            "Ritter Sport",
            "Lindt",
            "Seeberger",
            "Lorenz",
            "REWE Bio",
            "REWE Feine Welt",
            "Ja!",
        ],
        "bases": [
            (
                "Kürbiskerne geröstet",
                "crunchy roasted Styrian pumpkin seeds for salads & soups",
                "REC_HERBST",
            ),
            (
                "Walnusskerne",
                "brain-food walnut halves for snacking & autumn salads",
                "REC_HERBST",
            ),
            (
                "Studentenfutter Classic",
                "classic trail mix of nuts and sweet raisins",
                "REC_SNACK",
            ),
            (
                "Cashewkerne ungesalzen",
                "creamy raw cashews for vegan sauces and snacking",
                "REC_VEGAN",
            ),
            (
                "Mandeln geröstet & gesalzen",
                "crispy roasted salted almonds",
                "REC_SNACK",
            ),
            (
                "Edelbitter Schokolade 75%",
                "intense single-origin vegan dark chocolate",
                "REC_VEGAN",
            ),
            (
                "Alpenvollmilch Schokolade",
                "creamy Alpine milk chocolate bar",
                "REC_SNACK",
            ),
            (
                "Kesselchips Meersalz",
                "extra-crunchy kettle-cooked potato chips",
                "REC_SNACK",
            ),
            (
                "Linsenchips Paprika",
                "lighter protein-rich lentil chips for movie nights",
                "REC_FIT",
            ),
            (
                "Dattel-Nuss Riegel",
                "natural energy bar with dates and hazelnuts",
                "REC_FIT",
            ),
            (
                "Reiswaffeln Zartbitter",
                "gluten-free crispy rice cakes dipped in dark chocolate",
                "REC_GF",
            ),
            (
                "Spekulatius Gewürzgebäck",
                "traditional spiced autumn & Christmas cookies",
                "REC_WINTER",
            ),
            (
                "Lebkuchen Nürnberger Art",
                "soft spiced German gingerbread on wafer",
                "REC_WINTER",
            ),
        ],
        "variants": [
            "ungesalzen",
            "geröstet",
            "knackig",
            "fein gewürzt",
            "mit Meersalz",
            "zuckerreduziert",
        ],
        "units": ["100g", "125g", "150g", "200g", "250g", "300g", "400g"],
        "price": (0.99, 4.99),
        "nutri": {
            "nutriscore": "D",
            "calories": 495,
            "protein_g": 11.4,
            "carbs_g": 38.0,
            "fat_g": 31.0,
            "sugar_g": 18.0,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Drinks > Coffee & Tea",
        "brands": [
            "Tchibo",
            "Lavazza",
            "Jacobs",
            "REWE Bio",
            "REWE Feine Welt",
            "Meßmer",
            "Alnatura",
        ],
        "bases": [
            (
                "Caffè Crema ganze Bohne",
                "balanced medium-roast Arabica beans for crema",
                "REC_COFFEE",
            ),
            (
                "Espresso Intenso Bohne",
                "dark Italian-roast espresso beans",
                "REC_COFFEE",
            ),
            (
                "Filterkaffee mild gemahlen",
                "smooth aromatic ground filter coffee",
                "REC_COFFEE",
            ),
            (
                "Kräutertee Ingwer-Zitrone",
                "warming ginger-lemon herbal tea for chilly days",
                "REC_HERBST",
            ),
            (
                "Chai Tee Zimt-Kardamom",
                "spiced Indian chai blend perfect with oat milk",
                "REC_HERBST",
            ),
            ("Grüner Tee Sencha", "delicate Japanese-style green tea", "REC_FIT"),
            (
                "Pfefferminztee Bio",
                "refreshing whole-leaf peppermint infusion",
                "REC_CLASSIC",
            ),
            (
                "Früchtetee Winterzauber",
                "hibiscus, apple & cinnamon winter fruit tea",
                "REC_WINTER",
            ),
            (
                "Matcha Grünteepulver",
                "ceremonial grade Japanese green tea powder",
                "REC_FIT",
            ),
            (
                "Trinkschokolade Zartbitter",
                "rich vegan hot chocolate flakes",
                "REC_WINTER",
            ),
        ],
        "variants": [
            "Fairtrade",
            "100% Arabica",
            "entkoffeiniert",
            "mild",
            "intensiv",
            "lose",
            "20 Beutel",
        ],
        "units": ["30g", "100g", "250g", "500g", "1kg", "20er", "25er"],
        "price": (1.69, 14.99),
        "nutri": {
            "nutriscore": "A",
            "calories": 2,
            "protein_g": 0.1,
            "carbs_g": 0.3,
            "fat_g": 0.0,
            "sugar_g": 0.0,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Drinks > Juices & Smoothies",
        "brands": ["REWE Bio", "REWE Beste Wahl", "REWE Regional", "Ja!"],
        "bases": [
            (
                "Apfelsaft naturtrüb Direktsaft",
                "cloudy pressed regional apple juice, 100% fruit",
                "REC_BREAKFAST",
            ),
            (
                "Orangensaft Direktsaft",
                "100% pure pressed orange juice with pulp",
                "REC_BREAKFAST",
            ),
            (
                "Johannisbeernektar schwarz",
                "rich tart blackcurrant nectar",
                "REC_CLASSIC",
            ),
            (
                "Multivitaminsaft",
                "10-fruit vitamin juice blend for breakfast",
                "REC_BREAKFAST",
            ),
            (
                "Ingwer-Kurkuma Shot",
                "fiery cold-pressed ginger turmeric wellness shot",
                "REC_FIT",
            ),
            (
                "Green Smoothie Spinat-Mango",
                "cold-pressed green smoothie without added sugar",
                "REC_VEGAN",
            ),
            (
                "Apfel-Kirsch Direktsaft",
                "fruity autumn apple and sour cherry press",
                "REC_HERBST",
            ),
            (
                "Rote-Bete-Saft lactofermentiert",
                "organic earthy beetroot juice for endurance athletes",
                "REC_FIT",
            ),
        ],
        "variants": [
            "Direktsaft",
            "naturtrüb",
            "100% Frucht",
            "ohne Zuckerzusatz",
            "kaltgepresst",
        ],
        "units": ["150ml", "250ml", "500ml", "750ml", "1L"],
        "price": (1.19, 3.49),
        "nutri": {
            "nutriscore": "C",
            "calories": 44,
            "protein_g": 0.4,
            "carbs_g": 10.2,
            "fat_g": 0.1,
            "sugar_g": 9.6,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Drinks > Water & Soft Drinks",
        "brands": ["Gerolsteiner", "Vio", "REWE Beste Wahl", "REWE Bio", "Ja!"],
        "bases": [
            (
                "Mineralwasser Sprudel",
                "sparkling mineral-rich natural water",
                "REC_CLASSIC",
            ),
            ("Mineralwasser Still", "pure still mineral water", "REC_CLASSIC"),
            (
                "Apfelschorle naturtrüb",
                "refreshing sparkling apple spritzer",
                "REC_FIT",
            ),
            ("Rhabarberschorle", "tart German rhubarb spritzer", "REC_SUMMER"),
            (
                "Holunderblüten-Limonade",
                "floral elderflower craft lemonade",
                "REC_SUMMER",
            ),
            (
                "Kombucha Ingwer",
                "lightly fermented sparkling probiotic tea",
                "REC_VEGAN",
            ),
            ("Eistee Pfirsich zuckerfrei", "zero-sugar peach iced tea", "REC_FIT"),
            ("Tonic Water Dry", "crisp quinine tonic mixer", "REC_PARTY"),
        ],
        "variants": ["Classic", "Medium", "Still", "Zuckerfrei", "Naturtrüb", "Leicht"],
        "units": ["0,33L", "0,5L", "0,75L", "1L", "1,5L", "6x1L", "6x0,5L"],
        "price": (0.39, 5.99),
        "nutri": {
            "nutriscore": "B",
            "calories": 18,
            "protein_g": 0.0,
            "carbs_g": 4.4,
            "fat_g": 0.0,
            "sugar_g": 4.2,
        },
        "vegan": True,
        "veg": True,
        "gf": True,
        "lf": True,
        "hp": False,
    },
    {
        "cat": "Drinks > Beer & Wine",
        "brands": [
            "Paulaner",
            "Bitburger",
            "Rotkäppchen",
            "REWE Feine Welt",
            "REWE Beste Wahl",
        ],
        "bases": [
            (
                "Weißbier Alkoholfrei",
                "isotonic alcohol-free Bavarian wheat beer for recovery",
                "REC_FIT",
            ),
            ("Pils Premium", "crisp hoppy German Pilsner beer", "REC_GRILL"),
            ("Helles Lager", "smooth golden Munich-style Helles", "REC_GRILL"),
            (
                "Riesling trocken Mosel",
                "crisp mineral German Riesling white wine",
                "REC_GOURMET",
            ),
            (
                "Spätburgunder trocken Baden",
                "velvety German Pinot Noir for autumn dishes",
                "REC_HERBST",
            ),
            (
                "Glühwein rot gewürzt",
                "classic spiced mulled red wine for winter",
                "REC_WINTER",
            ),
            (
                "Sekt Alkoholfrei",
                "sparkling dealcoholized cuvée for celebrations",
                "REC_PARTY",
            ),
            (
                "Primitivo Puglia IGT",
                "full-bodied Italian red wine for pasta & steak",
                "REC_GOURMET",
            ),
        ],
        "variants": [
            "Trocken",
            "Alkoholfrei",
            "Fassfrisch",
            "Barrique",
            "2024er",
            "Naturtrüb",
        ],
        "units": ["0,33L", "0,5L", "0,75L", "6x0,33L", "6x0,5L"],
        "price": (0.89, 11.99),
        "nutri": {
            "nutriscore": "D",
            "calories": 46,
            "protein_g": 0.3,
            "carbs_g": 3.2,
            "fat_g": 0.0,
            "sugar_g": 0.6,
        },
        "vegan": True,
        "veg": True,
        "gf": False,
        "lf": True,
        "hp": False,
    },
]

# --------------------------------------------------------------------------- #
# Customer personas (20 authentic, non-generic archetypes)
# --------------------------------------------------------------------------- #
PERSONAS: list[dict[str, Any]] = [
    {
        "summary": "Health-conscious urban professional, loyal to Bio and Vegan products.",
        "dietary": [["vegan", "bio-only"], ["vegan"]],
        "sens": ["Low", "Medium"],
        "age": (24, 42),
        "hh": (1, 2),
        "tiers": ["Gold", "Platinum", "Silver"],
    },
    {
        "summary": "Budget-focused parent of two, looks for Ja! brand deals and family-sized packs.",
        "dietary": [["no-restrictions"], ["lactose-free"]],
        "sens": ["High"],
        "age": (30, 48),
        "hh": (3, 5),
        "tiers": ["Silver", "Bronze", "Gold"],
    },
    {
        "summary": "The Regional Patriot — prefers local German produce, seasonal vegetables, and REWE Regional dairy.",
        "dietary": [["bio-only"], ["no-restrictions"]],
        "sens": ["Medium", "Low"],
        "age": (35, 68),
        "hh": (2, 4),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Gluten-Free Endurance Runner — trains for half-marathons and fuels with gluten-free carbs and plant proteins.",
        "dietary": [["gluten-free", "high-protein"], ["gluten-free"]],
        "sens": ["Medium", "Low"],
        "age": (22, 44),
        "hh": (1, 2),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Weekend Gourmet Chef — loves REWE Feine Welt specialties, aged cheese, olive oil, and pairing wines.",
        "dietary": [["no-restrictions"], ["vegetarian"]],
        "sens": ["Low"],
        "age": (32, 62),
        "hh": (1, 3),
        "tiers": ["Platinum", "Gold"],
    },
    {
        "summary": "The Bio-Mom — prioritizes organic ingredients, fresh fruits, and additive-free snacks for the kids.",
        "dietary": [["bio-only"], ["bio-only", "vegetarian"]],
        "sens": ["Medium", "Low"],
        "age": (28, 45),
        "hh": (3, 5),
        "tiers": ["Gold", "Platinum"],
    },
    {
        "summary": "The High-Protein Fitness Enthusiast — stocks up on Skyr, chicken breast, tofu, oats, and protein snacks.",
        "dietary": [["high-protein"], ["high-protein", "lactose-free"]],
        "sens": ["Medium", "High"],
        "age": (20, 38),
        "hh": (1, 2),
        "tiers": ["Silver", "Gold"],
    },
    {
        "summary": "The Plant-Based Flexitarian — cooks mostly vegan during the week and loves meat alternatives and bowls.",
        "dietary": [["vegan"], ["vegetarian", "bio-only"]],
        "sens": ["Medium"],
        "age": (23, 40),
        "hh": (1, 3),
        "tiers": ["Silver", "Gold"],
    },
    {
        "summary": "The Busy Office Snacker — grabs quick smoothies, nut bars, barista oat coffee, and frozen bowls.",
        "dietary": [["no-restrictions"], ["vegetarian"]],
        "sens": ["Medium", "Low"],
        "age": (24, 39),
        "hh": (1, 2),
        "tiers": ["Silver", "Bronze"],
    },
    {
        "summary": "The Quick-Meal Student — shops smart with Ja! staples, pasta, frozen veggies, and energy-dense snacks.",
        "dietary": [["no-restrictions"], ["vegetarian"]],
        "sens": ["High"],
        "age": (19, 27),
        "hh": (1, 2),
        "tiers": ["Bronze", "Silver"],
    },
    {
        "summary": "The Sustainable Zero-Waste Senior — cooks from scratch with seasonal vegetables, lentils, and organic teas.",
        "dietary": [["bio-only", "vegetarian"], ["bio-only"]],
        "sens": ["Medium", "Low"],
        "age": (60, 79),
        "hh": (1, 2),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Frozen-Food Pro — relies on convenient frozen vegetable mixes, oven rolls, and quick 10-minute skillet meals.",
        "dietary": [["no-restrictions"]],
        "sens": ["High", "Medium"],
        "age": (23, 42),
        "hh": (1, 2),
        "tiers": ["Silver", "Bronze"],
    },
    {
        "summary": "The Mediterranean Home Cook — buys vine tomatoes, durum pasta, olive oil, basil, and aged Parmesan weekly.",
        "dietary": [["no-restrictions"], ["vegetarian"]],
        "sens": ["Medium", "Low"],
        "age": (29, 58),
        "hh": (2, 4),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Sweet-Tooth Weekend Baker — loves seasonal baking with spelt flour, berries, dark chocolate, and vanilla.",
        "dietary": [["vegetarian"], ["no-restrictions"]],
        "sens": ["Medium"],
        "age": (26, 60),
        "hh": (2, 4),
        "tiers": ["Silver", "Gold"],
    },
    {
        "summary": "The Craft Beer & BBQ Host — plans weekend grill gatherings with steaks, grill cheese, sauces, and cold drinks.",
        "dietary": [["no-restrictions"]],
        "sens": ["Medium", "Low"],
        "age": (27, 52),
        "hh": (2, 4),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Ja!-Only Minimalist — sticks strictly to everyday low-price basics and weekly yellow-tag promotions.",
        "dietary": [["no-restrictions"]],
        "sens": ["High"],
        "age": (22, 65),
        "hh": (1, 4),
        "tiers": ["Bronze", "Silver"],
    },
    {
        "summary": "The Bulk-Buying Family Dad — fills the trunk with multipacks of milk, mineral water, pasta, and snacks.",
        "dietary": [["no-restrictions"]],
        "sens": ["High", "Medium"],
        "age": (33, 52),
        "hh": (4, 6),
        "tiers": ["Gold", "Silver"],
    },
    {
        "summary": "The Lactose-Free Breakfast Lover — starts every morning with oat barista milk, lactose-free yogurt, and berries.",
        "dietary": [["lactose-free"], ["lactose-free", "bio-only"]],
        "sens": ["Medium", "Low"],
        "age": (24, 50),
        "hh": (1, 3),
        "tiers": ["Silver", "Gold"],
    },
    {
        "summary": "The Asian-Fusion Home Cook — loves coconut milk, tofu, ginger, sesame oil, jasmine/basmati rice, and herbs.",
        "dietary": [["vegan"], ["lactose-free"]],
        "sens": ["Medium", "Low"],
        "age": (23, 43),
        "hh": (1, 3),
        "tiers": ["Silver", "Gold"],
    },
    {
        "summary": "The Coffee & Tea Connoisseur — seeks single-origin beans, herbal infusions, and artisanal biscuits.",
        "dietary": [["no-restrictions"], ["bio-only"]],
        "sens": ["Low"],
        "age": (30, 64),
        "hh": (1, 2),
        "tiers": ["Gold", "Platinum"],
    },
]

FIRST_NAMES_F = [
    "Lena",
    "Anna",
    "Laura",
    "Sarah",
    "Julia",
    "Marie",
    "Hannah",
    "Sophie",
    "Katharina",
    "Lisa",
    "Miriam",
    "Nina",
    "Clara",
    "Johanna",
    "Eva",
    "Franziska",
    "Sabine",
    "Petra",
    "Claudia",
    "Katrin",
    "Melanie",
    "Maja",
    "Emma",
    "Mia",
    "Leonie",
    "Teresa",
    "Ute",
    "Heike",
]
FIRST_NAMES_M = [
    "Lukas",
    "Jonas",
    "Maximilian",
    "Stefan",
    "Markus",
    "Tobias",
    "Sebastian",
    "Jan",
    "Tim",
    "Philipp",
    "Felix",
    "Moritz",
    "Paul",
    "Daniel",
    "Michael",
    "Christian",
    "Thomas",
    "Andreas",
    "Martin",
    "Matthias",
    "Julian",
    "Fabian",
    "Florian",
    "Niklas",
    "David",
    "Sven",
]


def _load_clean_133() -> list[dict[str, Any]]:
    """Reads the 133 clean existing products from BigQuery directly."""
    bq = bigquery.Client(project=PROJECT_ID)
    rows = [
        dict(r)
        for r in bq.query(f"""
        SELECT product_id, name, brand, category_path, stock_level,
               price_current, nutritional_info, marketing_copy, recipe_ids
        FROM `{FULL_DS}.product_catalog`
        WHERE product_id IN (
            SELECT product_id FROM `{FULL_DS}.product_catalog`
            GROUP BY product_id HAVING COUNT(*) = 1
        )
        ORDER BY product_id
    """)
    ]
    for r in rows:
        ni = r.get("nutritional_info")
        if isinstance(ni, str):
            r["nutritional_info"] = json.loads(ni)
    return rows


def _infer_flags_for_clean_product(p: dict[str, Any]) -> dict[str, bool]:
    blob = f"{p['name']} {p['brand']} {p['category_path']} {p.get('marketing_copy', '')}".lower()
    cat = p["category_path"].lower()
    non_vegan_kw = (
        "meat",
        "beef",
        "pork",
        "poultry",
        "sausage",
        "seafood",
        "dairy >",
        "cheese",
        "käse",
        "butter",
        "cream",
        "sahne",
        "joghurt",
        "yogurt",
        "milch",
        "milk",
        "eis",
        "ice cream",
        "schinken",
        "wurst",
        "lachs",
        "hähnchen",
        "rind",
        "schwein",
        "ei ",
        "eier",
        "honig",
        "tzatziki",
        "feta",
        "grillkäse",
        "halloumi",
        "mozzarella",
        "speck",
    )
    is_meat = any(
        k in cat or k in blob
        for k in (
            "meat",
            "beef",
            "pork",
            "poultry",
            "sausage",
            "seafood",
            "hähnchen",
            "rind",
            "schwein",
            "wurst",
            "lachs",
            "schinken",
            "bratwurst",
            "steak",
            "burger",
            "speck",
        )
    )
    if (
        "vegan" in blob
        or "plant-based" in blob
        or "meat alternatives" in cat
        or "dairy alternatives" in cat
    ):
        is_vegan = True
        is_veg = True
    else:
        is_veg = not is_meat
        is_vegan = is_veg and not any(k in blob or k in cat for k in non_vegan_kw)
    is_gf = (
        "gluten-free" in blob
        or "glutenfrei" in blob
        or ("produce" in cat or "drinks" in cat)
    )
    is_bio = (
        "bio" in p["brand"].lower()
        or "alnatura" in p["brand"].lower()
        or "regional" in p["brand"].lower()
    )
    is_hp = "protein" in blob or "tofu" in blob or "meat" in cat or "seafood" in cat
    return {
        "vegan": is_vegan,
        "veg": is_veg,
        "gf": is_gf,
        "lf": is_vegan or "laktosefrei" in blob,
        "bio": is_bio,
        "hp": is_hp,
    }


def _brand_price_factor(brand: str) -> float:
    if brand == "Ja!":
        return 0.68
    if brand in ("REWE Bio", "Alnatura", "Oatly"):
        return 1.25
    if brand in ("REWE Feine Welt", "Lindt", "Lavazza"):
        return 1.40
    return 1.0


def build_products(
    rng: random.Random,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, bool]]]:
    clean_133 = _load_clean_133()
    products: list[dict[str, Any]] = []
    flags: dict[str, dict[str, bool]] = {}
    used_names: set[str] = set()
    used_ids: set[str] = set()

    for r in clean_133:
        used_names.add(r["name"].lower())
        used_ids.add(r["product_id"])
        flags[r["product_id"]] = _infer_flags_for_clean_product(r)
        products.append(
            {
                "product_id": r["product_id"],
                "name": r["name"],
                "brand": r["brand"],
                "category_path": r["category_path"],
                "stock_level": int(r["stock_level"] or 100),
                "price_current": round(float(r["price_current"]), 2),
                "nutritional_info": r["nutritional_info"] or {"nutriscore": "A"},
                "marketing_copy": r["marketing_copy"],
                "recipe_ids": list(r.get("recipe_ids") or []),
            }
        )

    # Expand across all departments until we reach TARGET_PRODUCTS unique products.
    combos: list[tuple[dict[str, Any], str, tuple[str, str, str], str, str]] = []
    for dept in DEPARTMENTS:
        for brand in dept["brands"]:
            for base in dept["bases"]:
                for var in dept["variants"]:
                    for unit in dept["units"]:
                        combos.append((dept, brand, base, var, unit))
    rng.shuffle(combos)

    seq = 431
    for dept, brand, (base_name, eng_hint, rec_prefix), var, unit in combos:
        if len(products) >= TARGET_PRODUCTS:
            break
        # Keep brand prefix natural (don't write "REWE Bio Bio ...")
        if brand.lower() in base_name.lower():
            name = f"{base_name} {var} {unit}".strip()
        else:
            name = f"{brand} {base_name} {var} {unit}".strip()
        if name.lower() in used_names:
            continue

        used_names.add(name.lower())
        pid = f"EAN_{seq:04d}"
        while pid in used_ids:
            seq += 1
            pid = f"EAN_{seq:04d}"
        used_ids.add(pid)
        seq += 1

        lo, hi = dept["price"]
        raw_p = rng.uniform(lo, hi) * _brand_price_factor(brand)
        # Retail psychological pricing (.x9 or .x5)
        price = round(
            max(0.39, int(raw_p * 10) / 10 + rng.choice([0.09, 0.09, 0.05, 0.00])), 2
        )
        if price <= 0.35:
            price = 0.49

        n0 = dept["nutri"]
        nutri = {
            "nutriscore": n0["nutriscore"],
            "calories": max(0, int(n0["calories"] * rng.uniform(0.88, 1.12))),
            "protein_g": round(max(0.0, n0["protein_g"] * rng.uniform(0.85, 1.15)), 1),
            "carbs_g": round(max(0.0, n0["carbs_g"] * rng.uniform(0.85, 1.15)), 1),
            "fat_g": round(max(0.0, n0["fat_g"] * rng.uniform(0.85, 1.15)), 1),
            "sugar_g": round(max(0.0, n0["sugar_g"] * rng.uniform(0.85, 1.15)), 1),
        }

        is_bio = brand in ("REWE Bio", "Alnatura", "REWE Regional")
        is_gf = (
            dept["gf"]
            or "glutenfrei" in name.lower()
            or "gluten-free" in eng_hint.lower()
        )
        diet_notes = []
        if dept["vegan"]:
            diet_notes.append("100% plant-based / vegan")
        elif dept["veg"]:
            diet_notes.append("vegetarian")
        if is_bio:
            diet_notes.append("certified organic quality")
        if is_gf:
            diet_notes.append("naturally gluten-free")
        if dept["hp"]:
            diet_notes.append("rich in protein")
        diet_str = f" ({', '.join(diet_notes)})" if diet_notes else ""

        copy = (
            f"{base_name} ({var}, {unit}) by {brand}{diet_str}. Ideal for {eng_hint}."
        )
        rec_id = f"{rec_prefix}_{rng.randint(1, 20):02d}"

        products.append(
            {
                "product_id": pid,
                "name": name,
                "brand": brand,
                "category_path": dept["cat"],
                "stock_level": rng.randint(25, 1200),
                "price_current": price,
                "nutritional_info": nutri,
                "marketing_copy": copy,
                "recipe_ids": [rec_id],
            }
        )
        flags[pid] = {
            "vegan": dept["vegan"],
            "veg": dept["veg"],
            "gf": is_gf,
            "lf": dept["lf"] or "laktosefrei" in name.lower(),
            "bio": is_bio,
            "hp": dept["hp"] or "protein" in name.lower(),
        }

    assert len(products) == TARGET_PRODUCTS, f"Only built {len(products)} products"
    assert len({p["product_id"] for p in products}) == TARGET_PRODUCTS
    assert len({p["name"] for p in products}) == TARGET_PRODUCTS
    return products, flags


def build_customers(rng: random.Random) -> list[dict[str, Any]]:
    customers: list[dict[str, Any]] = []
    # Preserved canonical IDs referenced by tests & evaluation notebooks
    anchors: dict[int, dict[str, Any]] = {
        1: {
            "gender": "F",
            "first_name": "Lena",
            "age": 28,
            "hh": 1,
            "city": "Berlin",
            "zip_code": "10115",
            "region": "Berlin",
            "tier": "Gold",
            "points": 1250,
            "join_date": "2023-01-01",
            "dietary_tags": ["vegan", "bio-only"],
            "price_sensitivity": "Low",
            "predicted_clv": 2500.0,
            "churn_risk": 0.05,
            "persona_summary": "Health-conscious urban professional, loyal to Bio and Vegan products.",
        },
        2: {
            "gender": "M",
            "first_name": "Markus",
            "age": 39,
            "hh": 4,
            "city": "München",
            "zip_code": "80331",
            "region": "Bavaria",
            "tier": "Silver",
            "points": 640,
            "join_date": "2022-06-15",
            "dietary_tags": ["no-restrictions"],
            "price_sensitivity": "High",
            "predicted_clv": 3420.0,
            "churn_risk": 0.14,
            "persona_summary": "Budget-focused parent of two, looks for Ja! brand deals and family-sized packs.",
        },
        61: {
            "gender": "M",
            "first_name": "Stefan",
            "age": 46,
            "hh": 3,
            "city": "München",
            "zip_code": "80802",
            "region": "Bavaria",
            "tier": "Gold",
            "points": 1580,
            "join_date": "2023-04-10",
            "dietary_tags": ["bio-only"],
            "price_sensitivity": "Medium",
            "predicted_clv": 3180.0,
            "churn_risk": 0.08,
            "persona_summary": "The Regional Patriot — prefers local German produce, seasonal vegetables, and REWE Regional dairy.",
        },
    }

    tier_points = {
        "Bronze": (40, 350, 0.35, 0.85, 450, 1400),
        "Silver": (350, 1100, 0.15, 0.55, 1200, 2900),
        "Gold": (1100, 3200, 0.04, 0.25, 2500, 5200),
        "Platinum": (3200, 7500, 0.02, 0.10, 4800, 8800),
    }

    for idx in range(1, TARGET_CUSTOMERS + 1):
        cid = f"CUST{idx:03d}" if idx < 1000 else f"CUST{idx:04d}"
        if idx in anchors:
            a = anchors[idx]
            customers.append(
                {
                    "customer_id": cid,
                    "demographics": {
                        "first_name": a["first_name"],
                        "age": a["age"],
                        "gender": a["gender"],
                        "household_size": a["hh"],
                        "zip_code": a["zip_code"],
                        "city": a["city"],
                        "region": a["region"],
                    },
                    "loyalty": {
                        "join_date": a["join_date"],
                        "points": a["points"],
                        "tier": a["tier"],
                    },
                    "dietary_tags": a["dietary_tags"],
                    "predicted_clv": a["predicted_clv"],
                    "churn_risk": a["churn_risk"],
                    "price_sensitivity": a["price_sensitivity"],
                    "persona_summary": a["persona_summary"],
                    "consent_status": {
                        "marketing_email": True,
                        "personalized_ads": True,
                    },
                }
            )
            continue

        p_spec = PERSONAS[(idx - 1) % len(PERSONAS)]
        reg = REGIONS[(idx * 7) % len(REGIONS)]
        city, plz = rng.choice(reg["cities"])
        gender = rng.choice(["F", "M"])
        fname = rng.choice(FIRST_NAMES_F if gender == "F" else FIRST_NAMES_M)
        tier = rng.choice(p_spec["tiers"])
        p_lo, p_hi, c_lo, c_hi, clv_lo, clv_hi = tier_points[tier]
        join_days_ago = rng.randint(60, 2400)
        join_date = (NOW.date() - datetime.timedelta(days=join_days_ago)).isoformat()

        customers.append(
            {
                "customer_id": cid,
                "demographics": {
                    "first_name": fname,
                    "age": rng.randint(*p_spec["age"]),
                    "gender": gender,
                    "household_size": rng.randint(*p_spec["hh"]),
                    "zip_code": plz,
                    "city": city,
                    "region": reg["region"],
                },
                "loyalty": {
                    "join_date": join_date,
                    "points": rng.randint(p_lo, p_hi),
                    "tier": tier,
                },
                "dietary_tags": list(rng.choice(p_spec["dietary"])),
                "predicted_clv": round(rng.uniform(clv_lo, clv_hi), 2),
                "churn_risk": round(rng.uniform(c_lo, c_hi), 2),
                "price_sensitivity": rng.choice(p_spec["sens"]),
                "persona_summary": p_spec["summary"],
                "consent_status": {
                    "marketing_email": True,
                    "personalized_ads": rng.random() < 0.88,
                },
            }
        )
    assert len(customers) == TARGET_CUSTOMERS
    return customers


def build_interactions(
    rng: random.Random,
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
    flags: dict[str, dict[str, bool]],
) -> list[dict[str, Any]]:
    # Pre-index eligible products by dietary bitmask for fast consistent sampling.
    all_pids = [p["product_id"] for p in products]
    by_tag = {
        "vegan": [pid for pid in all_pids if flags[pid]["vegan"]],
        "vegetarian": [pid for pid in all_pids if flags[pid]["veg"]],
        "gluten-free": [pid for pid in all_pids if flags[pid]["gf"]],
        "lactose-free": [pid for pid in all_pids if flags[pid]["lf"]],
        "bio-only": [pid for pid in all_pids if flags[pid]["bio"]],
        "high-protein": [pid for pid in all_pids if flags[pid]["hp"]],
    }
    price_map = {p["product_id"]: p["price_current"] for p in products}
    brand_map = {p["product_id"]: p["brand"] for p in products}

    def eligible_pool(c: dict[str, Any]) -> list[str]:
        tags = set(c["dietary_tags"]) - {"no-restrictions"}
        if not tags:
            pool = all_pids
        else:
            sets = [set(by_tag[t]) for t in tags if t in by_tag]
            common = set.intersection(*sets) if sets else set(all_pids)
            if not common:
                # Never violate hard restrictions (vegan/vegetarian/gf/lf); relax bio if needed
                hard = [
                    set(by_tag[t])
                    for t in tags
                    & {"vegan", "vegetarian", "gluten-free", "lactose-free"}
                ]
                common = set.intersection(*hard) if hard else set(all_pids)
            pool = list(common)
        # Weight toward budget vs premium by price sensitivity
        if c["price_sensitivity"] == "High":
            cheap = [
                pid for pid in pool if brand_map[pid] == "Ja!" or price_map[pid] <= 3.0
            ]
            if len(cheap) >= 20:
                return cheap
        elif c["price_sensitivity"] == "Low":
            prem = [
                pid
                for pid in pool
                if brand_map[pid] in ("REWE Bio", "REWE Feine Welt", "REWE Regional")
                or price_map[pid] >= 2.0
            ]
            if len(prem) >= 20:
                return prem
        return pool

    pools = {c["customer_id"]: eligible_pool(c) for c in customers}
    events: list[dict[str, Any]] = []
    # Guarantee every customer has at least 6 recent interactions, up to TARGET_INTERACTIONS total.
    idx = 1
    for c in customers:
        pool = pools[c["customer_id"]]
        for _ in range(6):
            ts = NOW - datetime.timedelta(
                days=rng.randint(0, 89),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )
            events.append(
                {
                    "event_id": f"EVT_{idx:06d}",
                    "customer_id": c["customer_id"],
                    "event_type": rng.choices(
                        ["view", "add_to_cart", "purchase"], weights=[50, 28, 22]
                    )[0],
                    "object_id": rng.choice(pool),
                    "device_type": rng.choices(
                        ["mobile_app", "web", "desktop"], weights=[52, 28, 20]
                    )[0],
                    "timestamp": ts.isoformat(),
                }
            )
            idx += 1

    while len(events) < TARGET_INTERACTIONS:
        c = rng.choice(customers)
        pool = pools[c["customer_id"]]
        ts = NOW - datetime.timedelta(
            days=rng.randint(0, 89),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        events.append(
            {
                "event_id": f"EVT_{idx:06d}",
                "customer_id": c["customer_id"],
                "event_type": rng.choices(
                    ["view", "add_to_cart", "purchase"], weights=[50, 28, 22]
                )[0],
                "object_id": rng.choice(pool),
                "device_type": rng.choices(
                    ["mobile_app", "web", "desktop"], weights=[52, 28, 20]
                )[0],
                "timestamp": ts.isoformat(),
            }
        )
        idx += 1
    return events


def build_market_context() -> list[dict[str, Any]]:
    rows = []
    for i, r in enumerate(REGIONS):
        # Put Berlin / Bavaria / NRW first by timestamp so LIMIT 1 picks current top market.
        ts = NOW - datetime.timedelta(minutes=i)
        rows.append(
            {
                "region": r["region"],
                "current_weather": r["weather"],
                "active_promotion": r["promo"],
                "season": "Autumn",
                "timestamp": ts.isoformat(),
            }
        )
    return rows


def load_json_table(
    bq: bigquery.Client,
    table_id: str,
    rows: list[dict[str, Any]],
    schema: list[bigquery.SchemaField],
) -> None:
    cfg = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    job = bq.load_table_from_json(rows, table_id, job_config=cfg)
    job.result()
    print(f"  loaded {len(rows)} rows -> {table_id}")


def main() -> None:
    t0 = time.time()
    rng = random.Random(20261111)
    bq = bigquery.Client(project=PROJECT_ID)

    print("1. Generating consistent synthetic REWE data...")
    products, flags = build_products(rng)
    customers = build_customers(rng)
    interactions = build_interactions(rng, customers, products, flags)
    market = build_market_context()
    print(
        f"   products={len(products)}, customers={len(customers)}, "
        f"interactions={len(interactions)}, market_context={len(market)}"
    )

    # Stage raw rows (without embeddings yet), then generate 768-d embeddings in BQ.
    print("2. Loading staging tables into BigQuery (EU)...")
    prod_raw = f"{FULL_DS}._stage_prod_raw"
    cust_raw = f"{FULL_DS}._stage_cust_raw"
    prod_stg = f"{FULL_DS}._stage_product_catalog"
    cust_stg = f"{FULL_DS}._stage_customers_360"
    hist_stg = f"{FULL_DS}._stage_interaction_history"
    mkt_stg = f"{FULL_DS}._stage_market_context"

    load_json_table(
        bq,
        prod_raw,
        products,
        [
            bigquery.SchemaField("product_id", "STRING"),
            bigquery.SchemaField("name", "STRING"),
            bigquery.SchemaField("brand", "STRING"),
            bigquery.SchemaField("category_path", "STRING"),
            bigquery.SchemaField("stock_level", "INT64"),
            bigquery.SchemaField("price_current", "FLOAT64"),
            bigquery.SchemaField("nutritional_info", "JSON"),
            bigquery.SchemaField("marketing_copy", "STRING"),
            bigquery.SchemaField("recipe_ids", "STRING", mode="REPEATED"),
        ],
    )
    load_json_table(
        bq,
        cust_raw,
        customers,
        [
            bigquery.SchemaField("customer_id", "STRING"),
            bigquery.SchemaField("demographics", "JSON"),
            bigquery.SchemaField("loyalty", "JSON"),
            bigquery.SchemaField("dietary_tags", "STRING", mode="REPEATED"),
            bigquery.SchemaField("predicted_clv", "FLOAT64"),
            bigquery.SchemaField("churn_risk", "FLOAT64"),
            bigquery.SchemaField("price_sensitivity", "STRING"),
            bigquery.SchemaField("persona_summary", "STRING"),
            bigquery.SchemaField("consent_status", "JSON"),
        ],
    )
    load_json_table(
        bq,
        hist_stg,
        interactions,
        [
            bigquery.SchemaField("event_id", "STRING"),
            bigquery.SchemaField("customer_id", "STRING"),
            bigquery.SchemaField("event_type", "STRING"),
            bigquery.SchemaField("object_id", "STRING"),
            bigquery.SchemaField("device_type", "STRING"),
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
        ],
    )
    load_json_table(
        bq,
        mkt_stg,
        market,
        [
            bigquery.SchemaField("region", "STRING"),
            bigquery.SchemaField("current_weather", "STRING"),
            bigquery.SchemaField("active_promotion", "STRING"),
            bigquery.SchemaField("season", "STRING"),
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
        ],
    )

    print("3. Computing 768-dim embeddings via ML.GENERATE_EMBEDDING...")
    bq.query(f"""
        CREATE OR REPLACE TABLE `{prod_stg}` AS
        SELECT
            product_id, name, brand, category_path, stock_level,
            price_current, nutritional_info, marketing_copy, recipe_ids,
            ml_generate_embedding_result AS product_embedding
        FROM ML.GENERATE_EMBEDDING(
            MODEL `{FULL_DS}.embedding_model`,
            (SELECT *, CONCAT(name, ' | ', brand, ' | ', category_path, ' | ', marketing_copy) AS content
             FROM `{prod_raw}`),
            STRUCT(TRUE AS flatten_json_output, 768 AS output_dimensionality)
        )
    """).result()
    print("   product_catalog embeddings done.")

    bq.query(f"""
        CREATE OR REPLACE TABLE `{cust_stg}` AS
        SELECT
            customer_id, demographics, loyalty, dietary_tags,
            predicted_clv, churn_risk, price_sensitivity, persona_summary,
            ml_generate_embedding_result AS persona_embedding,
            consent_status
        FROM ML.GENERATE_EMBEDDING(
            MODEL `{FULL_DS}.embedding_model`,
            (SELECT *, CONCAT(persona_summary, ' | Diet: ', ARRAY_TO_STRING(dietary_tags, ', '), ' | Price: ', price_sensitivity) AS content
             FROM `{cust_raw}`),
            STRUCT(TRUE AS flatten_json_output, 768 AS output_dimensionality)
        )
    """).result()
    print("   customers_360 embeddings done.")

    print("4. Validating staged data integrity...")
    checks = next(
        iter(
            bq.query(f"""
        SELECT
            (SELECT COUNT(*) FROM `{cust_stg}`) AS cust_rows,
            (SELECT COUNT(DISTINCT customer_id) FROM `{cust_stg}`) AS cust_distinct,
            (SELECT COUNTIF(ARRAY_LENGTH(persona_embedding) != 768 OR persona_embedding IS NULL) FROM `{cust_stg}`) AS cust_bad_emb,
            (SELECT COUNT(*) FROM `{prod_stg}`) AS prod_rows,
            (SELECT COUNT(DISTINCT product_id) FROM `{prod_stg}`) AS prod_distinct_id,
            (SELECT COUNT(DISTINCT name) FROM `{prod_stg}`) AS prod_distinct_name,
            (SELECT COUNTIF(ARRAY_LENGTH(product_embedding) != 768 OR product_embedding IS NULL) FROM `{prod_stg}`) AS prod_bad_emb,
            (SELECT COUNT(*) FROM `{hist_stg}`) AS hist_rows,
            (SELECT COUNT(DISTINCT event_id) FROM `{hist_stg}`) AS hist_distinct,
            (SELECT COUNTIF(c.customer_id IS NULL OR p.product_id IS NULL)
             FROM `{hist_stg}` h
             LEFT JOIN `{cust_stg}` c ON h.customer_id = c.customer_id
             LEFT JOIN `{prod_stg}` p ON h.object_id = p.product_id) AS hist_orphans,
            (SELECT COUNT(*) FROM `{mkt_stg}`) AS mkt_rows
    """)
        )
    )
    c = dict(checks)
    print("   audit:", c)
    assert c["cust_rows"] == c["cust_distinct"] == TARGET_CUSTOMERS
    assert c["cust_bad_emb"] == 0
    assert (
        c["prod_rows"]
        == c["prod_distinct_id"]
        == c["prod_distinct_name"]
        == TARGET_PRODUCTS
    )
    assert c["prod_bad_emb"] == 0
    assert c["hist_rows"] == c["hist_distinct"] == TARGET_INTERACTIONS
    assert c["hist_orphans"] == 0
    assert c["mkt_rows"] == len(REGIONS)

    print("5. Promoting staging tables to production...")
    for stg, prod in [
        (cust_stg, f"{FULL_DS}.customers_360"),
        (prod_stg, f"{FULL_DS}.product_catalog"),
        (hist_stg, f"{FULL_DS}.interaction_history"),
        (mkt_stg, f"{FULL_DS}.market_context"),
    ]:
        bq.query(f"CREATE OR REPLACE TABLE `{prod}` AS SELECT * FROM `{stg}`").result()
        print(f"   promoted {prod}")

    for tmp in (prod_raw, cust_raw, prod_stg, cust_stg, hist_stg, mkt_stg):
        bq.delete_table(tmp, not_found_ok=True)

    print("6. Creating COSINE Vector Index on product_catalog(product_embedding)...")
    try:
        bq.query(f"""
            CREATE OR REPLACE VECTOR INDEX product_embedding_idx
            ON `{FULL_DS}.product_catalog`(product_embedding)
            OPTIONS(index_type = 'IVF', distance_type = 'COSINE')
        """).result()
        print("   vector index created (building asynchronously in background).")
    except Exception as e:
        print(f"   vector index creation note: {e}")

    print(f"All done in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
