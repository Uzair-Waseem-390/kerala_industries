# COGS / Gross Profit Engine — Design Discussion (2026-09-07)

Working notes from a design conversation about how to start selling Finished
Goods through `billing` now, without waiting for full actual-cost accounting
to exist, while still ending up with exact per-invoice/per-item gross profit
once the month closes. Not yet built — this is the agreed design to build
against. See `docs/client_requirements.md` for the source spec this
elaborates (sections 4-9 especially), and `docs/manufacturing-costing-notes.md`
for the inventory/production architecture this plugs into.

## The starting question

Client's requirement (`client_requirements.md` §5): COGS is a **month-end**
figure, computed as:

```
Direct Material Used = Opening RM + Purchases + Inward Freight − Closing RM
Total Manufacturing Cost (TMC) = Direct Material Used + Direct Labor + FOH
COGM = TMC + Opening WIP − Closing WIP
COGS = COGM + Opening FG − Closing FG
```

But sales can't wait for month-end. The question this conversation worked
through: if invoices get created and confirmed *during* the month, before
COGS is known, how do we later get back to an **exact** (not estimated)
gross profit for every individual invoice and every individual item sold —
and correctly subtract gross profit again when a return happens — such that
the sum of all those per-invoice figures reconciles exactly to the month-end
COGS formula above?

## Why this can't be fully real-time — and why that's fine

Two cost components behave completely differently:

- **Direct Material (DM)** is already exact and known the instant a Packing
  batch finishes — it's built entirely from real, already-settled purchase
  costs (jumbo, cores, packing material), FIFO-drawn through Rewinding →
  Cutting → Packing. Every `PackingOutputItem.unit_cost_snapshot` today
  already **is** an exact per-piece material cost. No estimation involved,
  no waiting required.
- **Direct Labor (DL) and Factory Overhead (FOH)** are mathematically
  incapable of being known in real time, by definition of the client's own
  formula: `labor/hour = month's total actual labor cost ÷ month's total
  production hours`. That rate needs the **whole month's** aggregate data —
  it literally doesn't exist yet on, say, the 3rd of the month. Any DL/FOH
  figure attached to a sale mid-month would necessarily be an estimate, not
  a real number.

This isn't a limitation of the design — it's the same reason real
manufacturing accounting uses **standard costing with period-end true-up**.
It maps directly onto the client doc's own two-track structure: §4
"Estimated Costing" (real-time, provisional) vs §5-9 "Actual Accounting
Month End" (final, true numbers), with §9 "Critical Reconciliation" existing
specifically to catch/handle the gap between the two.

## The agreed model (simplified further during the conversation)

Original idea explored: recognize *provisional* gross profit at sale time
(DM exact + DL/FOH estimated), then true it up at month-end. **Simplified
to something cleaner**: don't compute gross profit at all during the month.
Just record transactions (invoices, returns) as they happen, and compute
exact gross profit for everything retroactively once the month's DL/FOH
rate is known. No provisional numbers, no true-up deltas to reconcile later
— just "pending" until it can be exact.

### The one non-negotiable requirement this still needs, live

Even though the **dollar** cost isn't computed during the month, the
**physical batch traceability** must be captured at the moment of sale —
which batch(es) an invoice line's quantity was actually drawn from. This
cannot be reconstructed after the fact. It costs nothing to capture (it's
the same FIFO-draw mechanism already built for RM sales, Lost Inventory,
and every WIP/FG production stage in this app — `draw_fifo`/`return_fifo`
in `production/services/_shared.py`, `get_available_*_batches_for_fifo`
selectors) — it just needs to exist for FG sales in `billing` too, which it
doesn't yet (billing today only sells `purchases.Product`/RM).

