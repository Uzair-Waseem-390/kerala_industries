# Frontend Rules

Portable rules for a React + Vite + Tailwind app — reuse across projects with this stack.

- **Folders**: `pages/<domain>/`, `services/<domain>Api.js`, `hooks/use<Domain>.js`, `components/<domain>/` only for 2+ reuse, `components/ui/*` as the ONE shared system (no second "common" folder).
- **Central theme folder** (`src/style/` or `src/theme/`): colors, typography, spacing, breakpoints, shadows, animations, one `index.js` export. Every color/spacing/font in a component traces back to a token here — no raw hex, no magic pixel values. Extend the folder before patching a component locally.
- **Mobile responsive is a hard requirement**: design/verify mobile-first, not "doesn't break on desktop." Use the central breakpoint scale. Tables need a real narrow-screen treatment (stacked cards/scroll affordance), not overflow. Touch-sized targets. Actually check a mobile viewport before calling a page done.
- **API clients**: object literal namespaced by sub-resource, routed through one shared `api` wrapper — never raw axios/fetch in a component. Identical-shape resources → factory function, not copy-paste.
- **Hooks**: `usePaginatedList` shape `{data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch}`. Mutation hooks: `mutating` + try/catch/finally + `refetch()`.
- **Permissions**: route guard = auth only; role checks inline per page. Nav-hide AND page-level redirect both required.
- **Page skeleton**: role check → data hook → loading spinner → header → error alert w/ retry → filters → table/empty state → pagination → modal.
- **Forms**: controlled state via `useState`; one validation-ownership shape per app (form-owned or page-owned, not both); always `toast.error(extractErrorMessage(...))`.
- **Shared components**: `LoadingSpinner`, `InlineAlert`, `EmptyState`, `ConfirmDialog` (never `window.confirm()`), `Card`, `Badge`, `Button`, `Modal`, `Pagination`, `Table` with `onRowClick`.
- **Toasts** for mutation outcomes; **styling** via semantic tokens only, prefer `<Card>`, one consistent page-spacing scale; **animation** scoped to transitions/hover/modals, not list bodies; **icons** from one library, no emojis.
- **Routing**: flat, consistent guard+layout wrapping. A screenshot/share-only route is a deliberate minimal-chrome exception. Nav config stays pure data.
- **Pagination envelope**: one consistent shape everywhere, e.g. `{count, total_pages, current_page, page_size, results}`.
- **Performance**: critical data first, no duplicate API calls (check what's already fetched before adding a call), paginate/lazy-load anything unbounded, real loading/skeleton/empty/error states everywhere.
- **Errors**: surface real backend messages when available. Never native `alert()`/`confirm()` — use a confirm modal, toast, or inline alert instead.
- **Reuse before creating.** New pages should match the rest of the app's skeleton and component choices.
- **Workflow**: Inspect → Understand → Plan → Implement → Verify (functionality, mobile, loading/error/empty states, console errors, no duplicate requests).
