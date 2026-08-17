# Manufacturing Costing Extension — Working Notes

Running context for extending the AlphaPK trading ERP to meet
`docs/client_requirements.md`. Not a hard-constraint file — just
memory across sessions. Keep this short; expand only with load-bearing facts.

## Direction (confirmed 2026-08-18)

Extend this existing codebase (don't rebuild). Reuse `purchases`/`billing`/
`cash_flow`/`ledger` where domains overlap (raw material buys, FG sales,
cash movement); build new apps for production/recipes/WIP/costing, which
don't exist yet. Owner isn't 100% sure of final scope either —
`client_requirements.md` is the working spec; flag divergence, don't
silently reinterpret it.

## The gap

Existing ERP = trading business (buy/resell flat SKUs, FIFO-costed). Zero
production/BOM/WIP/manufacturing code anywhere (confirmed via full grep).
Client needs a manufacturer: Raw Material → WIP → Finished Goods,
multi-stage production (jumbo → cores → cut pieces → packing), estimated
vs actual costing, batch DM/DL/FOH, COGM/COGS, reconciliation. This is a
from-scratch extension, not a partial one.

## Today's cost mechanism (must integrate with, not replace)

- Cost is **per-purchase-line FIFO**, not averaged: `PurchaseItem.remaining_quantity`
  is the live FIFO layer, oldest-confirmed-order-first. Unit cost =
  `total_price / quantity` (tax-inclusive).
- Physical shelf location (`ShelfStock`) and cost-FIFO (`PurchaseItem`) are
  two independent systems draining the same quantities — not cross-checked.
- Sale confirm (`billing.confirm_invoice` → `_run_fifo`) snapshots COGS onto
  `InvoiceItem`/`Invoice` at that moment; most reports read those stored
  snapshots. Exception: Inventory Valuation report re-walks live FIFO layers.
- `Product` is a flat SKU today (no raw/WIP/finished type). `ProductRate`
  is selling price only, decoupled from cost.
- New finished-goods products from production still need to be ordinary
  sellable `Product`s with their own FIFO cost layer, so they flow through
  the existing `billing` sale path unchanged.

## Open questions

- FOH allocation basis — client says "to be finalized later."
- Does `Product` get a type field, or a separate model per inventory stage?
- Phase boundary (per client spec): Phase 1 = inventory flow + recipes +
  WIP/FG movement + COGM/COGS + estimated costing. Phase 2 = batch DL/FOH +
  actual per-piece costing + reconciliation + production planning reports.

## Session log

- 2026-08-18: Read `CLAUDE.md` + all of `instructions/` + `docs/client_requirements.md`
  . Mapped all 18 existing apps (mature, no stubs/TODOs).
  Confirmed direction with owner: extend, don't rebuild. Deep-dove
  purchases/billing FIFO+COGS mechanics (above). No plan drafted yet —
  owner wants context-gathering only for now.
