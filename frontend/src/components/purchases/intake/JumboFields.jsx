import PropTypes from 'prop-types';
import SearchableSelect from '../../ui/SearchableSelect';
import Input from '../../ui/Input';
import { purchasesApi } from '../../../services/purchasesApi';

const YARDS_PER_METER = 1.09361;

export const initialJumboData = {
    jumbo_name_id: '',
    jumbo_name_label: '',
    rate_per_kg: '',
    weight_kg: '',
    freight_cost: '',
    expected_length_m: '',
};

export const validateJumbo = (f) => {
    if (!f.jumbo_name_id) return 'Please select a Jumbo Name.';
    if (!f.rate_per_kg || parseFloat(f.rate_per_kg) <= 0) return 'Please enter a valid rate per kg.';
    if (!f.weight_kg || parseFloat(f.weight_kg) <= 0) return 'Please enter a valid weight (kg).';
    if (!f.expected_length_m || parseFloat(f.expected_length_m) <= 0) return 'Please enter a valid expected length (m).';
    return null;
};

export const buildJumboPayload = (f) => ({
    jumbo_name_id: parseInt(f.jumbo_name_id, 10),
    rate_per_kg: parseFloat(f.rate_per_kg) || 0,
    weight_kg: parseFloat(f.weight_kg) || 0,
    freight_cost: parseFloat(f.freight_cost) || 0,
    expected_length_m: parseFloat(f.expected_length_m) || 0,
});

// Jumbo intake fields — rate/weight/freight drive a live total-cost preview,
// expected_length_m drives a live meters->yards preview using the same
// 1.09361 conversion factor the backend applies.
const searchJumboNames = async (query) => {
    const res = await purchasesApi.jumboNames.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const JumboFields = ({ data, onChange }) => {
    const rate = parseFloat(data.rate_per_kg) || 0;
    const weight = parseFloat(data.weight_kg) || 0;
    const freight = parseFloat(data.freight_cost) || 0;
    const totalCost = rate * weight + freight;

    const meters = parseFloat(data.expected_length_m) || 0;
    const yards = meters * YARDS_PER_METER;

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-neutral-900">Jumbo Purchase</h3>

            <SearchableSelect
                label="Jumbo Name"
                value={data.jumbo_name_id}
                selectedLabel={data.jumbo_name_label}
                onChange={(val, option) => onChange({ ...data, jumbo_name_id: val, jumbo_name_label: option?.label ?? '' })}
                onSearch={searchJumboNames}
                placeholder="Search jumbo name..."
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

            <Input
                label="Freight Cost (PKR, optional)"
                type="number"
                step="0.01"
                min="0"
                value={data.freight_cost}
                onChange={(e) => onChange({ ...data, freight_cost: e.target.value })}
                placeholder="0"
            />

            {(rate > 0 || weight > 0 || freight > 0) && (
                <p className="text-sm text-neutral-500 -mt-2">
                    Total cost: <span className="font-medium text-neutral-900">{totalCost.toFixed(2)} PKR</span>
                    {' '}({rate} × {weight} + {freight})
                </p>
            )}

            <Input
                label="Expected Length (m)"
                type="number"
                step="0.01"
                min="0"
                value={data.expected_length_m}
                onChange={(e) => onChange({ ...data, expected_length_m: e.target.value })}
                required
            />
            {meters > 0 && (
                <p className="text-sm text-neutral-500 -mt-2">
                    {meters} meters: {meters} × {YARDS_PER_METER} = <span className="font-medium text-neutral-900">{yards.toFixed(4)} yards</span>
                </p>
            )}
        </div>
    );
};

JumboFields.propTypes = {
    data: PropTypes.object.isRequired,
    onChange: PropTypes.func.isRequired,
};

export default JumboFields;
