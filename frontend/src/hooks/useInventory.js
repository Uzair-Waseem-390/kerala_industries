import { inventoryApi } from '../services/inventoryApi';
import { productionApi } from '../services/productionApi';
import { usePaginatedList } from './usePaginatedList';

// Paginated inventory list — switches between the full list and the
// low-stock / out-of-stock breakdown endpoints depending on `stockView`
// ('all' | 'low' | 'out'). Extracted from InventoryPage's inline fetch
// function, same behavior.
//
// `isWipView` — RM's Inventory table structurally only ever holds
// Raw-Material-family products, so selecting the "WIP" family on the
// Inventory page has to switch to the separate production.WipInventory
// endpoint instead (WIP has no low/out-of-stock breakdown or family
// filter, so those params are dropped in that branch).
//
// `wipStage` — WIP-only sub-filter ('rewinding' | 'cutting' | undefined for
// all) distinguishing whole Rewound Cores from already-cut pieces. Ignored
// outside the WIP view.
export const useInventoryList = (stockView, searchTerm, isWipView = false, wipStage) => {
    const fetchInventoryPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        if (isWipView) {
            const { family, ...wipParams } = p;
            if (wipStage) wipParams.stage = wipStage;
            return productionApi.wipInventory.getAll(wipParams);
        }
        if (stockView === 'low') return inventoryApi.inventory.getLowStock(p);
        if (stockView === 'out') return inventoryApi.inventory.getOutOfStock(p);
        return inventoryApi.inventory.getAll(p);
    };

    return usePaginatedList(fetchInventoryPage, {}, 25, [searchTerm, stockView, isWipView, wipStage]);
};

// Products + quantities currently on one shelf — same paginated shape as
// every other list endpoint. `family` ('rm' | 'wip') switches between RM
// ShelfStock and production.WipShelfStock for the same shelf — the Shelf
// detail page's family tab. `stage` ('rewinding' | 'cutting' | undefined)
// is the WIP-only cores-vs-pieces sub-filter, ignored for 'rm'.
export const useShelfStock = (shelfId, searchTerm, family = 'rm', stage) => {
    const fetchStockPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        if (family === 'wip') {
            if (stage) p.stage = stage;
            return productionApi.wipShelfStock.getByShelf(shelfId, p);
        }
        return inventoryApi.shelfStock.getByShelf(shelfId, p);
    };

    return usePaginatedList(fetchStockPage, {}, 25, [shelfId, searchTerm, family, stage]);
};

// All Inventory — the merged RM+WIP list (one flat table, backend does the
// merge — see inventory.selectors.get_combined_inventory_rows). `typeFilter`:
// 'raw_material' | 'wip_core' | 'wip_piece' | undefined (all). `stockView`:
// 'all' | 'low' | 'out' — same Low Stock/Out of Stock card breakdown the
// RM-only page has, now covering WIP too.
export const useCombinedInventory = (searchTerm, typeFilter, stockView = 'all') => {
    const fetchCombinedPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        if (typeFilter) p.type = typeFilter;
        if (stockView !== 'all') p.stock_view = stockView;
        return inventoryApi.inventory.getAllCombined(p);
    };

    return usePaginatedList(fetchCombinedPage, {}, 25, [searchTerm, typeFilter, stockView]);
};
