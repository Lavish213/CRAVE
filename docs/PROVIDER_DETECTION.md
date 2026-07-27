# PROVIDER_DETECTION

**Responsibility:** Detect which menu platform a restaurant uses from its website URL or HTML.

---

## Detection Flow

```
Place.website or Place.menu_source_url
  → detect_provider(url)              # fast: URL pattern match
  → fetch_html(url)                   # if URL match fails
    → discover_provider_urls(html)    # scan hrefs/iframes/script srcs
      → route_provider(url)           # dispatch to correct extractor
```

---

## Known Providers

| Provider | Domain pattern | Extractor |
|----------|---------------|-----------|
| Toast | `toasttab.com` | `toast_extractor.py` |
| ChowNow | `chownow.com` | `chownow_extractor.py` |
| Clover | `clover.com` | `clover_extractor.py` |
| Square | `square.site`, `squareup.com` | `square_extractor.py` |
| Popmenu | `popmenu.com` | `popmenu_extractor.py` |
| Olo | `olo.com` | generic |
| Grubhub | `grubhub.com` | `grubhub_fetcher.py` (separate path) |

---

## Website Probe (`website_provider_probe.py`)

Used by `discover_menu_sources.py` to populate `Place.menu_source_url` before extraction.

### Confidence Levels

| Signal | Confidence | Condition |
|--------|-----------|-----------|
| Redirect to provider domain | 1.0 | Final URL after redirect matches provider |
| Provider link in HTML | 0.9 | `discover_provider_urls()` finds provider href |
| JSON-LD Menu schema | 0.7 | `@type: Menu/MenuSection/MenuItem` in page |
| No signal | 0.0 | None of the above |

- Minimum confidence to save: `0.7`
- Probe paths tried: `/, /menu, /order, /order-online, /online-ordering, /food-menu`
- Skipped domains: `yelp.com, tripadvisor.com, facebook.com, instagram.com, tiktok.com`

---

## Toast Extractor Rules

- Must parse hierarchy: `menu → groups → items`
- `price` field from API → convert to `price_cents` (int, cents)
- Extract `item.imageUrl` or `item.image_url` into item image pipeline
- Never store raw price strings — always integer cents

---

## Fallback Chain

```
Provider extractor fails
  → JSON-LD extraction
  → HTML menu extraction
  → Google fallback (mark fallback_used=true)
```

Google MUST NOT be used as primary source. Only when all extractors fail.

---

## Registry

- `app/services/menu/providers/provider_registry.py` — domain → extractor mapping
- `app/services/menu/extraction/js/js_provider_router.py` — runtime dispatch
- `app/services/menu/extraction/provider/provider_detector.py` — URL detection
