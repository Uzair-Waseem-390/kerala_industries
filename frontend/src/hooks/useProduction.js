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

    const [settingTime, setSettingTime] = useState(false);
    const [setTimeError, setSetTimeErrorState] = useState(null);

    const [addingLabor, setAddingLabor] = useState(false);
    const [addLaborError, setAddLaborError] = useState(null);
    const [removingLaborId, setRemovingLaborId] = useState(null);

    const [addingMachine, setAddingMachine] = useState(false);
    const [addMachineError, setAddMachineError] = useState(null);
    const [removingMachineId, setRemovingMachineId] = useState(null);

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

    const setTime = async (payload) => {
        setSettingTime(true);
        setSetTimeErrorState(null);
        try {
            await productionApi.recipes.setTime(id, payload);
            await fetchRecipe();
        } catch (err) {
            setSetTimeErrorState(extractErrorMessage(err, 'Failed to save time'));
            throw err;
        } finally {
            setSettingTime(false);
        }
    };

    const addLabor = async (payload) => {
        setAddingLabor(true);
        setAddLaborError(null);
        try {
            await productionApi.recipes.addLabor(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to add employee'));
            throw err;
        } finally {
            setAddingLabor(false);
        }
    };

    const removeLabor = async (employeeId) => {
        setRemovingLaborId(employeeId);
        setAddLaborError(null);
        try {
            await productionApi.recipes.removeLabor(id, employeeId);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to remove employee'));
            throw err;
        } finally {
            setRemovingLaborId(null);
        }
    };

    const addMachine = async (payload) => {
        setAddingMachine(true);
        setAddMachineError(null);
        try {
            await productionApi.recipes.addMachine(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to add machine'));
            throw err;
        } finally {
            setAddingMachine(false);
        }
    };

    const removeMachine = async (machineId) => {
        setRemovingMachineId(machineId);
        setAddMachineError(null);
        try {
            await productionApi.recipes.removeMachine(id, machineId);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to remove machine'));
            throw err;
        } finally {
            setRemovingMachineId(null);
        }
    };

    return {
        recipe, loading, error, refetch: fetchRecipe,
        issueMaterial, issuing, issueError,
        updateIssuedMaterial, updatingMaterial, updateMaterialError,
        addBreakdownItem, addingBreakdown, addBreakdownError,
        updateDescription, updatingDescription, updateDescriptionError,
        finish, finishing, finishError,
        setTime, settingTime, setTimeError,
        addLabor, addingLabor, addLaborError,
        removeLabor, removingLaborId,
        addMachine, addingMachine, addMachineError,
        removeMachine, removingMachineId,
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

    const [settingTime, setSettingTime] = useState(false);
    const [setTimeError, setSetTimeErrorState] = useState(null);

    const [addingLabor, setAddingLabor] = useState(false);
    const [addLaborError, setAddLaborError] = useState(null);
    const [removingLaborId, setRemovingLaborId] = useState(null);

    const [addingMachine, setAddingMachine] = useState(false);
    const [addMachineError, setAddMachineError] = useState(null);
    const [removingMachineId, setRemovingMachineId] = useState(null);

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

    const setTime = async (payload) => {
        setSettingTime(true);
        setSetTimeErrorState(null);
        try {
            await productionApi.cuttingRecipes.setTime(id, payload);
            await fetchRecipe();
        } catch (err) {
            setSetTimeErrorState(extractErrorMessage(err, 'Failed to save time'));
            throw err;
        } finally {
            setSettingTime(false);
        }
    };

    const addLabor = async (payload) => {
        setAddingLabor(true);
        setAddLaborError(null);
        try {
            await productionApi.cuttingRecipes.addLabor(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to add employee'));
            throw err;
        } finally {
            setAddingLabor(false);
        }
    };

    const removeLabor = async (employeeId) => {
        setRemovingLaborId(employeeId);
        setAddLaborError(null);
        try {
            await productionApi.cuttingRecipes.removeLabor(id, employeeId);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to remove employee'));
            throw err;
        } finally {
            setRemovingLaborId(null);
        }
    };

    const addMachine = async (payload) => {
        setAddingMachine(true);
        setAddMachineError(null);
        try {
            await productionApi.cuttingRecipes.addMachine(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to add machine'));
            throw err;
        } finally {
            setAddingMachine(false);
        }
    };

    const removeMachine = async (machineId) => {
        setRemovingMachineId(machineId);
        setAddMachineError(null);
        try {
            await productionApi.cuttingRecipes.removeMachine(id, machineId);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to remove machine'));
            throw err;
        } finally {
            setRemovingMachineId(null);
        }
    };

    return {
        recipe, loading, error, refetch: fetchRecipe,
        issueMaterial, issuing, issueError,
        updateIssuedMaterial, updatingMaterial, updateMaterialError,
        addBreakdownItem, addingBreakdown, addBreakdownError,
        updateDescription, updatingDescription, updateDescriptionError,
        finish, finishing, finishError,
        setTime, settingTime, setTimeError,
        addLabor, addingLabor, addLaborError,
        removeLabor, removingLaborId,
        addMachine, addingMachine, addMachineError,
        removeMachine, removingMachineId,
    };
};

// Packing Recipes — same list/create shape as useCuttingRecipes, pointed at
// the packing-recipes endpoints.
export const usePackingRecipes = (initialFilters = {}) => {
    const {
        data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch,
    } = usePaginatedList((params) => productionApi.packingRecipes.getAll(params), initialFilters);

    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState(null);

    const create = async (payload) => {
        setCreating(true);
        setCreateError(null);
        try {
            const result = await productionApi.packingRecipes.create(payload);
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

// One Packing recipe's full detail + every mutation — mirrors
// useCuttingRecipeDetail's shape, adapted for Packing's two independent
// issued inputs (a piece + a material, no jumbo/cores kind split) and no
// breakdown stage — finish itself carries the FG put-away shelf_allocations.
export const usePackingRecipeDetail = (id) => {
    const [recipe, setRecipe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [issuingPiece, setIssuingPiece] = useState(false);
    const [issuePieceError, setIssuePieceError] = useState(null);

    const [updatingPiece, setUpdatingPiece] = useState(false);
    const [updatePieceError, setUpdatePieceError] = useState(null);

    const [issuingMaterial, setIssuingMaterial] = useState(false);
    const [issueMaterialError, setIssueMaterialError] = useState(null);

    const [updatingMaterial, setUpdatingMaterial] = useState(false);
    const [updateMaterialError, setUpdateMaterialError] = useState(null);

    const [updatingDescription, setUpdatingDescription] = useState(false);
    const [updateDescriptionError, setUpdateDescriptionError] = useState(null);

    const [finishing, setFinishing] = useState(false);
    const [finishError, setFinishError] = useState(null);

    const [settingTime, setSettingTime] = useState(false);
    const [setTimeError, setSetTimeErrorState] = useState(null);

    const [addingLabor, setAddingLabor] = useState(false);
    const [addLaborError, setAddLaborError] = useState(null);
    const [removingLaborId, setRemovingLaborId] = useState(null);

    const [addingMachine, setAddingMachine] = useState(false);
    const [addMachineError, setAddMachineError] = useState(null);
    const [removingMachineId, setRemovingMachineId] = useState(null);

    const fetchRecipe = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const data = await productionApi.packingRecipes.getById(id);
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

    const issuePiece = async (payload) => {
        setIssuingPiece(true);
        setIssuePieceError(null);
        try {
            await productionApi.packingRecipes.issuePiece(id, payload);
            await fetchRecipe();
        } catch (err) {
            setIssuePieceError(extractErrorMessage(err, 'Failed to issue piece'));
            throw err;
        } finally {
            setIssuingPiece(false);
        }
    };

    const updateIssuedPiece = async (payload) => {
        setUpdatingPiece(true);
        setUpdatePieceError(null);
        try {
            await productionApi.packingRecipes.updateIssuedPiece(id, payload);
            await fetchRecipe();
        } catch (err) {
            setUpdatePieceError(extractErrorMessage(err, 'Failed to update issued piece'));
            throw err;
        } finally {
            setUpdatingPiece(false);
        }
    };

    const issueMaterial = async (payload) => {
        setIssuingMaterial(true);
        setIssueMaterialError(null);
        try {
            await productionApi.packingRecipes.issueMaterial(id, payload);
            await fetchRecipe();
        } catch (err) {
            setIssueMaterialError(extractErrorMessage(err, 'Failed to issue material'));
            throw err;
        } finally {
            setIssuingMaterial(false);
        }
    };

    const updateIssuedMaterial = async (payload) => {
        setUpdatingMaterial(true);
        setUpdateMaterialError(null);
        try {
            await productionApi.packingRecipes.updateIssuedMaterial(id, payload);
            await fetchRecipe();
        } catch (err) {
            setUpdateMaterialError(extractErrorMessage(err, 'Failed to update issued material'));
            throw err;
        } finally {
            setUpdatingMaterial(false);
        }
    };

    const updateDescription = async (description) => {
        setUpdatingDescription(true);
        setUpdateDescriptionError(null);
        try {
            await productionApi.packingRecipes.updateDescription(id, { description });
            await fetchRecipe();
        } catch (err) {
            setUpdateDescriptionError(extractErrorMessage(err, 'Failed to update description'));
            throw err;
        } finally {
            setUpdatingDescription(false);
        }
    };

    const finish = async (shelfAllocations) => {
        setFinishing(true);
        setFinishError(null);
        try {
            await productionApi.packingRecipes.finish(id, { shelf_allocations: shelfAllocations });
            await fetchRecipe();
        } catch (err) {
            setFinishError(extractErrorMessage(err, 'Failed to finish recipe'));
            throw err;
        } finally {
            setFinishing(false);
        }
    };

    const setTime = async (payload) => {
        setSettingTime(true);
        setSetTimeErrorState(null);
        try {
            await productionApi.packingRecipes.setTime(id, payload);
            await fetchRecipe();
        } catch (err) {
            setSetTimeErrorState(extractErrorMessage(err, 'Failed to save time'));
            throw err;
        } finally {
            setSettingTime(false);
        }
    };

    const addLabor = async (payload) => {
        setAddingLabor(true);
        setAddLaborError(null);
        try {
            await productionApi.packingRecipes.addLabor(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to add employee'));
            throw err;
        } finally {
            setAddingLabor(false);
        }
    };

    const removeLabor = async (employeeId) => {
        setRemovingLaborId(employeeId);
        setAddLaborError(null);
        try {
            await productionApi.packingRecipes.removeLabor(id, employeeId);
            await fetchRecipe();
        } catch (err) {
            setAddLaborError(extractErrorMessage(err, 'Failed to remove employee'));
            throw err;
        } finally {
            setRemovingLaborId(null);
        }
    };

    const addMachine = async (payload) => {
        setAddingMachine(true);
        setAddMachineError(null);
        try {
            await productionApi.packingRecipes.addMachine(id, payload);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to add machine'));
            throw err;
        } finally {
            setAddingMachine(false);
        }
    };

    const removeMachine = async (machineId) => {
        setRemovingMachineId(machineId);
        setAddMachineError(null);
        try {
            await productionApi.packingRecipes.removeMachine(id, machineId);
            await fetchRecipe();
        } catch (err) {
            setAddMachineError(extractErrorMessage(err, 'Failed to remove machine'));
            throw err;
        } finally {
            setRemovingMachineId(null);
        }
    };

    return {
        recipe, loading, error, refetch: fetchRecipe,
        issuePiece, issuingPiece, issuePieceError,
        updateIssuedPiece, updatingPiece, updatePieceError,
        issueMaterial, issuingMaterial, issueMaterialError,
        updateIssuedMaterial, updatingMaterial, updateMaterialError,
        updateDescription, updatingDescription, updateDescriptionError,
        finish, finishing, finishError,
        setTime, settingTime, setTimeError,
        addLabor, addingLabor, addLaborError,
        removeLabor, removingLaborId,
        addMachine, addingMachine, addMachineError,
        removeMachine, removingMachineId,
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

// FG Inventory — read-only paginated list, mirrors useWipInventory. Powers
// the standalone Finished Goods page; AllInventoryPage's finished_goods tab
// goes through useCombinedInventory (useInventory.js) instead.
export const useFgInventory = (initialFilters = {}) => {
    const { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch } =
        usePaginatedList((params) => productionApi.fgInventory.getAll(params), initialFilters);
    return { data, meta, loading, initialLoading, error, filters, setFilters, page, setPage, refetch };
};
