# Remaining cross-app integration for `manufacturing_costs`

The `manufacturing_costs` app itself (Employees, Machines, Rent/Electricity,
the payable-entity registry, payments, and the full cash-in-hand wiring) is
built, migrated, and verified. This file tracks what's still needed in
OTHER apps so real Direct Labor / Factory Overhead payments actually flow
through correctly everywhere they should — nothing below has been built yet.

**Next up (separate task, right after this): `production`.** Not detailed
here since it's being tackled immediately, not deferred — noted only so
it's not mistaken for one of the open gaps below.

---

## `profits` — real gap, will produce wrong numbers once this app is used

**The problem:** `profits.services._finalize_month` computes `net_profit`
by taking gross profit and subtracting a fixed list of real cash outflows:
`expenses_paid`, `recurring_expenses_paid`, `gst_paid`, `wht_paid`,
`lost_cash` (net of `found_cash`), `lost_inventory` (net of
`found_inventory`), `depreciation`, `disposal_gain_loss`. **Direct Labor and
Factory Overhead payments are not in this list.** The moment someone
records a real `manufacturing_costs.Payment`, real cash leaves the
business (confirmed — it moves `cash_in_hand` exactly like an Expense
does), but `MonthlyProfit.net_profit` won't reflect it. Net profit will be
**overstated** by however much DL/FOH gets paid, silently, from month one.

**What needs to happen** (mirrors `_compute_expenses_paid`/
`_compute_recurring_expenses_paid` exactly — same shape, not a new pattern):

1. Add `_compute_direct_labor_paid(first_day, last_day)` and
   `_compute_factory_overhead_paid(first_day, last_day)` (or one combined
   `_compute_manufacturing_costs_paid` returning both) to
   `profits/services.py` — a plain date-ranged `Sum` over
   `manufacturing_costs.Payment`, filtered by `entity__type` (employee vs
   machine/rent/electricity) same split the `movement_type` builder in
   `cash_flow/services.py` already uses.
2. Subtract both from the `net_profit` formula in `_finalize_month`.
3. Add `direct_labor_paid`/`factory_overhead_paid` fields to the
   `MonthlyProfit` model — every other component is snapshotted/frozen
   per month once finalized; these need the same treatment, not a live
   recompute.
4. `profits`' fast-path `_read()` (the live correlated-subquery version used
   before a month is finalized) sums the SAME sources independently from
   the slow/authoritative `_finalize_month` path, and
   `ProfitsEquivalenceTests` asserts the two produce byte-identical
   results — **both paths need the new sources added together**, or that
   test will start failing (correctly) the moment this is half-done.
5. New migration on `MonthlyProfit` for the two new fields — this table has
   real historical rows once real invoices exist, so treat it with the same
   migration-safety care as any other populated-table schema change.

**Why this isn't done as part of the `manufacturing_costs` build itself:**
scope was explicitly limited to `manufacturing_costs` + `cash_flow` +
`payment_methods` for this phase, specifically so it could be tested
standalone before touching `profits`/`accounting`/`production` — see the
design conversation this app was built from.

---

## `accounting` — partially done, one piece needs verification

**Done already** (part of the required cash-in-hand 7-step wiring, already
shipped with this app): the Cash Flow Statement correctly classifies
`direct_labor_payment`/`factory_overhead_payment` as Operating Activities
(`accounting/selectors.py`'s `OPERATING_MOVEMENT_TYPES` +
`_MOVEMENT_TYPE_LABELS`) — confirmed, not a guess.

**Not yet verified — needs investigation, not assumed either way:**
- **Income Statement** — unclear whether it derives its expense line items
  from a fixed category list (in which case DL/FOH would need a new line
  the same way the Cash Flow Statement did) or from a broader query that
  would already pick these up automatically. Needs reading
  `accounting/services.py`'s income statement computation before concluding
  either way.
- **Balance Sheet** — likely genuinely unaffected, since DL/FOH payments are
  pure cash-basis expenses with no accrual/payable concept in this app
  today (`PayableEntity` tracks payment *history*, not an "owed but
  unpaid" balance) — but this assumption should be confirmed, not just
  stated, before treating it as settled.

---

## Everything else — confirmed NOT needed / already correct

- `cash_flow` — fully wired (all 7 steps of `instructions/cash-in-hand.md`).
  Nothing further needed there.
- `payment_methods` — `record_allocations`/`reverse_allocations` already
  called correctly at create/delete; `PaymentMethod.balance` stays in sync.
  Nothing further needed.
- `reports`/Stock Movement Report — out of scope; that report is explicitly
  RM/billing-scoped in this codebase and manufacturing labor/overhead was
  never intended to feed it.
