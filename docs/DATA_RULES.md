# DATA_RULES

**Responsibility:** Validation and normalization rules for menu items and place data written to DB.

---

## Menu Item Rules

### Required Fields

| Field | Type | Rule |
|-------|------|------|
| `name` | str | Non-empty after strip; min length 2 |
| `price_cents` | int or NULL | Always integer cents — never raw price string |
| `fingerprint` | str | SHA-based hash of (name, section, price_cents) — must be non-null |
| `section` | str | Defaults to "Other" if not provided |

### Name Validation

- Strip whitespace
- Reject if empty or length < 2
- Reject LOW_SIGNAL_NAMES: `menu, home, contact, order, about, login, signup, register, checkout, cart`
- Reject NON_MENU_EXACT_NAMES: `napkins, spoons, forks, knives, plates, straws, utensils`
- Reject names matching patterns: `packet, sauce packet, extra napkins, cutlery, utensil(s)`

### Price Validation

- Store as `price_cents` (integer, in cents)
- `NULL` is valid (many places have no prices)
- Never store as float or string
- Conversion: `$12.99` → `1299`

### Duplicate Prevention

- Fingerprint dedup within a single write batch (in-memory `seen_fingerprints` set)
- DB unique constraint: `(place_id, fingerprint)`
- Batch-level dedup runs before insert

### Minimum Quality Gate

Reject entire menu if:
- `distinct_names < 2` (MIN_VALID_ITEMS)
- `len(rows) >= 4 AND priced == 0` (all items free is suspicious)
- `len(rows) >= 8 AND distinct_names <= 2` (near-duplicate flood)
- `len(rows) >= 10 AND priced <= 1 AND meaningful_descriptions == 0`

---

## Section Normalization

Canonical section names (input → canonical):

```
appetizer/appetizers/starter/starters → Appetizers
breakfast/desayuno → Breakfast
burgers → Burgers
pizza/pizzas → Pizza
wings → Wings
sandwich/sandwiches → Sandwiches
fries/sides → Sides
dessert/desserts → Desserts
drinks/beverages → Drinks
```

---

## Item Limits

| Limit | Value |
|-------|-------|
| MAX_ITEMS total per place | 2000 |
| MAX_ITEMS per source | 1500 |
| MIN_CANONICAL_ITEM_COUNT to write | 2 |

---

## Image Rules (from Phase 3)

- All images → `content_type` (never NULL)
- All images → `quality_score` (never NULL)
- Visibility: `hidden` / `gallery_only` / `candidate_primary` / `showcase`
- One primary per place (enforced by `place_image_invariant_service`)
- Hidden images never shown in API responses
- Ordering: `rowid ASC` (= Google quality rank order) — NEVER use UUID or created_at

---

## Place Field Rules

- `has_menu`: set `true` only when `menu_items count > 0` for that place
- `menu_source_url`: max 1024 chars
- Price tier (`price_tier`): NULL if not detected — do not fabricate
- No placeholder images — return `null` when image unavailable
