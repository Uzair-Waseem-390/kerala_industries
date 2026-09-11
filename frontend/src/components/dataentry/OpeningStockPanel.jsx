import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { PackagePlus, ClipboardList, Plus, Trash2 } from 'lucide-react';
import { dataEntryApi } from '../../services/dataEntryApi';
import { purchasesApi } from '../../services/purchasesApi';
import { extractErrorMessage } from '../../utils/errorMessage';
import { useToast } from '../../context/ToastContext';
import Card from '../ui/Card';
import Input from '../ui/Input';
import Button from '../ui/Button';
import SearchableSelect from '../ui/SearchableSelect';
import LoadingSpinner from '../ui/LoadingSpinner';
import InlineAlert from '../ui/InlineAlert';
import EmptyState from '../ui/EmptyState';
import Tabs from '../ui/Tabs';

const fmt = (v) => Number(v || 0).toFixed(2);

const TYPE_TABS = [
    { value: 'rm', label: 'Raw Material' },
    { value: 'wip_core', label: 'WIP — Core' },
    { value: 'wip_piece', label: 'WIP — Piece' },
    { value: 'fg', label: 'Finished Goods' },
];

// RM keeps its own row shape (free-text product search). WIP/FG are
// attribute-defined (name + yard + length, not freely named): "Name"
// backend-searches the real RM Jumbo Names (purchases.JumboName, 2026-09 —
// was a separate closed "binding" lookup), same server-side search_q()
// pattern as Product/Shelf below (purchases.selectors.get_all_jumbo_names)
// — the backend get-or-creates the matching RewoundCoreBinding from that
// name's value, mirroring how a real production recipe derives it.
// Yard/length are typed numbers — the backend get-or-creates the matching
// product by that exact value, reusing it and adding quantity if it
// already exists, or creating it if it doesn't.
const emptyRmRow = () => ({ product_id: '', product_label: '', shelf_id: '', shelf_label: '', quantity: '', unit_price: '', gst: '0', wht: '0', description: '' });
const emptyAttrRow = () => ({ jumbo_name_id: '', jumbo_name_label: '', yard_value: '', length_mm_value: '', shelf_id: '', shelf_label: '', quantity: '', unit_cost: '' });