So: **billing selling FG products, with a real FIFO consumption ledger
against `PackingOutputItem`, is a prerequisite for this whole design** — not
an optional nice-to-have. This was flagged explicitly as the scope
commitment being made by choosing this design (see "What billing needs to
build" below).

## Per-invoice-line `cogs` field — behavior

Proposed: a `cogs` field on the invoice line item (mirrors how every other
cost field in this app is a locked-in snapshot, never silently re-derived).

- **Only ever touched at invoice *confirm*, never at draft.** Drafts don't
  consume stock (matches existing RM behavior — `confirm_invoice` runs the
  FIFO draw, not draft creation). Locking cost to a draft would need
  reversal logic for every edit/discard and could race two drafts for the
  same batch stock.
- At confirm, the FIFO draw **always** happens and is **always** recorded
  (one consumption row per batch actually touched — same shape as
  `RecipeMaterialConsumption`/`LostInventoryFIFOConsumption`/
  `CuttingMaterialConsumption`: `{batch, quantity, unit_cost}` per row).
- Whether `cogs` gets a value immediately or stays null depends on whether
  every batch drawn from is **already fully costed**:
  - A batch produced in an **already-closed** prior month → its true cost
    is already known → that consumption row's `unit_cost` is filled in
    immediately, at confirm time.
  - A batch produced in the **current, still-open** month → cost unknown
    → that row's `unit_cost` stays null until this month's close.
- The invoice line's overall `cogs` is the sum of its consumption rows, but
  is only **final** once every row has a non-null `unit_cost`.

### The mixed-batch case (worked through explicitly)

Example: sell 20 units of product X — 10 from last month's (closed, costed)
batch, 10 from this month's (still-open) batch.

- Two consumption rows get created: Row 1 = 10 units @ known cost (filled
  immediately), Row 2 = 10 units @ null (pending).
- The invoice line stays "pending" (not fed into `profits`) until **both**
  rows are known.
- Critically, this is **never an unbounded wait**: a sale can only ever draw
  from a batch that already exists at the time of sale — either an
  already-closed prior month, or the *current* month. Never a future month.
  So the pending row always belongs to the same month the sale itself
  happened in — meaning the whole line finalizes in that same month's
  close, exactly as if it had been a single-batch sale. No line ever waits
  more than "until its own sale month closes."
- Returns compose the same way: a return against a still-pending line just
  records its own FIFO restoration against the right consumption row(s) and
  waits for the same month-end pass to resolve both the sale and its return
  together.

## Month-end batch costing engine — the mechanics

This is the actual "Production Batch Costing Engine" from client doc §6-8,
worked through in detail:

1. **Identify every batch that produced output this month** — every
   `Recipe` with `recipe_type=packing`, `status=finished`, `finished_at`
   within the month. Each has a `PackingOutputItem` (quantity + so-far
   DM-only cost).
2. **DM per batch** — already exact (see above), zero new work needed.
3. **DL per batch** — needs two things that don't exist yet:
   - **Production hours per batch** — no current tracking of how long a
     Rewinding/Cutting/Packing batch took. Needs a new field/log on
     `Recipe`, filled in by the supervisor (client's own example: "Batch =
     15 production hours").
   - **Monthly actual labor cost** — a real record of what was actually
     paid in labor that month. This is the "new app similar to Expenses"
     floated in conversation — a place to log actual labor cost per month.
   - At month-end: `labor rate/hour = month's total actual labor cost ÷
     month's total production hours (summed across every batch that ran
     that month)`, then `batch DL = that batch's own hours × labor
     rate/hour`.
4. **FOH per batch** — same shape as DL:
   - Needs a monthly actual FOH cost pool (rent, power, depreciation, etc.
     — likely a second "Expenses-like" record).
   - Needs a per-batch allocation base — client doc leaves this explicitly
     open ("machine hours, production hours, etc. — to be finalized
     later"). Could reuse the same production-hours figure as DL (no new
     tracking), or use a distinct base like machine hours (a second
     per-batch number to log). **Open question — needs the client's
     decision, not an assumption.**
   - `FOH rate = month's total FOH pool ÷ month's total allocation base`,
     then `batch FOH = batch's own base units × FOH rate`.
5. **Actual cost per piece, per batch**:
   ```
   Actual Batch Manufacturing Cost = DM + DL + FOH
   Actual Cost Per Piece = Actual Batch Manufacturing Cost ÷ Actual Good Output
   ```
   Matches the client doc's own worked example: Rs.272,000 ÷ 5,000 good
   pieces = Rs.54.40/piece.
6. **Where the number gets used, once computed**:
   - Every `PackingOutputItem` from that batch gets this as its true
     `unit_cost_snapshot` (replacing the DM-only figure it was created
     with).
   - Every pending (null-`unit_cost`) consumption row on any invoice line
     that drew from this batch — this month or any future month, since the
     batch's cost is now fixed forever once computed — gets filled in.
   - Whatever quantity from this batch is still unsold becomes part of
     **Closing FG value** for this month's COGM/COGS formula, at this same
     real cost.

## Why this reconciles by construction, not just by checking

Because every invoice line's COGS is built from the exact same batches that
feed the month-level COGM/COGS formula, summing every finalized invoice
line's COGS for the month mathematically **equals** the month-level COGS
number (COGM + Opening FG − Closing FG) — it cannot drift, because it isn't
two independently-computed numbers being compared. This satisfies client
doc §9's "Critical Reconciliation" requirement more strongly than a
compare-and-flag check would — the two numbers are the same number, viewed
two ways (aggregate vs. per-line).

## What needs to be built (not yet started — this is the punch list)

1. **Billing sells FG products** — `InvoiceItem` (or a parallel mechanism)
   needs to reference `production.FgProduct`, not just `purchases.Product`.
   This is the "big" billing rework flagged earlier as a real commitment,
   not a small add-on.
2. **FIFO consumption ledger for FG sales** — a new model mirroring
   `RecipeMaterialConsumption`/`LostInventoryFIFOConsumption` exactly: one
   row per `PackingOutputItem` batch actually drawn from, with a
   **nullable** `unit_cost` (null = pending this month's close).
3. **`cogs` field on the invoice line** — nullable, sum of its consumption
   rows, only treated as final once every row is costed.
4. **Return-side symmetry** — returns against FG invoice lines record their
   own FIFO restoration against the right consumption row(s), same
   null-aware pending behavior.
5. **Production-hours logging** — new field/log on `Recipe` for actual
   hours worked per batch.
6. **A "Direct Labor" tracking app** — records real monthly labor cost
   actuals (structure likely similar to the existing `expenses` app).
7. **A "Factory Overhead" tracking app** — same shape, for FOH actuals.
   (Items 6-7 might end up as one app with a labor/overhead split, or two
   separate apps — not decided.)
8. **The month-end batch costing job** — computes DL/FOH rates, applies
   them per batch, finalizes `PackingOutputItem.unit_cost_snapshot`, and
   walks forward to fill in every pending invoice-line consumption row and
   compute final gross profit per line.
9. **COGM/COGS statement** (client doc §5) — the aggregate month-level
   report, which should now also serve as the reconciliation check against
   the summed per-invoice figures from item 8.
10. **Feed into `profits`** — once a given month's invoice lines are fully
    finalized (all consumption rows costed), their gross profit becomes the
    real input to the `profits` app, replacing whatever mechanism exists
    there today for gross profit (currently profit calc doesn't account for
    manufacturing COGS at all — it predates WIP/FG).

## Open decisions needing the client's input (not to be assumed)

- **FOH allocation basis** — production hours (reusing DL's own figure) or
  a separate base like machine hours. Client doc explicitly defers this.
- **What counts as "a batch" for DL/FOH purposes** — Packing recipes only,
  or also Rewinding and Cutting individually (since real labor happens at
  every stage, not just Packing)? If Packing-only, earlier-stage labor/FOH
  gets absorbed as a lump sum into Packing's cost rather than attributed to
  where the work actually happened. Not resolved in the client doc either.
- **Whether normal (non-admin) users should see WIP/FG stock levels** —
  unrelated to COGS directly, but flagged as an open question in the same
  session (2026-09-06/07) — pending the client's confirmation, tracked
  separately, not part of this engine.
