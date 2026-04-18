"""
import_blog_signals.py
Bootstrap blog/editorial signals from static JSON data.
Matches by exact name (case-insensitive) + city_id. Fuzzy matches logged for review.

Usage:
    python scripts/import_blog_signals.py            # live run
    python scripts/import_blog_signals.py --dry-run  # count only
    python scripts/import_blog_signals.py --fuzzy-threshold 85  # adjust fuzzy cutoff

Signal values by source tier:
    bon_appetit_hot_10   → 0.90  (ranking)
    ny_times_100         → 0.85  (ranking)
    ny_times_best        → 0.85  (ranking)
    infatuation_guide    → 0.80  (ranking)
    infatuation_review   → 0.65  (discovery)
    eater_38             → 0.70  (ranking)
    eater_heatmap        → 0.60  (discovery)
    eater_best           → 0.65  (discovery)
    grub_street_99       → 0.75  (ranking)
    grub_street_best     → 0.65  (discovery)
    la_times_101         → 0.80  (ranking)
    sf_chronicle_top100  → 0.80  (ranking)
    serious_eats         → 0.60  (discovery)
    thrillist_best       → 0.55  (discovery)
    local_blog           → 0.50  (discovery)
    blog_warning         → 0.40  (risk)
"""
from __future__ import annotations
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.db.models.city import city_uuid
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

BLOG_SOURCE_VALUES = {
    "bon_appetit_hot_10":   0.90,
    "ny_times_100":         0.85,
    "ny_times_best":        0.85,
    "infatuation_guide":    0.80,
    "infatuation_review":   0.65,
    "eater_38":             0.70,
    "eater_heatmap":        0.60,
    "eater_best":           0.65,
    "grub_street_99":       0.75,
    "grub_street_best":     0.65,
    "la_times_101":         0.80,
    "sf_chronicle_top100":  0.80,
    "serious_eats":         0.60,
    "thrillist_best":       0.55,
    "local_blog":           0.50,
    "blog_warning":         0.40,
}

PROVIDER_MAP = {
    "bon_appetit_hot_10":   "bonappetit",
    "ny_times_100":         "nytimes",
    "ny_times_best":        "nytimes",
    "infatuation_guide":    "theinfatuation",
    "infatuation_review":   "theinfatuation",
    "eater_38":             "eater",
    "eater_heatmap":        "eater",
    "eater_best":           "eater",
    "grub_street_99":       "grubstreet",
    "grub_street_best":     "grubstreet",
    "la_times_101":         "latimes",
    "sf_chronicle_top100":  "sfchronicle",
    "serious_eats":         "seriouseats",
    "thrillist_best":       "thrillist",
    "local_blog":           "local",
    "blog_warning":         "editorial",
}

