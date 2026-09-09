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
        // Time taken + Direct Labor/Factory Overhead assignment — all
        // required before finish (server-enforced) so the DL+FOH cost pool
        // can be spread into full_cost_per_unit alongside the material-only
        // cost_per_unit that already existed.
        setTime: (id, data) => api.patch(`/production/recipes/${id}/time/`, data),
        addLabor: (id, data) => api.post(`/production/recipes/${id}/labor/`, data),
        removeLabor: (id, employeeId) => api.delete(`/production/recipes/${id}/labor/${employeeId}/`),
        // Backend rejects with 400 if the machine's category doesn't match
        // this recipe's own recipe_type.
        addMachine: (id, data) => api.post(`/production/recipes/${id}/machines/`, data),
        removeMachine: (id, machineId) => api.delete(`/production/recipes/${id}/machines/${machineId}/`),
    },

    // RM variants already purchased for a given kind ("jumbo" | "cores" |
    // "packing") — the picker source when issuing material into a recipe.
    // Search-as-you-type since there can be many attribute combinations.
    issuableProducts: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/issuable-products/${query ? `?${query}` : ''}`);
        },
    },

    // Cutting — second WIP stage. Issues whole Rewound Cores and breaks them
    // down into cut-length pieces. One issued material (no jumbo/cores
    // split like Rewinding) and breakdown items carry length_mm + quantity
    // instead of a single yard_value.
    cuttingRecipes: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/cutting-recipes/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/production/cutting-recipes/${id}/`),
        create: (data) => api.post('/production/cutting-recipes/', data),
        updateDescription: (id, data) => api.patch(`/production/cutting-recipes/${id}/description/`, data),
        // shelf_allocations: which shelves to pull the issued WIP core
        // quantity from — sourced from wipShelfCandidates below, same
        // consumption-style picker Rewinding's own issue-material uses.
        issueMaterial: (id, data) => api.post(`/production/cutting-recipes/${id}/issue-material/`, data),
        // quantity is the NEW total (not a delta), same as Rewinding's
        // update-issued-material — draws more on increase, returns WIP
        // stock on decrease.
        updateIssuedMaterial: (id, data) => api.patch(`/production/cutting-recipes/${id}/issued-material/`, data),
        // One output line per call: a cut length (length_mm) + how many
        // pieces of that length (quantity), plus put-away shelf_allocations.
        addBreakdownItem: (id, data) => api.post(`/production/cutting-recipes/${id}/breakdown-items/`, data),
        finish: (id) => api.post(`/production/cutting-recipes/${id}/finish/`),
        // Time taken + Direct Labor/Factory Overhead assignment — same
        // shape as Rewinding's own recipes.setTime/addLabor/addMachine.
        setTime: (id, data) => api.patch(`/production/cutting-recipes/${id}/time/`, data),
        addLabor: (id, data) => api.post(`/production/cutting-recipes/${id}/labor/`, data),
        removeLabor: (id, employeeId) => api.delete(`/production/cutting-recipes/${id}/labor/${employeeId}/`),
        addMachine: (id, data) => api.post(`/production/cutting-recipes/${id}/machines/`, data),
        removeMachine: (id, machineId) => api.delete(`/production/cutting-recipes/${id}/machines/${machineId}/`),
    },

    // Whole Rewound Cores (not already-cut pieces) available to issue into
    // a Cutting recipe — the picker source for Cutting's issue-material.
    issuableWipCores: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/issuable-wip-cores/${query ? `?${query}` : ''}`);
        },
    },

    // Shelves currently holding stock of a given WIP product — mirrors
    // purchasesApi.shelves.getCandidates, for Cutting's consumption-side
    // shelf picker (issuing a core, or increasing an already-issued qty).
    wipShelfCandidates: {
        getAll: (wipProductId, params = {}) => {
            const query = new URLSearchParams({ wip_product_id: wipProductId, ...params }).toString();
            return api.get(`/production/wip-shelves/candidates/?${query}`);
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

    // Packing — third and final WIP stage. Issues a Cut Piece (WIP,
    // stage=cutting) and a Packing Material (RM) and finishes directly into
    // one Finished Goods output line — no breakdown stage, output quantity
    // is always the issued piece quantity 1:1.
    packingRecipes: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/packing-recipes/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/production/packing-recipes/${id}/`),
        create: (data) => api.post('/production/packing-recipes/', data),
        updateDescription: (id, data) => api.patch(`/production/packing-recipes/${id}/description/`, data),
        // shelf_allocations: consumption-style — which shelves (holding this
        // Cut Piece) to draw `quantity` from. Same picker as Cutting's own
        // issue-material, sourced from wipShelfCandidates below.
        issuePiece: (id, data) => api.post(`/production/packing-recipes/${id}/issue-piece/`, data),
        // quantity is the NEW total (not a delta) — same increase/decrease
        // semantics as Cutting's update-issued-material.
        updateIssuedPiece: (id, data) => api.patch(`/production/packing-recipes/${id}/issued-piece/`, data),
        // shelf_allocations: consumption-style — RM Packing Material shelves,
        // same picker as Rewinding's own issue-material.
        issueMaterial: (id, data) => api.post(`/production/packing-recipes/${id}/issue-material/`, data),
        updateIssuedMaterial: (id, data) => api.patch(`/production/packing-recipes/${id}/issued-material/`, data),
        // No breakdown step — shelf_allocations here is putaway-style,
        // sized to the issued piece's quantity, and is where the newly
        // produced Finished Goods output gets put away.
        finish: (id, data) => api.post(`/production/packing-recipes/${id}/finish/`, data),
        // Time taken + Direct Labor/Factory Overhead assignment — same
        // shape as Rewinding's own recipes.setTime/addLabor/addMachine.
        setTime: (id, data) => api.patch(`/production/packing-recipes/${id}/time/`, data),
        addLabor: (id, data) => api.post(`/production/packing-recipes/${id}/labor/`, data),
        removeLabor: (id, employeeId) => api.delete(`/production/packing-recipes/${id}/labor/${employeeId}/`),
        addMachine: (id, data) => api.post(`/production/packing-recipes/${id}/machines/`, data),
        removeMachine: (id, machineId) => api.delete(`/production/packing-recipes/${id}/machines/${machineId}/`),
    },

    // Cut Pieces (WIP, stage=cutting) issuable into a Packing recipe — the
    // picker source for Packing's issue-piece. Mirrors issuableWipCores.
    issuableCuttingPieces: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/issuable-cutting-pieces/${query ? `?${query}` : ''}`);
        },
    },

    // FG Products / Inventory — read-only overview, mirrors wipProducts/wipInventory.
    fgInventory: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/production/fg-inventory/${query ? `?${query}` : ''}`);
        },
    },

    // Shelves currently holding stock of a given FG product — mirrors
    // wipShelfCandidates, for Packing's finish put-away picker and the All
    // Inventory page's Finished Goods product-detail modal.
    fgShelfCandidates: {
        getAll: (fgProductId, params = {}) => {
            const query = new URLSearchParams({ fg_product_id: fgProductId, ...params }).toString();
            return api.get(`/production/fg-shelves/candidates/?${query}`);
        },
    },
};
