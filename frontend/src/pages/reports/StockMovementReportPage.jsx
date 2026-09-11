import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, Printer, SlidersHorizontal, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { reportsApi } from '../../services/reportsApi';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { printReport } from '../../utils/print';
import { extractErrorMessage } from '../../utils/errorMessage';
import Card from '../../components/ui/Card';
import Table from '../../components/ui/Table';
import Button from '../../components/ui/Button';
import Badge from '../../components/ui/Badge';
import Tabs from '../../components/ui/Tabs';
import FilterBar from '../../components/ui/FilterBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Pagination from '../../components/ui/Pagination';
import BackLink from '../../components/ui/BackLink';
import InlineAlert from '../../components/ui/InlineAlert';
import EmptyState from '../../components/ui/EmptyState';

const filterConfig = [
    { name: 'date', label: 'Exact Date', type: 'date' },
    { name: 'date_from', label: 'Date From', type: 'date' },
    { name: 'date_to', label: 'Date To', type: 'date' },
    { name: 'search', label: 'Product', type: 'text' },
];

const TAB_TABS = [
    { value: 'purchase', label: 'Purchases' },
    { value: 'sales', label: 'Sales' },
];

// Purchase is always RM — nothing to type-badge here, unlike the Sales tab.
const purchaseColumns = [
    { key: 'product_name', label: 'Product' },
    { key: 'product_code', label: 'Code' },
    { key: 'total_purchased', label: 'Purchased' },
    { key: 'total_purchase_returned', label: 'Purchase Returned' },
    {
        key: '_net_purchased',
        label: 'Net Purchased',
        render: (_v, row) => row.total_purchased - row.total_purchase_returned,
    },
    { key: 'total_lost', label: 'Lost' },
    { key: 'total_found', label: 'Found' },
];

// Same badge convention as Inventory Valuation / Lost Inventory reports —
// what sells now spans RM Cartons and FG, unlike purchases.
const TYPE_BADGE = {
    raw_material: { variant: 'default', label: 'Raw Material' },
    finished_goods: { variant: 'success', label: 'Finished Goods' },
};

const salesColumns = [
    { key: 'product_name', label: 'Product' },
    {
        key: 'type',
        label: 'Type',
        render: (value) => (
            <Badge variant={TYPE_BADGE[value]?.variant || 'default'} size="sm">
                {TYPE_BADGE[value]?.label || value}
            </Badge>
        ),
    },
    { key: 'product_code', label: 'Code' },
    { key: 'total_sold', label: 'Sold' },
    { key: 'total_sale_returned', label: 'Sale Returned' },
    {
        key: '_net_sold',
        label: 'Net Sold',
        render: (_v, row) => row.total_sold - row.total_sale_returned,
    },
];

const StockMovementReportPage = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [tab, setTab] = useState('purchase');
    const [showFilters, setShowFilters] = useState(false);
    const [printing, setPrinting] = useState(false);

    const fetchPage = (params) => reportsApi.stockMovement.get({ ...params, tab });

    const {
        data: results, meta, extra, page, setPage, loading, error,
        filters, setFilters, refetch,
    } = usePaginatedList(fetchPage, {}, 25, [tab]);

    const stats = extra?.stats;
    const isSales = tab === 'sales';

    if (!isAdmin) {
        navigate('/dashboard');
        return null;
    }

    const handleTabChange = (value) => {
        setTab(value);
        setPage(1);
    };

    const handleApplyFilters = (filterValues) => setFilters(filterValues);
    const handleResetFilters = () => setFilters({});

    const handlePrint = async () => {
        setPrinting(true);
        try {
            await printReport('/reports/stock-movement/print/', { ...filters, tab });
        } catch (err) {
            toast.error(extractErrorMessage(err, 'Failed to print report'));
        } finally {
            setPrinting(false);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <BackLink to="/reports">Back to Reports</BackLink>
                <div className="flex items-center gap-3 mt-2">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-700 to-accent-600 flex items-center justify-center shadow-md shadow-primary-900/20 flex-shrink-0">
                        <Package className="w-5 h-5 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold text-neutral-900">Stock Movement Report</h1>
                </div>
                <p className="text-neutral-500 mt-1">
                    {isSales
                        ? 'How much of each Raw Material (Cartons) or Finished Good product was sold and returned by customers.'
                        : 'How much of each Raw Material was purchased, returned to suppliers, lost, and found.'}
                </p>
            </div>

            <Tabs tabs={TAB_TABS} activeTab={tab} onChange={handleTabChange} />

            <div className="space-y-4">
                <div className="flex flex-wrap gap-3">
                    <Button variant="secondary" icon={SlidersHorizontal} onClick={() => setShowFilters(!showFilters)}>
                        {showFilters ? 'Hide Filters' : 'Show Filters'}
                    </Button>
                    {Object.keys(filters).length > 0 && (
                        <Button variant="secondary" icon={X} onClick={handleResetFilters}>
                            Clear All
                        </Button>
                    )}
                    <Button variant="secondary" icon={Printer} onClick={handlePrint} loading={printing}>
                        Print
                    </Button>
                </div>

                {showFilters && (
                    <FilterBar
                        filters={filterConfig}
                        onApply={handleApplyFilters}
                        onReset={handleResetFilters}
                    />
                )}
            </div>

            {error && <InlineAlert variant="error" message={error} onRetry={refetch} />}

            {loading ? (
                <div className="flex items-center justify-center min-h-[40vh]">
                    <LoadingSpinner size="lg" />
                </div>
            ) : (
                <>
                    {stats && (
                        <div className={`grid grid-cols-2 sm:grid-cols-3 ${isSales ? 'lg:grid-cols-2' : 'lg:grid-cols-4'} gap-4`}>
                            {isSales ? (
                                <>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Sold</p>
                                        <p className="text-2xl font-bold text-success-600">{stats.total_sold}</p>
                                    </Card>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Sale Returned</p>
                                        <p className="text-2xl font-bold text-error-600">{stats.total_sale_returned}</p>
                                    </Card>
                                </>
                            ) : (
                                <>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Purchased</p>
                                        <p className="text-2xl font-bold text-neutral-900">{stats.total_purchased}</p>
                                    </Card>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Purchase Returned</p>
                                        <p className="text-2xl font-bold text-error-600">{stats.total_purchase_returned}</p>
                                    </Card>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Lost</p>
                                        <p className="text-2xl font-bold text-error-600">{stats.total_lost}</p>
                                    </Card>
                                    <Card className="p-4">
                                        <p className="text-sm text-neutral-500">Total Found</p>
                                        <p className="text-2xl font-bold text-success-600">{stats.total_found}</p>
                                    </Card>
                                </>
                            )}
                        </div>
                    )}

                    {results.length === 0 ? (
                        <EmptyState
                            title="No Movement Found"
                            description="Try adjusting your filters or search"
                        />
                    ) : (
                        <>
                            <Card className="p-0 overflow-hidden">
                                <Table columns={isSales ? salesColumns : purchaseColumns} data={results} />
                            </Card>
                            {meta.totalPages > 1 && (
                                <Pagination
                                    currentPage={meta.currentPage}
                                    totalPages={meta.totalPages}
                                    onPageChange={setPage}
                                />
                            )}
                        </>
                    )}
                </>
            )}
        </div>
    );
};

export default StockMovementReportPage;
