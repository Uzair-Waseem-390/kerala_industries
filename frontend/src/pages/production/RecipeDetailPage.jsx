import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Pencil, CheckCircle2, Plus, Layers, Trash2, X } from 'lucide-react';
import { useRecipeDetail } from '../../hooks/useProduction';
import { productionApi } from '../../services/productionApi';
import { purchasesApi } from '../../services/purchasesApi';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Card from '../../components/ui/Card';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Input from '../../components/ui/Input';
import SearchableSelect from '../../components/ui/SearchableSelect';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import InlineAlert from '../../components/ui/InlineAlert';
import EmptyState from '../../components/ui/EmptyState';
import ShelfAllocationEditor from '../../components/shared/ShelfAllocationEditor';
import RecipeStatusBadge from '../../components/production/RecipeStatusBadge';
import RecipeLaborMachineSection from '../../components/production/RecipeLaborMachineSection';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const KIND_LABELS = { jumbo: 'Jumbo', cores: 'Cores' };
const EPSILON = 0.0001;
const closeEnough = (a, b) => Math.abs(a - b) < EPSILON;
const sumAlloc = (list) => list.reduce((s, a) => s + (parseFloat(a.quantity) || 0), 0);
const toShelfPayload = (list) =>
    list
        .filter((a) => a.shelf_id && a.quantity)
        .map((a) => ({ shelf_id: parseInt(a.shelf_id, 10), quantity: parseFloat(a.quantity) }));

// Any-shelf put-away search (breakdown destination, and returning material
// to RM on a quantity decrease) — same pattern as PurchaseOrderDetailPage's
// put-away SearchableSelect.
const searchShelvesForPutAway = async (query) => {
    const res = await purchasesApi.shelves.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((s) => ({ value: s.id, label: s.name, name: s.name }));
};

