import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, ShieldAlert, Cog, RotateCcw } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useManufacturingCostMachines, useFactoryOverheadSetting } from '../../hooks/useManufacturingCosts';
import { extractErrorMessage } from '../../utils/errorMessage';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Card from '../../components/ui/Card';
import Modal from '../../components/ui/Modal';
import Input from '../../components/ui/Input';
import Select from '../../components/ui/Select';
import Badge from '../../components/ui/Badge';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Table from '../../components/ui/Table';
import Pagination from '../../components/ui/Pagination';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';

const fmt = (value) => {
    const num = typeof value === 'string' ? parseFloat(value) : Number(value);
    return isNaN(num) ? '0.00' : num.toFixed(2);
};

const categoryOptions = [
    { value: 'rewinding', label: 'Rewinding' },
    { value: 'cutting', label: 'Cutting' },
    { value: 'packing', label: 'Packing' },
];

const categoryBadge = (category) => {
    const label = categoryOptions.find((c) => c.value === category)?.label || category;
    if (category === 'rewinding') return <Badge variant="info">{label}</Badge>;
    if (category === 'cutting') return <Badge variant="warning">{label}</Badge>;
    return <Badge variant="success">{label}</Badge>;
};

const emptyForm = { name: '', category: '', avg_hours_per_day: '', working_days_per_month: '', monthly_repair_cost: '' };

