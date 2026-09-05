import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Pencil, CheckCircle2, Plus, Layers, Scissors } from 'lucide-react';
import { useCuttingRecipeDetail } from '../../hooks/useProduction';
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
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const EPSILON = 0.0001;
const closeEnough = (a, b) => Math.abs(a - b) < EPSILON;
const sumAlloc = (list) => list.reduce((s, a) => s + (parseFloat(a.quantity) || 0), 0);
const toShelfPayload = (list) =>
    list
        .filter((a) => a.shelf_id && a.quantity)
        .map((a) => ({ shelf_id: parseInt(a.shelf_id, 10), quantity: parseFloat(a.quantity) }));

// Any-shelf search — put-away side only (breakdown output, and returning
// WIP stock on a quantity decrease). The consumption side (issuing a core,
// or drawing more on an increase) uses real candidate shelves instead —
// see loadCandidateShelves below.
const searchShelvesForPutAway = async (query) => {
    const res = await purchasesApi.shelves.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((s) => ({ value: s.id, label: s.name, name: s.name }));
};

const searchIssuableWipCores = async (query) => {
    const res = await productionApi.issuableWipCores.getAll({ search: query });
    const results = res?.results ?? res ?? [];
    return results.map((p) => ({
        value: p.id,
        label: `${p.name} — ${p.available_quantity} available`,
        name: p.name,
    }));
};

const loadCandidateShelves = async (wipProductId) => {
    const res = await productionApi.wipShelfCandidates.getAll(wipProductId);
    return Array.isArray(res) ? res : (res?.results ?? []);
};