const OpeningStockPanel = () => {
    const { toast } = useToast();
    const [stockType, setStockType] = useState('rm');
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [saving, setSaving] = useState(false);
    const [rmRows, setRmRows] = useState([emptyRmRow()]);
    const [attrRows, setAttrRows] = useState([emptyAttrRow()]);
    const [bannerError, setBannerError] = useState('');

    const isRm = stockType === 'rm';
    const isFg = stockType === 'fg';
    const stage = stockType === 'wip_core' ? 'rewinding' : 'cutting';

    const loadRecords = useCallback(async (type) => {
        try {
            const endpoint = type === 'rm' ? dataEntryApi.openingStock
                : type === 'fg' ? dataEntryApi.openingFgStock
                : dataEntryApi.openingWipStock;
            const res = await endpoint.getAll({ page_size: 500 });
            setRecords(res?.results ?? res ?? []);
            setLoadError('');
        } catch (err) {
            setLoadError(extractErrorMessage(err, 'Failed to load opening stock entries.'));
        }
    }, []);

    useEffect(() => {
        (async () => {
            setLoading(true);
            try {
                await loadRecords(stockType);
            } finally {
                setLoading(false);
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stockType]);

    const handleTypeChange = (value) => {
        setStockType(value);
        setBannerError('');
        setRmRows([emptyRmRow()]);
        setAttrRows([emptyAttrRow()]);
    };

    const searchProducts = useCallback(async (query) => {
        const res = await purchasesApi.products.getAll({ search: query, page_size: 25 });
        const results = res?.results ?? res ?? [];
        return results.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }));
    }, []);

    const searchShelves = useCallback(async (query) => {
        const res = await purchasesApi.shelves.getAll({ search: query, page_size: 25 });
        const results = res?.results ?? res ?? [];
        return results.map(s => ({ value: s.id, label: s.name }));
    }, []);

    const searchJumboNames = useCallback(async (query) => {
        const res = await purchasesApi.jumboNames.getAll({ search: query, page_size: 25 });
        const results = res?.results ?? res ?? [];
        return results.map(n => ({ value: n.id, label: n.value }));
    }, []);

    const updateRmRow = (i, key, val) => setRmRows(rs => rs.map((r, idx) => idx === i ? { ...r, [key]: val } : r));
    const addRmRow = () => setRmRows(rs => [...rs, emptyRmRow()]);
    const removeRmRow = (i) => setRmRows(rs => rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs);

    const updateAttrRow = (i, key, val) => setAttrRows(rs => rs.map((r, idx) => idx === i ? { ...r, [key]: val } : r));
    const addAttrRow = () => setAttrRows(rs => [...rs, emptyAttrRow()]);
    const removeAttrRow = (i) => setAttrRows(rs => rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs);

    const handleSubmitRm = async (e) => {
        e.preventDefault();
        setBannerError('');

        const seen = new Set();
        const items = [];
        for (const r of rmRows) {
            if (!r.product_id) return setBannerError('Every row needs a product.');
            if (seen.has(r.product_id)) return setBannerError('A product is listed more than once.');
            seen.add(r.product_id);
            if (!r.shelf_id) return setBannerError('Every row needs a shelf.');
            if (!r.quantity || parseFloat(r.quantity) <= 0) return setBannerError('Quantity must be greater than 0.');
            if (!r.unit_price || parseFloat(r.unit_price) <= 0) return setBannerError('Unit price must be greater than 0.');
            items.push({
                product_id: parseInt(r.product_id),
                shelf_id: parseInt(r.shelf_id),
                quantity: parseFloat(r.quantity),
                unit_price: r.unit_price,
                gst: r.gst || 0,
                wht: r.wht || 0,
                description: r.description || '',
            });
        }

        setSaving(true);
        try {
            await dataEntryApi.openingStock.create({ items });
            toast.success('Opening stock added to inventory.');
            setRmRows([emptyRmRow()]);
            await loadRecords('rm');
        } catch (err) {
            setBannerError(extractErrorMessage(err, 'Failed to add opening stock.'));
        } finally {
            setSaving(false);
        }
    };

    const handleSubmitAttr = async (e) => {
        e.preventDefault();
        setBannerError('');

        const items = [];
        for (const r of attrRows) {
            if (!r.jumbo_name_id) return setBannerError('Every row needs a name.');
            if (!r.yard_value || parseFloat(r.yard_value) <= 0) return setBannerError('Yard must be greater than 0.');
            if (!r.length_mm_value || parseFloat(r.length_mm_value) <= 0) return setBannerError('Length (mm) must be greater than 0.');
            if (!r.shelf_id) return setBannerError('Every row needs a shelf.');
            if (!r.quantity || parseFloat(r.quantity) <= 0) return setBannerError('Quantity must be greater than 0.');
            if (!r.unit_cost || parseFloat(r.unit_cost) <= 0) return setBannerError('Unit cost must be greater than 0.');
            items.push({
                jumbo_name_id: parseInt(r.jumbo_name_id),
                yard_value: r.yard_value,
                length_mm_value: r.length_mm_value,
                shelf_id: parseInt(r.shelf_id),
                quantity: parseFloat(r.quantity),
                unit_cost: r.unit_cost,
                ...(isFg ? {} : { stage }),
            });
        }

        setSaving(true);
        try {
            const endpoint = isFg ? dataEntryApi.openingFgStock : dataEntryApi.openingWipStock;
            await endpoint.create({ items });
            toast.success('Opening stock added to inventory.');
            setAttrRows([emptyAttrRow()]);
            await loadRecords(stockType);
        } catch (err) {
            setBannerError(extractErrorMessage(err, 'Failed to add opening stock.'));
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>;
    }

    return (
        <div className="space-y-6">
            <Tabs tabs={TYPE_TABS} activeTab={stockType} onChange={handleTypeChange} />

            <Card hover={false}>
                <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center flex-shrink-0">
                        <PackagePlus className="w-5 h-5 text-primary-600" />
                    </div>
                    <h3 className="font-semibold text-neutral-900">Add Opening Stock</h3>
                </div>

                {isRm ? (
                    <form onSubmit={handleSubmitRm} className="space-y-4">
                        {rmRows.map((row, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="space-y-3 border border-neutral-100 rounded-xl p-4 bg-neutral-50/50"
                            >
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                                    <div className="md:col-span-3">
                                        <SearchableSelect
                                            label="Product"
                                            value={row.product_id}
                                            selectedLabel={row.product_label}
                                            onChange={(v, option) => {
                                                updateRmRow(i, 'product_id', v);
                                                updateRmRow(i, 'product_label', option?.label ?? '');
                                            }}
                                            onSearch={searchProducts}
                                            placeholder="Search product..."
                                        />
                                    </div>
                                    <div className="md:col-span-3">
                                        <SearchableSelect
                                            label="Shelf"
                                            value={row.shelf_id}
                                            selectedLabel={row.shelf_label}
                                            onChange={(v, option) => {
                                                updateRmRow(i, 'shelf_id', v);
                                                updateRmRow(i, 'shelf_label', option?.label ?? '');
                                            }}
                                            onSearch={searchShelves}
                                            placeholder="Search shelf..."
                                        />
                                    </div>
                                    <div className="md:col-span-3">
                                        <Input label="Qty" type="number" min="0.0001" step="0.0001"
                                            value={row.quantity} onChange={(e) => updateRmRow(i, 'quantity', e.target.value)} placeholder="Qty" />
                                    </div>
                                    <div className="md:col-span-3">
                                        <Input label="Unit Price" type="number" step="0.01" min="0.01"
                                            value={row.unit_price} onChange={(e) => updateRmRow(i, 'unit_price', e.target.value)} placeholder="Price" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                                    <div className="md:col-span-2">
                                        <Input label="GST%" type="number" step="0.01" min="0"
                                            value={row.gst} onChange={(e) => updateRmRow(i, 'gst', e.target.value)} />
                                    </div>
                                    <div className="md:col-span-2">
                                        <Input label="WHT%" type="number" step="0.01" min="0"
                                            value={row.wht} onChange={(e) => updateRmRow(i, 'wht', e.target.value)} />
                                    </div>
                                    <div className="md:col-span-6" />
                                    <div className="md:col-span-2">
                                        <Button type="button" variant="secondary" size="sm" className="w-full"
                                            icon={Trash2}
                                            onClick={() => removeRmRow(i)} disabled={rmRows.length === 1}>
                                            Remove
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        ))}

                        <div className="flex items-center gap-3">
                            <Button type="button" variant="outline" size="sm" icon={Plus} onClick={addRmRow}>
                                Add Product
                            </Button>
                        </div>

                        <InlineAlert
                            variant="info"
                            message="Adds quantities to inventory (FIFO-ready). No cash or supplier-payable effect."
                        />
                        {bannerError && <InlineAlert variant="error" message={bannerError} />}
                        <Button type="submit" loading={saving} icon={PackagePlus} className="w-full sm:w-auto">
                            Add Opening Stock
                        </Button>
                    </form>
                ) : (
                    <form onSubmit={handleSubmitAttr} className="space-y-4">
                        {attrRows.map((row, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="space-y-3 border border-neutral-100 rounded-xl p-4 bg-neutral-50/50"
                            >
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                                    <div className="md:col-span-3">
                                        <SearchableSelect
                                            label="Name"
                                            value={row.jumbo_name_id}
                                            selectedLabel={row.jumbo_name_label}
                                            onChange={(v, option) => {
                                                updateAttrRow(i, 'jumbo_name_id', v);
                                                updateAttrRow(i, 'jumbo_name_label', option?.label ?? '');
                                            }}
                                            onSearch={searchJumboNames}
                                            placeholder="Search name..."
                                        />
                                    </div>
                                    <div className="md:col-span-3">
                                        <Input
                                            label="Yard" type="number" step="0.0001" min="0.0001"
                                            value={row.yard_value}
                                            onChange={(e) => updateAttrRow(i, 'yard_value', e.target.value)}
                                            placeholder="e.g. 24"
                                        />
                                    </div>
                                    <div className="md:col-span-3">
                                        <Input
                                            label="Length (mm)" type="number" step="0.0001" min="0.0001"
                                            value={row.length_mm_value}
                                            onChange={(e) => updateAttrRow(i, 'length_mm_value', e.target.value)}
                                            placeholder="e.g. 100"
                                        />
                                    </div>
                                    <div className="md:col-span-3">
                                        <SearchableSelect
                                            label="Shelf"
                                            value={row.shelf_id}
                                            selectedLabel={row.shelf_label}
                                            onChange={(v, option) => {
                                                updateAttrRow(i, 'shelf_id', v);
                                                updateAttrRow(i, 'shelf_label', option?.label ?? '');
                                            }}
                                            onSearch={searchShelves}
                                            placeholder="Search shelf..."
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                                    <div className="md:col-span-3">
                                        <Input label="Qty" type="number" min="0.0001" step="0.0001"
                                            value={row.quantity} onChange={(e) => updateAttrRow(i, 'quantity', e.target.value)} placeholder="Qty" />
                                    </div>
                                    <div className="md:col-span-3">
                                        <Input label="Unit Cost" type="number" step="0.01" min="0.01"
                                            value={row.unit_cost} onChange={(e) => updateAttrRow(i, 'unit_cost', e.target.value)} placeholder="Cost" />
                                    </div>
                                    <div className="md:col-span-4" />
                                    <div className="md:col-span-2">
                                        <Button type="button" variant="secondary" size="sm" className="w-full"
                                            icon={Trash2}
                                            onClick={() => removeAttrRow(i)} disabled={attrRows.length === 1}>
                                            Remove
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        ))}

                        <div className="flex items-center gap-3">
                            <Button type="button" variant="outline" size="sm" icon={Plus} onClick={addAttrRow}>
                                Add Product
                            </Button>
                        </div>

                        <InlineAlert
                            variant="info"
                            message="Adds quantities to inventory (FIFO-ready, real cost basis). No cash effect. A matching product is reused if this exact name/yard/length combination already exists."
                        />
                        {bannerError && <InlineAlert variant="error" message={bannerError} />}
                        <Button type="submit" loading={saving} icon={PackagePlus} className="w-full sm:w-auto">
                            Add Opening Stock
                        </Button>
                    </form>
                )}
            </Card>

            <Card hover={false}>
                <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 rounded-xl bg-neutral-100 flex items-center justify-center flex-shrink-0">
                        <ClipboardList className="w-5 h-5 text-neutral-500" />
                    </div>
                    <h3 className="font-semibold text-neutral-900">Recorded Stock Entries ({records.length})</h3>
                </div>
                {loadError && <InlineAlert variant="error" message={loadError} onRetry={() => loadRecords(stockType)} className="mb-4" />}
                {records.length === 0 ? (
                    <EmptyState
                        title="No opening stock entries yet"
                        description="Stock batches you add will appear here for audit."
                    />
                ) : isRm ? (
                    <div className="space-y-4">
                        {records.map(order => (
                            <div key={order.id} className="border border-neutral-200 rounded-xl p-4">
                                <div className="flex items-center justify-between mb-2 flex-wrap gap-1">
                                    <span className="font-medium text-neutral-900">{order.order_number}</span>
                                    <span className="text-xs text-neutral-500">{new Date(order.created_at).toLocaleString()}</span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs text-neutral-500 border-b border-neutral-100">
                                                <th className="py-1 pr-3">Product</th>
                                                <th className="py-1 pr-3 text-right">Qty</th>
                                                <th className="py-1 pr-3 text-right">Unit Price</th>
                                                <th className="py-1 text-right">Total</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-neutral-50">
                                            {(order.items || []).map((it, idx) => (
                                                <tr key={idx}>
                                                    <td className="py-1 pr-3">{it.product_name}</td>
                                                    <td className="py-1 pr-3 text-right">{it.quantity}</td>
                                                    <td className="py-1 pr-3 text-right">{fmt(it.unit_price)}</td>
                                                    <td className="py-1 text-right">{fmt(it.total_price)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : isFg ? (
                    <div className="space-y-4">
                        {records.map(recipe => (
                            <div key={recipe.id} className="border border-neutral-200 rounded-xl p-4">
                                <div className="flex items-center justify-between flex-wrap gap-1">
                                    <span className="font-medium text-neutral-900">{recipe.recipe_number}</span>
                                    <span className="text-xs text-neutral-500">{new Date(recipe.created_at).toLocaleString()}</span>
                                </div>
                                <div className="text-sm mt-1 flex items-center justify-between">
                                    <span>{recipe.product_name} — Qty {recipe.quantity}</span>
                                    <span className="text-neutral-500">Unit Cost: {fmt(recipe.unit_cost)}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="space-y-4">
                        {records.map(recipe => (
                            <div key={recipe.id} className="border border-neutral-200 rounded-xl p-4">
                                <div className="flex items-center justify-between mb-2 flex-wrap gap-1">
                                    <span className="font-medium text-neutral-900">{recipe.recipe_number}</span>
                                    <span className="text-xs text-neutral-500">{new Date(recipe.created_at).toLocaleString()}</span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-xs text-neutral-500 border-b border-neutral-100">
                                                <th className="py-1 pr-3">Product</th>
                                                <th className="py-1 pr-3">Stage</th>
                                                <th className="py-1 pr-3 text-right">Qty</th>
                                                <th className="py-1 text-right">Unit Cost</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-neutral-50">
                                            {(recipe.items || []).map((it, idx) => (
                                                <tr key={idx}>
                                                    <td className="py-1 pr-3">{it.product_name}</td>
                                                    <td className="py-1 pr-3">{it.stage === 'cutting' ? 'Piece' : 'Core'}</td>
                                                    <td className="py-1 pr-3 text-right">{it.quantity}</td>
                                                    <td className="py-1 text-right">{fmt(it.unit_cost)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </div>
    );
};

export default OpeningStockPanel;