const ManufacturingCostMachinesPage = () => {
    const { user } = useAuth();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const {
        data: machines, meta, page, setPage, loading,
        refetch, create, update, delete: deleteMachine,
    } = useManufacturingCostMachines();

    const {
        data: foh, loading: fohLoading, update: updateFoh,
    } = useFactoryOverheadSetting();

    const [fohForm, setFohForm] = useState(null);
    const [fohLoaded, setFohLoaded] = useState(false);
    const [fohSaving, setFohSaving] = useState(false);
    const [fohError, setFohError] = useState('');
    const [resetConfirm, setResetConfirm] = useState(false);

    useEffect(() => {
        if (foh && !fohLoaded) {
            setFohForm({ rent_amount: foh.rent_amount, electricity_amount: foh.electricity_amount });
            setFohLoaded(true);
        }
    }, [foh, fohLoaded]);

    const [showModal, setShowModal] = useState(false);
    const [editingMachine, setEditingMachine] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [deleteLoading, setDeleteLoading] = useState(false);

    const resetForm = () => {
        setFormData(emptyForm);
        setEditingMachine(null);
        setFormError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError('');
        setFormLoading(true);
        try {
            const payload = {
                name: formData.name,
                category: formData.category,
                avg_hours_per_day: parseFloat(formData.avg_hours_per_day),
                working_days_per_month: parseFloat(formData.working_days_per_month),
                monthly_repair_cost: parseFloat(formData.monthly_repair_cost),
            };
            if (editingMachine) {
                await update(editingMachine.id, payload);
            } else {
                await create(payload);
            }
            setShowModal(false);
            resetForm();
            refetch();
            toast.success(editingMachine ? 'Machine updated successfully' : 'Machine added successfully');
        } catch (error) {
            setFormError(extractErrorMessage(error, 'Failed to save machine'));
        } finally {
            setFormLoading(false);
        }
    };

    const handleEdit = (machine) => {
        setEditingMachine(machine);
        setFormData({
            name: machine.name,
            category: machine.category,
            avg_hours_per_day: machine.avg_hours_per_day,
            working_days_per_month: machine.working_days_per_month,
            monthly_repair_cost: machine.monthly_repair_cost,
        });
        setShowModal(true);
    };

    const handleDelete = async (id) => {
        setDeleteLoading(true);
        try {
            await deleteMachine(id);
            setDeleteConfirm(null);
            refetch();
            toast.success('Machine deleted');
        } catch (error) {
            setDeleteConfirm(null);
            toast.error(extractErrorMessage(error, 'Failed to delete machine'));
        } finally {
            setDeleteLoading(false);
        }
    };

    const handleFohSave = async (e) => {
        e.preventDefault();
        setFohError('');
        setFohSaving(true);
        try {
            await updateFoh({
                rent_amount: parseFloat(fohForm.rent_amount) || 0,
                electricity_amount: parseFloat(fohForm.electricity_amount) || 0,
            });
            await refetch();
            toast.success('Rent/Electricity updated — machine rates refreshed');
        } catch (error) {
            setFohError(extractErrorMessage(error, 'Failed to update Rent/Electricity'));
        } finally {
            setFohSaving(false);
        }
    };

    const handleReset = async () => {
        setFohSaving(true);
        try {
            const result = await updateFoh({ rent_amount: 0, electricity_amount: 0 });
            setFohForm({ rent_amount: result.rent_amount, electricity_amount: result.electricity_amount });
            await refetch();
            setResetConfirm(false);
            toast.success('Rent/Electricity reset to 0 — machine rates refreshed');
        } catch (error) {
            setResetConfirm(false);
            toast.error(extractErrorMessage(error, 'Failed to reset Rent/Electricity'));
        } finally {
            setFohSaving(false);
        }
    };

    const columns = [
        { key: 'name', label: 'Name', render: (v) => <span className="font-medium text-neutral-900">{v}</span> },
        { key: 'category', label: 'Category', render: (v) => categoryBadge(v) },
        { key: 'avg_hours_per_day', label: 'Avg Hours/Day', render: (v) => fmt(v) },
        { key: 'working_days_per_month', label: 'Working Days/Month', render: (v) => fmt(v) },
        { key: 'monthly_repair_cost', label: 'Repair Cost (PKR)', render: (v) => `Rs. ${fmt(v)}` },
        { key: 'rate_per_hour', label: 'Rate/Hour (PKR)', render: (v) => <span className="font-semibold text-info-600">Rs. {fmt(v)}</span> },
        {
            key: 'actions',
            label: 'Actions',
            width: '200px',
            render: (_v, row) => (
                <div className="flex items-center gap-2">
                    <button onClick={() => handleEdit(row)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-primary-200 bg-primary-50 text-primary-700 hover:bg-primary-100 transition-colors text-sm font-medium min-h-[44px] sm:min-h-0">
                        <Pencil className="w-3.5 h-3.5" /> Edit
                    </button>
                    <button onClick={() => setDeleteConfirm(row)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-error-200 bg-error-50 text-error-700 hover:bg-error-100 transition-colors text-sm font-medium min-h-[44px] sm:min-h-0">
                        <Trash2 className="w-3.5 h-3.5" /> Delete
                    </button>
                </div>
            ),
        },
    ];

    if (!isAdmin) {
        return (
            <div className="flex flex-col items-center justify-center text-center py-20">
                <div className="w-14 h-14 rounded-full bg-error-50 flex items-center justify-center mb-4">
                    <ShieldAlert className="w-7 h-7 text-error-500" />
                </div>
                <h2 className="text-2xl font-semibold text-neutral-900">Access Denied</h2>
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view machines.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <BackLink to="/manufacturing-costs">Back to Manufacturing Costs</BackLink>
                    <h1 className="text-3xl font-bold text-neutral-900 mt-1">Machines</h1>
                    <p className="text-neutral-500 mt-1 max-w-2xl">
                        Factory overhead — rate/hour blends each machine's own repair cost with its share of Rent + Electricity below.
                    </p>
                </div>
                <Button onClick={() => { resetForm(); setShowModal(true); }} icon={Plus}>Add Machine</Button>
            </div>

            <Card className="p-6">
                <h3 className="font-semibold text-neutral-900 mb-1">Rent &amp; Electricity</h3>
                <p className="text-sm text-neutral-500 mb-4">
                    Shared factory overhead, allocated across every machine proportional to its hours. Changing either
                    immediately affects every machine's rate/hour above.
                </p>
                {fohLoading && !fohForm ? (
                    <div className="flex items-center justify-center py-4">
                        <LoadingSpinner size="md" />
                    </div>
                ) : (
                    <form onSubmit={handleFohSave} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <Input
                                label="Rent (PKR)"
                                type="number"
                                step="0.01"
                                min="0"
                                value={fohForm?.rent_amount ?? ''}
                                onChange={(e) => setFohForm({ ...fohForm, rent_amount: e.target.value })}
                            />
                            <Input
                                label="Electricity (PKR)"
                                type="number"
                                step="0.01"
                                min="0"
                                value={fohForm?.electricity_amount ?? ''}
                                onChange={(e) => setFohForm({ ...fohForm, electricity_amount: e.target.value })}
                            />
                        </div>
                        {fohError && <InlineAlert variant="error" message={fohError} />}
                        <div className="flex flex-wrap gap-3">
                            <Button type="submit" loading={fohSaving}>Save</Button>
                            <Button type="button" variant="secondary" icon={RotateCcw} onClick={() => setResetConfirm(true)} disabled={fohSaving}>
                                Reset to 0
                            </Button>
                        </div>
                    </form>
                )}
            </Card>

            {loading ? (
                <div className="flex items-center justify-center py-8">
                    <LoadingSpinner size="lg" />
                </div>
            ) : machines.length === 0 ? (
                <EmptyState
                    icon={<Cog className="w-8 h-8 text-neutral-400" />}
                    title="No Machines Yet"
                    description="Add a machine to start tracking factory overhead cost."
                />
            ) : (
                <>
                    <Table columns={columns} data={machines} />
                    {meta.totalPages > 1 && (
                        <Pagination currentPage={meta.currentPage} totalPages={meta.totalPages} onPageChange={setPage} />
                    )}
                </>
            )}

            <Modal
                isOpen={showModal}
                onClose={() => { setShowModal(false); resetForm(); }}
                title={editingMachine ? 'Edit Machine' : 'Add Machine'}
                size="lg"
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input
                        label="Name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="e.g. Rewinder 1"
                        required
                    />
                    <Select
                        label="Category"
                        value={formData.category}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                        options={categoryOptions}
                        placeholder="Select a category"
                        required
                    />
                    <Input
                        label="Average Working Hours per Day"
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={formData.avg_hours_per_day}
                        onChange={(e) => setFormData({ ...formData, avg_hours_per_day: e.target.value })}
                        required
                    />
                    <Input
                        label="Working Days per Month"
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={formData.working_days_per_month}
                        onChange={(e) => setFormData({ ...formData, working_days_per_month: e.target.value })}
                        required
                    />
                    <Input
                        label="Monthly Average Repair/Maintenance Cost (PKR)"
                        type="number"
                        step="0.01"
                        min="0"
                        value={formData.monthly_repair_cost}
                        onChange={(e) => setFormData({ ...formData, monthly_repair_cost: e.target.value })}
                        required
                    />

                    <InlineAlert
                        variant="info"
                        message="Rate/hour is computed automatically and can't be edited directly — it also changes if Rent/Electricity or another machine's hours change."
                    />

                    {formError && <InlineAlert variant="error" message={formError} />}

                    <div className="flex justify-end gap-3 pt-4">
                        <Button type="button" variant="secondary" onClick={() => { setShowModal(false); resetForm(); }}>
                            Cancel
                        </Button>
                        <Button type="submit" loading={formLoading}>
                            {editingMachine ? 'Update' : 'Create'}
                        </Button>
                    </div>
                </form>
            </Modal>

            <ConfirmDialog
                isOpen={!!deleteConfirm}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => handleDelete(deleteConfirm?.id)}
                loading={deleteLoading}
                title="Delete Machine"
                message={`Are you sure you want to delete "${deleteConfirm?.name}"? This is a soft delete — their payment history stays intact, and it unlocks deleting their record on the Payment Records page.`}
            />

            <ConfirmDialog
                isOpen={resetConfirm}
                onClose={() => setResetConfirm(false)}
                onConfirm={handleReset}
                loading={fohSaving}
                title="Reset Rent & Electricity"
                message="Are you sure you want to reset both Rent and Electricity to 0? Every machine's rate/hour will be recomputed immediately."
            />
        </div>
    );
};

export default ManufacturingCostMachinesPage;
