import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Pencil, CheckCircle2, Plus, PackageCheck } from 'lucide-react';
import { usePackingRecipeDetail } from '../../hooks/useProduction';
import { productionApi } from '../../services/productionApi';
import { purchasesApi } from '../../services/purchasesApi';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Card from '../../components/ui/Card';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Input from '../../components/ui/Input';
import SearchableSelect from '../../components/ui/SearchableSelect';
import Modal from '../../components/ui/Modal';
import InlineAlert from '../../components/ui/InlineAlert';
import ShelfAllocationEditor from '../../components/shared/ShelfAllocationEditor';
import RecipeStatusBadge from '../../components/production/RecipeStatusBadge';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const EPSILON = 0.0001;
const closeEnough = (a, b) => Math.abs(a - b) < EPSILON;
const sumAlloc = (list) => list.reduce((s, a) => s + (parseFloat(a.quantity) || 0), 0);
const toShelfPayload = (list) =>
    list
        .filter((a) => a.shelf_id && a.quantity)
        .map((a) => ({ shelf_id: parseInt(a.shelf_id, 10), quantity: parseFloat(a.quantity) }));

// Any-shelf search — put-away side only (finish's FG destination, and
// returning issued stock on a quantity decrease). The consumption side
// (issuing more on an increase) uses real candidate shelves instead.
const searchShelvesForPutAway = async (query) => {
    const res = await purchasesApi.shelves.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((s) => ({ value: s.id, label: s.name, name: s.name }));
};

const searchIssuableCuttingPieces = async (query) => {
    const res = await productionApi.issuableCuttingPieces.getAll({ search: query });
    const results = res?.results ?? res ?? [];
    return results.map((p) => ({
        value: p.id,
        label: `${p.name} — ${p.available_quantity} available`,
        name: p.name,
    }));
};

const searchIssuablePackingMaterial = async (query) => {
    const res = await productionApi.issuableProducts.getAll({ kind: 'packing', search: query });
    const results = res?.results ?? res ?? [];
    return results.map((p) => ({
        value: p.id,
        label: `${p.name}${p.code ? ` (${p.code})` : ''} — ${p.available_quantity} available`,
        name: p.name,
    }));
};

const loadWipCandidateShelves = async (wipProductId) => {
    const res = await productionApi.wipShelfCandidates.getAll(wipProductId);
    return Array.isArray(res) ? res : (res?.results ?? []);
};

const loadRmCandidateShelves = async (productId) => {
    const res = await purchasesApi.shelves.getCandidates(productId);
    return Array.isArray(res) ? res : (res?.results ?? []);
};

