import PropTypes from 'prop-types';
import SearchableSelect from '../../ui/SearchableSelect';
import Input from '../../ui/Input';
import { purchasesApi } from '../../../services/purchasesApi';

export const initialCoreData = {
    quantity: '',
    unit_price: '',
    core_name_id: '',
    core_name_label: '',
    core_length_id: '',
    core_length_label: '',
    core_thickness_id: '',
    core_thickness_label: '',
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

const searchCoreNames = async (query) => {
    const res = await purchasesApi.coreNames.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const searchCoreLengths = async (query) => {
    const res = await purchasesApi.coreLengths.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const searchCoreThicknesses = async (query) => {
    const res = await purchasesApi.coreThicknesses.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

// Core intake — simplest form: pick optional attribute tags, enter
// quantity + unit price. Total is quantity * unit_price.
const CoreFields = ({ data, onChange }) => {
    const quantity = parseFloat(data.quantity) || 0;
    const unitPrice = parseFloat(data.unit_price) || 0;
    const total = quantity * unitPrice;

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-neutral-900">Core Purchase</h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <SearchableSelect
                    label="Core Name (optional)"
                    value={data.core_name_id}
                    selectedLabel={data.core_name_label}
                    onChange={(val, option) => onChange({ ...data, core_name_id: val, core_name_label: option?.label ?? '' })}
                    onSearch={searchCoreNames}
                    placeholder="Search core name..."
                />
                <SearchableSelect
                    label="Core Length (optional)"
                    value={data.core_length_id}
                    selectedLabel={data.core_length_label}
                    onChange={(val, option) => onChange({ ...data, core_length_id: val, core_length_label: option?.label ?? '' })}
                    onSearch={searchCoreLengths}
                    placeholder="Search core length..."
                />
                <SearchableSelect
                    label="Core Thickness (optional)"
                    value={data.core_thickness_id}
                    selectedLabel={data.core_thickness_label}
                    onChange={(val, option) => onChange({ ...data, core_thickness_id: val, core_thickness_label: option?.label ?? '' })}
                    onSearch={searchCoreThicknesses}
                    placeholder="Search core thickness..."
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
