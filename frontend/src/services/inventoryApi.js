import { api } from '../utils/api';

// Base API functions for the inventory app — extracted out of purchasesApi
// when the backend split its inventory-tracking code (Inventory, ShelfStock,
// ShelfStockMovement, ProductStockMovement, StockMovementFlow,
// InventoryStatsFlow) out of the purchases app into a dedicated `inventory`
// app. All URL paths are unchanged from before the split.
export const inventoryApi = {
    // Inventory — current stock levels per product.
    inventory: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/inventory/${query ? `?${query}` : ''}`);
        },
        // O(1) whole-inventory stats for the summary cards — served off a
        // stored counter, not a live count, so it's always global (not
        // affected by search/category/shelf filters).
        getStats: () => api.get('/inventory/stats/'),
        // Breakdown lists behind the Low Stock / Out of Stock cards.
        // Same search/category/shelf params as getAll, paginated.
        getLowStock: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/inventory/low-stock/${query ? `?${query}` : ''}`);
        },
        getOutOfStock: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/inventory/out-of-stock/${query ? `?${query}` : ''}`);
        },
        getByProduct: (productId) => api.get(`/inventory/${productId}/`),
        // Every product's inventory, RM + WIP merged into one flat list.
        // `type`: 'raw_material' | 'wip_core' | 'wip_piece' | undefined (all).
        getAllCombined: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/inventory/all/${query ? `?${query}` : ''}`);
        },
    },

    // Shelf stock — products + quantities currently physically on one
    // shelf. Route is nested under the purchases Shelf routes' pk, but
    // served by the backend inventory app.
    shelfStock: {
        getByShelf: (shelfId, params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/shelves/${shelfId}/stock/${query ? `?${query}` : ''}`);
        },
    },
};
