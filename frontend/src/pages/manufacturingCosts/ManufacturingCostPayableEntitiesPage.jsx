import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, Receipt, SlidersHorizontal, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useManufacturingCostPayableEntities } from '../../hooks/useManufacturingCosts';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import SearchBar from '../../components/ui/SearchBar';
import Badge from '../../components/ui/Badge';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Table from '../../components/ui/Table';
import FilterBar from '../../components/ui/FilterBar';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';

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

const typeFilterOptions = [
    { value: '', label: 'All' },
    { value: 'employee', label: 'Employee' },
    { value: 'machine', label: 'Machine' },
    { value: 'rent', label: 'Rent' },
    { value: 'electricity', label: 'Electricity' },
];

const ManufacturingCostPayableEntitiesPage = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [searchTerm, setSearchTerm] = useState('');
    const [showFilters, setShowFilters] = useState(false);

    const {
        data: entities, meta, page, setPage, loading, filters, setFilters,
    } = useManufacturingCostPayableEntities();

    const handleSearch = (value) => {
        setSearchTerm(value);
        setFilters({ ...filters, search: value || undefined });
    };

    const handleApplyFilters = (values) => setFilters({ ...filters, ...values });
    const handleResetFilters = () => {
        setSearchTerm('');
        setFilters({});
    };

    const filterConfig = [
        { name: 'type', label: 'Type', type: 'select', options: typeFilterOptions },
    ];

    const columns = [
        { key: 'name', label: 'Name', render: (v) => <span className="font-medium text-neutral-900">{v}</span> },
        { key: 'type', label: 'Type', render: (v) => typeBadge(v) },
        { key: 'overall_total_paid', label: 'Total Paid (PKR)', render: (v) => <span className="font-semibold text-success-600">Rs. {fmt(v)}</span> },
        { key: 'overall_payment_count', label: 'Payments', render: (v) => v ?? 0 },
        {
            key: 'can_be_deleted',
            label: 'Status',
            render: (v) => v ? <Badge variant="error">Source deleted</Badge> : <Badge variant="default">Active</Badge>,
        },
    ];

    if (!isAdmin) {
        return (
            <div className="flex flex-col items-center justify-center text-center py-20">
                <div className="w-14 h-14 rounded-full bg-error-50 flex items-center justify-center mb-4">
                    <ShieldAlert className="w-7 h-7 text-error-500" />
                </div>
                <h2 className="text-2xl font-semibold text-neutral-900">Access Denied</h2>
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view payment records.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <BackLink to="/manufacturing-costs">Back to Manufacturing Costs</BackLink>
                <h1 className="text-3xl font-bold text-neutral-900 mt-1">Payment Records</h1>
                <p className="text-neutral-500 mt-1 max-w-2xl">
                    One row per employee, machine, and the fixed Rent/Electricity rows — click one to record a payment
                    or view its history.
                </p>
            </div>

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1">
                        <SearchBar onSearch={handleSearch} placeholder="Search by name..." className="w-full" />
                    </div>
                    <div className="flex gap-3">
                        <Button variant="secondary" icon={SlidersHorizontal} onClick={() => setShowFilters(!showFilters)}>
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

            {loading ? (
                <div className="flex items-center justify-center py-8">
                    <LoadingSpinner size="lg" />
                </div>
            ) : entities.length === 0 ? (
                <EmptyState
                    icon={<Receipt className="w-8 h-8 text-neutral-400" />}
                    title="No Records Found"
                    description="Add an employee or machine to see it appear here automatically."
                />
            ) : (
                <>
                    <Table
                        columns={columns}
                        data={entities}
                        onRowClick={(row) => navigate(`/manufacturing-costs/payable-entities/${row.id}`)}
                    />
                    {meta.totalPages > 1 && (
                        <Pagination currentPage={meta.currentPage} totalPages={meta.totalPages} onPageChange={setPage} />
                    )}
                </>
            )}
        </div>
    );
};

export default ManufacturingCostPayableEntitiesPage;
