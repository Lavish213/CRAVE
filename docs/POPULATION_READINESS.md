# CRAVE population readiness

**Status:** prepared for a one-city canary after this change is reviewed,
merged, migrated, and deployed. This is not authorization for a global import.

The first production canary was staged as blocked/unresolved rows on
2026-08-30 and is intentionally on hold pending entity/current-existence
review. See `docs/POPULATION_CANARY_2026-08-30.md` for measurements, findings,
and the exact rollback.

## Verified production baseline (2026-08-29/30)

Read-only Railway queries produced this baseline:

| Surface | Current coverage |
| --- | --- |
| Places | 35,289 total; 34,934 active |
| Required identity | 0 active places missing name or coordinates |
| Address | 13,797 / 34,934 active places (39.5%) |
| Website | 13,162 / 34,934 (37.7%) |
| Category | 31,158 / 34,934 (89.2%) |
| Price tier | 0 / 34,934; do not invent this field |
| Places flagged with a menu | 937 / 34,934 (2.7%) |
| Published menu items | 57,669 active; 1,153 lack price and 18,555 lack description |
| Menu item images/providers | 0 before this branch; provenance was dropped during materialization |
| Public place images | 14,288 / 34,934 places (40.9%) have at least one |
| Discovery queue | 38,191 candidates; 37,089 promoted; 1,102 below the confidence gate |
| Overture candidates | 0 before this branch |

Menu extraction is producing snapshots but not enough successful truth:
13,698 snapshots in 30 days, 811 successful and 12,887 failed. Source records are
mostly HTML (311), then Square (71), hydration JSON (39), and Toast (5).

## Confirmed blockers fixed in this branch

1. **Branch identity:** `places(city_id, name)` was unique, so two real chain
   locations with the same name in one city could not coexist. Promotion now
   uses a stable candidate-derived UUID and the database constraint is removed.
   Entity matching still decides identity from address, website, and distance.
2. **Lost menu provenance:** extraction claims carried provider, source type,
   source URL, and image URL, but materialization and publishing discarded all
   four. They now survive claims -> canonical truth -> `menu_items` -> API.
3. **False-green Overture job:** production recorded successful Overture runs
   with zero results. Release discovery used a stale S3-listing strategy and
   fetch exceptions became empty arrays. Release discovery now uses Overture's
   authoritative STAC catalog and failures are raised. A read-only 0.01-degree
   San Francisco sandbox query against release `2026-08-19.0` returned 257 food
   places.

## Canonical contract

The existing model can accept population data without a rewrite:

- `DiscoveryCandidate`: source/external ID, name, city, category hint,
  coordinates, address, phone, website, raw payload, confidence, retry state,
  corroboration, and promoted-place link.
- `Place`: canonical display/search/map identity, address, website/menu URLs,
  coordinates, categories, lifecycle, menu/image retry state, and scoring.
- `MenuSource` / `MenuSnapshot`: source URL/provider lineage, attempts, status,
  hashes, raw/normalized payloads, and failure evidence.
- `MenuItem`: name/title, section, integer cents, description, image, stable
  fingerprint, confidence, provider, source type, and source payload.
- `PlaceImage`: candidate/public/primary lifecycle, provenance, moderation,
  quality, failures, and ordering.

One old resolver (`app/services/truth/place_resolver.py`) is unused and writes
nonexistent `Place.phone` / `Place.category_id` fields. Do not connect new
imports to it; the active discovery matcher/promotion pipeline is canonical.

## Free-source order

Use sources by confidence and operating cost, not by how easy they are to
scrape:

1. **Overture Places monthly release** as the bulk catalog spine. Preserve its
   GERS ID in `DiscoveryCandidate.external_id`; use Overture bridge files when
   reconciling source IDs across releases.
2. **Municipal health, license, and permit datasets** for authoritative local
   existence/address evidence. Keep each jurisdiction as a provider adapter.
3. **OSM regional/bounding-box acquisition** for independent corroboration and
   gaps. Public Nominatim/Overpass infrastructure must remain low-rate,
   identified, cached, and incremental; never use it for an unbounded dump.
4. **AllThePlaces published weekly output** for first-party locator URLs and
   chain gaps. Consume its published data; do not rerun the entire spider fleet.
5. **Foursquare Open Source Places** only after measuring gaps not already
   covered by Overture, because Overture incorporates upstream datasets and a
   blind union creates duplicate work.
6. **Official restaurant sites for menus:** documented/observed JSON APIs first,
   JSON-LD or hydration state second, static HTML/PDF third, headless browser or
   OCR last. Every adapter must preserve provider/source URL and comply with
   robots, terms, rate limits, caching, and backoff.
7. **Images:** user uploads first; permitted official-site structured images
   next; Wikimedia Commons only with license/creator/attribution/restriction
   metadata. Do not scrape Google/Yelp imagery or hotlink unknown copyrighted
   assets.

Overture may already contain Foursquare/Meta/other contributions. The candidate
external ID and corroboration keys must be used to reconcile, not simply append,
every source.

## Safe population sequence

1. Merge/deploy the extraction observability work and this branch; run the new
   migration.
2. Run one Overture fetch in a sandbox and archive counts/errors as job evidence.
3. Run a **single-city dry run**, then a capped write canary. Record fetched,
   created, matched, rejected, duplicate-distance distribution, missing-field
   rates, and runtime.
4. Manually inspect a stratified sample: chains with multiple branches,
   independent venues, closed venues, same-name collisions, boundary venues,
   and records with conflicting addresses.
5. Re-materialize existing menu truth in batches so preserved provider/image
   data can backfill. Compare item counts/fingerprints before publishing.
6. Run image candidate scoring/classification for the 2,476 unscored images;
   never promote an image without license/provenance and moderation evidence.
7. Expand city-by-city only when duplicate, rejection, and field-quality gates
   pass. Stop automatically on source failure or anomalous zero yield.

Do not synthesize price tiers merely to fill the column. Derive them later from
city/cuisine-normalized menu price distributions, label the derivation, and keep
the underlying menu evidence.

## Required canary gates

- No database/source exception may be reported as a successful empty run.
- Same-name branches remain distinct; true duplicates converge idempotently.
- All canonical updates retain source/external ID, observation time, and raw
  evidence through the candidate/snapshot lineage.
- Closed or low-confidence records do not become active silently.
- Menu publication does not reduce active-item coverage unexpectedly.
- Image URLs are fetched/proxied only when permitted and must retain provenance.
- Production writes are capped, reversible by batch/source, and observed before
  the next city starts.

## Primary references

- Overture Places and schema: <https://docs.overturemaps.org/guides/places/>
  and <https://docs.overturemaps.org/schema/reference/places/place/>
- Overture release discovery: <https://github.com/OvertureMaps/data#release-discovery>
- Overture GERS bridge files: <https://docs.overturemaps.org/gers/bridge-files/>
- Foursquare Open Source Places: <https://docs.foursquare.com/data-products/docs/fsq-places-open-source>
- AllThePlaces data contract: <https://github.com/alltheplaces/alltheplaces/blob/master/DATA_FORMAT.md>
- Schema.org menu structures: <https://schema.org/Menu> and <https://schema.org/MenuItem>
- Nominatim policy: <https://operations.osmfoundation.org/policies/nominatim/>
- OSM tile policy: <https://operations.osmfoundation.org/policies/tiles/>
- Robots Exclusion Protocol: <https://www.rfc-editor.org/info/rfc9309/>
- Wikimedia Commons metadata: <https://www.mediawiki.org/wiki/Extension:CommonsMetadata/en>
