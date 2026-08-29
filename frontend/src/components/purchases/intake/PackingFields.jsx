import PropTypes from 'prop-types';
import Select from '../../ui/Select';
import Input from '../../ui/Input';
import { purchasesApi } from '../../../services/purchasesApi';
import { useLookupOptions } from '../../../hooks/usePurchases';

export const initialPackingData = {
    packing_size_id: '',
    rate_per_kg: '',
    weight_kg: '',
};

export const validatePacking = (f) => {
    if (!f.packing_size_id) return 'Please select a Packing Size.';
    if (!f.rate_per_kg || parseFloat(f.rate_per_kg) <= 0) return 'Please enter a valid rate per kg.';
    if (!f.weight_kg || parseFloat(f.weight_kg) <= 0) return 'Please enter a valid weight (kg).';
    return null;
};

export const buildPackingPayload = (f) => ({
    packing_size_id: parseInt(f.packing_size_id, 10),
    rate_per_kg: parseFloat(f.rate_per_kg) || 0,
    weight_kg: parseFloat(f.weight_kg) || 0,
});

// Packing intake — total = rate_per_kg * weight_kg. The stored quantity IS
// the weight in kg, no unit conversion — called out explicitly since that's
// easy to misread as a piece count.
const PackingFields = ({ data, onChange }) => {
    const { options: packingSizeOptions, loading: loadingSizes } = useLookupOptions(purchasesApi.packingSizes);

    const rate = parseFloat(data.rate_per_kg) || 0;
    const weight = parseFloat(data.weight_kg) || 0;
    const total = rate * weight;

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-neutral-900">Packing Purchase</h3>

            <Select
                label="Packing Size"
                value={data.packing_size_id}
                onChange={(e) => onChange({ ...data, packing_size_id: e.target.value })}
                options={packingSizeOptions}
                placeholder={loadingSizes ? 'Loading...' : 'Select packing size'}
                disabled={loadingSizes}
                required
            />

            <div className="grid grid-cols-2 gap-4">
                <Input
                    label="Rate per kg (PKR)"
                    type="number"
                    step="0.01"
                    min="0"
                    value={data.rate_per_kg}
                    onChange={(e) => onChange({ ...data, rate_per_kg: e.target.value })}
                    required
                />
                <Input
                    label="Weight (kg)"
                    type="number"
                    step="0.01"
                    min="0"
                    value={data.weight_kg}
                    onChange={(e) => onChange({ ...data, weight_kg: e.target.value })}
                    required
                />
            </div>
            <p className="text-xs text-neutral-400 -mt-2">
                The quantity recorded on the purchase item is this weight in kg — there's no separate piece count.
            </p>

            {(rate > 0 || weight > 0) && (
                <p className="text-sm text-neutral-500">
                    Total cost: <span className="font-medium text-neutral-900">{total.toFixed(2)} PKR</span>
                    {' '}({rate} × {weight})
                </p>
            )}
        </div>
    );
};

PackingFields.propTypes = {
    data: PropTypes.object.isRequired,
    onChange: PropTypes.func.isRequired,
};

export default PackingFields;
