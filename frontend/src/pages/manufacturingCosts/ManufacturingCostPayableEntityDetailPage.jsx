import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Plus, Trash2, ShieldAlert, Receipt } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { manufacturingCostsApi } from '../../services/manufacturingCostsApi';
import { useManufacturingCostEntityPayments } from '../../hooks/useManufacturingCosts';
import { extractErrorMessage } from '../../utils/errorMessage';
import { todayLocalDate } from '../../utils/helpers';
import MethodSplitPicker, { isSplitBalanced } from '../../components/paymentMethods/MethodSplitPicker';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Card from '../../components/ui/Card';
import Modal from '../../components/ui/Modal';
import Input from '../../components/ui/Input';
import Badge from '../../components/ui/Badge';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Table from '../../components/ui/Table';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';

const fmt = (value) => {
    const num = typeof value === 'string' ? parseFloat(value) : Number(value);
    return isNaN(num) ? '0.00' : num.toFixed(2);
};

const typeBadge = (type) => {
    if (type === 'employee') return <Badge variant="info">Employee</Badge>;
    if (type === 'machine') return <Badge variant="warning">Machine</Badge>;
    if (type === 'rent') return <Badge variant="success">Rent</Badge>;
    return <Badge variant="success">Electricity</Badge>;
};

const ManufacturingCostPayableEntityDetailPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [entity, setEntity] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [statsLoading, setStatsLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [deleteEntityConfirm, setDeleteEntityConfirm] = useState(false);
    const [deleteEntityError, setDeleteEntityError] = useState('');
    const [deletingEntity, setDeletingEntity] = useState(false);

    const {
        data: payments, meta, page, setPage, loading: paymentsLoading,
        refetch: refetchPayments, create, delete: deletePayment,
    } = useManufacturingCostEntityPayments(id);

    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({ amount: '', payment_date: todayLocalDate(), note: '' });
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');
    const [methodAllocations, setMethodAllocations] = useState([]);
    const [splitError, setSplitError] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [deletePaymentLoading, setDeletePaymentLoading] = useState(false);

    const fetchEntity = useCallback(async () => {
        setLoading(true);
        setLoadError('');
        try {
            const data = await manufacturingCostsApi.payableEntities.getById(id);
            setEntity(data);
        } catch (error) {
            setLoadError(extractErrorMessage(error, 'Failed to load record'));
            setEntity(null);
        } finally {
            setLoading(false);
        }
    }, [id]);

    const fetchStats = useCallback(async () => {
        setStatsLoading(true);
        try {
            const data = await manufacturingCostsApi.payableEntities.getStats(id);
            setStats(data);
        } catch {
            setStats(null);
        } finally {
            setStatsLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchEntity();
        fetchStats();
    }, [fetchEntity, fetchStats]);

    const resetForm = () => {
        setFormData({ amount: '', payment_date: todayLocalDate(), note: '' });
        setFormError('');
        setMethodAllocations([]);
        setSplitError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError('');
        setSplitError('');
        setFormLoading(true);
        try {
            await create({
                entity_id: Number(id),
                amount: parseFloat(formData.amount),
                payment_date: formData.payment_date,
                note: formData.note,
                method_allocations: methodAllocations,
            });
            setShowModal(false);
            resetForm();
            await Promise.all([refetchPayments(), fetchEntity(), fetchStats()]);
            toast.success('Payment recorded successfully');
        } catch (error) {
            const data = error?.response?.data;
            const methodError = data?.method_allocations || data?.splits;
            if (methodError) {
                setSplitError(Array.isArray(methodError) ? methodError[0] : methodError);
            } else {
                setFormError(extractErrorMessage(error, 'Failed to record payment'));
            }
        } finally {
            setFormLoading(false);
        }
    };

    const handleDeletePayment = async (paymentId) => {
        setDeletePaymentLoading(true);
        try {
            await deletePayment(paymentId);
            setDeleteConfirm(null);
            await Promise.all([refetchPayments(), fetchEntity(), fetchStats()]);
            toast.success('Payment deleted and cash in hand restored');
        } catch (error) {
            setDeleteConfirm(null);
            toast.error(extractErrorMessage(error, 'Failed to delete payment'));
        } finally {
            setDeletePaymentLoading(false);
        }
    };

    const handleDeleteEntity = async () => {
        setDeleteEntityError('');
        setDeletingEntity(true);
        try {
            await manufacturingCostsApi.payableEntities.delete(id);
            toast.success('Record deleted');
            navigate('/manufacturing-costs/payable-entities');
        } catch (error) {
            setDeleteEntityConfirm(false);
            setDeleteEntityError(extractErrorMessage(error, "Couldn't delete — its source may not be deleted yet."));
        } finally {
            setDeletingEntity(false);
        }
    };

    const columns = [
        { key: 'reference_number', label: 'Reference' },
        { key: 'payment_date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
        { key: 'amount', label: 'Amount (PKR)', render: (v) => <span className="font-semibold text-success-600">Rs. {fmt(v)}</span> },
        { key: 'note', label: 'Note', render: (v) => v || <span className="text-neutral-300">—</span> },
        {
            key: 'actions',
            label: 'Actions',
            width: '100px',
            render: (_v, row) => (
                <button
                    onClick={(e) => { e.stopPropagation(); setDeleteConfirm(row); }}
                    className="inline-flex items-center gap-1 text-error-600 hover:text-error-700 text-sm font-medium min-h-[44px] sm:min-h-0"
                >
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
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
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view this.</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    if (!entity) {
        return (
            <div className="space-y-4">
                <BackLink to="/manufacturing-costs/payable-entities">Back to Payment Records</BackLink>
                <InlineAlert variant="error" title="Couldn't load this record" message={loadError || 'Record not found'} onRetry={fetchEntity} />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div>
                    <BackLink to="/manufacturing-costs/payable-entities">Back to Payment Records</BackLink>
                    <div className="flex items-center gap-3 mt-1">
                        <h1 className="text-3xl font-bold text-neutral-900">{entity.name}</h1>
                        {typeBadge(entity.type)}
                    </div>
                    <p className="text-neutral-500">
                        {entity.overall_payment_count} payment{entity.overall_payment_count === 1 ? '' : 's'} recorded · Rs. {fmt(entity.overall_total_paid)} total
                    </p>
                </div>
                <div className="flex gap-3">
                    <Button
                        variant="danger"
                        icon={Trash2}
                        disabled={!entity.can_be_deleted}
                        title={!entity.can_be_deleted ? 'Delete the source Employee/Machine first' : undefined}
                        onClick={() => { setDeleteEntityError(''); setDeleteEntityConfirm(true); }}
                    >
                        Delete
                    </Button>
                    <Button icon={Plus} onClick={() => { resetForm(); setShowModal(true); }}>Record Payment</Button>
                </div>
            </div>

            {deleteEntityError && (
                <InlineAlert variant="error" title="Couldn't delete" message={deleteEntityError} />
            )}

            {!entity.can_be_deleted && (entity.type === 'employee' || entity.type === 'machine') && (
                <InlineAlert
                    variant="info"
                    message={`This record can only be deleted after its ${entity.type === 'employee' ? 'Employee' : 'Machine'} is deleted first — its payment history stays intact either way.`}
                />
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {statsLoading ? (
                    <div className="col-span-full flex items-center justify-center py-8">
                        <LoadingSpinner size="lg" />
                    </div>
                ) : (
                    <>
                        <Card className="p-4">
                            <p className="text-xs text-neutral-500 mb-1">All-Time Monthly Average</p>
                            <p className="text-xl font-bold text-info-600">Rs. {fmt(stats?.overall_average_monthly)}</p>
                        </Card>
                        <Card className="p-4">
                            <p className="text-xs text-neutral-500 mb-1">Last Month's Expense</p>
                            <p className="text-xl font-bold text-neutral-900">Rs. {fmt(stats?.last_month_expense)}</p>
                        </Card>
                        <Card className="p-4">
                            <p className="text-xs text-neutral-500 mb-1">Average of Last 3 Months</p>
                            <p className="text-xl font-bold text-neutral-900">Rs. {fmt(stats?.avg_last_3_months)}</p>
                        </Card>
                    </>
                )}
            </div>

            <div className="space-y-4">
                <h2 className="text-lg font-semibold text-neutral-900">Payment History</h2>
                {paymentsLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <LoadingSpinner size="lg" />
                    </div>
                ) : payments.length === 0 ? (
                    <EmptyState
                        icon={<Receipt className="w-8 h-8 text-neutral-400" />}
                        title="No Payments Yet"
                        description="Record a payment to see it appear here."
                    />
                ) : (
                    <>
                        <Table
                            columns={columns}
                            data={payments}
                            onRowClick={(row) => navigate(`/manufacturing-costs/payments/${row.id}`)}
                        />
                        {meta.totalPages > 1 && (
                            <Pagination currentPage={meta.currentPage} totalPages={meta.totalPages} onPageChange={setPage} />
                        )}
                    </>
                )}
            </div>

            <Modal
                isOpen={showModal}
                onClose={() => { setShowModal(false); resetForm(); }}
                title="Record Payment"
                size="lg"
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input
                        label="Amount (PKR)"
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={formData.amount}
                        onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                        required
                    />
                    <Input
                        label="Payment Date"
                        type="date"
                        value={formData.payment_date}
                        onChange={(e) => setFormData({ ...formData, payment_date: e.target.value })}
                        required
                    />
                    <Input
                        label="Note"
                        value={formData.note}
                        onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                        placeholder="Optional"
                    />

                    <MethodSplitPicker
                        totalAmount={formData.amount}
                        value={methodAllocations}
                        onChange={setMethodAllocations}
                        error={splitError}
                    />

                    {formError && <InlineAlert variant="error" message={formError} />}

                    <div className="flex justify-end gap-3 pt-4">
                        <Button type="button" variant="secondary" onClick={() => { setShowModal(false); resetForm(); }}>
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            loading={formLoading}
                            disabled={!isSplitBalanced(formData.amount, methodAllocations)}
                        >
                            Record Payment
                        </Button>
                    </div>
                </form>
            </Modal>

            <ConfirmDialog
                isOpen={!!deleteConfirm}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => handleDeletePayment(deleteConfirm?.id)}
                loading={deletePaymentLoading}
                title="Delete Payment"
                message={`Are you sure you want to delete this Rs. ${fmt(deleteConfirm?.amount)} payment? This will restore the amount to cash in hand.`}
            />

            <ConfirmDialog
                isOpen={deleteEntityConfirm}
                onClose={() => setDeleteEntityConfirm(false)}
                onConfirm={handleDeleteEntity}
                loading={deletingEntity}
                title="Delete Record"
                message={`Are you sure you want to delete this record for "${entity.name}"? Its payment history is unaffected — only deleting an individual payment reverses cash.`}
            />
        </div>
    );
};

export default ManufacturingCostPayableEntityDetailPage;
