# "Accrued Manufacturing Cost Payable" (`dl_foh_payable`) — what it is, why it exists

> **Context (2026-09):** Added as part of the fix that stopped Direct Labor
> (DL) / Factory Overhead (FOH) cash payments from being subtracted twice
> from profit. This note explains the figure in plain terms, where it shows
> up, and — mirroring the precedent set in
> `backend/profits/how_to_restore_tax_outstanding_in_business_worth.md` —
> exactly how to hide it from client-facing screens later if it turns out to
> raise more questions than it answers, without breaking the underlying math.

## The problem this solves

Two different things happen to Direct Labor / Factory Overhead cost, and
they don't automatically agree with each other:

1. **Cost gets accrued into production.** Every time a Rewinding, Cutting,
   or Packing recipe finishes, the labor and machine-overhead cost for that
   recipe gets baked into the finished batch's value
   (`production.services._shared.compute_labor_overhead_pool`, frozen into
   `full_unit_cost_snapshot`). This happens regardless of whether anyone's
   actually been paid yet.
2. **Cash actually gets paid.** Real money paid to employees, machines,
   rent, electricity (`manufacturing_costs.Payment`), tracked as an
   all-time running total on `PayableEntity.overall_total_paid`.

Before this fix, `net_profit` simply subtracted whatever DL/FOH cash was
paid that month — which double-counted labor cost once it started flowing
through COGS when Finished Goods sales went live (the same labor rupee
would reduce profit once on payment, and again when the goods it helped
make were sold). The fix: stop subtracting the cash payment directly, and
let it hit the books exactly once — through COGS, when the batch sells,
exactly like raw-material cost already does.

That fix is correct, but it leaves a gap: cost that's been accrued into
inventory but not yet paid in cash (or vice versa) needs *something* to
account for the difference, or the Balance Sheet stops balancing. That
something is `dl_foh_payable`.

## The formula

```
dl_foh_payable = total_dl_foh_accrued − total_paid
```

- `total_dl_foh_accrued` — `manufacturing_costs.models.ManufacturingCostsStats.total_dl_foh_accrued`,
  an all-time running total, incremented every time a recipe finishes
  (`manufacturing_costs.services.record_dl_foh_accrued`, called from
  `production/services/{rewinding,cutting,packing}.py`).
- `total_paid` — `Σ manufacturing_costs.models.PayableEntity.overall_total_paid`
  across every employee/machine/rent/electricity entity — already an
  all-time running total, unrelated to this fix.
- Computed by `manufacturing_costs.selectors.get_dl_foh_payable_balance()`.

**Positive** → the business has accrued more manufacturing cost into
production than it's actually paid out in cash. A real liability: wages/
overhead owed against goods already produced.

**Negative** → the business has paid more cash than it's accrued into
production so far (e.g. a wage paid for a recipe that hasn't finished yet).
Effectively a prepayment — shown as a negative liability line rather than
moved into assets, same convention this codebase already uses for other
signed figures (e.g. `disposal_gain_loss`).

## Where it shows up today

1. **Balance Sheet** (`accounting.selectors._assemble_balance_sheet`) — a
   new liability line, "Manufacturing Cost Payable (Accrued DL/FOH)", on
   both the live view and the PDF export, and on frozen month-end snapshots
   (`accounting.models.BalanceSheetSnapshot.dl_foh_payable`). Frontend:
   `frontend/src/pages/accounting/BalanceSheetPage.jsx`.
2. **Total Business Worth / Ownership Split**
   (`profits.selectors.get_business_worth`/`get_ownership_split`) — the
   same figure, subtracted from `total_business_worth`. This one matters
   more than the Balance Sheet line cosmetically: `total_business_worth` is
   what every investor's ownership `share_percent` is divided against, and
   that percentage gets **permanently snapshotted** onto
   `MonthlyProfitInvestorShare` at month-end finalization — so leaving this
   out would have silently and permanently skewed real profit-share splits,
   not just a display number. Frontend:
   `frontend/src/pages/profits/BusinessWorthPage.jsx`.

Both `direct_labor_paid`/`factory_overhead_paid` (the raw cash-paid figures)
and `dl_foh_payable` (this reconciling figure) are always computed and
stored — nothing here is optional at the data layer. What's optional is
whether either one is *shown* on a given screen.

## Status (2026-09): excluded from both totals, per explicit client request

The client didn't just want the line hidden — they explicitly said they
don't want `dl_foh_payable` factored into Business Worth or the Balance
Sheet at all ("we don't need it here"). Current state:

- `accounting.selectors._assemble_balance_sheet`'s `total_liabilities` no
  longer includes `dl_foh_payable` (the term is commented out, not
  deleted).
- `profits.selectors.get_business_worth`'s `total_business_worth` no
  longer subtracts `dl_foh_payable` (same commented-out treatment already
  used for `sales_tax_outstanding`/`wht_outstanding` there).
- `dl_foh_payable` is still **computed and returned** in both dicts/
  serializers (`accounting.serializers.BalanceSheetLiabilitiesSerializer`,
  `profits.serializers.OwnershipSplitSerializer`) — nothing was removed at
  the data layer, only from the two totals.
- Both frontend lines (`BalanceSheetPage.jsx`, `BusinessWorthPage.jsx`) are
  also commented out (display-only, was already done first before the
  calculation exclusion was requested).

**Known consequence, accepted by the client**: the Balance Sheet's
`is_balanced`/`balance_check` will no longer be exactly zero whenever
there's an outstanding accrued-vs-paid DL/FOH gap (a recipe finished with
cost accrued into inventory but the wages/overhead not yet paid, or vice
versa) — `balance_check` will land exactly on `dl_foh_payable`'s value in
that scenario, since nothing else absorbs the gap anymore. This is the
expected, understood trade-off of the exclusion, not a bug —
`accounting.tests.DlFohPayableReconciliationTests` documents and asserts
this exact behavior.

## To fully reverse (restore both totals)

Un-comment the `- dl_foh_payable` line in
`profits.selectors.get_business_worth`'s `total_business_worth` formula,
and restore `+ dl_foh_payable` to `accounting.selectors
._assemble_balance_sheet`'s `total_liabilities` formula. The frontend
display lines and `DlFohPayableReconciliationTests` would also need
restoring to their pre-2026-09 form (see git history).
