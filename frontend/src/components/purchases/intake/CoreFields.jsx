import PropTypes from 'prop-types';
import Select from '../../ui/Select';
import Input from '../../ui/Input';
import { purchasesApi } from '../../../services/purchasesApi';
import { useLookupOptions } from '../../../hooks/usePurchases';

export const initialCoreData = {
    quantity: '',
    unit_price: '',
    core_name_id: '',
    core_length_id: '',
    core_thickness_id: '',
};

export const validateCore = (f) => {
    if (!f.quantity || parseFloat(f.quantity) <= 0) return 'Please enter a valid quantity.';
    if (!f.unit_price || parseFloat(f.unit_price) <= 0) return 'Please enter a valid unit price.';
    return null;
};

export const buildCorePayload = (f) => ({
    quantity: parseInt(f.quantity, 10) || 0,
    unit_price: parseFloat(f.unit_price) || 0,
    ...(f.core_name_id ? { core_name_id: parseInt(f.core_name_id, 10) } : {}),
    ...(f.core_length_id ? { core_length_id: parseInt(f.core_length_id, 10) } : {}),
    ...(f.core_thickness_id ? { core_thickness_id: parseInt(f.core_thickness_id, 10) } : {}),
});

// Core intake — simplest form: pick optional attribute tags, enter
// quantity + unit price. Total is quantity * unit_price.
const CoreFields = ({ data, onChange }) => {
    const { options: coreNameOptions, loading: loadingNames } = useLookupOptions(purchasesApi.coreNames);
    const { options: coreLengthOptions, loading: loadingLengths } = useLookupOptions(purchasesApi.coreLengths);
    const { options: coreThicknessOptions, loading: loadingThicknesses } = useLookupOptions(purchasesApi.coreThicknesses);

    const quantity = parseFloat(data.quantity) || 0;
    const unitPrice = parseFloat(data.unit_price) || 0;
    const total = quantity * unitPrice;

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-neutral-900">Core Purchase</h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Select
                    label="Core Name (optional)"
                    value={data.core_name_id}
                    onChange={(e) => onChange({ ...data, core_name_id: e.target.value })}
                    options={coreNameOptions}
                    placeholder={loadingNames ? 'Loading...' : 'Select core name'}
                    disabled={loadingNames}
                />
                <Select
                    label="Core Length (optional)"
                    value={data.core_length_id}
                    onChange={(e) => onChange({ ...data, core_length_id: e.target.value })}
                    options={coreLengthOptions}
                    placeholder={loadingLengths ? 'Loading...' : 'Select core length'}
                    disabled={loadingLengths}
                />
                <Select
                    label="Core Thickness (optional)"
                    value={data.core_thickness_id}
                    onChange={(e) => onChange({ ...data, core_thickness_id: e.target.value })}
                    options={coreThicknessOptions}
                    placeholder={loadingThicknesses ? 'Loading...' : 'Select core thickness'}
                    disabled={loadingThicknesses}
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <Input
                    label="Quantity"
                    type="number"
                    step="1"
                    min="1"
                    value={data.quantity}
                    onChange={(e) => onChange({ ...data, quantity: e.target.value })}
                    required
                />
                <Input
                    label="Unit Price (PKR)"
                    type="number"
                    step="0.01"
                    min="0"
                    value={data.unit_price}
                    onChange={(e) => onChange({ ...data, unit_price: e.target.value })}
                    required
                />
            </div>

            {(quantity > 0 || unitPrice > 0) && (
                <p className="text-sm text-neutral-500 -mt-2">
                    Total cost: <span className="font-medium text-neutral-900">{total.toFixed(2)} PKR</span>
                    {' '}({quantity} × {unitPrice})
                </p>
            )}
        </div>
    );
};

CoreFields.propTypes = {
    data: PropTypes.object.isRequired,
    onChange: PropTypes.func.isRequired,
};

export default CoreFields;
