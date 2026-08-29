import { useState } from 'react';
import { Boxes, SlidersHorizontal, X, PackageSearch, Loader2, Ruler } from 'lucide-react';
import { usePurchaseBatches } from '../../hooks/usePurchases';
import Table from '../../components/ui/Table';
import Button from '../../components/ui/Button';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import FilterBar from '../../components/ui/FilterBar';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';
import OrderStatusBadge from '../../components/purchases/OrderStatusBadge';
import CorrectJumboLengthModal from '../../components/purchases/CorrectJumboLengthModal';

const fmtNum = (value, digits = 2) => {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return num == null || isNaN(num) ? '—' : num.toFixed(digits);
};

const dash = (value) => (value === null || value === undefined || value === '' ? '—' : value);

// Read-only single-table view combining ALL FOUR RM families (Jumbo/Cores/
// Packing/Cartons) — explicit client requirement, not four separate views.
// Attribute columns not relevant to a row's family come back null from the
// backend and render as "—" here.
const PurchaseBatchesPage = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [showFilters, setShowFilters] = useState(false);
    const [correctingItem, setCorrectingItem] = useState(null);

    const {
        data: batches, meta, page, setPage, loading, initialLoading, error,
        filters, setFilters, refetch,
    } = usePurchaseBatches({});

    const handleSearch = (value) => {
        setSearchTerm(value);
        setFilters({ ...filters, search: value || undefined });
    };

    const handleApplyFilters = (filterValues) => {
        setFilters({ ...filterValues, search: searchTerm || undefined });
    };

    const handleResetFilters = () => {
        setSearchTerm('');
        setFilters({});
    };

    const filterConfig = [
        {
            name: 'status',
            label: 'Status',
            type: 'select',
            options: [
                { value: 'draft', label: 'Draft' },
                { value: 'confirmed', label: 'Confirmed' },
            ],
        },
        { name: 'date_from', label: 'Date From', type: 'date' },
        { name: 'date_to', label: 'Date To', type: 'date' },
    ];

    const attributeLabel = (row) =>
        row.jumbo_name || row.core_name || row.core_length || row.core_thickness
            || row.packing_size || row.carton_size || '—';

    const columns = [
        { key: 'order_number', label: 'Order #', width: '110px' },
        {
            key: 'order_status',
            label: 'Status',
            width: '100px',
            render: (value) => <OrderStatusBadge status={value} />,
        },
        {
            key: 'order_date',
            label: 'Date',
            width: '110px',
            render: (value) => value ? new Date(value).toLocaleDateString() : '—',
        },
        {
            key: 'supplier_name',
            label: 'Supplier',
            render: (value, row) => value ? `${value}${row.supplier_code ? ` (${row.supplier_code})` : ''}` : '—',
        },
        {
            key: 'product_name',
            label: 'Product',
            render: (value, row) => value ? `${value}${row.product_code ? ` (${row.product_code})` : ''}` : '—',
        },
        {
            key: 'attributes',
            label: 'Attributes',
            render: (_, row) => attributeLabel(row),
        },
        {
            key: 'quantity',
            label: 'Qty',
            render: (value, row) => `${dash(value)} / ${dash(row.remaining_quantity)} left`,
        },
        {
            key: 'unit_price',
            label: 'Unit Price',
            render: (value) => fmtNum(value),
        },
        {
            key: 'weight_kg',
            label: 'Weight (kg)',
            render: (value) => value == null ? '—' : fmtNum(value),
        },
        {
            key: 'rate_per_kg',
            label: 'Rate/kg',
            render: (value) => value == null ? '—' : fmtNum(value),
        },
        {
            key: 'freight_cost',
            label: 'Freight',
            render: (value) => value == null ? '—' : fmtNum(value),
        },
        {
            key: 'expected_length_m',
            label: 'Expected (m)',
            render: (value) => value == null ? '—' : fmtNum(value),
        },
        {
            key: 'exact_length_m',
            label: 'Exact (m)',
            render: (value) => value == null ? '—' : fmtNum(value),
        },
        {
            key: 'total_price',
            label: 'Total',
            render: (value) => <span className="font-medium tabular-nums">{fmtNum(value)}</span>,
        },
        {
            key: 'actions',
            label: '',
            width: '140px',
            render: (_, row) => (
                row.expected_length_m != null && row.order_status === 'confirmed' ? (
                    <Button
                        size="sm"
                        variant="secondary"
                        icon={Ruler}
                        onClick={(e) => {
                            e.stopPropagation();
                            setCorrectingItem(row);
                        }}
                    >
                        Correct Length
                    </Button>
                ) : null
            ),
        },
    ];

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
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                    <Boxes className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">Purchase Batches</h1>
                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                        All Jumbo, Core, Packing, and Carton purchase batches in one place
                    </p>
                </div>
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1">
                        <SearchBar
                            onSearch={handleSearch}
                            placeholder="Search by order #, supplier, or product..."
                            className="w-full"
                        />
                    </div>
                    <div className="flex gap-3">
                        <Button
                            variant="secondary"
                            onClick={() => setShowFilters(!showFilters)}
                            icon={SlidersHorizontal}
                            className="flex-1 sm:flex-none"
                        >
                            {showFilters ? 'Hide Filters' : 'Filters'}
                        </Button>
                        {(Object.keys(filters).length > 0 || searchTerm) && (
                            <Button variant="secondary" onClick={handleResetFilters} icon={X} className="flex-1 sm:flex-none">
                                Clear
                            </Button>
                        )}
                    </div>
                </div>

                {showFilters && (
                    <FilterBar
                        filters={filterConfig}
                        onApply={handleApplyFilters}
                        onReset={handleResetFilters}
                    />
                )}
            </div>

            <div className="relative">
                {loading && (
                    <div className="absolute right-2 top-2 z-10 flex items-center gap-1.5 text-xs text-neutral-400">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Refreshing…
                    </div>
                )}
                {batches.length === 0 ? (
                    <EmptyState
                        title="No purchase batches found"
                        description="Try adjusting your search or filters."
                        icon={<PackageSearch className="w-8 h-8 text-neutral-400" />}
                    />
                ) : (
                    <div className={loading ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
                        <Table columns={columns} data={batches} />
                    </div>
                )}
            </div>

            {meta.totalPages > 1 && (
                <Pagination
                    currentPage={meta.currentPage}
                    totalPages={meta.totalPages}
                    onPageChange={setPage}
                />
            )}

            <CorrectJumboLengthModal
                isOpen={!!correctingItem}
                onClose={() => setCorrectingItem(null)}
                item={correctingItem}
                onCorrected={() => {
                    setCorrectingItem(null);
                    refetch();
                }}
            />
        </div>
    );
};

export default PurchaseBatchesPage;
