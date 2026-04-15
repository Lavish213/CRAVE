"""
Migrate SQLite data to PostgreSQL.
Handles boolean columns (0/1 → false/true) and NULL edge cases.
"""
import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "app.db")
PG_URL = os.environ.get("DATABASE_URL", "")

# Boolean columns per table
BOOL_COLS = {
    "cities": {"is_active"},
    "places": {"is_active", "has_menu", "needs_recompute", "image_blocked"},
    "categories": {"is_active"},
    "enrichment_jobs": {"is_active", "is_completed", "has_error"},
    "place_truths": {"is_verified"},
    "place_feed_snapshots": {"is_active"},
    "hitlist_saves": set(),
    "hitlist_suggestions": {"is_resolved", "is_dismissed"},
    "hitlist_dedup_keys": set(),
    "place_signals": set(),
    "place_images": {"is_primary", "is_active"},
    "place_claims": {"is_verified_source", "is_user_submitted"},
    "menu_sources": {"is_active"},
    "menu_snapshots": {"is_current"},
    "menu_items": {"is_available"},
    "discovery_candidates": {"resolved", "blocked"},
    "city_place_rankings": set(),
    "place_categories": set(),
    "place_image_fetch_logs": set(),
    "crave_items": set(),
}

# Migration order (respects FK deps)
TABLE_ORDER = [
    "cities",
    "categories",
    "places",
    "place_categories",
    "city_place_rankings",
    "place_signals",
    "place_truths",
    "place_images",
    "place_image_fetch_logs",
    "place_claims",
    "place_feed_snapshots",
    "menu_sources",
    "menu_snapshots",
    "menu_items",
    "enrichment_jobs",
    "discovery_candidates",
    "hitlist_saves",
    "hitlist_suggestions",
    "hitlist_dedup_keys",
    "crave_items",
]


def convert_row(row: dict, bool_cols: set) -> dict:
    for col in bool_cols:
        if col in row and row[col] is not None:
            row[col] = bool(row[col])
    return row


def migrate_table(sqlite_cur, pg_cur, table: str):
    bool_cols = BOOL_COLS.get(table, set())

    sqlite_cur.execute(f"SELECT * FROM {table}")
    rows = sqlite_cur.fetchall()
    if not rows:
        print(f"  {table}: 0 rows (skip)")
        return

    cols = [d[0] for d in sqlite_cur.description]
    converted = [convert_row(dict(zip(cols, row)), bool_cols) for row in rows]

    placeholders = ", ".join([f"%({c})s" for c in cols])
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    psycopg2.extras.execute_batch(pg_cur, sql, converted, page_size=500)
    print(f"  {table}: {len(converted)} rows")


def main():
    if not PG_URL:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(PG_URL)
    pg_cur = pg_conn.cursor()

    print(f"Migrating {SQLITE_PATH} → PostgreSQL\n")

    # Widen place_images.url to accommodate longer Google URLs
    pg_cur.execute("ALTER TABLE place_images ALTER COLUMN url TYPE VARCHAR(1024)")
    pg_conn.commit()
    print("  Widened place_images.url to VARCHAR(1024)\n")

    for table in TABLE_ORDER:
        try:
            migrate_table(sqlite_cur, pg_cur, table)
            pg_conn.commit()
        except Exception as e:
            pg_conn.rollback()
            print(f"  ERROR on {table}: {e}")

    sqlite_conn.close()
    pg_conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
