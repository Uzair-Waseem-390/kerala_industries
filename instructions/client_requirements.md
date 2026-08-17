# Production Software — Final Flow for Developer

**Core objective:**
The software needs to accurately give 3 things:

1. Actual COGS → Gross Profit
2. Actual COGM → Manufacturing Cost
3. Product/Batch level actual cost → per piece/carton cost

And the product-level costing's total accounting should reconcile with COGS/COGM.

---

## 1. Inventory Structure

Separate inventory:
- Raw Material
- WIP
- Finished Goods

Opening balances/values will be entered manually.

Physical flow:
Raw Material → WIP → Finished Goods → Sales

---

## 2. Production Flow

### A. Jumbo → Rewinded Cores

A Production Batch/Recipe will be created.

Supervisor will select:
- Jumbo roll
- Jumbo's actual length
- Jumbo's actual cost
- Raw cores consumed
- Damaged/unused cores
- Output core sizes + quantities + yards

Example:
> 4,000Y jumbo
> → 50Y × X cores
> → 30Y × X cores
> → 100Y × X cores

The system will show input vs output variance:
> Input = 4,000Y
> Output = 3,900Y
> Variance = −100Y

No profit/loss at this stage.

Jumbo + cores:
Raw Material ↓ → WIP ↑

---

### B. Rewinded Cores → Cut Pieces

Core will be selected from WIP.

Supervisor enters:
- Core size/length
- Required cutting sizes
- Quantity of each size produced
- Damaged/failed output

Example:
> 1248mm core → 24mm × X pieces, 48mm × X pieces, etc.

Cut pieces will remain WIP for now because packing is not yet complete.

WIP remains WIP.

---

### C. Packing → Finished Goods

Packing material will be issued from raw-material inventory:
- Shrink
- Packing material
- Tape used for packing
- Cartons
- Other packaging

Actual quantity/weight consumed will be recorded.

After packing is complete:
WIP ↓ → Finished Goods ↑

In Finished Goods:
- Product
- Size
- Yard
- Pieces
- Cartons

will be tracked.

---

## 3. No Profit/Loss During Production

Raw Material → WIP → FG is only inventory transformation.

Profit/loss will only be recognized when Finished Goods are sold.

> Sales − COGS = Gross Profit

---

## 4. Estimated Costing

Sales will not wait for production to be complete.

Every product will have an Estimated Cost Sheet.

Example:

Jumbo component

Jumbo cost ÷ expected output pieces

> Rs.46.75/piece

Estimated manufacturing cost

Example:
> Rs.1,000/carton

If carton = 180 pieces:
> 1,000 ÷ 180 = Rs.5.56/piece

Estimated total cost:
> 46.75 + 5.56 = Rs.52.31/piece

Then adding the desired margin, the estimated selling/transfer price will be calculated.

**Important:** The components defined in the Rs.1,000 should not be double-counted with the jumbo.

---

## 5. Actual Accounting — Month End

**Direct Material Used**

```
Opening Direct Materials
+ Purchases
+ Inward Freight/Transport
− Closing Direct Materials
= Direct Material Used
```

Jumbo, cores, packing material etc. that were consumed directly in production will be included here at actual cost.

**TMC**

```
Direct Material Used
+ Direct Labor
+ Factory Overheads
= Total Manufacturing Cost (TMC)
```

**COGM**

```
TMC
+ Opening WIP
− Closing WIP
= COGM
```

COGM tells:
> Is month kitni cost ka finished product manufacture hua? (How much cost worth of finished product was manufactured this month?)

**COGS**

```
Opening Finished Goods
+ COGM
− Closing Finished Goods
= COGS
```

COGS tells:
> What was the cost of the finished goods that were actually sold?

Then:

```
Sales
− COGS
= Gross Profit

Gross Profit
− Operating Expenses
= Net Profit
```

---

## 6. Actual Per-Product / Per-Piece Costing

The COGS statement will give total actual COGS, but for product-wise cost, a Production Batch Costing Engine is needed.

Every production batch records:

**Direct Material**

Exactly traceable:
- Jumbo
- Cores
- Cartons
- Packing material

→ Assign actual cost to the batch.

**Direct Labor**

Supervisor/production system will record the batch's production time.

Example:
> Batch = 15 production hours

Monthly actual labor cost ÷ total production hours:
> Actual labor/hour

Then:
> Batch hours × actual labor/hour = Batch DL

**Factory Overhead**

FOH will have to be allocated to batches on a predetermined allocation basis.

Possible basis:
- Machine hours
- Production hours
- etc.

This allocation rule is to be finalized later.

---

## 7. Actual Cost Per Piece

For every batch:

```
Actual DM
+ Actual DL
+ Allocated Actual FOH
= Actual Batch Manufacturing Cost
```

Then:

```
Actual Batch Cost
÷ Actual Good Output
= Actual Cost Per Piece
```

Example:
> Batch cost = Rs.272,000
> Output = 5,000 pieces

Actual cost:
> Rs.54.40/piece

---

## 8. FG & COGS From Batch Cost

If batch produced 5,000 pieces:
- 3,000 sold
- 2,000 remain in FG

Then:

**COGS**
> 3,000 × Rs.54.40 = Rs.163,200

**Closing FG**
> 2,000 × Rs.54.40 = Rs.108,800

**Total:**
> 163,200 + 108,800 = Rs.272,000

So the batch's complete cost is accounted for.

---

## 9. Critical Reconciliation

At month end, the software must verify:

> Product/Batch-level allocated manufacturing cost = Accounting-level manufacturing cost

And:

> Product-level COGS = Financial statement COGS

If a difference exists:

> Cost Reconciliation Variance

The software should flag it instead of silently accepting incorrect costing.

---

## 10. Management Reports

The software should ultimately show:

**Factory**
- Total production
- COGM
- COGS
- Raw Material
- WIP
- Finished Goods
- Production vs Sales

**Product**
- Estimated cost/piece
- Actual cost/piece
- Estimated vs actual variance
- Estimated margin
- Actual margin

**Production Planning**

Compare:
> Production vs Sales

Example:

If:
> Production = 800 cartons
> Sales = 500 cartons

then inventory is accumulating.

The software should show this so management can decide whether to:
- Reduce production
- Increase sales
- Increase capacity
- Change product mix

---

## Developer's One-Line Architecture

> Purchase → Raw Material → Production Batch → WIP → FG → Sale/COGS, with a parallel Costing Engine that assigns actual DM + DL + FOH to each production batch, calculates actual cost/piece, and reconciles product-level costing back to the accounting COGM/COGS.

**Phase 1** focus: inventory flow + production recipes + WIP/FG movement + COGM/COGS + basic estimated costing.

**Phase 2**: batch-level DL/FOH allocation + actual per-piece costing + reconciliation + production planning/variance reports.