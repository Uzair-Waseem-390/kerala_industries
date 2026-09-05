import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { purchasesApi } from '../../services/purchasesApi';
import { inventoryApi } from '../../services/inventoryApi';
import { productionApi } from '../../services/productionApi';
import Card from '../../components/ui/Card';
import SearchBar from '../../components/ui/SearchBar';
import Input from '../../components/ui/Input';
import Select from '../../components/ui/Select';
import Button from '../../components/ui/Button';
import Badge from '../../components/ui/Badge';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import InlineAlert from '../../components/ui/InlineAlert';
import ShelfAllocationEditor from '../../components/shared/ShelfAllocationEditor';
import BackLink from '../../components/ui/BackLink';

const formatCurrency = (value) => {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return isNaN(num) ? '0.00' : num.toFixed(2);
};

const TYPE_OPTIONS = [
    { value: 'raw_material', label: 'Raw Material' },
    { value: 'wip_core', label: 'WIP — Core' },
    { value: 'wip_piece', label: 'WIP — Piece' },
    { value: 'finished_goods', label: 'Finished Goods' },
];

const TYPE_BADGE = {
    raw_material: { variant: 'default', label: 'Raw Material' },
    wip_core: { variant: 'warning', label: 'WIP — Core' },
    wip_piece: { variant: 'info', label: 'WIP — Piece' },
    finished_goods: { variant: 'success', label: 'Finished Goods' },
};

// One shared envelope shape across all four catalogs' inventory search
// endpoints: {..., product: {id, name, code, ...}, quantity}. Only the
// endpoint (and, for WIP, a client-side stage filter) differs per type.
const searchInventoryByType = (type, searchTerm) => {
    const params = { search: searchTerm, page_size: 8 };
    if (type === 'raw_material') return inventoryApi.inventory.getAll(params);
    if (type === 'finished_goods') return productionApi.fgInventory.getAll(params);
    return productionApi.wipInventory.getAll(params);
};

const WIP_STAGE_FOR_TYPE = { wip_core: 'rewinding', wip_piece: 'cutting' };

const getShelfCandidatesByType = (type, productId) => {
    if (type === 'raw_material') return purchasesApi.shelves.getCandidates(productId);
    if (type === 'finished_goods') return productionApi.fgShelfCandidates.getAll(productId);
    return productionApi.wipShelfCandidates.getAll(productId);
};

const cartLineKey = (type, productId) => `${type}:${productId}`;

