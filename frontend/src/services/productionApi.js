import { api } from '../utils/api';

// Read-only system-derived lookup resources (Rewound Core Bindings/Yards/
// Length-mm) — display-only, no create/edit/delete API.
const createReadOnlyLookupApi = (path) => ({
    getAll: (params = {}) => {
        const query = new URLSearchParams(params).toString();
        return api.get(`/production/${path}/${query ? `?${query}` : ''}`);
    },
    getById: (id) => api.get(`/production/${path}/${id}/`),
});

// API functions for the `production` app (Rewinding — first of a 3-stage
// Work-In-Process flow: Cutting and Packing come later, not built yet).
export const productionApi = {
    // Recipes — one production batch each. recipe_type defaults to
    // "rewinding" on the backend (the only type that exists so far).
    recipes: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/recipes/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/production/recipes/${id}/`),
        create: (data) => api.post('/production/recipes/', data),
        // kind: "jumbo" | "cores". shelf_allocations: consumption-style —
        // which RM shelves to pull `quantity` from.
        issueMaterial: (id, data) => api.post(`/production/recipes/${id}/issue-material/`, data),
        // quantity is the NEW total (not a delta). shelf_allocations sum to
        // the delta: consumption-style if raising the total, putaway-style
        // (return to RM) if lowering it.
        updateIssuedMaterial: (id, kind, data) =>
            api.patch(`/production/recipes/${id}/issued-materials/${kind}/`, data),
        // shelf_allocations must sum to `quantity`, putaway-style (any
        // shelf) — destination for the newly-produced WIP quantity.
        addBreakdownItem: (id, data) => api.post(`/production/recipes/${id}/breakdown-items/`, data),
        finish: (id) => api.post(`/production/recipes/${id}/finish/`),
        // Description is optional at creation, editable any time the recipe
        // is still under_processing, and required before finish.
        updateDescription: (id, data) => api.patch(`/production/recipes/${id}/description/`, data),
    },

    // RM variants already purchased for a given kind — the picker source
    // when issuing material into a recipe. Search-as-you-type since there
    // can be many attribute combinations.
    issuableProducts: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/issuable-products/${query ? `?${query}` : ''}`);
        },
    },

    // WIP Products / Inventory — read-only overview.
    wipProducts: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/wip-products/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/production/wip-products/${id}/`),
    },
    wipInventory: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/wip-inventory/${query ? `?${query}` : ''}`);
        },
    },

    // WIP products + quantities currently on one shelf — powers the Shelf
    // detail page's WIP tab. Same nested-route shape as
    // inventoryApi.shelfStock.getByShelf, just served by production.
    wipShelfStock: {
        getByShelf: (shelfId, params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/shelves/${shelfId}/wip-stock/${query ? `?${query}` : ''}`);
        },
    },

    // System-derived WIP attribute lookups — read-only, probably not worth
    // their own page but available for display.
    rewoundCoreBindings: createReadOnlyLookupApi('rewound-core-bindings'),
    rewoundCoreYards: createReadOnlyLookupApi('rewound-core-yards'),
    rewoundCoreLengthMms: createReadOnlyLookupApi('rewound-core-length-mms'),
};