// The single issued-piece slot for a Packing recipe (one Cut Piece, WIP
// stage=cutting). Issue form when not yet issued, current quantity + inline
// "change quantity" editor when it is — mirrors CuttingIssuedMaterialPanel.
const IssuedPiecePanel = ({ piece, disabled, onIssue, onUpdate }) => {
    const { toast } = useToast();

    const [productId, setProductId] = useState('');
    const [productLabel, setProductLabel] = useState('');
    const [quantity, setQuantity] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [candidateShelves, setCandidateShelves] = useState([]);
    const [shelvesLoading, setShelvesLoading] = useState(false);
    const [issuing, setIssuing] = useState(false);
    const [issueError, setIssueError] = useState('');

    const [editing, setEditing] = useState(false);
    const [editQuantity, setEditQuantity] = useState('');
    const [editAllocations, setEditAllocations] = useState([]);
    const [editShelves, setEditShelves] = useState([]);
    const [editShelvesLoading, setEditShelvesLoading] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [updateError, setUpdateError] = useState('');

    const handleSelectProduct = async (val, option) => {
        setProductId(val);
        setProductLabel(option?.name || option?.label || '');
        setAllocations([]);
        setShelvesLoading(true);
        try {
            setCandidateShelves(await loadWipCandidateShelves(val));
        } catch (err) {
            toast.error(extractErrorMessage(err, 'Failed to load candidate shelves'));
            setCandidateShelves([]);
        } finally {
            setShelvesLoading(false);
        }
    };

    const issueQty = parseFloat(quantity) || 0;
    const canIssue = productId && issueQty > 0 && closeEnough(sumAlloc(allocations), issueQty);

    const handleIssueSubmit = async (e) => {
        e.preventDefault();
        setIssueError('');
        setIssuing(true);
        try {
            await onIssue({
                wip_product_id: productId,
                quantity: issueQty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Piece issued');
            setProductId(''); setProductLabel(''); setQuantity(''); setAllocations([]);
        } catch (err) {
            setIssueError(extractErrorMessage(err, 'Failed to issue piece'));
        } finally {
            setIssuing(false);
        }
    };

    const startEdit = async () => {
        setEditing(true);
        setUpdateError('');
        setEditQuantity(String(piece.quantity));
        setEditAllocations([]);
        if (piece?.wip_product?.id) {
            setEditShelvesLoading(true);
            try {
                setEditShelves(await loadWipCandidateShelves(piece.wip_product.id));
            } catch {
                setEditShelves([]);
            } finally {
                setEditShelvesLoading(false);
            }
        }
    };

    const currentQty = parseFloat(piece?.quantity || 0);
    const newQty = parseFloat(editQuantity || 0);
    const delta = newQty - currentQty;
    const editMode = delta >= 0 ? 'consumption' : 'putaway';
    const requiredQuantity = Math.abs(delta);
    const canUpdate = delta !== 0 && newQty >= 0 && closeEnough(sumAlloc(editAllocations), requiredQuantity);

    const handleEditSubmit = async (e) => {
        e.preventDefault();
        setUpdateError('');
        setUpdating(true);
        try {
            await onUpdate({
                quantity: newQty,
                shelf_allocations: toShelfPayload(editAllocations),
            });
            toast.success('Issued quantity updated');
            setEditing(false);
        } catch (err) {
            setUpdateError(extractErrorMessage(err, 'Failed to update issued piece'));
        } finally {
            setUpdating(false);
        }
    };

    return (
        <Card className="p-6" hover={false}>
            <h3 className="font-semibold text-neutral-900 mb-3">Issued Piece</h3>

            {!piece ? (
                disabled ? (
                    <p className="text-sm text-neutral-400 italic">Not issued.</p>
                ) : (
                    <form onSubmit={handleIssueSubmit} className="space-y-4">
                        {issueError && <InlineAlert variant="error" message={issueError} />}
                        <SearchableSelect
                            label="Cut Piece"
                            value={productId}
                            selectedLabel={productLabel}
                            onChange={handleSelectProduct}
                            onSearch={searchIssuableCuttingPieces}
                            placeholder="Search by name..."
                            required
                        />
                        <Input
                            label="Quantity"
                            type="number"
                            min="0.0001"
                            step="0.0001"
                            value={quantity}
                            onChange={(e) => { setQuantity(e.target.value); setAllocations([]); }}
                            required
                        />
                        {productId && (
                            shelvesLoading ? (
                                <p className="text-sm text-neutral-400">Loading shelves holding this product...</p>
                            ) : (
                                <ShelfAllocationEditor
                                    value={allocations}
                                    onChange={setAllocations}
                                    shelves={candidateShelves}
                                    requiredQuantity={issueQty}
                                    mode="consumption"
                                />
                            )
                        )}
                        <div className="flex justify-end">
                            <Button type="submit" size="sm" icon={Plus} loading={issuing} disabled={!canIssue}>
                                Issue Piece
                            </Button>
                        </div>
                    </form>
                )
            ) : (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="font-medium">{piece.wip_product?.name}</p>
                            <p className="text-sm text-neutral-500">Quantity: {piece.quantity}</p>
                        </div>
                        {!disabled && !editing && (
                            <Button variant="secondary" size="sm" icon={Pencil} onClick={startEdit}>
                                Change Quantity
                            </Button>
                        )}
                    </div>

                    {(piece.consumptions?.length > 0 || piece.shelf_draws?.length > 0) && (
                        <div>
                            <p className="text-xs font-medium text-neutral-500 mb-1">Drawn from</p>
                            <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 text-sm">
                                {piece.consumptions?.map((c) => (
                                    <div key={`c-${c.id}`} className="flex items-center justify-between px-3 py-1.5">
                                        <span>
                                            {c.product_name}
                                            {c.source_recipe_number && (
                                                <span className="text-neutral-400"> — from {c.source_recipe_number}</span>
                                            )}
                                        </span>
                                        <span className="text-neutral-500">
                                            {c.quantity} @ {c.unit_cost != null ? parseFloat(c.unit_cost).toFixed(2) : '—'}
                                        </span>
                                    </div>
                                ))}
                                {piece.shelf_draws?.map((d) => (
                                    <div key={`s-${d.id}`} className="flex items-center justify-between px-3 py-1.5">
                                        <span className="text-neutral-500">Shelf: {d.shelf_name}</span>
                                        <span className={d.direction === 'return' ? 'text-warning-600 font-medium' : 'text-neutral-500'}>
                                            {d.direction === 'return' ? 'Returned' : 'Drawn'} {d.quantity}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {editing && (
                        <form onSubmit={handleEditSubmit} className="space-y-4 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
                            {updateError && <InlineAlert variant="error" message={updateError} />}
                            <Input
                                label="New total quantity"
                                type="number"
                                min="0"
                                step="0.0001"
                                value={editQuantity}
                                onChange={(e) => { setEditQuantity(e.target.value); setEditAllocations([]); }}
                                required
                            />
                            {delta !== 0 && (
                                <>
                                    <p className="text-sm text-neutral-500">
                                        {delta > 0
                                            ? `Drawing ${requiredQuantity} more — pick which shelf(s) to draw it from.`
                                            : `Returning ${requiredQuantity} — pick which shelf(s) to put it away on.`}
                                    </p>
                                    {editMode === 'consumption' ? (
                                        editShelvesLoading ? (
                                            <p className="text-sm text-neutral-400">Loading shelves holding this product...</p>
                                        ) : (
                                            <ShelfAllocationEditor
                                                value={editAllocations}
                                                onChange={setEditAllocations}
                                                shelves={editShelves}
                                                requiredQuantity={requiredQuantity}
                                                mode="consumption"
                                            />
                                        )
                                    ) : (
                                        <ShelfAllocationEditor
                                            value={editAllocations}
                                            onChange={setEditAllocations}
                                            onSearchShelves={searchShelvesForPutAway}
                                            requiredQuantity={requiredQuantity}
                                            mode="putaway"
                                        />
                                    )}
                                </>
                            )}
                            <div className="flex justify-end gap-3">
                                <Button type="button" variant="secondary" size="sm" onClick={() => setEditing(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit" size="sm" loading={updating} disabled={!canUpdate}>
                                    Save
                                </Button>
                            </div>
                        </form>
                    )}
                </div>
            )}
        </Card>
    );
};

// The single issued-material slot for a Packing recipe (RM Packing Material,
// in kg) — mirrors Rewinding's IssuedMaterialPanel, no jumbo/cores kind split.
const IssuedMaterialPanel = ({ material, disabled, onIssue, onUpdate }) => {
    const { toast } = useToast();

    const [productId, setProductId] = useState('');
    const [productLabel, setProductLabel] = useState('');
    const [quantity, setQuantity] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [candidateShelves, setCandidateShelves] = useState([]);
    const [shelvesLoading, setShelvesLoading] = useState(false);
    const [issuing, setIssuing] = useState(false);
    const [issueError, setIssueError] = useState('');

    const [editing, setEditing] = useState(false);
    const [editQuantity, setEditQuantity] = useState('');
    const [editAllocations, setEditAllocations] = useState([]);
    const [editShelves, setEditShelves] = useState([]);
    const [editShelvesLoading, setEditShelvesLoading] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [updateError, setUpdateError] = useState('');

    const handleSelectProduct = async (val, option) => {
        setProductId(val);
        setProductLabel(option?.name || option?.label || '');
        setAllocations([]);
        setShelvesLoading(true);
        try {
            setCandidateShelves(await loadRmCandidateShelves(val));
        } catch (err) {
            toast.error(extractErrorMessage(err, 'Failed to load candidate shelves'));
            setCandidateShelves([]);
        } finally {
            setShelvesLoading(false);
        }
    };

    const issueQty = parseFloat(quantity) || 0;
    const canIssue = productId && issueQty > 0 && closeEnough(sumAlloc(allocations), issueQty);

    const handleIssueSubmit = async (e) => {
        e.preventDefault();
        setIssueError('');
        setIssuing(true);
        try {
            await onIssue({
                product_id: productId,
                quantity: issueQty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Packing material issued');
            setProductId(''); setProductLabel(''); setQuantity(''); setAllocations([]); setCandidateShelves([]);
        } catch (err) {
            setIssueError(extractErrorMessage(err, 'Failed to issue material'));
        } finally {
            setIssuing(false);
        }
    };

    const startEdit = async () => {
        setEditing(true);
        setUpdateError('');
        setEditQuantity(String(material.quantity));
        setEditAllocations([]);
        if (material?.product_id) {
            setEditShelvesLoading(true);
            try {
                setEditShelves(await loadRmCandidateShelves(material.product_id));
            } catch {
                setEditShelves([]);
            } finally {
                setEditShelvesLoading(false);
            }
        }
    };

    const currentQty = parseFloat(material?.quantity || 0);
    const newQty = parseFloat(editQuantity || 0);
    const delta = newQty - currentQty;
    const editMode = delta >= 0 ? 'consumption' : 'putaway';
    const requiredQuantity = Math.abs(delta);
    const canUpdate = delta !== 0 && newQty >= 0 && closeEnough(sumAlloc(editAllocations), requiredQuantity);

    const handleEditSubmit = async (e) => {
        e.preventDefault();
        setUpdateError('');
        setUpdating(true);
        try {
            await onUpdate({
                quantity: newQty,
                shelf_allocations: toShelfPayload(editAllocations),
            });
            toast.success('Issued quantity updated');
            setEditing(false);
        } catch (err) {
            setUpdateError(extractErrorMessage(err, 'Failed to update issued material'));
        } finally {
            setUpdating(false);
        }
    };

    return (
        <Card className="p-6" hover={false}>
            <h3 className="font-semibold text-neutral-900 mb-3">Packing Material</h3>

            {!material ? (
                disabled ? (
                    <p className="text-sm text-neutral-400 italic">Not issued.</p>
                ) : (
                    <form onSubmit={handleIssueSubmit} className="space-y-4">
                        {issueError && <InlineAlert variant="error" message={issueError} />}
                        <SearchableSelect
                            label="Packing Material product"
                            value={productId}
                            selectedLabel={productLabel}
                            onChange={handleSelectProduct}
                            onSearch={searchIssuablePackingMaterial}
                            placeholder="Search by name or code..."
                            required
                        />
                        <Input
                            label="Quantity (kg)"
                            type="number"
                            min="0.0001"
                            step="0.0001"
                            value={quantity}
                            onChange={(e) => { setQuantity(e.target.value); setAllocations([]); }}
                            required
                        />
                        {productId && (
                            shelvesLoading ? (
                                <div className="flex items-center py-2"><LoadingSpinner size="sm" /></div>
                            ) : (
                                <ShelfAllocationEditor
                                    value={allocations}
                                    onChange={setAllocations}
                                    shelves={candidateShelves}
                                    requiredQuantity={issueQty}
                                    mode="consumption"
                                    productId={productId}
                                    autoAllocateApi={purchasesApi.shelves.autoAllocate}
                                />
                            )
                        )}
                        <div className="flex justify-end">
                            <Button type="submit" size="sm" icon={Plus} loading={issuing} disabled={!canIssue}>
                                Issue Material
                            </Button>
                        </div>
                    </form>
                )
            ) : (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="font-medium">{material.product_name} {material.product_code ? `(${material.product_code})` : ''}</p>
                            <p className="text-sm text-neutral-500">Quantity: {material.quantity}</p>
                        </div>
                        {!disabled && !editing && (
                            <Button variant="secondary" size="sm" icon={Pencil} onClick={startEdit}>
                                Change Quantity
                            </Button>
                        )}
                    </div>

                    {(material.consumptions?.length > 0 || material.shelf_draws?.length > 0) && (
                        <div>
                            <p className="text-xs font-medium text-neutral-500 mb-1">Drawn from</p>
                            <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 text-sm">
                                {material.consumptions?.map((c, i) => (
                                    <div key={`c-${c.purchase_item_id ?? i}`} className="flex items-center justify-between px-3 py-1.5">
                                        <span>{c.product_name}</span>
                                        <span className="text-neutral-500">
                                            {c.quantity} @ {c.unit_cost != null ? parseFloat(c.unit_cost).toFixed(2) : '—'}
                                        </span>
                                    </div>
                                ))}
                                {material.shelf_draws?.map((d) => (
                                    <div key={`s-${d.id}`} className="flex items-center justify-between px-3 py-1.5">
                                        <span className="text-neutral-500">Shelf: {d.shelf_name}</span>
                                        <span className={d.direction === 'return' ? 'text-warning-600 font-medium' : 'text-neutral-500'}>
                                            {d.direction === 'return' ? 'Returned' : 'Drawn'} {d.quantity}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {editing && (
                        <form onSubmit={handleEditSubmit} className="space-y-4 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
                            {updateError && <InlineAlert variant="error" message={updateError} />}
                            <Input
                                label="New total quantity"
                                type="number"
                                min="0"
                                step="0.0001"
                                value={editQuantity}
                                onChange={(e) => { setEditQuantity(e.target.value); setEditAllocations([]); }}
                                required
                            />
                            {delta !== 0 && (
                                <>
                                    <p className="text-sm text-neutral-500">
                                        {delta > 0
                                            ? `Pulling ${requiredQuantity} more — pick shelves to draw it from.`
                                            : `Returning ${requiredQuantity} to raw material — pick a shelf to put it away on.`}
                                    </p>
                                    {editMode === 'consumption' && editShelvesLoading ? (
                                        <div className="flex items-center py-2"><LoadingSpinner size="sm" /></div>
                                    ) : (
                                        <ShelfAllocationEditor
                                            value={editAllocations}
                                            onChange={setEditAllocations}
                                            shelves={editShelves}
                                            onSearchShelves={searchShelvesForPutAway}
                                            requiredQuantity={requiredQuantity}
                                            mode={editMode}
                                            productId={material.product_id}
                                            autoAllocateApi={editMode === 'consumption' ? purchasesApi.shelves.autoAllocate : undefined}
                                        />
                                    )}
                                </>
                            )}
                            <div className="flex justify-end gap-3">
                                <Button type="button" variant="secondary" size="sm" onClick={() => setEditing(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit" size="sm" loading={updating} disabled={!canUpdate}>
                                    Save
                                </Button>
                            </div>
                        </form>
                    )}
                </div>
            )}
        </Card>
    );
};

// Finish modal — Packing has no breakdown stage, so the FG put-away
// shelf_allocations (sized to the issued piece's quantity, 1:1 into
// Finished Goods) are picked here at finish time instead.
const FinishPackingModal = ({ isOpen, onClose, requiredQuantity, onFinish, finishing }) => {
    const [allocations, setAllocations] = useState([]);
    const [error, setError] = useState('');

    const canFinish = requiredQuantity > 0 && closeEnough(sumAlloc(allocations), requiredQuantity);

    const handleClose = () => {
        setAllocations([]);
        setError('');
        onClose();
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        try {
            await onFinish(toShelfPayload(allocations));
            setAllocations([]);
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to finish recipe'));
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={handleClose} title="Finish Recipe">
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <InlineAlert variant="error" message={error} />}
                <p className="text-sm text-neutral-500">
                    Pick where to put away the {requiredQuantity} finished-goods unit(s) this recipe produces.
                    This locks the recipe permanently — no further edits will be possible.
                </p>
                <ShelfAllocationEditor
                    value={allocations}
                    onChange={setAllocations}
                    onSearchShelves={searchShelvesForPutAway}
                    requiredQuantity={requiredQuantity}
                    mode="putaway"
                />
                <div className="flex justify-end gap-3 pt-2">
                    <Button type="button" variant="secondary" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button type="submit" variant="success" loading={finishing} disabled={!canFinish}>
                        Finish Recipe
                    </Button>
                </div>
            </form>
        </Modal>
    );
};

const PackingRecipeDetailPage = () => {
    const { id } = useParams();
    const { toast } = useToast();
    const {
        recipe, loading, error, refetch,
        issuePiece, updateIssuedPiece,
        issueMaterial, updateIssuedMaterial,
        updateDescription, updatingDescription,
        finish, finishing,
    } = usePackingRecipeDetail(id);

    const [showFinishModal, setShowFinishModal] = useState(false);

    const [editingDescription, setEditingDescription] = useState(false);
    const [descriptionDraft, setDescriptionDraft] = useState('');
    const [descriptionError, setDescriptionError] = useState('');

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    if (!recipe) {
        return (
            <div className="text-center py-12">
                {error ? (
                    <div className="max-w-md mx-auto text-left">
                        <InlineAlert variant="error" message={error} onRetry={refetch} />
                    </div>
                ) : (
                    <h2 className="text-2xl font-semibold text-neutral-900">Recipe Not Found</h2>
                )}
                <BackLink to="/production/packing-recipes" className="mt-4">Back to Packing Recipes</BackLink>
            </div>
        );
    }

    const isFinished = recipe.status === 'finished';
    const issuedPiece = recipe.packing_issued_piece || null;
    const issuedMaterial = recipe.packing_issued_material || null;
    const outputItem = recipe.packing_output_item || null;
    const hasDescription = !!recipe.description?.trim();
    const canFinish = !!issuedPiece && !!issuedMaterial && hasDescription;

    const startEditDescription = () => {
        setDescriptionDraft(recipe.description || '');
        setDescriptionError('');
        setEditingDescription(true);
    };

    const handleSaveDescription = async (e) => {
        e.preventDefault();
        setDescriptionError('');
        try {
            await updateDescription(descriptionDraft);
            toast.success('Description updated');
            setEditingDescription(false);
        } catch (err) {
            setDescriptionError(extractErrorMessage(err, 'Failed to update description'));
        }
    };

    const handleFinish = async (shelfAllocations) => {
        await finish(shelfAllocations);
        toast.success('Recipe finished');
        setShowFinishModal(false);
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <BackLink to="/production/packing-recipes">Back to Packing Recipes</BackLink>
                    <h1 className="text-3xl font-bold text-neutral-900 mt-1">{recipe.recipe_number} — {recipe.name}</h1>
                    <div className="flex gap-2 mt-1 flex-wrap items-center">
                        <RecipeStatusBadge status={recipe.status} />
                        {isFinished && recipe.cost_per_unit != null && (
                            <span className="text-sm font-semibold text-primary-700">
                                Cost / unit: {parseFloat(recipe.cost_per_unit).toFixed(2)}
                            </span>
                        )}
                    </div>
                </div>
                {!isFinished && (
                    <div className="flex flex-col items-end gap-1">
                        <Button
                            variant="success"
                            icon={CheckCircle2}
                            disabled={!canFinish}
                            onClick={() => setShowFinishModal(true)}
                        >
                            Finish Recipe
                        </Button>
                        {!hasDescription && (
                            <p className="text-xs text-error-600">Add a description before finishing.</p>
                        )}
                        {hasDescription && !issuedPiece && (
                            <p className="text-xs text-error-600">Issue a piece before finishing.</p>
                        )}
                        {hasDescription && issuedPiece && !issuedMaterial && (
                            <p className="text-xs text-error-600">Issue packing material before finishing.</p>
                        )}
                    </div>
                )}
            </div>

            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3">Details</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <p className="text-sm text-neutral-500 mb-1">Description</p>
                        {!isFinished && editingDescription ? (
                            <form onSubmit={handleSaveDescription} className="space-y-2">
                                {descriptionError && <InlineAlert variant="error" message={descriptionError} />}
                                <textarea
                                    value={descriptionDraft}
                                    onChange={(e) => setDescriptionDraft(e.target.value)}
                                    rows={3}
                                    placeholder="Describe this production batch"
                                    autoFocus
                                    className="w-full px-3 py-2 bg-white border border-neutral-200 rounded-lg focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 outline-none transition-all text-sm"
                                />
                                <div className="flex gap-2">
                                    <Button type="submit" size="sm" loading={updatingDescription}>Save</Button>
                                    <Button type="button" variant="secondary" size="sm" onClick={() => setEditingDescription(false)}>
                                        Cancel
                                    </Button>
                                </div>
                            </form>
                        ) : (
                            <div className="flex items-start justify-between gap-2">
                                <p className="font-medium">
                                    {hasDescription
                                        ? recipe.description
                                        : <span className="text-neutral-400 italic">No description yet</span>}
                                </p>
                                {!isFinished && (
                                    <Button variant="secondary" size="sm" icon={Pencil} onClick={startEditDescription}>
                                        Edit
                                    </Button>
                                )}
                            </div>
                        )}
                    </div>
                    <div>
                        <p className="text-sm text-neutral-500">Recipe Type</p>
                        <p className="font-medium capitalize">{recipe.recipe_type}</p>
                    </div>
                    {isFinished && (
                        <>
                            <div>
                                <p className="text-sm text-neutral-500">Finished By</p>
                                <p className="font-medium">{recipe.finished_by || 'N/A'}</p>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Finished At</p>
                                <p className="font-medium">
                                    {recipe.finished_at ? new Date(recipe.finished_at).toLocaleString() : 'N/A'}
                                </p>
                            </div>
                        </>
                    )}
                </div>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <IssuedPiecePanel
                    piece={issuedPiece}
                    disabled={isFinished}
                    onIssue={issuePiece}
                    onUpdate={updateIssuedPiece}
                />
                <IssuedMaterialPanel
                    material={issuedMaterial}
                    disabled={isFinished}
                    onIssue={issueMaterial}
                    onUpdate={updateIssuedMaterial}
                />
            </div>

            {outputItem && (
                <Card className="p-6" hover={false}>
                    <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                        <PackageCheck className="w-4 h-4" /> Finished Goods Output
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <p className="text-sm text-neutral-500">FG Product</p>
                            <p className="font-medium">{outputItem.fg_product?.name || 'N/A'}</p>
                        </div>
                        <div>
                            <p className="text-sm text-neutral-500">Quantity</p>
                            <p className="font-medium">{outputItem.quantity}</p>
                        </div>
                        <div>
                            <p className="text-sm text-neutral-500">Remaining</p>
                            <p className="font-medium">{outputItem.remaining_quantity}</p>
                        </div>
                        <div>
                            <p className="text-sm text-neutral-500">Unit Cost</p>
                            <p className="font-medium">
                                {outputItem.unit_cost_snapshot != null ? parseFloat(outputItem.unit_cost_snapshot).toFixed(2) : '—'}
                            </p>
                        </div>
                        <div className="sm:col-span-2">
                            <p className="text-sm text-neutral-500 mb-1">Put away on</p>
                            <p className="text-sm text-neutral-700">
                                {outputItem.shelf_allocations?.length > 0
                                    ? outputItem.shelf_allocations.map((a) => `${a.shelf_name} (${a.quantity})`).join(', ')
                                    : '—'}
                            </p>
                        </div>
                    </div>
                </Card>
            )}

            <FinishPackingModal
                isOpen={showFinishModal}
                onClose={() => setShowFinishModal(false)}
                requiredQuantity={parseFloat(issuedPiece?.quantity || 0)}
                onFinish={handleFinish}
                finishing={finishing}
            />
        </div>
    );
};

export default PackingRecipeDetailPage;
