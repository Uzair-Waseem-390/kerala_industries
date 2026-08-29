import { api } from '../utils/api';

// Identical-shape {id, value, ...} lookup resources (Jumbo Names/Bindings,
// Core Lengths/Thicknesses, Packing/Carton Sizes) — full CRUD, admin-only,
// same envelope/permission tier as Categories. Factory avoids 6x copy-paste.
const createLookupApi = (path) => ({
    getAll: (params = {}) => {
        const query = new URLSearchParams(params).toString();
        return api.get(`/${path}/${query ? `?${query}` : ''}`);
    },
    create: (data) => api.post(`/${path}/`, data),
    update: (id, data) => api.patch(`/${path}/${id}/`, data),
    delete: (id) => api.delete(`/${path}/${id}/`),
});

// Base API functions for purchases app
export const purchasesApi = {
    // Families — fixed/seeded lookup on Product (Raw Material / WIP /
    // Finished Goods), read-only: no create/edit/delete API.
    families: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/families/${query ? `?${query}` : ''}`);
        },
    },

    // Shelves
    shelves: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/shelves/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/shelves/${id}/`),
        create: (data) => api.post('/shelves/', data),
        update: (id, data) => api.patch(`/shelves/${id}/`, data),
        delete: (id) => api.delete(`/shelves/${id}/`),
        // Products + quantities currently on one shelf — moved to
        // inventoryApi.shelfStock.getByShelf() (inventory app concern).
        // Shelves that currently hold stock (qty > 0) of a given product —
        // the backend search source for consumption allocations (sale,
        // purchase return, lost inventory). search narrows by shelf name.
        getCandidates: (productId, search = '') => {
            const query = new URLSearchParams({ product_id: productId });
            if (search) query.set('search', search);
            return api.get(`/shelves/candidates/?${query.toString()}`);
        },
        moveStock: (data) => api.post('/shelves/move/', data),
        // Auto-allocate `quantity` units of a product across shelves that
        // currently hold stock, skipping `excludeShelfIds` (shelves the
        // caller already has manual rows for). Returns whatever it could
        // allocate plus a `shortfall` if total remaining stock fell short —
        // caller applies the allocations as-is either way.
        autoAllocate: (productId, quantity, excludeShelfIds = []) =>
            api.post('/shelves/auto-allocate/', {
                product_id: productId,
                quantity,
                exclude_shelf_ids: excludeShelfIds,
            }),
    },

    // Suppliers
    suppliers: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/suppliers/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/suppliers/${id}/`),
        create: (data) => api.post('/suppliers/', data),
        update: (id, data) => api.patch(`/suppliers/${id}/`, data),
        delete: (id) => api.delete(`/suppliers/${id}/`),
        getOutstanding: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/suppliers/outstanding/${query ? `?${query}` : ''}`);
        },
        getPayableSummary: (id) => api.get(`/suppliers/${id}/payable-summary/`),
        getOutstandingOrders: (id) => api.get(`/suppliers/${id}/outstanding-orders/`),
    },

    // Products — frozen to 4 fixed rows (Jumbo/Cores/Packing/Cartons),
    // seeded by a management command. Backend removed create/edit/delete;
    // only list/detail (GET) remain.
    products: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/products/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/products/${id}/`),
    },

    // Product attribute lookups — standalone tag values, not attached to
    // Product yet (prep for a future production/recipe feature).
    jumboNames: createLookupApi('jumbo-names'),
    coreNames: createLookupApi('core-names'),
    coreLengths: createLookupApi('core-lengths'),
    coreThicknesses: createLookupApi('core-thicknesses'),
    packingSizes: createLookupApi('packing-sizes'),
    cartonSizes: createLookupApi('carton-sizes'),

    // Purchase Orders
    orders: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/${query ? `?${query}` : ''}`);
        },
        getDrafts: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/drafts/${query ? `?${query}` : ''}`);
        },
        getConfirmed: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/confirmed/${query ? `?${query}` : ''}`);
        },
        getOutstanding: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/outstanding/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/orders/${id}/`),
        create: (data) => api.post('/orders/', data),
        update: (id, data) => api.patch(`/orders/${id}/`, data),
        delete: (id) => api.delete(`/orders/${id}/`),
        confirm: (id) => api.post(`/orders/${id}/confirm/`),
        getPaymentSummary: (id) => api.get(`/orders/${id}/payment-summary/`),
        print: (id, isDraft = false) =>
            api.get(`/orders/${id}/print/?is_draft=${isDraft}`, { responseType: 'blob' }),
        savePDF: (id, data) => api.post(`/orders/${id}/pdf/save/`, data),
        getPDFs: (id) => api.get(`/orders/${id}/pdf/`),
        deletePDF: (pdfId) => api.delete(`/pdf/${pdfId}/`),
    },

    // Purchase Item shelf allocations (put-away plan while order is draft)
    purchaseItems: {
        setShelfAllocations: (purchaseItemId, allocations) =>
            api.post(`/purchase-items/${purchaseItemId}/shelf-allocations/`, { allocations }),
        // Jumbo exact-length correction — confirmed Jumbo items only (items
        // with expected_length_m set). Recomputes yards from exact_length_m
        // and applies shelf_allocations to cover the shortfall/surplus vs.
        // the item's current quantity.
        correctJumboLength: (purchaseItemId, data) =>
            api.post(`/purchase-items/${purchaseItemId}/correct-jumbo-length/`, data),
    },

    // Raw-material purchase intake — 4 family-specific create endpoints.
    // Each returns the created PurchaseOrder (nested items) in DRAFT status;
    // shelf allocation + confirm still go through the existing order flow
    // (purchasesApi.orders / purchasesApi.purchaseItems above).
    jumboPurchases: {
        create: (data) => api.post('/jumbo-purchases/', data),
    },
    corePurchases: {
        create: (data) => api.post('/core-purchases/', data),
    },
    packingPurchases: {
        create: (data) => api.post('/packing-purchases/', data),
    },
    cartonPurchases: {
        create: (data) => api.post('/carton-purchases/', data),
    },

    // Purchase Batches — read-only combined view across all 4 RM families
    // (Jumbo/Cores/Packing/Cartons), one table per client requirement.
    purchaseBatches: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/purchase-batches/${query ? `?${query}` : ''}`);
        },
    },

    // Purchase Return Item shelf allocations (consumption plan while pending)
    purchaseReturnItems: {
        setShelfAllocations: (returnItemId, allocations) =>
            api.post(`/return-items/${returnItemId}/shelf-allocations/`, { allocations }),
    },

    // Payments
    payments: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/payments/${query ? `?${query}` : ''}`);
        },
        getByOrder: (orderId, params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/${orderId}/payments/${query ? `?${query}` : ''}`);
        },
        create: (orderId, data) => {
            // The backend expects 'order' field
            const payload = {
                order: parseInt(orderId),  // Use 'order' field name
                amount: data.amount,
                method_allocations: data.method_allocations,
                payment_date: data.payment_date,
                note: data.note || '',
            };
            return api.post(`/orders/${orderId}/payments/`, payload);
        },
        delete: (paymentId) => api.delete(`/payments/${paymentId}/`),
    },

    // Returns
    // Returns
    returns: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/returns/${query ? `?${query}` : ''}`);
        },
        getByOrder: (orderId, params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/orders/${orderId}/returns/${query ? `?${query}` : ''}`);
        },
        create: (orderId, data) => {
            // The backend expects 'order_id' and items with 'purchase_item_id'
            const payload = {
                order_id: parseInt(orderId),  // Changed from invoice_id to order_id
                items: data.items.map(item => ({
                    purchase_item_id: parseInt(item.purchase_item_id),  // Changed from invoice_item_id
                    quantity: parseInt(item.quantity) || 0,
                })),
                note: data.note || '',
            };
            console.log('Sending return payload:', payload); // Debug log
            return api.post(`/orders/${orderId}/returns/`, payload);
        },
        accept: (returnId) => api.post(`/returns/${returnId}/accept/`),
        update: (returnId, data) => {
            const payload = {
                items: data.items.map(item => ({
                    purchase_item_id: parseInt(item.purchase_item_id),
                    quantity: parseInt(item.quantity) || 0,
                    gst: item.gst || 0,
                    wht: item.wht || 0,
                })),
                ...(data.note !== undefined ? { note: data.note } : {}),
            };
            return api.patch(`/returns/${returnId}/`, payload);
        },
        cancel: (returnId) => api.delete(`/returns/${returnId}/`),
    },

    // Inventory — moved to services/inventoryApi.js (inventoryApi.inventory)
    // when inventory-tracking code was split into its own backend app.

    // Lost Inventory
    lostInventory: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/lost-inventory/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/lost-inventory/${id}/`),
        create: (data) => api.post('/lost-inventory/', data),
        fifoPreview: (productId, quantity) => {
            const query = new URLSearchParams({ product_id: productId, quantity }).toString();
            return api.get(`/lost-inventory/fifo-preview/?${query}`);
        },
        markFound: (itemId, quantity, shelfAllocations = []) =>
            api.post(`/lost-inventory/items/${itemId}/found/`, {
                quantity,
                shelf_allocations: shelfAllocations,
            }),
    },
};