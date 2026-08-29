import PropTypes from 'prop-types';
import SearchableSelect from '../../ui/SearchableSelect';
import Input from '../../ui/Input';
import Select from '../../ui/Select';
import MethodSplitPicker from '../../paymentMethods/MethodSplitPicker';

// Fields shared by all 4 RM purchase-intake forms (Jumbo/Cores/Packing/
// Cartons): supplier, GST/WHT, description, payment type + advance +
// method-allocation split. Mirrors the supplier/payment-type/advance block
// in PurchaseOrderFormModal so the two flows feel identical.
const PurchaseIntakeCommonFields = ({
    common, setCommon, methodAllocations, setMethodAllocations, onSearchSuppliers,
}) => {
    const isAdvance = common.payment_type === 'advance';
    const advanceAmountValue = parseFloat(common.advance_amount) || 0;

    return (
        <div className="space-y-4">
            <SearchableSelect
                label="Supplier"
                value={common.supplier}
                selectedLabel={common.supplier_label}
                onChange={(value, option) => setCommon({
                    ...common,
                    supplier: value,
                    supplier_label: option?.label ?? '',
                })}
                onSearch={onSearchSuppliers}
                placeholder="Search supplier by name or code"
                required
            />

            <div className="grid grid-cols-2 gap-4">
                <Input
                    label="GST %"
                    type="number"
                    step="0.01"
                    min="0"
                    value={common.gst}
                    onChange={(e) => setCommon({ ...common, gst: e.target.value })}
                    placeholder="0"
                />
                <Input
                    label="WHT %"
                    type="number"
                    step="0.01"
                    min="0"
                    value={common.wht}
                    onChange={(e) => setCommon({ ...common, wht: e.target.value })}
                    placeholder="0"
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <Select
                    label="Payment Type"
                    value={common.payment_type}
                    onChange={(e) => setCommon({ ...common, payment_type: e.target.value })}
                    options={[
                        { value: 'advance', label: 'Advance' },
                        { value: 'after_delivery', label: 'After Delivery' },
                    ]}
                    required
                />
                {isAdvance && (
                    <Input
                        label="Advance Amount (PKR)"
                        type="number"
                        step="0.01"
                        min="0"
                        value={common.advance_amount}
                        onChange={(e) => setCommon({ ...common, advance_amount: e.target.value })}
                        placeholder="Enter advance amount"
                        required
                    />
                )}
            </div>

            {isAdvance && (
                <div>
                    <p className="text-sm font-medium text-neutral-700 mb-2">Advance Payment Method</p>
                    <MethodSplitPicker
                        totalAmount={advanceAmountValue}
                        value={methodAllocations}
                        onChange={setMethodAllocations}
                    />
                </div>
            )}

            <Input
                label="Description"
                value={common.description}
                onChange={(e) => setCommon({ ...common, description: e.target.value })}
                placeholder="Purchase description (optional)"
            />
        </div>
    );
};

PurchaseIntakeCommonFields.propTypes = {
    common: PropTypes.object.isRequired,
    setCommon: PropTypes.func.isRequired,
    methodAllocations: PropTypes.array.isRequired,
    setMethodAllocations: PropTypes.func.isRequired,
    onSearchSuppliers: PropTypes.func.isRequired,
};

export default PurchaseIntakeCommonFields;
