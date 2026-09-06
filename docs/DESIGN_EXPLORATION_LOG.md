# CRAVE design exploration log

A living record of visual-direction decisions and constraints from
each mockup round, so a reaction to a set of concepts doesn't
disappear once the next set is generated. Append a new round below
the existing ones — never overwrite a prior round's entries. This is
part of the same documentation discipline as the release-certification
matrix: decisions live in the repo, not only in chat history.

## The product thesis (established after Round 1)

**CRAVE = appetite first, visually. Decision intelligence, underneath
it.**

Not DoorDash's catalog. Not Yelp's ratings directory. Not Tinder for
restaurants. Not a restaurant magazine. The food gets someone's
attention; CRAVE tells them *why this is the place they should
actually choose*.

This thesis is the filter every future direction gets checked against
— a concept that could describe a different app (a generic food
delivery catalog, a generic ratings directory, a dating-app clone, a
generic food magazine) has failed the check regardless of how polished
it looks.

## Round 1 (2026-09-06)

Four directions generated: **A. Food-First** (full-bleed photography,
swipe X/heart controls), **B. Decision-First** (match-% cards with
reasoning bullets, filter pills), **C. Editorial** (magazine-style,
tabbed Today/Neighborhoods/Guides/For You), **D. Utility-Dense** (dense
list, star ratings, filter chips).

### REJECT

- **D's star-rating model.** Shows 4.8/4.7/4.6-style star ratings as
  the primary signal — this directly conflicts with CRAVE's actual
  ranking mechanic and its own positioning ("no star ratings, no
  guessing what a '4' means," per `docs/STORE_METADATA_DRAFT.md`).
  Utility density itself is not rejected — a dense variant is still
  worth exploring — but it must use CRAVE-native signals (tier,
  percentile, comparative position, decision reasoning) instead of
  stars.
- **A's Tinder-style X/heart swipe interaction.** Unmistakably
  dating-app-coded, not just a stylistic borrow — a swipe-to-decide
  gesture for restaurant discovery reads as "recolored version of
  another app's core interaction," which is exactly what CRAVE's own
  uniqueness rule exists to prevent. Photography can carry emotion
  without adopting swipe-dating as the interaction model.

### PROMOTE

- **B's product hierarchy.** Decision Session (match-% cards with
  reasoning: "You love Italian," "Highly rated for pasta," "Similar to
  places you've saved") deserves testing as the Feed's **primary**
  organizing idea, not an accessory strip sitting above a conventional
  restaurant list — which is how it currently ships (see
  `docs/SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`'s Feed
  findings: a "DECIDE NOW" block above the normal tiered feed, two
  parallel entry points rather than one funnel). This isn't a new
  direction being invented — it's already the documented intent:
  `docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md` line
  58 states outright, **"Decision Session is the primary decision
  surface when data exists."** Round 1 mockups are the first visual
  test of a product decision that was already made, not a new one.

### KEEP

- **A's appetite/photography emphasis.** Full-bleed, emotional food
  photography is a real, distinctive strength worth carrying forward
  — just decoupled from the swipe-dating interaction it arrived with
  in Round 1.

### DEPRIORITIZE

- **C as the core Feed architecture.** Tabs like Today/Neighborhoods/
  Guides/For You read as a generic content/magazine app — nothing in
  this direction surfaces ranking, comparison, or the head-to-head
  decision mechanic at all, making it the least tied to what CRAVE
  actually does of the four. Editorial *techniques* (typography,
  storytelling, occasional collections/discovery modules) may still be
  useful as secondary surfaces — just not as the Feed's main engine.

### DO NOT DECIDE (from these mockups)

- **Light vs. dark theme.** Three of four Round 1 concepts (B, C, D)
  were light-mode; the shipped app is dark end-to-end by design
  (`background: #0A0A0A`, `userInterfaceStyle: "dark"` in `app.json`,
  every token in `constants/colors.ts` built dark-first). Round 1's
  concepts were exploratory and not generated with that constraint in
  mind — they are not evidence the product should switch themes.
  **Dark is the current constraint unless explicitly reopened as its
  own decision**, not something a mockup round decides by default.

## Round 2 brief (not yet generated)

Instead of four unrelated styles, Round 2 explores four **structurally
different interpretations of the same thesis**: Photography ×
Decision Intelligence × Dark CRAVE × No Stars × No Swipe-Dating UI.

Candidate structural variants (same doctrine, radically different
composition):
1. A dominant single restaurant recommendation as the hero.
2. A three-choice Decision Session (best_fit / safe_bet / wildcard —
   matching the roles the backend already produces) as the primary
   Feed surface.
3. A composition emphasizing head-to-head comparison (Rank's own
   comparison-duel mechanic surfaced earlier/more prominently, not
   just reachable via a separate flow).
4. A denser "decision queue" — utility-dense in information density,
   but using tier/percentile/reasoning instead of stars.

**The question Round 2 needs to answer**: what should CRAVE's actual
decision mechanic look and feel like when it becomes the hero of the
Feed — not just "which visual style is nicest."

## Maintenance

Append each new round below this one, in the same REJECT/PROMOTE/KEEP/
DEPRIORITIZE/DO NOT DECIDE structure where it applies. Once a
direction is locked, record that explicitly as its own dated entry
("Direction locked: ...") rather than letting it stay implicit in the
last round's PROMOTE line. This log feeds
`docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 10 (screen/UX
design certification track) once an actual polish/redesign
implementation pass begins.
