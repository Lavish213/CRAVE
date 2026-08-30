# Overture Oakland canary entity review — 2026-08-30

Batch: `oakland-20260830-a`

## Decision

**One new location is releasable after code review; nine candidates must not
create new places.** The batch contains one verified-current missing location,
three exact matches to existing CRAVE entities, one historical alias, and five
closed/moved/replaced records.

This document is evidence for a guarded disposition command. It is not proof
that the command has run. Until the reviewed command is applied, all ten
production candidates remain blocked, unresolved, and invisible.

## Record-level dispositions

| Candidate | Decision | Existing CRAVE reconciliation | Evidence |
| --- | --- | --- | --- |
| Forge Pizza, 66 Franklin St | Reject stale; deactivate stale canonical record | Existing `FORGE PIZZA DANVILLE LLC` at the old address | The Jack London location closed in December 2024; current Forge is at 5900 College Ave. [Official Forge](https://forgerockridge.com/) · [SF Chronicle closure report](https://www.sfchronicle.com/food/restaurants/article/the-forge-pizzeria-jack-london-20002155.php) |
| Good Vybes & Brews, 412 Madison #103 | Match existing | Exact CRAVE place 1.1 m away | Current first-party page and the Jack London district both list the exact address. [First-party page](https://goodvybesandbrews.carrd.co/) · [district listing](https://jacklondonoakland.org/go/good-vybes-and-brews) |
| Miette, 85 Webster St | Reject stale | No matching CRAVE place | Miette closed; Timeless Coffee now operates at 85 Webster. [Current ordering page](https://order.toasttab.com/online/timeless-coffee-jlsq-85-webster-street) · [2022 replacement report](https://hoodline.com/2022/08/jack-london-square-will-get-six-new-restaurants-this-year-starting-this-week/) |
| Miss Pearl's, 1 Broadway | Reject stale | No matching CRAVE place; current nearby entity is Waterfront Cafe & Bar | Miss Pearl's was sold/replaced in 2013; its successor Lungomare later closed. [Eater sale report](https://sf.eater.com/2012/11/5/6526227/miss-pearls-sold-will-be-lungomare-in-2013) · [Lungomare closure record](https://sf.eater.com/venue/11702/lungomare) |
| NIDO Kitchen & Bar, 444 Oak St | Historical alias of Odin; deactivate stale NIDO canonical record | Exact NIDO and Odin records exist at the same location | The owners state that original NIDO is now ODIN; Odin's current page lists 444 Oak. [NIDO team](https://www.nidooakland.com/team) · [ODIN history](https://www.odinoakland.com/about-2) |
| North Beach Sandwicheez, 308 Jackson #5 | **Promote as one new location** | No CRAVE place at this branch; same brand has other Oakland locations | Current first-party brand material, local district listing, and active ordering all identify this branch. [Official menu/location PDF](https://media-cdn.getbento.com/accounts/29af413457a5fc32cec9f6558923fb90/media/IT33oRxIQI84aVWTERe3_fm1m4m6QTs2iD4AbH8Nf_xyaTef0uS4GO0i6RapDK_NBSandwicheez_PrintMenu.pdf) · [district listing](https://jacklondonoakland.org/go/north-beach-sandwicheez) · [active ordering](https://www.ezcater.com/catering/north-beach-food-oakland) |
| Oakland United Beerworks, 262 2nd St | Match existing | Exact CRAVE place 6 m away | Current first-party contact page lists the address and hours. [Official contact page](https://oaklandunitedbeerworks.com/contact-us/) |
| Odin, 444 Oak St | Match existing | Exact CRAVE place 8.5 m away | Current first-party page and current reservation listing corroborate name/address. [Official site](https://www.odinoakland.com/about-2) · [Resy](https://resy.com/cities/oakland-ca/venues/odin-mexican-restaurant-bar) |
| Tiger's Taproom, 308 Jackson #4 | Reject stale; deactivate stale canonical record | Exact active CRAVE record is now stale | Owner announced a final service date of March 1, 2026; newer closure reporting overrides the stale official-hours page. [East Bay Nosh closure report](https://richmondside.org/2026/02/26/barbary-guss-world-famous-tigers-taproom-closed/) |
| World Ground Cafe, 308 Jackson St | Reject stale | No matching CRAVE place | The Jack London location closed in October 2017. [East Bay Express closure report](https://eastbayexpress.com/overland-country-bar-and-world-ground-cafe-shut-their-doors-2-1/) |

## Database reconciliation findings

- Good Vybes, Oakland United Beerworks, and Odin already have active canonical
  CRAVE places at the reviewed coordinates.
- NIDO and Odin both remain active in CRAVE even though first-party evidence
  says NIDO became Odin. The disposition links the alias to Odin and deactivates
  the stale NIDO record.
- Forge and Tiger's Taproom also have stale active CRAVE records. Rejecting only
  the canary rows would leave the app wrong, so the guarded disposition also
  deactivates those exact stale canonical IDs.
- North Beach Sandwicheez already has other Oakland branch records. The live
  entity matcher previously treated a shared brand website as location proof,
  which would merge 308 Jackson into the distant Kaiser Center branch. The
  accompanying fix requires address or spatial agreement for physical-place
  identity.

## Expected guarded-apply result

- 3 candidates resolve into existing entities.
- 1 historical alias resolves into Odin.
- 5 stale candidates become rejected.
- 1 verified-current location becomes a new Place.
- 3 stale active canonical Places become inactive (old Forge, NIDO, Tiger's).
- All ten candidate rows remain `blocked=true` as an audit barrier, even after
  they are resolved.

## Execution gate

Preview is the default:

```bash
cd backend
python3 scripts/apply_overture_entity_review.py
```

The full disposition can be exercised inside a transaction that is always
rolled back:

```bash
cd backend
python3 scripts/apply_overture_entity_review.py \
  --simulate --confirm SIMULATE_OVERTURE_ENTITY_REVIEW
```

Production application is allowed only after independent review and merge:

```bash
cd backend
python3 scripts/apply_overture_entity_review.py \
  --apply --confirm APPLY_OVERTURE_ENTITY_REVIEW
```

After application, verify the exact new Jackson Street place on Feed, Search,
Map, and Place Detail; verify the old Forge, NIDO, and Tiger's records no longer
appear; and verify the API/database/cache/worker health endpoints remain green.

## Production application record

Applied on 2026-08-30 from merged commit `5f4e81f`, after an unchanged
production preview, an exact-count transaction simulation that rolled back,
and a second unchanged preview. The guarded apply returned:

- 3 matched candidates
- 1 historical alias
- 5 rejected stale candidates
- 1 promoted new location
- 3 deactivated stale canonical places

Independent post-commit database verification found all 10 candidates resolved
and still blocked. Status counts were `matched=3`, `alias=1`, `rejected=5`, and
`promoted=1`.

The new active place is **North Beach Sandwicheez**, ID
`1ca94f55-9d2d-5f5a-84ea-5c39f88291e9`, at 308 Jackson Street, Suite 5.
The deactivated records are:

- old Forge: `1e4a547c-e3f8-52dd-99bd-2c578d4cbdd3`
- old NIDO: `5ca2b059-5eec-55d7-bf68-e713b639e3d1`
- Tiger's Taproom: `c6d7a916-0cde-508a-8074-3a85b79a70ce`

Live HTTP verification after commit:

- `/health` returned 200 with DB, cache, and worker all `ok`.
- `/api/v1/place/1ca94f55-9d2d-5f5a-84ea-5c39f88291e9` returned 200.
- exact Search returned the new place once.
- a 0.2 km Map query returned the new place once.
- all three deactivated place-detail IDs returned 404.
- the global Feed endpoint returned 200. The new zero-score place was not in
  its first ranked 100, which is expected and is not an API visibility failure.
