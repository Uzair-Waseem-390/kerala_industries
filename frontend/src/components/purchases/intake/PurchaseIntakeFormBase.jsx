import { useState } from 'react';
import PropTypes from 'prop-types';
import Button from '../../ui/Button';
import InlineAlert from '../../ui/InlineAlert';
import PurchaseIntakeCommonFields from './PurchaseIntakeCommonFields';
import { isSplitBalanced } from '../../paymentMethods/MethodSplitPicker';
import { extractErrorMessage } from '../../../utils/errorMessage';

const emptyCommon = {
    supplier: '',
    supplier_label: '',
    gst: '',
    wht: '',
    description: '',
    payment_type: 'after_delivery',
    advance_amount: '',
};

// Shared shell for the 4 RM purchase-intake forms (Jumbo/Cores/Packing/
// Cartons). Owns the fields every family shares (supplier, GST/WHT,
// description, payment type/advance/method split) plus submit/validate
// wiring; each family only supplies its own extra fields via `renderFamilyFields`
// and how to validate/serialize them. Mount with `key={family}` from the
// parent tab so switching families resets all state cleanly (same pattern
// as ProductAttributesPage -> LookupManagerPanel).
const PurchaseIntakeFormBase = ({
    initialFamilyData,
    renderFamilyFields,
    validateFamily,
    buildFamilyPayload,
    createApi,
    onSearchSuppliers,
    onCreated,
    submitLabel,
}) => {
    const [common, setCommon] = useState(emptyCommon);
    const [familyData, setFamilyData] = useState(initialFamilyData);
    const [methodAllocations, setMethodAllocations] = useState([]);
    const [error, setError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const isAdvance = common.payment_type === 'advance';
    const advanceAmountValue = parseFloat(common.advance_amount) || 0;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!common.supplier) {
            setError('Please select a supplier.');
            return;
        }
        if (isAdvance && (!advanceAmountValue || advanceAmountValue <= 0)) {
            setError('Please enter a valid advance amount.');
            return;
        }
        if (isAdvance && !isSplitBalanced(advanceAmountValue, methodAllocations)) {
            setError('Payment method split must add up to the full advance amount.');
            return;
        }
        const familyError = validateFamily(familyData);
        if (familyError) {
            setError(familyError);
            return;
        }

        const payload = {
            supplier_id: parseInt(common.supplier, 10),
            gst: parseFloat(common.gst) || 0,
            wht: parseFloat(common.wht) || 0,
            description: common.description || '',
            payment_type: common.payment_type,
            advance_amount: isAdvance ? advanceAmountValue : 0,
            ...(isAdvance ? { method_allocations: methodAllocations } : {}),
            ...buildFamilyPayload(familyData),
        };

        setSubmitting(true);
        try {
            const order = await createApi(payload);
            // Reset the form so the same tab is ready for another entry.
            setCommon(emptyCommon);
            setFamilyData(initialFamilyData);
            setMethodAllocations([]);
            onCreated(order);
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to create purchase. Please check your input.'));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {renderFamilyFields(familyData, setFamilyData)}

            <div className="pt-4 border-t border-neutral-200">
                <PurchaseIntakeCommonFields
                    common={common}
                    setCommon={setCommon}
                    methodAllocations={methodAllocations}
                    setMethodAllocations={setMethodAllocations}
                    onSearchSuppliers={onSearchSuppliers}
                />
            </div>

            {error && <InlineAlert variant="error" message={error} />}

            <div className="flex justify-end">
                <Button
                    type="submit"
                    loading={submitting}
                    disabled={isAdvance && !isSplitBalanced(advanceAmountValue, methodAllocations)}
                >
                    {submitLabel}
                </Button>
            </div>
        </form>
    );
};

PurchaseIntakeFormBase.propTypes = {
    initialFamilyData: PropTypes.object.isRequired,
    renderFamilyFields: PropTypes.func.isRequired,
    validateFamily: PropTypes.func.isRequired,
    buildFamilyPayload: PropTypes.func.isRequired,
    createApi: PropTypes.func.isRequired,
    onSearchSuppliers: PropTypes.func.isRequired,
    onCreated: PropTypes.func.isRequired,
    submitLabel: PropTypes.string.isRequired,
};

export default PurchaseIntakeFormBase;
