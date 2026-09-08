import { useState } from 'react';
import { Plus, Pencil, Trash2, ShieldAlert, Users } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useManufacturingCostEmployees } from '../../hooks/useManufacturingCosts';
import { extractErrorMessage } from '../../utils/errorMessage';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Modal from '../../components/ui/Modal';
import Input from '../../components/ui/Input';
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

const emptyForm = { name: '', monthly_salary: '', avg_hours_per_day: '', working_days_per_month: '' };

const ManufacturingCostEmployeesPage = () => {
    const { user } = useAuth();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const {
        data: employees, meta, page, setPage, loading,
        refetch, create, update, delete: deleteEmployee,
    } = useManufacturingCostEmployees();

    const [showModal, setShowModal] = useState(false);
    const [editingEmployee, setEditingEmployee] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [deleteLoading, setDeleteLoading] = useState(false);

    const resetForm = () => {
        setFormData(emptyForm);
        setEditingEmployee(null);
        setFormError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError('');
        setFormLoading(true);
        try {
            const payload = {
                name: formData.name,
                monthly_salary: parseFloat(formData.monthly_salary),
                avg_hours_per_day: parseFloat(formData.avg_hours_per_day),
                working_days_per_month: parseFloat(formData.working_days_per_month),
            };
            if (editingEmployee) {
                await update(editingEmployee.id, payload);
            } else {
                await create(payload);
            }
            setShowModal(false);
            resetForm();
            refetch();
            toast.success(editingEmployee ? 'Employee updated successfully' : 'Employee added successfully');
        } catch (error) {
            setFormError(extractErrorMessage(error, 'Failed to save employee'));
        } finally {
            setFormLoading(false);
        }
    };

    const handleEdit = (employee) => {
        setEditingEmployee(employee);
        setFormData({
            name: employee.name,
            monthly_salary: employee.monthly_salary,
            avg_hours_per_day: employee.avg_hours_per_day,
            working_days_per_month: employee.working_days_per_month,
        });
        setShowModal(true);
    };

    const handleDelete = async (id) => {
        setDeleteLoading(true);
        try {
            await deleteEmployee(id);
            setDeleteConfirm(null);
            refetch();
            toast.success('Employee deleted');
        } catch (error) {
            setDeleteConfirm(null);
            toast.error(extractErrorMessage(error, 'Failed to delete employee'));
        } finally {
            setDeleteLoading(false);
        }
    };

    const columns = [
        { key: 'name', label: 'Name', render: (v) => <span className="font-medium text-neutral-900">{v}</span> },
        { key: 'monthly_salary', label: 'Monthly Salary (PKR)', render: (v) => `Rs. ${fmt(v)}` },
        { key: 'avg_hours_per_day', label: 'Avg Hours/Day', render: (v) => fmt(v) },
        { key: 'working_days_per_month', label: 'Working Days/Month', render: (v) => fmt(v) },
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
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view employees.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <BackLink to="/manufacturing-costs">Back to Manufacturing Costs</BackLink>
                    <h1 className="text-3xl font-bold text-neutral-900 mt-1">Employees</h1>
                    <p className="text-neutral-500 mt-1 max-w-2xl">
                        Direct labor — rate/hour is computed automatically from salary, hours/day, and working days/month.
                    </p>
                </div>
                <Button onClick={() => { resetForm(); setShowModal(true); }} icon={Plus}>Add Employee</Button>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-8">
                    <LoadingSpinner size="lg" />
                </div>
            ) : employees.length === 0 ? (
                <EmptyState
                    icon={<Users className="w-8 h-8 text-neutral-400" />}
                    title="No Employees Yet"
                    description="Add an employee to start tracking direct labor cost."
                />
            ) : (
                <>
                    <Table columns={columns} data={employees} />
                    {meta.totalPages > 1 && (
                        <Pagination currentPage={meta.currentPage} totalPages={meta.totalPages} onPageChange={setPage} />
                    )}
                </>
            )}

            <Modal
                isOpen={showModal}
                onClose={() => { setShowModal(false); resetForm(); }}
                title={editingEmployee ? 'Edit Employee' : 'Add Employee'}
                size="lg"
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input
                        label="Name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="e.g. Ali Khan"
                        required
                    />
                    <Input
                        label="Monthly Salary (PKR)"
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={formData.monthly_salary}
                        onChange={(e) => setFormData({ ...formData, monthly_salary: e.target.value })}
                        required
                    />
                    <Input
                        label="Average Working Hours per Day (on machines)"
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

                    <InlineAlert
                        variant="info"
                        message="Rate/hour is computed automatically as salary ÷ (hours/day × working days/month) and can't be edited directly."
                    />

                    {formError && <InlineAlert variant="error" message={formError} />}

                    <div className="flex justify-end gap-3 pt-4">
                        <Button type="button" variant="secondary" onClick={() => { setShowModal(false); resetForm(); }}>
                            Cancel
                        </Button>
                        <Button type="submit" loading={formLoading}>
                            {editingEmployee ? 'Update' : 'Create'}
                        </Button>
                    </div>
                </form>
            </Modal>

            <ConfirmDialog
                isOpen={!!deleteConfirm}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => handleDelete(deleteConfirm?.id)}
                loading={deleteLoading}
                title="Delete Employee"
                message={`Are you sure you want to delete "${deleteConfirm?.name}"? This is a soft delete — their payment history stays intact, and it unlocks deleting their record on the Payment Records page.`}
            />
        </div>
    );
};

export default ManufacturingCostEmployeesPage;
