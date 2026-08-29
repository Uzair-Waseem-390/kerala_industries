# Manufacturing Costing Extension — Working Notes

Running context for extending the AlphaPK trading ERP to meet
`docs/client_requirements.md`. Not a hard-constraint file — just
memory across sessions. Keep this short; expand only with load-bearing facts.
See `instructions/multi-inventory-expansion.md` for the hard rule this
informs: no piecemeal changes to purchases/billing/inventory/rates for this
initiative until the full design below is finalized.

## Direction (confirmed 2026-08-18)

Extend this existing codebase (don't rebuild). Reuse `purchases`/`billing`/
`cash_flow`/`ledger` where domains overlap (raw material buys, FG sales,
cash movement); build new apps for production/recipes/WIP/costing, which
don't exist yet. Owner isn't 100% sure of final scope either —
`client_requirements.md` is the working spec; flag divergence, don't
silently reinterpret it.

## The gap

Existing ERP = trading business (buy/resell flat SKUs, FIFO-costed). Client
needs a manufacturer: Raw Material → WIP → Finished Goods, multi-stage
production (jumbo → cores → cut pieces → packing), estimated vs actual
costing, batch DM/DL/FOH, COGM/COGS, reconciliation. From-scratch
extension. Today, only the Raw Material layer exists
(`purchases.Product` + `inventory.Inventory`) — WIP and Finished Goods are
fully unbuilt.

## Multi-inventory architecture — decided, not yet built (2026-08-29)

- **RM/WIP/FG are structurally separate** — three independent product
  catalogs + three independent inventory trackers, not one shared
  `Product`/`Inventory` table with a stage label. Tried a `Family` FK
  field on a shared `Product` table twice this session; reverted both
  times. The separation must be structural (different models), because
  WIP/FG items are genuinely different things with different attributes
  (a rewound core isn't "an RM core with a label"), not variants of the
  same row.
- `purchases.Product` + `inventory.Inventory` **is** the Raw Material
  layer, already correct as-is. No `family`/`category` field needed on it.
- WIP and FG will each define their **own** attribute lookups when built.
  They do NOT reuse the six RM lookups already built
  (`JumboName`/`JumboBinding`/`CoreLength`/`CoreThickness`/`PackingSize`/
  `CartonSize`) — those stay RM-scoped, standalone, unwired to anything.
- **Future registry model** (not built) will index all three stages for
  cross-stage reporting — client doc's Factory report (#10) and
  reconciliation (#9) need RM/WIP/FG side by side. Modeled on
  `cash_flow.CashMovement`'s event-table pattern, but with real FK columns
  (one nullable FK per stage's product table, exactly one set per row)
  instead of `CashMovement`'s `source_model`/`source_id` string pair —
  the registry only ever needs a closed set of 3 possible targets, so a
  real FK gives referential integrity `CashMovement`'s pattern can't.
  `purchases.services.create_product()` will need to write the matching
  registry row in the same transaction once this exists (the seed command
  doesn't need its own change — it only calls `create_product()`).
- Frontend: Inventory and Products become grouped nav sections (RM/WIP/FG
  sub-pages each), mirroring other multi-page domains already in this app.
  A future "Factory Overview" page reads from the registry.

## Today's cost mechanism (must integrate with, not replace)

- Cost is **per-purchase-line FIFO**, not averaged: `PurchaseItem.remaining_quantity`
  is the live FIFO layer, oldest-confirmed-order-first. Unit cost =
  `total_price / quantity` (tax-inclusive).
- Physical shelf location (`ShelfStock`) and cost-FIFO (`PurchaseItem`) are
  two independent systems draining the same quantities — not cross-checked.
- Sale confirm (`billing.confirm_invoice` → `_run_fifo`) snapshots COGS onto
  `InvoiceItem`/`Invoice` at that moment; most reports read those stored
  snapshots. Exception: Inventory Valuation report re-walks live FIFO layers.
- `ProductRate` is selling price only, decoupled from cost.
- New finished-goods products from production still need to be ordinary
  sellable somethings with their own cost layer, so they can flow through
  a `billing`-like sale path — exact mechanism (does billing sell FG
  products directly, or does FG need its own sale path?) still open.

## Cross-app dependents to remember for later inventory work

- `profits` app (`profits/services.py`, `profits/models.py`) imports
  `LostInventoryRecord`/`LostInventoryRecovery` directly from
  `purchases.models` for monthly profit calc. Lost Inventory stays in
  `purchases` today — if it ever moves as part of multi-inventory work,
  `profits` is a dependent that must be updated too.

## Open questions

- FOH allocation basis — client says "to be finalized later."
- FG products track multiple units simultaneously (Yard/Pieces/Cartons per
  client doc) — implies a UoM conversion (e.g. 1 carton = 180 pieces) not
  yet designed. Deferred until FG inventory is actually built.
- How many distinct FG product lines exist, what distinguishes one from
  another — needs the owner's real product catalog, not guessable from
  the client doc.
- Does "Cut Pieces" (WIP) vary by cut size only, or also by which source
  Rewound Core it came from?
- Does `billing` need to change to sell FG products instead of/alongside
  RM products once FG exists? Not resolved.
- Phase boundary (per client spec): Phase 1 = inventory flow + recipes +
  WIP/FG movement + COGM/COGS + estimated costing. Phase 2 = batch DL/FOH +
  actual per-piece costing + reconciliation + production planning reports.

## Done

- `inventory` app extracted out of `purchases` (mechanical move, state-only
  migration, verified — see git history).
- `purchases.Category` removed entirely (real DROP TABLE) — replaced by
  6 RM-scoped attribute lookups (`JumboName`, `JumboBinding`, `CoreLength`,
  `CoreThickness`, `PackingSize`, `CartonSize`), full CRUD, admin-only.
- `purchases.Product` frozen to exactly 4 fixed rows (Jumbo, Cores,
  Packing, Cartons — codes `PRO-1000`–`PRO-1003`), seeded by
  `seed_fixed_products` management command. No create/edit/delete API.