// The single issued-material slot for a Cutting recipe (one whole Rewound
// Core product, no jumbo/cores split like Rewinding). Issue form when not
// yet issued, current quantity + inline "change quantity" editor when it is.
const CuttingIssuedMaterialPanel = ({ material, disabled, onIssue, onUpdate }) => {
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
                wip_product_id: productId,
                quantity: issueQty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Material issued');
            setProductId(''); setProductLabel(''); setQuantity(''); setAllocations([]);
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
        if (material?.wip_product_id) {
            setEditShelvesLoading(true);
            try {
                setEditShelves(await loadCandidateShelves(material.wip_product_id));
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
            <h3 className="font-semibold text-neutral-900 mb-3">Issued Material</h3>

            {!material ? (
                disabled ? (
                    <p className="text-sm text-neutral-400 italic">Not issued.</p>
                ) : (
                    <form onSubmit={handleIssueSubmit} className="space-y-4">
                        {issueError && <InlineAlert variant="error" message={issueError} />}
                        <SearchableSelect
                            label="Rewound Core"
                            value={productId}
                            selectedLabel={productLabel}
                            onChange={handleSelectProduct}
                            onSearch={searchIssuableWipCores}
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
                                Issue Material
                            </Button>
                        </div>
                    </form>
                )
            ) : (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="font-medium">{material.wip_product_name}</p>
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
                                {material.consumptions?.map((c) => (
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

// Add-one-breakdown-item form: cut length (mm) + piece quantity + put-away
// shelf picker for the newly-produced WIP quantity.
const BreakdownForm = ({ onAdd }) => {
    const { toast } = useToast();
    const [lengthMm, setLengthMm] = useState('');
    const [quantity, setQuantity] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const qty = parseFloat(quantity) || 0;
    const canSubmit = parseFloat(lengthMm) > 0 && qty > 0 && closeEnough(sumAlloc(allocations), qty);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSubmitting(true);
        try {
            await onAdd({
                length_mm: parseFloat(lengthMm),
                quantity: qty,
                shelf_allocations: toShelfPayload(allocations),
            });
            toast.success('Breakdown item added');
            setLengthMm(''); setQuantity(''); setAllocations([]);
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
                    label="Length (mm)"
                    type="number"
                    min="0.0001"
                    step="0.0001"
                    value={lengthMm}
                    onChange={(e) => setLengthMm(e.target.value)}
                    required
                />
                <Input
                    label="Quantity (pieces)"
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

const CuttingRecipeDetailPage = () => {
    const { id } = useParams();
    const { toast } = useToast();
    const {
        recipe, loading, error, refetch,
        issueMaterial, updateIssuedMaterial,
        addBreakdownItem,
        updateDescription, updatingDescription,
        finish, finishing,
    } = useCuttingRecipeDetail(id);

    const [confirmFinishOpen, setConfirmFinishOpen] = useState(false);
    const [finishError, setFinishError] = useState('');

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
                <BackLink to="/production/cutting-recipes" className="mt-4">Back to Cutting Recipes</BackLink>
            </div>
        );
    }

    const isFinished = recipe.status === 'finished';
    const issuedMaterial = recipe.cutting_issued_material || null;
    const breakdownItems = recipe.cutting_breakdown_items || [];
    const hasDescription = !!recipe.description?.trim();

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
                    <BackLink to="/production/cutting-recipes">Back to Cutting Recipes</BackLink>
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
                            disabled={breakdownItems.length === 0 || !hasDescription}
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
                    </div>
                )}
            </div>

            {finishError && <InlineAlert variant="error" message={finishError} />}

            {/* Waste is a key deliverable of Cutting — shown as its own
                prominent stat card once the recipe is finished, alongside
                cost/unit which already appears in the header above. */}
            {isFinished && (recipe.waste_length_mm != null || recipe.waste_cost != null) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Card className="p-6 border-2 border-warning-200 bg-warning-50" hover={false}>
                        <p className="text-sm font-medium text-warning-700">Waste Length (mm)</p>
                        <p className="text-2xl font-bold text-warning-800 mt-1">
                            {recipe.waste_length_mm != null ? parseFloat(recipe.waste_length_mm).toFixed(2) : '—'}
                        </p>
                    </Card>
                    <Card className="p-6 border-2 border-warning-200 bg-warning-50" hover={false}>
                        <p className="text-sm font-medium text-warning-700">Waste Cost</p>
                        <p className="text-2xl font-bold text-warning-800 mt-1">
                            {recipe.waste_cost != null ? parseFloat(recipe.waste_cost).toFixed(2) : '—'}
                        </p>
                    </Card>
                </div>
            )}

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

            <CuttingIssuedMaterialPanel
                material={issuedMaterial}
                disabled={isFinished}
                onIssue={issueMaterial}
                onUpdate={updateIssuedMaterial}
            />

            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Breakdown Items
                </h3>

                {breakdownItems.length === 0 ? (
                    <EmptyState
                        icon={<Scissors className="w-8 h-8 text-neutral-400" />}
                        title="No breakdown items yet"
                        description="Add what was actually cut from this recipe."
                    />
                ) : (
                    <div className="overflow-x-auto mb-4">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-neutral-200">
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">WIP Product</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Length (mm)</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Quantity</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Remaining</th>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-neutral-500">Shelves</th>
                                    {isFinished && (
                                        <>
                                            <th className="px-3 py-2 text-right text-xs font-medium text-neutral-500">Before Waste</th>
                                            <th className="px-3 py-2 text-right text-xs font-medium text-neutral-500">Final</th>
                                        </>
                                    )}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-neutral-100">
                                {breakdownItems.map((item) => (
                                    <tr key={item.id} className="hover:bg-neutral-50">
                                        <td className="px-3 py-2 text-sm">{item.wip_product?.name || 'N/A'}</td>
                                        <td className="px-3 py-2 text-sm">{item.length_mm}</td>
                                        <td className="px-3 py-2 text-sm">{item.quantity}</td>
                                        <td className="px-3 py-2 text-sm">{item.remaining_quantity}</td>
                                        <td className="px-3 py-2 text-sm text-neutral-500">
                                            {item.shelf_allocations?.length > 0
                                                ? item.shelf_allocations.map((a) => `${a.shelf_name} (${a.quantity})`).join(', ')
                                                : '—'}
                                        </td>
                                        {isFinished && (
                                            <>
                                                <td className="px-3 py-2 text-sm text-right">
                                                    {item.unit_cost_before_waste != null ? parseFloat(item.unit_cost_before_waste).toFixed(2) : '—'}
                                                </td>
                                                <td className="px-3 py-2 text-sm text-right font-medium">
                                                    {item.unit_cost_snapshot != null ? parseFloat(item.unit_cost_snapshot).toFixed(2) : '—'}
                                                </td>
                                            </>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {!isFinished && <BreakdownForm onAdd={addBreakdownItem} />}
            </Card>

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

export default CuttingRecipeDetailPage;
