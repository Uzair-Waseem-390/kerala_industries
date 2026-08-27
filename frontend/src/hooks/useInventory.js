import { inventoryApi } from '../services/inventoryApi';
import { usePaginatedList } from './usePaginatedList';

// Paginated inventory list — switches between the full list and the
// low-stock / out-of-stock breakdown endpoints depending on `stockView`
// ('all' | 'low' | 'out'). Extracted from InventoryPage's inline fetch
// function, same behavior.
export const useInventoryList = (stockView, searchTerm) => {
    const fetchInventoryPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        if (stockView === 'low') return inventoryApi.inventory.getLowStock(p);
        if (stockView === 'out') return inventoryApi.inventory.getOutOfStock(p);
        return inventoryApi.inventory.getAll(p);
    };

    return usePaginatedList(fetchInventoryPage, {}, 25, [searchTerm, stockView]);
};

// Products + quantities currently on one shelf — same paginated shape as
// every other list endpoint.
export const useShelfStock = (shelfId, searchTerm) => {
    const fetchStockPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        return inventoryApi.shelfStock.getByShelf(shelfId, p);
    };

    return usePaginatedList(fetchStockPage, {}, 25, [shelfId, searchTerm]);
};