BLOG_ENTRIES = [
    # ─── OAKLAND ───────────────────────────────────────────────────────────────
    # Bon Appétit
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "bon_appetit_hot_10",  "year": 2022, "blog_type": "verified"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "bon_appetit_hot_10",  "year": 2023, "blog_type": "verified"},
    {"place_name": "FOB Kitchen",                 "city_id": "oakland", "source_type": "bon_appetit_hot_10",  "year": 2022, "blog_type": "verified"},
    {"place_name": "Hawking Bird",                "city_id": "oakland", "source_type": "bon_appetit_hot_10",  "year": 2023, "blog_type": "verified"},
    {"place_name": "Wahpepah's Kitchen",          "city_id": "oakland", "source_type": "bon_appetit_hot_10",  "year": 2022, "blog_type": "verified"},
    # NY Times
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "ny_times_best",       "year": 2023, "blog_type": "verified"},
    {"place_name": "Sobre Mesa",                  "city_id": "oakland", "source_type": "ny_times_best",       "year": 2023, "blog_type": "verified"},
    {"place_name": "Commis",                      "city_id": "oakland", "source_type": "ny_times_100",        "year": 2022, "blog_type": "verified"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "ny_times_best",       "year": 2023, "blog_type": "verified"},
    {"place_name": "Cholita Linda",               "city_id": "oakland", "source_type": "ny_times_best",       "year": 2023, "blog_type": "verified"},
    {"place_name": "Ramen Shop",                  "city_id": "oakland", "source_type": "ny_times_100",        "year": 2022, "blog_type": "verified"},
    {"place_name": "Wahpepah's Kitchen",          "city_id": "oakland", "source_type": "ny_times_best",       "year": 2022, "blog_type": "verified"},
    # Infatuation — Oakland
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Sobre Mesa",                  "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2023, "blog_type": "verified"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Cholita Linda",               "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "FOB Kitchen",                 "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Hawking Bird",                "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Commis",                      "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Ramen Shop",                  "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Belotti",                     "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Kiraku",                      "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Calavera",                    "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Boichik Bagels",              "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Tacos Oscar",                 "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "alaMar Dominican Kitchen and Bar","city_id":"oakland","source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Kingston 11 Cuisine",         "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2023, "blog_type": "verified"},
    {"place_name": "Soba Ichi",                   "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Homeroom",                    "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Vientian Cafe",               "city_id": "oakland", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Phnom Penh",                  "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Drexl",                       "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Xolo Taqueria",               "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Itani Ramen",                 "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Marufuku Ramen",              "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Breads of India",             "city_id": "oakland", "source_type": "infatuation_review",  "year": 2024, "blog_type": "neutral"},
    {"place_name": "Great China",                 "city_id": "oakland", "source_type": "infatuation_review",  "year": 2023, "blog_type": "neutral"},
    # Eater Oakland — blog features (distinct from award signals)
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Sobre Mesa",                  "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "FOB Kitchen",                 "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Cholita Linda",               "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Ramen Shop",                  "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "alaMar Dominican Kitchen and Bar","city_id":"oakland","source_type": "eater_38",           "year": 2024, "blog_type": "verified"},
    {"place_name": "Kingston 11 Cuisine",         "city_id": "oakland", "source_type": "eater_38",            "year": 2023, "blog_type": "verified"},
    {"place_name": "Wahpepah's Kitchen",          "city_id": "oakland", "source_type": "eater_38",            "year": 2023, "blog_type": "verified"},
    {"place_name": "Boichik Bagels",              "city_id": "oakland", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Tacos Oscar",                 "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Hawking Bird",                "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Belotti",                     "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Kiraku",                      "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Oori",                        "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Marufuku Ramen",              "city_id": "oakland", "source_type": "eater_heatmap",       "year": 2024, "blog_type": "neutral"},
    {"place_name": "Calavera",                    "city_id": "oakland", "source_type": "eater_best",          "year": 2024, "blog_type": "neutral"},
    {"place_name": "Homeroom",                    "city_id": "oakland", "source_type": "eater_best",          "year": 2024, "blog_type": "neutral"},
    {"place_name": "Soba Ichi",                   "city_id": "oakland", "source_type": "eater_best",          "year": 2024, "blog_type": "neutral"},
    {"place_name": "Vientian Cafe",               "city_id": "oakland", "source_type": "eater_best",          "year": 2024, "blog_type": "neutral"},
    {"place_name": "Itani Ramen",                 "city_id": "oakland", "source_type": "eater_best",          "year": 2024, "blog_type": "neutral"},
    # Grub Street — Oakland
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "grub_street_best",    "year": 2023, "blog_type": "neutral"},
    {"place_name": "Commis",                      "city_id": "oakland", "source_type": "grub_street_best",    "year": 2023, "blog_type": "neutral"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "grub_street_best",    "year": 2023, "blog_type": "neutral"},
    {"place_name": "Ramen Shop",                  "city_id": "oakland", "source_type": "grub_street_best",    "year": 2022, "blog_type": "neutral"},
    # Serious Eats — Oakland
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "serious_eats",        "year": 2022, "blog_type": "neutral"},
    {"place_name": "Shan Dong Restaurant",        "city_id": "oakland", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    {"place_name": "Phnom Penh",                  "city_id": "oakland", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    {"place_name": "Breads of India",             "city_id": "oakland", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    {"place_name": "Fentons Creamery",            "city_id": "oakland", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    {"place_name": "Bakesale Betty's",            "city_id": "oakland", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    # Thrillist — Oakland
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "thrillist_best",      "year": 2023, "blog_type": "neutral"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "thrillist_best",      "year": 2023, "blog_type": "neutral"},
    {"place_name": "Calavera",                    "city_id": "oakland", "source_type": "thrillist_best",      "year": 2023, "blog_type": "neutral"},
    {"place_name": "Hawking Bird",                "city_id": "oakland", "source_type": "thrillist_best",      "year": 2023, "blog_type": "neutral"},
    # SF Chronicle Top 100 — Oakland
    {"place_name": "Commis",                      "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Horn Barbecue",               "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Pizzaiolo",                   "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Sobre Mesa",                  "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Soba Ichi",                   "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Tacos Oscar",                 "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "FOB Kitchen",                 "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Ramen Shop",                  "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Wahpepah's Kitchen",          "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Cholita Linda",               "city_id": "oakland", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},

    # ─── BERKELEY ──────────────────────────────────────────────────────────────
    # Bon Appétit — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "bon_appetit_hot_10", "year": 2023, "blog_type": "verified"},
    {"place_name": "Gather",                      "city_id": "berkeley", "source_type": "bon_appetit_hot_10", "year": 2022, "blog_type": "verified"},
    {"place_name": "Cheeseboard Pizza",           "city_id": "berkeley", "source_type": "bon_appetit_hot_10", "year": 2022, "blog_type": "verified"},
    # NY Times — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "ny_times_100",       "year": 2023, "blog_type": "verified"},
    {"place_name": "Gather",                      "city_id": "berkeley", "source_type": "ny_times_best",      "year": 2023, "blog_type": "verified"},
    {"place_name": "Revival Kitchen",             "city_id": "berkeley", "source_type": "ny_times_best",      "year": 2022, "blog_type": "verified"},
    {"place_name": "Great China",                 "city_id": "berkeley", "source_type": "ny_times_100",       "year": 2022, "blog_type": "verified"},
    {"place_name": "Angeline's Louisiana Kitchen","city_id": "berkeley", "source_type": "ny_times_best",      "year": 2022, "blog_type": "verified"},
    # Infatuation — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Comal",                       "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Gather",                      "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Revival Kitchen",             "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Ippuku",                      "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Kirala",                      "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Cheeseboard Pizza",           "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Great China",                 "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Tacubaya",                    "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "Agrodolce",                   "city_id": "berkeley", "source_type": "infatuation_guide",  "year": 2024, "blog_type": "verified"},
    {"place_name": "La Marcha",                   "city_id": "berkeley", "source_type": "infatuation_review", "year": 2024, "blog_type": "neutral"},
    {"place_name": "Saul's Deli",                 "city_id": "berkeley", "source_type": "infatuation_review", "year": 2024, "blog_type": "neutral"},
    {"place_name": "Jupiter",                     "city_id": "berkeley", "source_type": "infatuation_review", "year": 2024, "blog_type": "neutral"},
    {"place_name": "Cafe Raj",                    "city_id": "berkeley", "source_type": "infatuation_review", "year": 2024, "blog_type": "neutral"},
    # Eater — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "eater_38",           "year": 2024, "blog_type": "verified"},
    {"place_name": "Comal",                       "city_id": "berkeley", "source_type": "eater_best",         "year": 2023, "blog_type": "neutral"},
    {"place_name": "La Marcha",                   "city_id": "berkeley", "source_type": "eater_best",         "year": 2024, "blog_type": "neutral"},
    {"place_name": "Zut!",                        "city_id": "berkeley", "source_type": "eater_best",         "year": 2024, "blog_type": "neutral"},
    {"place_name": "Cheeseboard Pizza",           "city_id": "berkeley", "source_type": "eater_38",           "year": 2024, "blog_type": "verified"},
    {"place_name": "Gather",                      "city_id": "berkeley", "source_type": "eater_38",           "year": 2024, "blog_type": "verified"},
    {"place_name": "Revival Kitchen",             "city_id": "berkeley", "source_type": "eater_best",         "year": 2024, "blog_type": "neutral"},
    {"place_name": "Great China",                 "city_id": "berkeley", "source_type": "eater_best",         "year": 2024, "blog_type": "neutral"},
    {"place_name": "Angeline's Louisiana Kitchen","city_id": "berkeley", "source_type": "eater_38",           "year": 2023, "blog_type": "verified"},
    {"place_name": "Tacubaya",                    "city_id": "berkeley", "source_type": "eater_heatmap",      "year": 2024, "blog_type": "neutral"},
    {"place_name": "Ippuku",                      "city_id": "berkeley", "source_type": "eater_heatmap",      "year": 2024, "blog_type": "neutral"},
    # Serious Eats / Thrillist — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "serious_eats",       "year": 2023, "blog_type": "neutral"},
    {"place_name": "Cheeseboard Pizza",           "city_id": "berkeley", "source_type": "serious_eats",       "year": 2023, "blog_type": "neutral"},
    {"place_name": "Great China",                 "city_id": "berkeley", "source_type": "serious_eats",       "year": 2023, "blog_type": "neutral"},
    # SF Chronicle Top 100 — Berkeley
    {"place_name": "Chez Panisse",                "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},
    {"place_name": "Comal",                       "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},
    {"place_name": "Gather",                      "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},
    {"place_name": "Revival Kitchen",             "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},
    {"place_name": "Great China",                 "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},
    {"place_name": "Cheeseboard Pizza",           "city_id": "berkeley", "source_type": "sf_chronicle_top100","year": 2024, "blog_type": "verified"},

    # ─── SAN FRANCISCO ─────────────────────────────────────────────────────────
    # SF only has 1 place in DB (Panda Express) — keeping these entries for
    # when SF gets populated; they will remain unmatched for now but are real picks.
    {"place_name": "Atelier Crenn",               "city_id": "san-francisco", "source_type": "bon_appetit_hot_10",  "year": 2023, "blog_type": "verified"},
    {"place_name": "Quince",                      "city_id": "san-francisco", "source_type": "ny_times_100",        "year": 2023, "blog_type": "verified"},
    {"place_name": "Mister Jiu's",                "city_id": "san-francisco", "source_type": "bon_appetit_hot_10",  "year": 2022, "blog_type": "verified"},
    {"place_name": "Mister Jiu's",                "city_id": "san-francisco", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Mister Jiu's",                "city_id": "san-francisco", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Nopa",                        "city_id": "san-francisco", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Nopa",                        "city_id": "san-francisco", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Tartine Manufactory",         "city_id": "san-francisco", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Tartine Manufactory",         "city_id": "san-francisco", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Rich Table",                  "city_id": "san-francisco", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Rich Table",                  "city_id": "san-francisco", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "Zuni Café",                   "city_id": "san-francisco", "source_type": "ny_times_100",        "year": 2022, "blog_type": "verified"},
    {"place_name": "Zuni Café",                   "city_id": "san-francisco", "source_type": "infatuation_guide",   "year": 2024, "blog_type": "verified"},
    {"place_name": "State Bird Provisions",       "city_id": "san-francisco", "source_type": "bon_appetit_hot_10",  "year": 2022, "blog_type": "verified"},
    {"place_name": "State Bird Provisions",       "city_id": "san-francisco", "source_type": "eater_38",            "year": 2024, "blog_type": "verified"},
    {"place_name": "Atelier Crenn",               "city_id": "san-francisco", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Nopa",                        "city_id": "san-francisco", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Rich Table",                  "city_id": "san-francisco", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Zuni Café",                   "city_id": "san-francisco", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Tartine Manufactory",         "city_id": "san-francisco", "source_type": "sf_chronicle_top100", "year": 2024, "blog_type": "verified"},
    {"place_name": "Burma Superstar",             "city_id": "san-francisco", "source_type": "serious_eats",        "year": 2023, "blog_type": "neutral"},
    {"place_name": "Burma Superstar",             "city_id": "san-francisco", "source_type": "thrillist_best",      "year": 2023, "blog_type": "neutral"},

    # ─── WARNING SIGNALS (inconsistency / decline notes) ────────────────────
    # signal_class="risk" — penalize overhyped or inconsistent places
    {"place_name": "Burma Superstar",             "city_id": "san-francisco",  "source_type": "blog_warning", "blog_type": "warning", "year": 2023},
    {"place_name": "Tartine Manufactory",         "city_id": "san-francisco",  "source_type": "blog_warning", "blog_type": "warning", "year": 2024},
]


def _signal_class(entry: dict) -> str:
    """Derive routing class from entry's blog_type and source_type."""
    blog_type = entry.get("blog_type", "neutral")
    if blog_type == "warning":
        return "risk"
    source_type = entry["source_type"]
    if source_type in {
        "bon_appetit_hot_10", "ny_times_100", "ny_times_best",
        "infatuation_guide", "eater_38", "grub_street_99",
        "la_times_101", "sf_chronicle_top100",
    }:
        return "ranking"
    return "discovery"


def _load_place_map(db):
    rows = db.execute(select(Place.id, Place.name, Place.city_id).where(Place.is_active.is_(True))).fetchall()
    return {(row.city_id, row.name.strip().lower()): row.id for row in rows}


def _external_event_id(entry: dict) -> str:
    safe_name = entry["place_name"].lower().replace(" ", "_")[:40]
    return f"blog_{entry['source_type']}_{safe_name}_{entry['year']}"


def run(dry_run=False, fuzzy_threshold=88):
    db = SessionLocal()
    place_map = _load_place_map(db)
    matched, fuzzy_candidates, unmatched = [], [], []

    for entry in BLOG_ENTRIES:
        city_id = city_uuid(entry["city_id"])
        name_lower = entry["place_name"].strip().lower()
        key = (city_id, name_lower)
        if key in place_map:
            matched.append((place_map[key], entry))
            continue
        if HAS_RAPIDFUZZ:
            best_score, best_key = 0, None
            for (cid, nlower), pid in place_map.items():
                if cid != city_id:
                    continue
                score = fuzz.ratio(name_lower, nlower)
                if score > best_score:
                    best_score, best_key = score, (cid, nlower)
            if best_score >= fuzzy_threshold and best_key:
                fuzzy_candidates.append({
                    "entry": entry,
                    "matched_name": best_key[1],
                    "score": best_score,
                    "place_id": place_map[best_key],
                })
                continue
        unmatched.append(entry)

    print(f"Matched: {len(matched)} | Fuzzy candidates: {len(fuzzy_candidates)} | Unmatched: {len(unmatched)}")

    if fuzzy_candidates:
        print("\nFuzzy matches (review before promoting):")
        for fc in fuzzy_candidates:
            print(f"  [{fc['score']}] \"{fc['entry']['place_name']}\" → \"{fc['matched_name']}\" ({fc['entry']['city_id']})")

    if unmatched:
        print("\nUnmatched entries (no place found):")
        for u in unmatched:
            print(f"  \"{u['place_name']}\" in {u['city_id']} ({u['source_type']} {u['year']})")

    if dry_run:
        print("\nDRY RUN — no writes")
        db.close()
        return

    inserted, skipped = 0, 0
    try:
        for place_id, entry in matched:
            value = BLOG_SOURCE_VALUES.get(entry["source_type"], 0.5)
            provider = PROVIDER_MAP.get(entry["source_type"], "editorial")
            sig_class = _signal_class(entry)
            ext_id = _external_event_id(entry)
            existing = db.execute(
                select(PlaceSignal.id).where(
                    PlaceSignal.place_id == place_id,
                    PlaceSignal.provider == provider,
                    PlaceSignal.signal_type == "blog",
                    PlaceSignal.external_event_id == ext_id,
                )
            ).first()
            if existing:
                skipped += 1
                continue
            db.add(PlaceSignal(
                place_id=place_id,
                provider=provider,
                signal_type="blog",
                value=value,
                raw_value=f"{entry['source_type']}:{entry['year']}:{entry.get('blog_type', 'neutral')}",
                external_event_id=ext_id,
                signal_class=sig_class,
            ))
            inserted += 1

        db.commit()
    finally:
        db.close()

    print(f"\nInserted {inserted} blog signals ({skipped} already existed)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fuzzy-threshold", type=int, default=88)
    args = parser.parse_args()
    run(dry_run=args.dry_run, fuzzy_threshold=args.fuzzy_threshold)
