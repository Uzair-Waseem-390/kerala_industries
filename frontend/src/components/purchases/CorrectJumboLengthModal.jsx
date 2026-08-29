import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import Modal from '../ui/Modal';
import Input from '../ui/Input';
import Button from '../ui/Button';
import InlineAlert from '../ui/InlineAlert';
import ShelfAllocationEditor from '../shared/ShelfAllocationEditor';
import { purchasesApi } from '../../services/purchasesApi';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const YARDS_PER_METER = 1.09361;

// Jumbo exact-length correction (confirmed Jumbo items only — items with
// expected_length_m set). Entering the exact length recomputes yards via
// the same 1.09361 factor the backend uses; if the new yards differ from
// the item's current quantity, the shortfall (removed from stock) or
// surplus (put away) must be covered by explicit shelf allocations summing
// exactly to that difference.
const CorrectJumboLengthModal = ({ isOpen, onClose, item, onCorrected }) => {
    const { toast } = useToast();
    const [exactLengthM, setExactLengthM] = useState('');
    const [allocations, setAllocations] = useState([]);
    const [error, setError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    // Batch rows (the source of `item` here) now carry product_id directly
    // (PurchaseBatchSerializer), so shelves.getCandidates can use it as-is.
    const productId = item?.product_id ?? null;

    useEffect(() => {
        if (isOpen) {
            setExactLengthM('');
            setAllocations([]);
            setError('');
        }
    }, [isOpen]);

    const meters = parseFloat(exactLengthM) || 0;
    const newYards = meters * YARDS_PER_METER;
    const currentQuantity = parseFloat(item?.quantity) || 0;
    // Positive = shortfall (must pull FROM shelves), negative = surplus
    // (must put away TO shelves) — either way the picker needs the absolute
    // difference the allocations must sum to.
    const diff = currentQuantity - newYards;
    const hasDiff = meters > 0 && Math.abs(diff) > 0.0001;

    // Consumption candidates for a shortfall (shelves that currently hold
    // this product) vs. put-away search for a surplus (any shelf).
    const searchShelvesForPutAway = async (query) => {
        const res = await purchasesApi.shelves.getAll({ search: query, page_size: 25 });
        const results = res?.results ?? res ?? [];
        return results.map((s) => ({ value: s.id, label: s.name, name: s.name }));
    };

    const [shortfallCandidates, setShortfallCandidates] = useState([]);
    const [loadingCandidates, setLoadingCandidates] = useState(false);

    useEffect(() => {
        if (!isOpen || !productId) return;
        if (diff <= 0) return; // only need candidate shelves for a shortfall
        let cancelled = false;
        setLoadingCandidates(true);
        purchasesApi.shelves.getCandidates(productId)
            .then((res) => {
                if (cancelled) return;
                const results = res?.results ?? res ?? [];
                setShortfallCandidates(results.map((s) => ({
                    id: s.id,
                    name: s.name,
                    available_quantity: s.available_quantity ?? s.quantity,
                })));
            })
            .catch(() => { if (!cancelled) setShortfallCandidates([]); })
            .finally(() => { if (!cancelled) setLoadingCandidates(false); });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, productId, diff > 0]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!meters || meters <= 0) {
            setError('Please enter a valid exact length.');
            return;
        }
        if (hasDiff) {
            const requiredTotal = Math.abs(diff);
            const allocatedTotal = allocations.reduce((sum, a) => sum + (parseFloat(a.quantity) || 0), 0);
            if (Math.abs(allocatedTotal - requiredTotal) > 0.0001) {
                setError(
                    `Shelf allocations must sum to exactly the ${diff > 0 ? 'shortfall' : 'surplus'} (${requiredTotal}), got ${allocatedTotal}.`
                );
                return;
            }
        }

        setSubmitting(true);
        try {
            const payload = {
                exact_length_m: meters,
                shelf_allocations: hasDiff
                    ? allocations
                        .filter((a) => a.shelf_id && a.quantity)
                        .map((a) => ({ shelf_id: parseInt(a.shelf_id, 10), quantity: parseFloat(a.quantity) }))
                    : [],
            };
            const updatedItem = await purchasesApi.purchaseItems.correctJumboLength(item.id, payload);
            toast.success('Jumbo length corrected');
            onCorrected(updatedItem);
            onClose();
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to correct jumbo length'));
        } finally {
            setSubmitting(false);
        }
    };

    if (!item) return null;

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Correct Jumbo Exact Length" size="lg">
            <form onSubmit={handleSubmit} className="space-y-5">
                <div className="text-sm text-neutral-500">
                    <p><span className="font-medium text-neutral-900">{item.product_name}</span> {item.product_code ? `(${item.product_code})` : ''}</p>
                    <p>Current quantity on this batch: <span className="font-medium text-neutral-900">{currentQuantity}</span> yards</p>
                </div>

                <Input
                    label="Exact Length (m)"
                    type="number"
                    step="0.01"
                    min="0"
                    value={exactLengthM}
                    onChange={(e) => setExactLengthM(e.target.value)}
                    required
                />

                {meters > 0 && (
                    <p className="text-sm text-neutral-500 -mt-3">
                        {meters} meters: {meters} × {YARDS_PER_METER} = <span className="font-medium text-neutral-900">{newYards.toFixed(4)} yards</span>
                    </p>
                )}

                {hasDiff && (
                    <div className="p-4 bg-neutral-50 rounded-lg border border-neutral-200 space-y-3">
                        <p className="text-sm font-medium text-neutral-700">
                            {diff > 0
                                ? `This correction removes ${diff.toFixed(4)} yards — pick which shelf(s) to pull it from.`
                                : `This correction adds ${(-diff).toFixed(4)} yards — pick which shelf(s) to put it away on.`}
                        </p>
                        {diff > 0 ? (
                            <>
                                {loadingCandidates ? (
                                    <p className="text-sm text-neutral-400">Loading shelves holding this product...</p>
                                ) : (
                                    <ShelfAllocationEditor
                                        value={allocations}
                                        onChange={setAllocations}
                                        shelves={shortfallCandidates}
                                        requiredQuantity={Math.abs(diff)}
                                        mode="consumption"
                                        disabled={submitting}
                                    />
                                )}
                            </>
                        ) : (
                            <ShelfAllocationEditor
                                value={allocations}
                                onChange={setAllocations}
                                onSearchShelves={searchShelvesForPutAway}
                                requiredQuantity={Math.abs(diff)}
                                mode="putaway"
                                disabled={submitting}
                            />
                        )}
                    </div>
                )}

                {error && <InlineAlert variant="error" message={error} />}

                <div className="flex justify-end gap-3 pt-2 border-t border-neutral-200">
                    <Button type="button" variant="secondary" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit" loading={submitting}>
                        Save Correction
                    </Button>
                </div>
            </form>
        </Modal>
    );
};

CorrectJumboLengthModal.propTypes = {
    isOpen: PropTypes.bool.isRequired,
    onClose: PropTypes.func.isRequired,
    item: PropTypes.object,
    onCorrected: PropTypes.func.isRequired,
};

export default CorrectJumboLengthModal;