const LostInventoryPage = () => {
    const { user } = useAuth();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searching, setSearching] = useState(false);
    const [addType, setAddType] = useState('raw_material');

    const [cart, setCart] = useState([]);
    const [note, setNote] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    const previewTimer = useRef(null);
    const [shelfCandidatesByProduct, setShelfCandidatesByProduct] = useState({});
    const [bulkAutoAllocating, setBulkAutoAllocating] = useState(false);

    useEffect(() => {
        if (!searchTerm) {
            setSearchResults([]);
            return;
        }
        let cancelled = false;
        setSearching(true);
        searchInventoryByType(addType, searchTerm)
            .then((res) => {
                if (cancelled) return;
                let items = res?.results || res || [];
                const requiredStage = WIP_STAGE_FOR_TYPE[addType];
                if (requiredStage) items = items.filter((i) => i.product?.stage === requiredStage);
                setSearchResults(items.filter((i) => (i.quantity || 0) > 0));
            })
            .catch(() => { if (!cancelled) setSearchResults([]); })
            .finally(() => { if (!cancelled) setSearching(false); });
        return () => { cancelled = true; };
    }, [searchTerm, addType]);

    // Debounced FIFO cost preview — refreshes whenever a cart line's quantity changes.
    useEffect(() => {
        if (previewTimer.current) clearTimeout(previewTimer.current);
        previewTimer.current = setTimeout(() => {
            cart.forEach((line, index) => {
                const quantity = Number(line.quantity);
                if (!quantity || quantity <= 0) return;
                purchasesApi.lostInventory.fifoPreview(line.type, line.product_id, quantity)
                    .then((preview) => {
                        setCart((prev) => prev.map((l, i) => (
                            i === index
                                ? {
                                    ...l,
                                    unit_cost: preview.unit_cost,
                                    total_cost: preview.total_cost,
                                    available_quantity: preview.available_quantity,
                                    sufficient_stock: preview.sufficient_stock,
                                    previewLoading: false,
                                }
                                : l
                        )));
                    })
                    .catch(() => {
                        setCart((prev) => prev.map((l, i) => (
                            i === index ? { ...l, previewLoading: false } : l
                        )));
                    });
            });
        }, 400);
        return () => clearTimeout(previewTimer.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cart.map((l) => `${l.type}:${l.product_id}:${l.quantity}`).join(',')]);

    // Fetch candidate shelves (only shelves currently holding stock of the product)
    // for every product currently in the cart — cached per type+product_id so a
    // quantity edit doesn't trigger a refetch. Already a small, bounded set,
    // so a plain dropdown. Keyed by type too since RM/WIP/FG product ids are
    // independent sequences and can collide numerically.
    useEffect(() => {
        cart.forEach((line) => {
            const cacheKey = cartLineKey(line.type, line.product_id);
            if (shelfCandidatesByProduct[cacheKey] !== undefined) return;
            setShelfCandidatesByProduct((prev) => ({ ...prev, [cacheKey]: null })); // mark as loading
            getShelfCandidatesByType(line.type, line.product_id)
                .then((res) => {
                    const candidates = res?.results || res || [];
                    setShelfCandidatesByProduct((prev) => ({ ...prev, [cacheKey]: candidates }));
                })
                .catch(() => {
                    setShelfCandidatesByProduct((prev) => ({ ...prev, [cacheKey]: [] }));
                });
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cart.map((l) => cartLineKey(l.type, l.product_id)).join(',')]);

    const handleAddProduct = (item) => {
        const productId = item.product?.id;
        if (!productId) return;
        if (cart.some((l) => l.type === addType && l.product_id === productId)) {
            setError('This product is already in the batch.');
            return;
        }
        setError('');
        setCart((prev) => [...prev, {
            type: addType,
            product_id: productId,
            product_name: item.product?.name,
            product_code: item.product?.code,
            available_quantity: item.quantity,
            quantity: '1',
            reason: '',
            unit_cost: 0,
            total_cost: 0,
            sufficient_stock: true,
            previewLoading: true,
            shelf_allocations: [],
        }]);
        setSearchTerm('');
        setSearchResults([]);
    };

    const handleUpdateLine = (index, field, value) => {
        setCart((prev) => prev.map((l, i) => (
            i === index
                ? { ...l, [field]: value, ...(field === 'quantity' ? { previewLoading: true } : {}) }
                : l
        )));
    };

    const handleRemoveLine = (index) => {
        setCart((prev) => prev.filter((_, i) => i !== index));
    };

    // One click auto-allocates every RM line in the batch at once — fills only
    // each line's remaining gap, never touches rows already present. No
    // separate save step here: the whole batch persists together on submit.
    // WIP/FG lines have no auto-allocate endpoint (RM-only backend feature),
    // so those are skipped here and must be allocated manually.
    const handleAutoAllocateAllLines = async () => {
        const allocatableLines = cart.filter((l) => l.type === 'raw_material');
        if (allocatableLines.length === 0) return;
        setBulkAutoAllocating(true);
        setError('');
        let failedCount = 0;
        await Promise.all(allocatableLines.map(async (line) => {
            const allocatedTotal = lineAllocatedTotal(line);
            const remaining = (Number(line.quantity) || 0) - allocatedTotal;
            if (remaining <= 0) return;
            try {
                const excludeShelfIds = (line.shelf_allocations || []).map((a) => a.shelf_id).filter(Boolean);
                const data = await purchasesApi.shelves.autoAllocate(line.product_id, remaining, excludeShelfIds);
                const newRows = (data?.allocations || []).map((a) => ({
                    shelf_id: a.shelf_id, quantity: a.quantity, shelf_name: a.shelf_name || '',
                }));
                if (newRows.length > 0) {
                    setCart((prev) => prev.map((l) => (
                        l.type === 'raw_material' && l.product_id === line.product_id
                            ? { ...l, shelf_allocations: [...(l.shelf_allocations || []), ...newRows] }
                            : l
                    )));
                }
            } catch (err) {
                console.error(`Failed to auto-allocate line ${line.product_id}:`, err);
                failedCount += 1;
            }
        }));
        setBulkAutoAllocating(false);
        if (failedCount > 0) {
            setError(`Auto-allocate failed for ${failedCount} item(s) — you can still allocate them manually.`);
        }
    };

    const grandTotal = cart.reduce((sum, l) => sum + (parseFloat(l.total_cost) || 0), 0);
    const hasInsufficientStock = cart.some((l) => !l.sufficient_stock);
    const lineAllocatedTotal = (line) => (line.shelf_allocations || [])
        .reduce((sum, a) => sum + (parseFloat(a.quantity) || 0), 0);
    const hasUnallocatedShelves = cart.some((l) => lineAllocatedTotal(l) !== (Number(l.quantity) || 0));

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');

        if (cart.length === 0) {
            setError('Add at least one product to the batch.');
            return;
        }
        if (cart.some((l) => !Number(l.quantity) || Number(l.quantity) <= 0)) {
            setError('Enter a valid quantity greater than zero for every item.');
            return;
        }
        if (hasInsufficientStock) {
            setError('One or more items exceed available stock. Adjust the quantity before submitting.');
            return;
        }
        if (hasUnallocatedShelves) {
            setError('Every item\'s shelf allocations must sum exactly to its quantity before submitting.');
            return;
        }

        setSubmitting(true);
        try {
            const result = await purchasesApi.lostInventory.create({
                items: cart.map((l) => ({
                    type: l.type,
                    product_id: l.product_id,
                    quantity: Number(l.quantity),
                    reason: l.reason || '',
                    shelf_allocations: (l.shelf_allocations || []).map((a) => ({
                        shelf_id: parseInt(a.shelf_id, 10),
                        quantity: parseFloat(a.quantity),
                    })),
                })),
                note,
            });
            setSuccessMessage(`Recorded as ${result.reference_number} — total loss Rs. ${formatCurrency(result.total_lost_amount)}.`);
            setCart([]);
            setNote('');
        } catch (err) {
            const data = err.response?.data;
            if (data && typeof data === 'object') {
                const messages = Object.entries(data)
                    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
                    .join('\n');
                setError(messages);
            } else {
                setError(err.message || 'Failed to record lost inventory. Please try again.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    if (!isAdmin) {
        return (
            <div className="text-center py-12">
                <h2 className="text-2xl font-semibold text-neutral-900">Access Denied</h2>
                <p className="text-neutral-500 mt-2">Only admins or superusers can manage lost inventory.</p>
                <BackLink to="/purchases/inventory" className="mt-4">Back to Inventory</BackLink>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-neutral-900">Manage Inventory</h1>
                <p className="text-neutral-500 mt-1">Mark lost, damaged, or missing products from inventory</p>
                <div className="mt-2 flex gap-4">
                    <BackLink to="/purchases/inventory">Back to Inventory</BackLink>
                    <BackLink to="/purchases/lost-inventory/records" direction="right">View Lost Inventory Records</BackLink>
                </div>
            </div>

            <Card className="p-6 space-y-4">
                <h3 className="font-semibold text-neutral-900">Search Product</h3>
                <Select
                    label="Type"
                    value={addType}
                    onChange={(e) => {
                        setAddType(e.target.value);
                        setSearchTerm('');
                        setSearchResults([]);
                    }}
                    options={TYPE_OPTIONS}
                />
                <SearchBar
                    onSearch={setSearchTerm}
                    placeholder="Search products by name or code, then press Enter..."
                />

                {searching && (
                    <div className="flex justify-center py-4">
                        <LoadingSpinner size="sm" />
                    </div>
                )}

                {!searching && searchResults.length > 0 && (
                    <div className="divide-y divide-neutral-100 border border-neutral-200 rounded-xl overflow-hidden">
                        {searchResults.map((item) => (
                            <button
                                key={item.id}
                                type="button"
                                onClick={() => handleAddProduct(item)}
                                className="w-full flex items-center justify-between px-4 py-3 hover:bg-neutral-50 transition-colors text-left"
                            >
                                <div>
                                    <p className="font-medium text-neutral-900">{item.product?.name}</p>
                                    <p className="text-xs text-neutral-500">{item.product?.code}</p>
                                </div>
                                <Badge variant={item.quantity <= 5 ? 'warning' : 'success'}>
                                    In stock: {item.quantity}
                                </Badge>
                            </button>
                        ))}
                    </div>
                )}
            </Card>

            <Card className="p-6 space-y-4">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <h3 className="font-semibold text-neutral-900">Lost Items Batch</h3>
                    {cart.length > 0 && (
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleAutoAllocateAllLines}
                            loading={bulkAutoAllocating}
                        >
                            Auto-Allocate All
                        </Button>
                    )}
                </div>

                {cart.length === 0 ? (
                    <p className="text-center text-neutral-500 py-6">
                        Search for a product above and select it to add to this batch.
                    </p>
                ) : (
                    <div className="space-y-3">
                        {cart.map((line, index) => (
                            <div key={cartLineKey(line.type, line.product_id)} className="grid grid-cols-1 md:grid-cols-6 gap-3 p-4 bg-neutral-50 rounded-xl items-end">
                                <div className="md:col-span-2">
                                    <Badge variant={TYPE_BADGE[line.type]?.variant || 'default'} size="sm">
                                        {TYPE_BADGE[line.type]?.label || line.type}
                                    </Badge>
                                    <p className="text-sm font-medium text-neutral-900 mt-1">{line.product_name}</p>
                                    <p className="text-xs text-neutral-500">
                                        {line.product_code} — Available: {line.available_quantity}
                                    </p>
                                </div>
                                <Input
                                    label="Quantity Lost"
                                    type="number"
                                    min="1"
                                    value={line.quantity}
                                    onChange={(e) => {
                                        const raw = e.target.value;
                                        if (raw !== '' && !/^\d+$/.test(raw)) return;
                                        handleUpdateLine(index, 'quantity', raw);
                                    }}
                                />
                                <Input
                                    label="Reason (optional)"
                                    value={line.reason}
                                    onChange={(e) => handleUpdateLine(index, 'reason', e.target.value)}
                                    placeholder="Damaged, expired..."
                                />
                                <div>
                                    <p className="text-xs text-neutral-500">FIFO Cost</p>
                                    {line.previewLoading ? (
                                        <p className="text-sm text-neutral-400">Calculating...</p>
                                    ) : (
                                        <>
                                            <p className="font-semibold text-neutral-900">Rs. {formatCurrency(line.total_cost)}</p>
                                            <p className="text-xs text-neutral-500">@ Rs. {formatCurrency(line.unit_cost)}/unit</p>
                                        </>
                                    )}
                                    {!line.previewLoading && !line.sufficient_stock && (
                                        <p className="text-xs text-error-600 mt-1">Exceeds available stock</p>
                                    )}
                                </div>
                                <Button
                                    variant="danger"
                                    size="sm"
                                    onClick={() => handleRemoveLine(index)}
                                >
                                    Remove
                                </Button>
                                <div className="md:col-span-6">
                                    <p className="text-xs font-medium text-neutral-700 mb-1.5">
                                        Shelf Allocation (which shelves this quantity is taken from)
                                    </p>
                                    <ShelfAllocationEditor
                                        mode="consumption"
                                        value={line.shelf_allocations}
                                        onChange={(next) => handleUpdateLine(index, 'shelf_allocations', next)}
                                        shelves={shelfCandidatesByProduct[cartLineKey(line.type, line.product_id)] || []}
                                        requiredQuantity={Number(line.quantity) || 0}
                                        productId={line.product_id}
                                        autoAllocateApi={line.type === 'raw_material' ? purchasesApi.shelves.autoAllocate : undefined}
                                        disabled={bulkAutoAllocating}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <div className="pt-2">
                    <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                        Batch Note (optional)
                    </label>
                    <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        rows={2}
                        placeholder="Overall note for this batch, e.g. warehouse audit 2026-07-16"
                        className="w-full px-4 py-3 bg-white border border-neutral-200 rounded-xl focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 outline-none transition-all"
                    />
                </div>

                {error && <InlineAlert variant="error" message={error} />}

                {successMessage && <InlineAlert variant="success" message={successMessage} />}

                <div className="flex items-center justify-between pt-4 border-t border-neutral-200">
                    <div>
                        <p className="text-sm text-neutral-500">Total Lost Value</p>
                        <p className="text-2xl font-bold text-error-600">Rs. {formatCurrency(grandTotal)}</p>
                    </div>
                    <Button onClick={handleSubmit} loading={submitting} disabled={cart.length === 0 || hasUnallocatedShelves}>
                        Record Lost Inventory
                    </Button>
                </div>
            </Card>
        </div>
    );
};

export default LostInventoryPage;
