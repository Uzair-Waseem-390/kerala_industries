import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SlidersHorizontal, X, Wallet, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { manufacturingCostsApi } from '../../services/manufacturingCostsApi';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import SearchBar from '../../components/ui/SearchBar';
import Badge from '../../components/ui/Badge';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Table from '../../components/ui/Table';
import FilterBar from '../../components/ui/FilterBar';
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

const entityTypeOptions = [
    { value: '', label: 'All Types' },
    { value: 'employee', label: 'Employee' },
    { value: 'machine', label: 'Machine' },
    { value: 'rent', label: 'Rent' },
    { value: 'electricity', label: 'Electricity' },
];

const ManufacturingCostPaymentsPage = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [searchTerm, setSearchTerm] = useState('');
    const [showFilters, setShowFilters] = useState(false);

    const fetchPaymentsPage = (params) => {
        const p = { ...params };
        if (searchTerm) p.search = searchTerm;
        return manufacturingCostsApi.payments.getAll(p);
    };

    const {
        data: payments, meta, page, setPage, loading, initialLoading, error: listError, refetch,
        filters, setFilters,
    } = usePaginatedList(fetchPaymentsPage, {}, 25, [searchTerm]);

    const handleApplyFilters = (values) => setFilters(values);
    const handleResetFilters = () => {
        setFilters({});
        setSearchTerm('');
    };
    const handleSearch = (value) => {
        setSearchTerm(value);
        setPage(1);
    };

    const filterConfig = [
        { name: 'entity_type', label: 'Entity Type', type: 'select', options: entityTypeOptions },
        { name: 'date_from', label: 'Date From', type: 'date' },
        { name: 'date_to', label: 'Date To', type: 'date' },
    ];

    const columns = [
        { key: 'reference_number', label: 'Reference', width: '160px' },
        { key: 'entity_name', label: 'Entity' },
        { key: 'entity_type', label: 'Type', render: (v) => typeBadge(v) },
        { key: 'amount', label: 'Amount (PKR)', render: (v) => <span className="font-semibold text-success-600">Rs. {fmt(v)}</span> },
        {
            key: 'allocations',
            label: 'Method',
            render: (value) => (
                Array.isArray(value) && value.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                        {value.map((a) => (
                            <Badge key={a.id}>{a.payment_method_name}: {fmt(a.amount)}</Badge>
                        ))}
                    </div>
                ) : <span className="text-neutral-300">—</span>
            ),
        },
        { key: 'payment_date', label: 'Date', render: (v) => v ? new Date(v).toLocaleDateString() : 'N/A' },
        { key: 'note', label: 'Note', render: (v) => v || <span className="text-neutral-300">—</span> },
    ];

    if (!isAdmin) {
        return (
            <div className="flex flex-col items-center justify-center text-center py-20">
                <div className="w-14 h-14 rounded-full bg-error-50 flex items-center justify-center mb-4">
                    <ShieldAlert className="w-7 h-7 text-error-500" />
                </div>
                <h2 className="text-2xl font-semibold text-neutral-900">Access Denied</h2>
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view payments.</p>
            </div>
        );
    }

    if (initialLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center flex-shrink-0">
                    <Wallet className="w-5.5 h-5.5" />
                </div>
                <div>
                    <BackLink to="/manufacturing-costs">Back to Manufacturing Costs</BackLink>
                    <h1 className="text-3xl font-bold text-neutral-900 mt-1">All Payments</h1>
                    <p className="text-neutral-500 mt-1">
                        Every payment ever recorded across every employee, machine, Rent, and Electricity.
                    </p>
                </div>
            </div>

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1">
                        <SearchBar
                            onSearch={handleSearch}
                            placeholder="Search by reference number (e.g., MFG-2026-0001)..."
                            className="w-full"
                        />
                    </div>
                    <div className="flex gap-3">
                        <Button variant="secondary" onClick={() => setShowFilters(!showFilters)} icon={SlidersHorizontal}>
                            {showFilters ? 'Hide Filters' : 'Show Filters'}
                        </Button>
                        {(Object.keys(filters).length > 0 || searchTerm) && (
                            <Button variant="secondary" icon={X} onClick={handleResetFilters}>Clear</Button>
                        )}
                    </div>
                </div>

                {showFilters && (
                    <FilterBar filters={filterConfig} onApply={handleApplyFilters} onReset={handleResetFilters} />
                )}
            </div>

            {listError && (
                <InlineAlert variant="error" message={listError} onRetry={refetch} />
            )}

            <div className={`relative transition-opacity ${loading ? 'opacity-60' : 'opacity-100'}`}>
                {loading && (
                    <div className="absolute right-2 top-2 z-10">
                        <LoadingSpinner size="sm" />
                    </div>
                )}
                {payments.length === 0 && !loading ? (
                    <EmptyState title="No payments found" description="Try adjusting your search or filters." />
                ) : (
                    <Table
                        columns={columns}
                        data={payments}
                        onRowClick={(row) => navigate(`/manufacturing-costs/payable-entities/${row.entity}`)}
                    />
                )}
            </div>

            {meta.totalPages > 1 && (
                <Pagination currentPage={meta.currentPage} totalPages={meta.totalPages} onPageChange={setPage} />
            )}
        </div>
    );
};

export default ManufacturingCostPaymentsPage;
