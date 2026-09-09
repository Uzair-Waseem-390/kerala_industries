import { useState } from 'react';
import { Trash2, Clock, Users, Wrench } from 'lucide-react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import SearchableSelect from '../ui/SearchableSelect';
import InlineAlert from '../ui/InlineAlert';
import LoadingSpinner from '../ui/LoadingSpinner';
import { manufacturingCostsApi } from '../../services/manufacturingCostsApi';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const searchEmployees = async (query, excludeIds) => {
    const res = await manufacturingCostsApi.employees.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results
        .filter((e) => !excludeIds.includes(e.id))
        .map((e) => ({
            value: e.id,
            label: `${e.name} — ${parseFloat(e.rate_per_hour || 0).toFixed(2)}/hr`,
            name: e.name,
        }));
};

const searchMachines = async (query, category, excludeIds) => {
    const res = await manufacturingCostsApi.machines.getAll({ search: query, category, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results
        .filter((m) => !excludeIds.includes(m.id))
        .map((m) => ({
            value: m.id,
            label: `${m.name} — ${parseFloat(m.rate_per_hour || 0).toFixed(2)}/hr`,
            name: m.name,
        }));
};

// Time taken + Direct Labor (employees) + Factory Overhead (machines) — the
// three inputs the backend needs to compute the Direct Labor + Factory
// Overhead cost pool that gets spread into full_cost_per_unit. Shown on all
// three recipe detail pages (Rewinding/Cutting/Packing) while the recipe is
// still under_processing; each add/remove hits its own endpoint and the
// parent hook refetches the recipe afterward so labor_entries/machine_entries
// stay in sync. Machines are filtered to the recipe's own type — a machine's
// category must match (backend enforces this too, rejecting a mismatch with
// a 400 that surfaces below the picker).
const RecipeLaborMachineSection = ({
    recipe,
    disabled,
    onSetTime, settingTime,
    onAddLabor, addingLabor,
    onRemoveLabor, removingLaborId,
    onAddMachine, addingMachine,
    onRemoveMachine, removingMachineId,
}) => {
    const { toast } = useToast();

    const [hours, setHours] = useState(String(recipe.time_hours ?? 0));
    const [minutes, setMinutes] = useState(String(recipe.time_minutes ?? 0));
    const [timeError, setTimeError] = useState('');

    const [employeeId, setEmployeeId] = useState('');
    const [employeeLabel, setEmployeeLabel] = useState('');
    const [laborError, setLaborError] = useState('');

    const [machineId, setMachineId] = useState('');
    const [machineLabel, setMachineLabel] = useState('');
    const [machineError, setMachineError] = useState('');

    const laborEntries = recipe.labor_entries || [];
    const machineEntries = recipe.machine_entries || [];

    const handleSaveTime = async (e) => {
        e.preventDefault();
        setTimeError('');
        try {
            await onSetTime({
                time_hours: parseInt(hours, 10) || 0,
                time_minutes: parseInt(minutes, 10) || 0,
            });
            toast.success('Time saved');
        } catch (err) {
            setTimeError(extractErrorMessage(err, 'Failed to save time'));
        }
    };

    const handleAddLabor = async (val, option) => {
        setLaborError('');
        try {
            await onAddLabor({ employee_id: val });
            toast.success(`${option?.name || 'Employee'} added`);
            setEmployeeId('');
            setEmployeeLabel('');
        } catch (err) {
            setLaborError(extractErrorMessage(err, 'Failed to add employee'));
        }
    };

    const handleRemoveLabor = async (entry) => {
        setLaborError('');
        try {
            await onRemoveLabor(entry.employee);
            toast.success(`${entry.employee_name} removed`);
        } catch (err) {
            setLaborError(extractErrorMessage(err, 'Failed to remove employee'));
        }
    };

    const handleAddMachine = async (val, option) => {
        setMachineError('');
        try {
            await onAddMachine({ machine_id: val });
            toast.success(`${option?.name || 'Machine'} added`);
            setMachineId('');
            setMachineLabel('');
        } catch (err) {
            setMachineError(extractErrorMessage(err, 'Failed to add machine'));
        }
    };

    const handleRemoveMachine = async (entry) => {
        setMachineError('');
        try {
            await onRemoveMachine(entry.machine);
            toast.success(`${entry.machine_name} removed`);
        } catch (err) {
            setMachineError(extractErrorMessage(err, 'Failed to remove machine'));
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Time Taken
                </h3>
                {timeError && <InlineAlert variant="error" message={timeError} />}
                {disabled ? (
                    <p className="text-sm text-neutral-700">
                        {recipe.time_hours ?? 0}h {recipe.time_minutes ?? 0}m
                    </p>
                ) : (
                    <form onSubmit={handleSaveTime} className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <Input
                                label="Hours"
                                type="number"
                                min="0"
                                step="1"
                                value={hours}
                                onChange={(e) => setHours(e.target.value)}
                            />
                            <Input
                                label="Minutes"
                                type="number"
                                min="0"
                                max="59"
                                step="1"
                                value={minutes}
                                onChange={(e) => setMinutes(e.target.value)}
                            />
                        </div>
                        <div className="flex justify-end">
                            <Button type="submit" size="sm" loading={settingTime}>
                                Save Time
                            </Button>
                        </div>
                    </form>
                )}
            </Card>

            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                    <Users className="w-4 h-4" /> Employees
                </h3>
                {laborError && <InlineAlert variant="error" message={laborError} />}
                {!disabled && (
                    <div className="mb-3">
                        <SearchableSelect
                            value={employeeId}
                            selectedLabel={employeeLabel}
                            onChange={handleAddLabor}
                            onSearch={(q) => searchEmployees(q, laborEntries.map((l) => l.employee))}
                            placeholder="Search employee to add..."
                            disabled={addingLabor}
                        />
                    </div>
                )}
                {laborEntries.length === 0 ? (
                    <p className="text-sm text-neutral-400 italic">No employees assigned yet.</p>
                ) : (
                    <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 text-sm">
                        {laborEntries.map((entry) => (
                            <div key={entry.id} className="flex items-center justify-between px-3 py-1.5">
                                <span>
                                    {entry.employee_name}
                                    <span className="text-neutral-400"> — {parseFloat(entry.rate_per_hour_snapshot).toFixed(2)}/hr</span>
                                </span>
                                {!disabled && (
                                    <button
                                        type="button"
                                        onClick={() => handleRemoveLabor(entry)}
                                        disabled={removingLaborId === entry.employee}
                                        className="text-neutral-400 hover:text-error-600 transition-colors disabled:opacity-50"
                                    >
                                        {removingLaborId === entry.employee ? (
                                            <LoadingSpinner size="sm" />
                                        ) : (
                                            <Trash2 className="w-4 h-4" />
                                        )}
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Card>

            <Card className="p-6" hover={false}>
                <h3 className="font-semibold text-neutral-900 mb-3 flex items-center gap-2">
                    <Wrench className="w-4 h-4" /> Machines
                </h3>
                {machineError && <InlineAlert variant="error" message={machineError} />}
                {!disabled && (
                    <div className="mb-3">
                        <SearchableSelect
                            value={machineId}
                            selectedLabel={machineLabel}
                            onChange={handleAddMachine}
                            onSearch={(q) => searchMachines(q, recipe.recipe_type, machineEntries.map((m) => m.machine))}
                            placeholder="Search machine to add..."
                            disabled={addingMachine}
                        />
                    </div>
                )}
                {machineEntries.length === 0 ? (
                    <p className="text-sm text-neutral-400 italic">No machines assigned yet.</p>
                ) : (
                    <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 text-sm">
                        {machineEntries.map((entry) => (
                            <div key={entry.id} className="flex items-center justify-between px-3 py-1.5">
                                <span>
                                    {entry.machine_name}
                                    <span className="text-neutral-400"> — {parseFloat(entry.rate_per_hour_snapshot).toFixed(2)}/hr</span>
                                </span>
                                {!disabled && (
                                    <button
                                        type="button"
                                        onClick={() => handleRemoveMachine(entry)}
                                        disabled={removingMachineId === entry.machine}
                                        className="text-neutral-400 hover:text-error-600 transition-colors disabled:opacity-50"
                                    >
                                        {removingMachineId === entry.machine ? (
                                            <LoadingSpinner size="sm" />
                                        ) : (
                                            <Trash2 className="w-4 h-4" />
                                        )}
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </div>
    );
};

export default RecipeLaborMachineSection;