// One Jumbo / Cores slot: issue form when not yet issued, current quantity
// + inline "change quantity" editor when it is. The editor sizes the
// ShelfAllocationEditor to the delta and switches its mode (consumption to
// pull more, putaway to return the difference) based on the sign.
const IssuedMaterialPanel = ({ kind, material, disabled, onIssue, onUpdate }) => {
    const { toast } = useToast();

    // Issue form (not yet issued)
    const [productId, setProductId] = useState('');
    const [productLabel, setProductLabel] = useState('');
    const [quantity, setQuantity] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [candidateShelves, setCandidateShelves] = useState([]);
    const [shelvesLoading, setShelvesLoading] = useState(false);
    const [issuing, setIssuing] = useState(false);
    const [issueError, setIssueError] = useState('');

    // Edit form (already issued)
    const [editing, setEditing] = useState(false);
    const [editQuantity, setEditQuantity] = useState('');
    const [editAllocations, setEditAllocations] = useState([]);
    const [editShelves, setEditShelves] = useState([]);
    const [editShelvesLoading, setEditShelvesLoading] = useState(false);
    const [updating, setUpdating] = useState(false);
    const [updateError, setUpdateError] = useState('');

    const searchIssuableProducts = async (query) => {
        const res = await productionApi.issuableProducts.getAll({ kind, search: query });
        const results = res?.results ?? res ?? [];
        return results.map((p) => ({
            value: p.id,
            label: `${p.name}${p.code ? ` (${p.code})` : ''} — ${p.available_quantity} available`,
            name: p.name,
        }));
    };

    const loadCandidateShelves = async (productId) => {
        const res = await purchasesApi.shelves.getCandidates(productId);
        return Array.isArray(res) ? res : (res?.results ?? []);
    };

    const handleSelectProduct = async (val, option) => {
        setProductId(val);
        setProductLabel(option?.name || option?.label || '');
        setAllocations([]);
        setShelvesLoading(true);
        try {
            setCandidateShelves(await loadCandidateShelves(val));
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
                kind,
                product_id: productId,
                quantity: issueQty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success(`${KIND_LABELS[kind]} material issued`);
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
                setEditShelves(await loadCandidateShelves(material.product_id));
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
            await onUpdate(kind, {
                quantity: newQty,
                shelf_allocations: toShelfPayload(editAllocations),
            });
            toast.success(`${KIND_LABELS[kind]} quantity updated`);
            setEditing(false);
        } catch (err) {
            setUpdateError(extractErrorMessage(err, 'Failed to update issued material'));
        } finally {
            setUpdating(false);
        }
    };

    return (
        <Card className="p-6" hover={false}>
            <h3 className="font-semibold text-neutral-900 mb-3">{KIND_LABELS[kind]}</h3>

            {!material ? (
                disabled ? (
                    <p className="text-sm text-neutral-400 italic">Not issued.</p>
                ) : (
                    <form onSubmit={handleIssueSubmit} className="space-y-4">
                        {issueError && <InlineAlert variant="error" message={issueError} />}
                        <SearchableSelect
                            label={`${KIND_LABELS[kind]} product`}
                            value={productId}
                            selectedLabel={productLabel}
                            onChange={handleSelectProduct}
                            onSearch={searchIssuableProducts}
                            placeholder="Search by name or code..."
                            required
                        />
                        <Input
                            label="Quantity"
                            type="number"
                            min="0.0001"
                            step="0.0001"
                            value={quantity}
                            onChange={(e) => setQuantity(e.target.value)}
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
                                Issue {KIND_LABELS[kind]}
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
                                {/* Which shelf(s) this quantity was drawn from (and, on a
                                    decrease, returned to) — already included in the recipe
                                    detail response alongside consumptions, no extra request. */}
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

// Add-one-breakdown-item form: yard value + quantity + put-away shelf
// picker for the newly-produced WIP quantity.
const BreakdownForm = ({ onAdd }) => {
    const { toast } = useToast();
    const [yardValue, setYardValue] = useState('');
    const [quantity, setQuantity] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const qty = parseFloat(quantity) || 0;
    const canSubmit = parseFloat(yardValue) > 0 && qty > 0 && closeEnough(sumAlloc(allocations), qty);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSubmitting(true);
        try {
            await onAdd({
                yard_value: parseFloat(yardValue),
                quantity: qty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Breakdown item added');
            setYardValue(''); setQuantity(''); setAllocations([]);
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to add breakdown item'));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
            {error && <InlineAlert variant="error" message={error} />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                    label="Yard value"
                    type="number"
                    min="0.0001"
                    step="0.0001"
                    value={yardValue}
                    onChange={(e) => setYardValue(e.target.value)}
                    required
                />
                <Input
                    label="Core quantity"
                    type="number"
                    min="0.0001"
                    step="0.0001"
                    value={quantity}
                    onChange={(e) => { setQuantity(e.target.value); setAllocations([]); }}
                    required
                />
            </div>
            <ShelfAllocationEditor
                value={allocations}
                onChange={setAllocations}
                onSearchShelves={searchShelvesForPutAway}
                requiredQuantity={qty}
                mode="putaway"
            />
            <div className="flex justify-end">
                <Button type="submit" size="sm" icon={Plus} loading={submitting} disabled={!canSubmit}>
                    Add Breakdown Item
                </Button>
            </div>
        </form>
    );
};

// Inline edit form for one existing breakdown item — same fields as
// BreakdownForm, pre-filled, PATCHes in place instead of creating a new row.
const BreakdownItemEditForm = ({ item, onSave, onCancel }) => {
    const { toast } = useToast();
    const [yardValue, setYardValue] = useState(String(item.wip_product?.yard?.value ?? ''));
    const [quantity, setQuantity] = useState(String(item.quantity));
    const [allocations, setAllocations] = useState(
        (item.shelf_allocations || []).map((a) => ({ shelf_id: String(a.shelf_id), quantity: String(a.quantity) })),
    );
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const qty = parseFloat(quantity) || 0;
    const canSubmit = parseFloat(yardValue) > 0 && qty > 0 && closeEnough(sumAlloc(allocations), qty);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSubmitting(true);
        try {
            await onSave({
                yard_value: parseFloat(yardValue),
                quantity: qty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Breakdown item updated');
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to update breakdown item'));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
            {error && <InlineAlert variant="error" message={error} />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                    label="Yard value"
                    type="number" min="0.0001" step="0.0001"
                    value={yardValue}
                    onChange={(e) => setYardValue(e.target.value)}
                    required
                />
                <Input
                    label="Core quantity"
                    type="number" min="0.0001" step="0.0001"
                    value={quantity}
                    onChange={(e) => { setQuantity(e.target.value); setAllocations([]); }}
                    required
                />
            </div>
            <ShelfAllocationEditor
                value={allocations}
                onChange={setAllocations}
                onSearchShelves={searchShelvesForPutAway}
                requiredQuantity={qty}
                mode="putaway"
            />
            <div className="flex justify-end gap-3">
                <Button type="button" variant="secondary" size="sm" onClick={onCancel}>Cancel</Button>
                <Button type="submit" size="sm" loading={submitting} disabled={!canSubmit}>Save</Button>
            </div>
        </form>
    );
};

// Only while under_processing — reverses every issued material back to RM
// inventory at the shelves the user picks, then soft-deletes the recipe.
// An inline panel (not a modal) so the ShelfAllocationEditor has room and
// matches this page's own established "edit inline" pattern (description,
// quantity) rather than introducing a new modal shape.
const DeleteRecipeSection = ({ jumboMaterial, coresMaterial, onDelete, deleting, onDeleted }) => {
    const { toast } = useToast();
    const [open, setOpen] = useState(false);
    const [jumboAllocations, setJumboAllocations] = useState([]);
    const [coresAllocations, setCoresAllocations] = useState([]);
    const [jumboShelves, setJumboShelves] = useState([]);
    const [coresShelves, setCoresShelves] = useState([]);
    const [shelvesLoading, setShelvesLoading] = useState(false);
    const [error, setError] = useState('');

    const loadCandidateShelves = async (productId) => {
        const res = await purchasesApi.shelves.getCandidates(productId);
        return Array.isArray(res) ? res : (res?.results ?? []);
    };

    const handleOpen = async () => {
        setOpen(true);
        setError('');
        setJumboAllocations([]);
        setCoresAllocations([]);
        setShelvesLoading(true);
        try {
            const [j, c] = await Promise.all([
                jumboMaterial ? loadCandidateShelves(jumboMaterial.product_id) : Promise.resolve([]),
                coresMaterial ? loadCandidateShelves(coresMaterial.product_id) : Promise.resolve([]),
            ]);
            setJumboShelves(j);
            setCoresShelves(c);
        } catch (err) {
            toast.error(extractErrorMessage(err, 'Failed to load candidate shelves'));
        } finally {
            setShelvesLoading(false);
        }
    };

    const jumboOk = !jumboMaterial || closeEnough(sumAlloc(jumboAllocations), jumboMaterial.quantity);
    const coresOk = !coresMaterial || closeEnough(sumAlloc(coresAllocations), coresMaterial.quantity);
    const canDelete = jumboOk && coresOk;

    const handleConfirm = async () => {
        setError('');
        try {
            await onDelete({
                jumbo_shelf_allocations: toShelfPayload(jumboAllocations),
                cores_shelf_allocations: toShelfPayload(coresAllocations),
            });
            toast.success('Recipe deleted');
            onDeleted();
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to delete recipe'));
        }
    };

    if (!open) {
        return (
            <Card className="p-6 border-error-200" hover={false}>
                <h3 className="font-semibold text-error-700 mb-1">Danger Zone</h3>
                <p className="text-sm text-neutral-500 mb-3">
                    Deleting this recipe reverses every issued material back to raw material inventory. Breakdown items are discarded — none of them have entered stock yet.
                </p>
                <Button variant="danger" size="sm" icon={Trash2} onClick={handleOpen}>Delete Recipe</Button>
            </Card>
        );
    }

    return (
        <Card className="p-6 border-error-200" hover={false}>
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-error-700">Delete Recipe</h3>
                <Button variant="secondary" size="sm" icon={X} onClick={() => setOpen(false)}>Cancel</Button>
            </div>
            {error && <InlineAlert variant="error" message={error} />}
            {shelvesLoading ? (
                <div className="flex items-center py-2"><LoadingSpinner size="sm" /></div>
            ) : (
                <div className="space-y-4">
                    {jumboMaterial && (
                        <div>
                            <p className="text-sm font-medium text-neutral-700 mb-2">
                                Return {jumboMaterial.quantity} Jumbo ({jumboMaterial.product_name}) to —
                            </p>
                            <ShelfAllocationEditor
                                value={jumboAllocations}
                                onChange={setJumboAllocations}
                                shelves={jumboShelves}
                                onSearchShelves={searchShelvesForPutAway}
                                requiredQuantity={jumboMaterial.quantity}
                                mode="putaway"
                            />
                        </div>
                    )}
                    {coresMaterial && (
                        <div>
                            <p className="text-sm font-medium text-neutral-700 mb-2">
                                Return {coresMaterial.quantity} Cores ({coresMaterial.product_name}) to —
                            </p>
                            <ShelfAllocationEditor
                                value={coresAllocations}
                                onChange={setCoresAllocations}
                                shelves={coresShelves}
                                onSearchShelves={searchShelvesForPutAway}
                                requiredQuantity={coresMaterial.quantity}
                                mode="putaway"
                            />
                        </div>
                    )}
                    {!jumboMaterial && !coresMaterial && (
                        <p className="text-sm text-neutral-500 italic">No material has been issued — nothing to return.</p>
                    )}
                    <div className="flex justify-end">
                        <Button variant="danger" size="sm" icon={Trash2} loading={deleting} disabled={!canDelete} onClick={handleConfirm}>
                            Confirm Delete
                        </Button>
                    </div>
                </div>
            )}
        </Card>
    );
};

const RecipeDetailPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { toast } = useToast();
    const {
        recipe, loading, error, refetch,
        issueMaterial, updateIssuedMaterial,
        addBreakdownItem, updateBreakdownItem, deleteBreakdownItem,
        updateDescription, updatingDescription,
        updateName, updatingName,
        deleteRecipe, deleting,
        finish, finishing,
        setTime, settingTime,
        addLabor, addingLabor,
        removeLabor, removingLaborId,
        addMachine, addingMachine,
        removeMachine, removingMachineId,
    } = useRecipeDetail(id);

    const [confirmFinishOpen, setConfirmFinishOpen] = useState(false);
    const [finishError, setFinishError] = useState('');

    // Description is optional at create time but required before finish
    // (server-enforced too — see handleFinish's disabled guard below).
    const [editingDescription, setEditingDescription] = useState(false);
    const [descriptionDraft, setDescriptionDraft] = useState('');
    const [descriptionError, setDescriptionError] = useState('');

    const [editingName, setEditingName] = useState(false);
    const [nameDraft, setNameDraft] = useState('');
    const [nameError, setNameError] = useState('');

    const [confirmDeleteItemId, setConfirmDeleteItemId] = useState(null);
    const [editingItemId, setEditingItemId] = useState(null);
    const [deletingItem, setDeletingItem] = useState(false);
    const [itemActionError, setItemActionError] = useState('');

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
                <BackLink to="/production/recipes" className="mt-4">Back to Rewinding Recipes</BackLink>
            </div>
        );
    }

    const isFinished = recipe.status === 'finished';
    const jumboMaterial = recipe.issued_materials?.find((m) => m.kind === 'jumbo') || null;
    const coresMaterial = recipe.issued_materials?.find((m) => m.kind === 'cores') || null;
    const breakdownItems = recipe.breakdown_items || [];
    const hasDescription = !!recipe.description?.trim();
    const hasTime = (recipe.time_hours || 0) > 0 || (recipe.time_minutes || 0) > 0;
    const hasLabor = (recipe.labor_entries || []).length > 0;
    const hasMachine = (recipe.machine_entries || []).length > 0;

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

    const startEditName = () => {
        setNameDraft(recipe.name || '');
        setNameError('');
        setEditingName(true);
    };

    const handleSaveName = async (e) => {
        e.preventDefault();
        setNameError('');
        try {
            await updateName(nameDraft);
            toast.success('Name updated');
            setEditingName(false);
        } catch (err) {
            setNameError(extractErrorMessage(err, 'Failed to update name'));
        }
    };

    const handleUpdateBreakdownItem = async (itemId, payload) => {
        await updateBreakdownItem(itemId, payload);
        setEditingItemId(null);
    };

    const handleDeleteBreakdownItem = async () => {
        setItemActionError('');
        setDeletingItem(true);
        try {
            await deleteBreakdownItem(confirmDeleteItemId);
            toast.success('Breakdown item deleted');
            setConfirmDeleteItemId(null);
        } catch (err) {
            const msg = extractErrorMessage(err, 'Failed to delete breakdown item');
            setItemActionError(msg);
            toast.error(msg);
        } finally {
            setDeletingItem(false);
        }
    };

    const handleFinish = async () => {
        setFinishError('');
        try {
            await finish();
            toast.success('Recipe finished');
            setConfirmFinishOpen(false);
        } catch (err) {
            const msg = extractErrorMessage(err, 'Failed to finish recipe');
            setFinishError(msg);
            toast.error(msg);
            setConfirmFinishOpen(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <BackLink to="/production/recipes">Back to Rewinding Recipes</BackLink>
                    {!isFinished && editingName ? (
                        <form onSubmit={handleSaveName} className="flex items-center gap-2 mt-1">
                            {nameError && <span className="text-xs text-error-600">{nameError}</span>}
                            <span className="text-3xl font-bold text-neutral-900">{recipe.recipe_number} —</span>
                            <Input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} autoFocus required className="text-lg" />
                            <Button type="submit" size="sm" loading={updatingName}>Save</Button>
                            <Button type="button" variant="secondary" size="sm" onClick={() => setEditingName(false)}>Cancel</Button>
                        </form>
                    ) : (
                        <h1 className="text-3xl font-bold text-neutral-900 mt-1 flex items-center gap-2">
                            {recipe.recipe_number} — {recipe.name}
                            {!isFinished && (
                                <button type="button" onClick={startEditName} className="text-neutral-400 hover:text-neutral-600" title="Edit name">
                                    <Pencil className="w-4 h-4" />
                                </button>
                            )}
                        </h1>
                    )}
                    <div className="flex gap-2 mt-1 flex-wrap items-center">
                        <RecipeStatusBadge status={recipe.status} />
                        {isFinished && recipe.cost_per_unit != null && (
                            <span className="text-sm font-semibold text-primary-700">
                                Cost / unit: {parseFloat(recipe.cost_per_unit).toFixed(2)}
                            </span>
                        )}
                        {isFinished && recipe.full_cost_per_unit != null && (
                            <span className="text-sm font-semibold text-accent-700">
                                Full Cost / Unit: {parseFloat(recipe.full_cost_per_unit).toFixed(2)}
                            </span>
                        )}
                    </div>
                </div>
                {!isFinished && (
                    <div className="flex flex-col items-end gap-1">
                        <Button
                            variant="success"
                            icon={CheckCircle2}
                            disabled={breakdownItems.length === 0 || !hasDescription || !hasTime || !hasLabor || !hasMachine}
                            onClick={() => setConfirmFinishOpen(true)}
                        >
                            Finish Recipe
                        </Button>
                        {!hasDescription && (
                            <p className="text-xs text-error-600">Add a description before finishing.</p>
                        )}
                        {hasDescription && breakdownItems.length === 0 && (
                            <p className="text-xs text-error-600">Add at least one breakdown item before finishing.</p>
                        )}
                        {!hasTime && (
                            <p className="text-xs text-error-600">Time taken (hours/minutes) must be entered before finishing this recipe.</p>
                        )}
                        {!hasLabor && (
                            <p className="text-xs text-error-600">At least one employee must be assigned before finishing this recipe.</p>
                        )}
                        {!hasMachine && (
                            <p className="text-xs text-error-600">At least one machine must be assigned before finishing this recipe.</p>
                        )}
                    </div>
                )}
            </div>

            {finishError && <InlineAlert variant="error" message={finishError} />}

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

            <div>
                <h2 className="text-xl font-semibold text-neutral-900 mb-3">Issued Materials</h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <IssuedMaterialPanel
                        kind="jumbo"
                        material={jumboMaterial}
                        disabled={isFinished}
                        onIssue={issueMaterial}
                        onUpdate={updateIssuedMaterial}
                    />
                    <IssuedMaterialPanel
                        kind="cores"
                        material={coresMaterial}
                        disabled={isFinished}
                        onIssue={issueMaterial}
                        onUpdate={updateIssuedMaterial}
                    />
                </div>
            </div>

            <div>
                <h2 className="text-xl font-semibold text-neutral-900 mb-3">Time &amp; Cost Inputs</h2>
                <RecipeLaborMachineSection
                    recipe={recipe}
                    disabled={isFinished}
                    onSetTime={setTime} settingTime={settingTime}
                    onAddLabor={addLabor} addingLabor={addingLabor}
                    onRemoveLabor={removeLabor} removingLaborId={removingLaborId}
                    onAddMachine={addMachine} addingMachine={addingMachine}
                    onRemoveMachine={removeMachine} removingMachineId={removingMachineId}
                />
            </div>

            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Breakdown Items
                </h3>

                {itemActionError && <InlineAlert variant="error" message={itemActionError} />}

                {breakdownItems.length === 0 ? (
                    <EmptyState
                        title="No breakdown items yet"
                        description="Add what was actually produced from this recipe."
                    />
                ) : (
                    <div className="overflow-x-auto mb-4">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-neutral-200">
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">WIP Product</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Quantity</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Remaining</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Shelves</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-neutral-500">Material Cost</th>
                                    {isFinished && (
                                        <th className="px-3 py-2 text-right text-xs font-medium text-neutral-500">Full Cost</th>
                                    )}
                                    {!isFinished && (
                                        <th className="px-3 py-2 text-right text-xs font-medium text-neutral-500">Actions</th>
                                    )}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-neutral-100">
                                {breakdownItems.map((item) => (
                                    <React.Fragment key={item.id}>
                                        <tr className="hover:bg-neutral-50">
                                            <td className="px-3 py-2 text-sm">{item.wip_product?.name || 'N/A'}</td>
                                            <td className="px-3 py-2 text-sm">{item.quantity}</td>
                                            <td className="px-3 py-2 text-sm">{item.remaining_quantity}</td>
                                            <td className="px-3 py-2 text-sm text-neutral-500">
                                                {item.shelf_allocations?.length > 0
                                                    ? item.shelf_allocations.map((a) => `${a.shelf_name} (${a.quantity})`).join(', ')
                                                    : '—'}
                                            </td>
                                            <td className="px-3 py-2 text-sm text-right font-medium">
                                                {item.unit_cost_snapshot != null ? parseFloat(item.unit_cost_snapshot).toFixed(2) : '—'}
                                            </td>
                                            {isFinished && (
                                                <td className="px-3 py-2 text-sm text-right font-medium">
                                                    {item.full_unit_cost_snapshot != null ? parseFloat(item.full_unit_cost_snapshot).toFixed(2) : '—'}
                                                </td>
                                            )}
                                            {!isFinished && (
                                                <td className="px-3 py-2 text-right">
                                                    <div className="flex justify-end gap-1">
                                                        <button
                                                            type="button"
                                                            title="Edit"
                                                            onClick={() => setEditingItemId(editingItemId === item.id ? null : item.id)}
                                                            className="p-1.5 text-neutral-400 hover:text-primary-600 rounded"
                                                        >
                                                            <Pencil className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            type="button"
                                                            title="Delete"
                                                            onClick={() => setConfirmDeleteItemId(item.id)}
                                                            className="p-1.5 text-neutral-400 hover:text-error-600 rounded"
                                                        >
                                                            <Trash2 className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                </td>
                                            )}
                                        </tr>
                                        {editingItemId === item.id && (
                                            <tr>
                                                <td colSpan={isFinished ? 6 : 6} className="px-3 pb-3">
                                                    <BreakdownItemEditForm
                                                        item={item}
                                                        onSave={(payload) => handleUpdateBreakdownItem(item.id, payload)}
                                                        onCancel={() => setEditingItemId(null)}
                                                    />
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {!isFinished && <BreakdownForm onAdd={addBreakdownItem} />}
            </Card>

            {!isFinished && (
                <DeleteRecipeSection
                    jumboMaterial={jumboMaterial}
                    coresMaterial={coresMaterial}
                    onDelete={deleteRecipe}
                    deleting={deleting}
                    onDeleted={() => navigate('/production/recipes')}
                />
            )}

            <ConfirmDialog
                isOpen={confirmDeleteItemId != null}
                onClose={() => setConfirmDeleteItemId(null)}
                onConfirm={handleDeleteBreakdownItem}
                title="Delete Breakdown Item"
                message="This item hasn't entered WIP stock yet (put-away only happens when the recipe finishes), so nothing needs to be reversed. This cannot be undone."
                confirmText="Delete"
                loading={deletingItem}
            />

            <ConfirmDialog
                isOpen={confirmFinishOpen}
                onClose={() => setConfirmFinishOpen(false)}
                onConfirm={handleFinish}
                title="Finish Recipe"
                message="Are you sure you want to finish this recipe? This locks it permanently — no further edits will be possible."
                confirmText="Finish"
                variant="primary"
                loading={finishing}
            />
        </div>
    );
};

export default RecipeDetailPage;
