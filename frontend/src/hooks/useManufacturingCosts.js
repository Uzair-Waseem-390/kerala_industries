import { useState, useEffect, useCallback } from 'react';
import { manufacturingCostsApi } from '../services/manufacturingCostsApi';
import { usePaginatedList } from './usePaginatedList';

// Hook for employee management (create + update + soft-delete).
export const useManufacturingCostEmployees = (initialFilters = {}) => {
    const {
        data, meta, loading: listLoading, error: listError,
        filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => manufacturingCostsApi.employees.getAll(params), initialFilters);

    const [mutating, setMutating] = useState(false);
    const [mutationError, setMutationError] = useState(null);

    const create = async (payload) => {
        setMutating(true);
        try {
            const result = await manufacturingCostsApi.employees.create(payload);
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
        try {
            const result = await manufacturingCostsApi.employees.update(id, payload);
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
        try {
            await manufacturingCostsApi.employees.delete(id);
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
        data, meta, page, setPage,
        loading: listLoading || mutating,
        error: listError || mutationError,
        filters, setFilters, refetch,
        create, update, delete: deleteItem,
    };
};

// Hook for machine management (create + update + soft-delete).
export const useManufacturingCostMachines = (initialFilters = {}) => {
    const {
        data, meta, loading: listLoading, error: listError,
        filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => manufacturingCostsApi.machines.getAll(params), initialFilters);

    const [mutating, setMutating] = useState(false);
    const [mutationError, setMutationError] = useState(null);

    const create = async (payload) => {
        setMutating(true);
        try {
            const result = await manufacturingCostsApi.machines.create(payload);
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
        try {
            const result = await manufacturingCostsApi.machines.update(id, payload);
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
        try {
            await manufacturingCostsApi.machines.delete(id);
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
        data, meta, page, setPage,
        loading: listLoading || mutating,
        error: listError || mutationError,
        filters, setFilters, refetch,
        create, update, delete: deleteItem,
    };
};

// Hook for the singleton Rent/Electricity setting.
export const useFactoryOverheadSetting = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [mutating, setMutating] = useState(false);

    const fetchSetting = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await manufacturingCostsApi.factoryOverheadSetting.get();
            setData(result);
        } catch (err) {
            setError(err.message || 'Failed to fetch factory overhead setting');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSetting();
    }, [fetchSetting]);

    const update = async (payload) => {
        setMutating(true);
        try {
            const result = await manufacturingCostsApi.factoryOverheadSetting.update(payload);
            setData(result);
            return result;
        } finally {
            setMutating(false);
        }
    };

    return { data, loading: loading || mutating, error, refetch: fetchSetting, update };
};

// Hook for the Page 4 registry list (read-only — rows are auto-created server-side).
export const useManufacturingCostPayableEntities = (initialFilters = {}) => {
    const {
        data, meta, loading, error, filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => manufacturingCostsApi.payableEntities.getAll(params), initialFilters);

    return { data, meta, loading, error, filters, setFilters, page, setPage, refetch };
};

// Hook for one entity's payment history (create + delete), scoped by entityId.
export const useManufacturingCostEntityPayments = (entityId, initialFilters = {}) => {
    const {
        data, meta, loading: listLoading, error: listError,
        filters, setFilters, page, setPage, refetch,
    } = usePaginatedList(
        (params) => manufacturingCostsApi.payableEntities.getPayments(entityId, params),
        initialFilters, 25, [entityId],
    );

    const [mutating, setMutating] = useState(false);
    const [mutationError, setMutationError] = useState(null);

    const create = async (payload) => {
        setMutating(true);
        try {
            const result = await manufacturingCostsApi.payments.create(payload);
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
        try {
            await manufacturingCostsApi.payments.delete(id);
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
        data, meta, page, setPage,
        loading: listLoading || mutating,
        error: listError || mutationError,
        filters, setFilters, refetch,
        create, delete: deleteItem,
    };
};

// Hook for Page 5 — the flat, searchable, filterable list of every payment.
export const useManufacturingCostPayments = (initialFilters = {}) => {
    const {
        data, meta, loading, error, filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => manufacturingCostsApi.payments.getAll(params), initialFilters);

    return { data, meta, loading, error, filters, setFilters, page, setPage, refetch };
};
