import { useState, useEffect } from 'react';
import { purchasesApi } from '../services/purchasesApi';
import { usePaginatedList } from './usePaginatedList';

// Fetches one lookup resource's active values once (Jumbo Name, Core
// Name/Length/Thickness, Packing/Carton Size) and shapes them as
// {value, label} Select options — used by the RM purchase-intake forms.
// These lists are small admin-managed tag sets (not paginated in the UI),
// so a single page_size:100 fetch on mount is enough.
export const useLookupOptions = (resource) => {
    const [options, setOptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        resource.getAll({ page_size: 100 })
            .then((res) => {
                if (cancelled) return;
                const results = res?.results ?? res ?? [];
                setOptions(
                    results
                        .filter((r) => !r.is_deleted)
                        .map((r) => ({ value: r.id, label: r.value }))
                );
            })
            .catch((err) => {
                if (!cancelled) setError(err.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [resource]);

    return { options, loading, error };
};

// Generic hook for CRUD operations — thin wrapper around usePaginatedList.
export const useCRUD = (service, initialFilters = {}) => {
    const {
        data, meta, loading: listLoading, error: listError,
        filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => service.getAll(params), initialFilters);

    const [mutating, setMutating] = useState(false);
    const [mutationError, setMutationError] = useState(null);

    const create = async (payload) => {
        setMutating(true);
        setMutationError(null);
        try {
            const result = await service.create(payload);
            await refetch();
            return result;
        } catch (err) {
            setMutationError(err.message);
            throw err;
        } finally {
            setMutating(false);
        }
    };

    const update = async (id, payload) => {
        setMutating(true);
        setMutationError(null);
        try {
            const result = await service.update(id, payload);
            await refetch();
            return result;
        } catch (err) {
            setMutationError(err.message);
            throw err;
        } finally {
            setMutating(false);
        }
    };

    const deleteItem = async (id) => {
        setMutating(true);
        setMutationError(null);
        try {
            await service.delete(id);
            // Deleted the last item on a page beyond page 1 — step back a page.
            if (data.length === 1 && page > 1) {
                setPage(page - 1);
            } else {
                await refetch();
            }
        } catch (err) {
            setMutationError(err.message);
            throw err;
        } finally {
            setMutating(false);
        }
    };

    return {
        data,
        meta,
        page,
        setPage,
        // Only the list fetch gates a full-page spinner — a create/update/
        // delete in flight (`mutating`) must not blank the whole page out
        // from under the user, since callers already show their own
        // form/button-level loading state for that.
        loading: listLoading,
        mutating,
        error: listError || mutationError,
        filters,
        setFilters,
        refetch,
        create,
        update,
        delete: deleteItem,
    };
};

// Generic create-only mutation hook for the 4 RM purchase-intake endpoints
// (Jumbo/Cores/Packing/Cartons) — each just POSTs and returns the created
// draft PurchaseOrder, no accompanying list to refetch.
export const usePurchaseIntake = (createFn) => {
    const [mutating, setMutating] = useState(false);
    const [error, setError] = useState(null);

    const create = async (payload) => {
        setMutating(true);
        setError(null);
        try {
            return await createFn(payload);
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setMutating(false);
        }
    };

    return { create, mutating, error };
};

// Purchase Batches — read-only combined list across all 4 RM families.
export const usePurchaseBatches = (initialFilters = {}) => {
    const { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch } =
        usePaginatedList((params) => purchasesApi.purchaseBatches.getAll(params), initialFilters);

    return { data, meta, page, setPage, loading, initialLoading, error, filters, setFilters, refetch };
};

// Hook for supplier outstanding — Suppliers are excluded from pagination
// (client confirmed there are only ~10-15), so this stays a plain list fetch.
// The suppliers-outstanding endpoint IS paginated (only the plain suppliers
// list is excluded), so this wraps usePaginatedList like the other lists.
export const useSuppliersOutstanding = (initialFilters = {}) => {
    const { data, meta, loading, error, filters, setFilters, page, setPage, refetch } =
        usePaginatedList((params) => purchasesApi.suppliers.getOutstanding(params), initialFilters);

    return { data, meta, page, setPage, loading, error, filters, setFilters, refetch };
};
