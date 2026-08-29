# Multi-inventory expansion — read before touching purchases, billing, inventory, or rates

We are building a second product on top of this existing trading ERP: a
manufacturing costing system per `docs/client_requirements.md` (Raw
Material → WIP → Finished Goods, with a production/recipe engine and a
costing layer on top). This is a live, multi-session design-in-progress —
not yet implemented beyond the Raw Material layer. See
`docs/manufacturing-costing-notes.md` for the running decision log.

## The rule this file exists to state

**Do not make incremental, piecemeal changes to `purchases`, `billing`,
`inventory`, or `rates` for this initiative until the full WIP/Finished
Goods design is settled.** The eventual shape (separate WIP/FG product +
inventory models, a cross-stage registry, recipes, billing eventually
selling Finished Goods instead of/alongside Raw Material) touches several
of these apps at once. Landing partial changes to one app now, then more
later, then reworking earlier pieces once the full picture is clear, is
exactly the rework this file exists to prevent.

**Until that design is finalized and explicitly approved for
implementation: keep the currently-working apps (`purchases`, `billing`,
`inventory`, `rates`, and everything else already built) stable and
polished.** Bug fixes, performance work, and unrelated feature requests in
these apps are fine and expected — normal work continues. What's paused is
*speculative* multi-inventory-shaped changes landing ahead of the
finalized design.

## Confirmed direction so far (decisions made across design discussion, not yet built)

- **RM, WIP, and FG are structurally separate** — three independent
  product catalogs and three independent inventory trackers, not one
  shared `Product`/`Inventory` table with a stage label. `purchases.Product`
  + `inventory.Inventory` (today's implementation) **is** the Raw Material
  layer — nothing wrong with it, it just doesn't yet have WIP/FG
  counterparts.
- A `family`/`Category`-style label field on a shared `Product` table was
  tried and explicitly reverted twice this session — the separation needs
  to be structural (different models), not a field. Don't reintroduce it.
- WIP and FG will each define their **own** attribute lookups when built —
  they do NOT reuse `purchases`' `CoreLength`/`CoreThickness`/etc. lookups,
  even though those were originally discussed in a RM context. Those six
  lookups (`JumboName`, `JumboBinding`, `CoreLength`, `CoreThickness`,
  `PackingSize`, `CartonSize`) stay standalone and RM-scoped.
- A future **registry model** will index all three stages for cross-stage
  reporting (the client doc's Factory report and reconciliation
  requirements need RM/WIP/FG side by side) — modeled on this codebase's
  existing `cash_flow.CashMovement` event-table pattern, but using real FK
  columns (one nullable FK per stage's product table, exactly one set per
  row) rather than `CashMovement`'s `source_model`/`source_id` string pair,
  since the registry only ever needs to reference a closed set of exactly
  three tables, not an open-ended one.
- Frontend: Inventory and Products will become grouped nav sections
  (Raw Material / WIP / Finished Goods sub-pages under each), mirroring
  how other multi-page domains in this app are already grouped. A new
  "Factory Overview"-style page will read from the registry once it exists.
- `purchases.services.create_product()` will need to write the matching
  registry row in the same transaction once the registry model exists —
  the seed command (`seed_fixed_products.py`) doesn't need its own change
  for this, since it only ever calls `create_product()`.

None of the above is built yet. This file records the decisions so a
future session (or a context-compacted continuation of this one) doesn't
have to re-derive them or, worse, re-litigate a design question that's
already been settled.
