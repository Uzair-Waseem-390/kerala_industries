import { useState, useEffect, useCallback } from 'react';
import { productionApi } from '../services/productionApi';
import { usePaginatedList } from './usePaginatedList';
import { extractErrorMessage } from '../utils/errorMessage';

// Recipes — paginated list with status/search filters, plus a create
// mutation (name + description; recipe_type is a constant the page sends).
export const useRecipes = (initialFilters = {}) => {
    const {
        data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => productionApi.recipes.getAll(params), initialFilters);

    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState(null);

    const create = async (payload) => {
        setCreating(true);
        setCreateError(null);
        try {
            const result = await productionApi.recipes.create(payload);
            await refetch();
            return result;
        } catch (err) {
            setCreateError(extractErrorMessage(err, 'Failed to create recipe'));
            throw err;
        } finally {
            setCreating(false);
        }
    };

    return {
        data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch,
        creating, createError, create,
    };
};

// One recipe's full detail + every mutation that can happen to it while
// under_processing (issue/adjust materials, add breakdown items, finish).
// Each mutation exposes its own `mutating`/`error` pair so the detail page
// can show inline feedback per-section without one busy flag blocking the
// whole screen.
export const useRecipeDetail = (id) => {
    const [recipe, setRecipe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [issuing, setIssuing] = useState(false);
    const [issueError, setIssueError] = useState(null);

    const [updatingMaterial, setUpdatingMaterial] = useState(false);
    const [updateMaterialError, setUpdateMaterialError] = useState(null);

    const [addingBreakdown, setAddingBreakdown] = useState(false);
    const [addBreakdownError, setAddBreakdownError] = useState(null);

    const [updatingDescription, setUpdatingDescription] = useState(false);
    const [updateDescriptionError, setUpdateDescriptionError] = useState(null);

    const [finishing, setFinishing] = useState(false);
    const [finishError, setFinishError] = useState(null);

    const fetchRecipe = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const data = await productionApi.recipes.getById(id);
            setRecipe(data);
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to load recipe'));
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchRecipe();
    }, [fetchRecipe]);

    const issueMaterial = async (payload) => {
        setIssuing(true);
        setIssueError(null);
        try {
            await productionApi.recipes.issueMaterial(id, payload);
            await fetchRecipe();
        } catch (err) {
            setIssueError(extractErrorMessage(err, 'Failed to issue material'));
            throw err;
        } finally {
            setIssuing(false);
        }
    };

    const updateIssuedMaterial = async (kind, payload) => {
        setUpdatingMaterial(true);
        setUpdateMaterialError(null);
        try {
            await productionApi.recipes.updateIssuedMaterial(id, kind, payload);
            await fetchRecipe();
        } catch (err) {
            setUpdateMaterialError(extractErrorMessage(err, 'Failed to update issued material'));
            throw err;
        } finally {
            setUpdatingMaterial(false);
        }
    };

    const addBreakdownItem = async (payload) => {
        setAddingBreakdown(true);
        setAddBreakdownError(null);
        try {
            await productionApi.recipes.addBreakdownItem(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddBreakdownError(extractErrorMessage(err, 'Failed to add breakdown item'));
            throw err;
        } finally {
            setAddingBreakdown(false);
        }
    };

    // Description is optional at create time, editable any time the recipe
    // is still under_processing, and required before finish (enforced
    // server-side too — this is a UX convenience, not the boundary).
    const updateDescription = async (description) => {
        setUpdatingDescription(true);
        setUpdateDescriptionError(null);
        try {
            await productionApi.recipes.updateDescription(id, { description });
            await fetchRecipe();
        } catch (err) {
            setUpdateDescriptionError(extractErrorMessage(err, 'Failed to update description'));
            throw err;
        } finally {
            setUpdatingDescription(false);
        }
    };

    const finish = async () => {
        setFinishing(true);
        setFinishError(null);
        try {
            await productionApi.recipes.finish(id);
            await fetchRecipe();
        } catch (err) {
            setFinishError(extractErrorMessage(err, 'Failed to finish recipe'));
            throw err;
        } finally {
            setFinishing(false);
        }
    };

    return {
        recipe, loading, error, refetch: fetchRecipe,
        issueMaterial, issuing, issueError,
        updateIssuedMaterial, updatingMaterial, updateMaterialError,
        addBreakdownItem, addingBreakdown, addBreakdownError,
        updateDescription, updatingDescription, updateDescriptionError,
        finish, finishing, finishError,
    };
};

