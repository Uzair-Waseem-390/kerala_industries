# Multi-inventory expansion — read before touching purchases, billing, inventory, or rates

We're mid-design on a manufacturing costing expansion (Raw Material → WIP →
Finished Goods) on top of this trading ERP, per `docs/client_requirements.md`.
Only the Raw Material layer exists today. Full decision log:
`docs/manufacturing-costing-notes.md` — read it for the actual architecture
(structurally separate RM/WIP/FG catalogs, no shared `family` field, future
FK-based registry model, etc.) before proposing anything in this space.

**The rule:** don't land incremental, speculative multi-inventory-shaped
changes to `purchases`/`billing`/`inventory`/`rates` until the full WIP/FG
design is finalized and approved — it touches several of these apps at
once, and partial changes now get reworked once the full picture lands.
Normal bug fixes and unrelated work in these apps continue as usual; only
*this* initiative's pieces are paused.
