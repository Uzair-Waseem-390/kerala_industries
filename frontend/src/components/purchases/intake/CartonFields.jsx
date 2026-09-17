import PropTypes from 'prop-types';
import SearchableSelect from '../../ui/SearchableSelect';
import Input from '../../ui/Input';
import { purchasesApi } from '../../../services/purchasesApi';

export const initialCartonData = {
    carton_size_id: '',
    carton_size_label: '',
    quantity: '',
    unit_price: '',
};

export const validateCarton = (f) => {
    if (!f.carton_size_id) return 'Please select a Carton Size.';
    if (!f.quantity || parseFloat(f.quantity) <= 0) return 'Please enter a valid quantity.';
    if (!f.unit_price || parseFloat(f.unit_price) <= 0) return 'Please enter a valid unit price.';
    return null;
};

export const buildCartonPayload = (f) => ({
    carton_size_id: parseInt(f.carton_size_id, 10),
    quantity: parseInt(f.quantity, 10) || 0,
    unit_price: parseFloat(f.unit_price) || 0,
});

const searchCartonSizes = async (query) => {
    const res = await purchasesApi.cartonSizes.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

// Carton intake — unit_price is price per piece; total = quantity * unit_price.
const CartonFields = ({ data, onChange }) => {
    const quantity = parseFloat(data.quantity) || 0;
    const unitPrice = parseFloat(data.unit_price) || 0;
    const total = quantity * unitPrice;

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-neutral-900">Carton Purchase</h3>

            <SearchableSelect
                label="Carton Size"
                value={data.carton_size_id}
                selectedLabel={data.carton_size_label}
                onChange={(val, option) => onChange({ ...data, carton_size_id: val, carton_size_label: option?.label ?? '' })}
                onSearch={searchCartonSizes}
                placeholder="Search carton size..."
                required
            />

            <div className="grid grid-cols-2 gap-4">
                <Input
                    label="Quantity (pieces)"
                    type="number"
                    step="1"
                    min="1"
                    value={data.quantity}
                    onChange={(e) => onChange({ ...data, quantity: e.target.value })}
                    required
                />
                <Input
                    label="Unit Price (PKR / piece)"
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

CartonFields.propTypes = {
    data: PropTypes.object.isRequired,
    onChange: PropTypes.func.isRequired,
};

export default CartonFields;