// Cutting Recipes — same list/create shape as useRecipes, just pointed at
// the cutting-recipes endpoints.
export const useCuttingRecipes = (initialFilters = {}) => {
    const {
        data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => productionApi.cuttingRecipes.getAll(params), initialFilters);

    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState(null);

    const create = async (payload) => {
        setCreating(true);
        setCreateError(null);
        try {
            const result = await productionApi.cuttingRecipes.create(payload);
            await refetch();
            return result;
        } catch (err) {
            setCreateError(extractErrorMessage(err, 'Failed to create recipe'));
            throw err;
        } finally {
            setCreating(false);
        }
    };

    return {
        data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch,
        creating, createError, create,
    };
};

// One Cutting recipe's full detail + every mutation — mirrors
// useRecipeDetail's shape, adapted for Cutting's single issued material
// (no jumbo/cores kind split) and length_mm+quantity breakdown items.
export const useCuttingRecipeDetail = (id) => {
    const [recipe, setRecipe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [issuing, setIssuing] = useState(false);
    const [issueError, setIssueError] = useState(null);

    const [updatingMaterial, setUpdatingMaterial] = useState(false);
    const [updateMaterialError, setUpdateMaterialError] = useState(null);

    const [addingBreakdown, setAddingBreakdown] = useState(false);
    const [addBreakdownError, setAddBreakdownError] = useState(null);

    const [updatingDescription, setUpdatingDescription] = useState(false);
    const [updateDescriptionError, setUpdateDescriptionError] = useState(null);

    const [finishing, setFinishing] = useState(false);
    const [finishError, setFinishError] = useState(null);

    const fetchRecipe = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const data = await productionApi.cuttingRecipes.getById(id);
            setRecipe(data);
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to load recipe'));
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchRecipe();
    }, [fetchRecipe]);

    const issueMaterial = async (payload) => {
        setIssuing(true);
        setIssueError(null);
        try {
            await productionApi.cuttingRecipes.issueMaterial(id, payload);
            await fetchRecipe();
        } catch (err) {
            setIssueError(extractErrorMessage(err, 'Failed to issue material'));
            throw err;
        } finally {
            setIssuing(false);
        }
    };

    const updateIssuedMaterial = async (payload) => {
        setUpdatingMaterial(true);
        setUpdateMaterialError(null);
        try {
            await productionApi.cuttingRecipes.updateIssuedMaterial(id, payload);
            await fetchRecipe();
        } catch (err) {
            setUpdateMaterialError(extractErrorMessage(err, 'Failed to update issued material'));
            throw err;
        } finally {
            setUpdatingMaterial(false);
        }
    };

    const addBreakdownItem = async (payload) => {
        setAddingBreakdown(true);
        setAddBreakdownError(null);
        try {
            await productionApi.cuttingRecipes.addBreakdownItem(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddBreakdownError(extractErrorMessage(err, 'Failed to add breakdown item'));
            throw err;
        } finally {
            setAddingBreakdown(false);
        }
    };

    const updateDescription = async (description) => {
        setUpdatingDescription(true);
        setUpdateDescriptionError(null);
        try {
            await productionApi.cuttingRecipes.updateDescription(id, { description });
            await fetchRecipe();
        } catch (err) {
            setUpdateDescriptionError(extractErrorMessage(err, 'Failed to update description'));
            throw err;
        } finally {
            setUpdatingDescription(false);
        }
    };

    const finish = async () => {
        setFinishing(true);
        setFinishError(null);
        try {
            await productionApi.cuttingRecipes.finish(id);
            await fetchRecipe();
        } catch (err) {
            setFinishError(extractErrorMessage(err, 'Failed to finish recipe'));
            throw err;
        } finally {
            setFinishing(false);
        }
    };

    return {
        recipe, loading, error, refetch: fetchRecipe,
        issueMaterial, issuing, issueError,
        updateIssuedMaterial, updatingMaterial, updateMaterialError,
        addBreakdownItem, addingBreakdown, addBreakdownError,
        updateDescription, updatingDescription, updateDescriptionError,
        finish, finishing, finishError,
    };
};

// WIP Products — read-only paginated list.
export const useWipProducts = (initialFilters = {}) => {
    const { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch } =
        usePaginatedList((params) => productionApi.wipProducts.getAll(params), initialFilters);
    return { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch };
};

// WIP Inventory — read-only paginated list. Kept for the standalone WIP
// Inventory page; InventoryPage's WIP family filter goes through
// useInventoryList (useInventory.js) instead so it shares one list/pagination
// UI with the RM view.
export const useWipInventory = (initialFilters = {}) => {
    const { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch } =
        usePaginatedList((params) => productionApi.wipInventory.getAll(params), initialFilters);
    return { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch };
};
