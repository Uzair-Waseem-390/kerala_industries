import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Boxes, PackageCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';
import { inventoryApi } from '../../services/inventoryApi';
import { purchasesApi } from '../../services/purchasesApi';
import { productionApi } from '../../services/productionApi';
import { useCombinedInventory } from '../../hooks/useInventory';
import Table from '../../components/ui/Table';
import SearchBar from '../../components/ui/SearchBar';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Badge from '../../components/ui/Badge';
import Card from '../../components/ui/Card';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';
import Tabs from '../../components/ui/Tabs';

// 'finished_goods' isn't a real backend type filter — Finished Goods has no
// inventory model yet (see docs/manufacturing-costing-notes.md). Selecting
// it shows a coming-soon empty state client-side instead of hitting the API.
const TYPE_TABS = [
    { value: 'all', label: 'All' },
    { value: 'raw_material', label: 'Raw Material' },
    { value: 'wip_core', label: 'WIP — Cores' },
    { value: 'wip_piece', label: 'WIP — Pieces' },
    { value: 'finished_goods', label: 'Finished Goods' },
];

const TYPE_BADGE = {
    raw_material: { variant: 'default', label: 'Raw Material' },
    wip_core: { variant: 'warning', label: 'WIP — Core' },
    wip_piece: { variant: 'info', label: 'WIP — Piece' },
};

// Every product's inventory in one place — Raw Material, WIP (cores +
// pieces), and (once built) Finished Goods. Client asked for one page that
// "covers everything" instead of separate RM/WIP screens, with the same
// stat cards, manage-inventory buttons, and click-through product detail
// the RM-only Inventory page already has.
const AllInventoryPage = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const [searchTerm, setSearchTerm] = useState('');
    const [activeType, setActiveType] = useState('all');
    const [stats, setStats] = useState(null);
    // Which list the table shows: 'all' | 'low' | 'out'. Driven by clicking
    // the Low Stock / Out of Stock cards — mirrors the RM-only Inventory
    // page exactly, now covering WIP too (see backend stock_view param).
    const [stockView, setStockView] = useState('all');

    const isFinishedGoodsView = activeType === 'finished_goods';
    const typeFilter = isFinishedGoodsView || activeType === 'all' ? undefined : activeType;

    const {
        data: rows, meta, page, setPage, loading, initialLoading, error, refetch,
    } = useCombinedInventory(searchTerm, typeFilter, stockView);

    // Click again (or click Total Products) to return to the full list.
    const handleCardClick = (view) => {
        setStockView((current) => (current === view ? 'all' : view));
        setPage(1);
    };

    // Detail modal state
    const [showDetailModal, setShowDetailModal] = useState(false);
    const [selectedRow, setSelectedRow] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [shelfBreakdown, setShelfBreakdown] = useState([]);
    const [shelfBreakdownLoading, setShelfBreakdownLoading] = useState(false);

    useEffect(() => {
        loadStats();
    }, []);

    // O(1) stats read off the backend singletons — always whole-inventory
    // numbers (RM + WIP combined), independent of the active search/filter.
    const loadStats = async () => {
        try {
            const data = await inventoryApi.inventory.getAllCombinedStats();
            setStats(data);
        } catch (err) {
            console.error('Failed to load inventory stats:', err);
            toast.error(extractErrorMessage(err, 'Failed to load inventory stats'));
        }
    };

    const handleSearch = (value) => {
        setSearchTerm(value);
        setPage(1);
    };

    const handleClearFilters = () => {
        setSearchTerm('');
        setActiveType('all');
        setStockView('all');
        setPage(1);
    };

    const handleRowClick = async (row) => {
        setSelectedRow(row);
        setShowDetailModal(true);
        setDetailLoading(true);
        setShelfBreakdownLoading(true);
        try {
            if (row.type === 'raw_material') {
                const shelves = await purchasesApi.shelves.getCandidates(row.product_id);
                setShelfBreakdown(shelves?.results || shelves || []);
            } else {
                const shelves = await productionApi.wipShelfCandidates.getAll(row.product_id);
                setShelfBreakdown(shelves?.results || shelves || []);
            }
        } catch (err) {
            console.error('Failed to fetch shelf breakdown:', err);
            toast.error(extractErrorMessage(err, 'Failed to load shelf breakdown'));
            setShelfBreakdown([]);
        } finally {
            setShelfBreakdownLoading(false);
            setDetailLoading(false);
        }
    };

    const closeDetailModal = () => {
        setShowDetailModal(false);
        setSelectedRow(null);
        setShelfBreakdown([]);
    };

    const columns = [
        {
            key: 'name',
            label: 'Product',
        },
        {
            key: 'type',
            label: 'Type',
            render: (value) => {
                const badge = TYPE_BADGE[value] || { variant: 'default', label: value };
                return <Badge variant={badge.variant}>{badge.label}</Badge>;
            },
        },
        {
            key: 'code',
            label: 'Code',
            render: (value) => value || '—',
        },
        {
            key: 'category',
            label: 'Category',
            render: (value) => value || '—',
        },
        {
            key: 'quantity',
            label: 'Quantity',
            render: (value) => {
                const num = typeof value === 'string' ? parseFloat(value) : value;
                return (
                    <span className={`font-semibold ${num <= 0 ? 'text-error-600' : num <= 5 ? 'text-warning-600' : 'text-success-600'}`}>
                        {isNaN(num) ? '0' : num}
                    </span>
                );
            },
        },
        {
            key: 'last_updated_at',
            label: 'Last Updated',
            render: (value) => value ? new Date(value).toLocaleString() : 'N/A',
        },
    ];

    if (initialLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    const totalProducts = stats?.total_products ?? 0;
    const totalStock = stats?.total_stock ?? 0;
    const lowStockItems = stats?.low_stock_count ?? 0;
    const outOfStockItems = stats?.out_of_stock_count ?? 0;

    const selectedQuantity = selectedRow ? (parseFloat(selectedRow.quantity) || 0) : 0;

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                            <Boxes className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">All Inventory</h1>
                            <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                                Raw Material, WIP, and Finished Goods in one place
                            </p>
                        </div>
                    </div>
                    <p className="text-sm text-neutral-400 mt-1">Click on any row to view detailed product information</p>
                </div>
                {isAdmin && (
                    <div className="flex flex-wrap gap-3">
                        <Button
                            variant="secondary"
                            onClick={() => navigate('/purchases/lost-inventory/records')}
                            icon={({ className }) => (
                                <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-6h6v6m-9 4h12a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                </svg>
                            )}
                        >
                            Lost Inventory Records
                        </Button>
                        <Button
                            onClick={() => navigate('/purchases/lost-inventory')}
                            icon={({ className }) => (
                                <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                            )}
                        >
                            Manage Inventory
                        </Button>
                    </div>
                )}
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            {/* Summary Cards — O(1) singleton reads, RM + WIP combined. Low
                Stock / Out of Stock are clickable and switch the table to
                that breakdown; click again (or Total Products) to go back. */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card
                    className={`p-4 cursor-pointer transition-shadow hover:shadow-md ${stockView === 'all' ? 'ring-2 ring-primary-500' : ''}`}
                    onClick={() => handleCardClick('all')}
                >
                    <p className="text-sm text-neutral-500">Total Products</p>
                    <p className="text-2xl font-bold text-neutral-900">{totalProducts}</p>
                </Card>
                <Card className="p-4">
                    <p className="text-sm text-neutral-500">Total Stock</p>
                    <p className="text-2xl font-bold text-neutral-900">{totalStock}</p>
                </Card>
                <Card
                    className={`p-4 cursor-pointer transition-shadow hover:shadow-md ${stockView === 'low' ? 'ring-2 ring-warning-500' : ''}`}
                    onClick={() => handleCardClick('low')}
                >
                    <p className="text-sm text-neutral-500">Low Stock (≤ 5)</p>
                    <p className="text-2xl font-bold text-warning-600">{lowStockItems}</p>
                    <p className="text-xs text-neutral-400 mt-1">Click to view breakdown</p>
                </Card>
                <Card
                    className={`p-4 cursor-pointer transition-shadow hover:shadow-md ${stockView === 'out' ? 'ring-2 ring-error-500' : ''}`}
                    onClick={() => handleCardClick('out')}
                >
                    <p className="text-sm text-neutral-500">Out of Stock</p>
                    <p className="text-2xl font-bold text-error-600">{outOfStockItems}</p>
                    <p className="text-xs text-neutral-400 mt-1">Click to view breakdown</p>
                </Card>
            </div>

            {stockView !== 'all' && (
                <div className={`flex items-center justify-between rounded-lg px-4 py-2 ${stockView === 'low' ? 'bg-warning-50 text-warning-700' : 'bg-error-50 text-error-700'}`}>
                    <p className="text-sm font-medium">
                        Showing {stockView === 'low' ? 'low stock' : 'out of stock'} products only
                    </p>
                    <button
                        className="text-sm font-semibold underline"
                        onClick={() => handleCardClick(stockView)}
                    >
                        Show all
                    </button>
                </div>
            )}

            <div className="flex gap-4">
                <div className="flex-1">
                    <SearchBar
                        onSearch={handleSearch}
                        value={searchTerm}
                        placeholder="Search products..."
                        className="w-full"
                    />
                </div>
                {(searchTerm || activeType !== 'all' || stockView !== 'all') && (
                    <Button variant="secondary" onClick={handleClearFilters}>
                        Clear Filter
                    </Button>
                )}
            </div>

            <Tabs
                tabs={TYPE_TABS}
                activeTab={activeType}
                onChange={(value) => { setActiveType(value); setPage(1); }}
            />

            <Card className="p-0 overflow-hidden" hover={false}>
                {isFinishedGoodsView ? (
                    <EmptyState
                        icon={<PackageCheck className="w-8 h-8 text-neutral-400" />}
                        title="Coming soon"
                        description="Finished Goods tracking arrives once the Packing stage (WIP → Finished Goods) is built."
                    />
                ) : rows.length === 0 ? (
                    <EmptyState
                        icon={<Boxes className="w-8 h-8 text-neutral-400" />}
                        title="No inventory found"
                        description="Try adjusting your search or filters."
                    />
                ) : (
                    <div className={loading ? 'opacity-60 transition-opacity p-2' : 'transition-opacity p-2'}>
                        <Table columns={columns} data={rows} onRowClick={handleRowClick} />
                    </div>
                )}
            </Card>

            {!isFinishedGoodsView && meta.totalPages > 1 && (
                <Pagination
                    currentPage={meta.currentPage}
                    totalPages={meta.totalPages}
                    onPageChange={setPage}
                />
            )}

            {/* Product Details modal — mirrors the RM Inventory page's modal,
                branching the shelf-breakdown source by row type. */}
            <Modal
                isOpen={showDetailModal}
                onClose={closeDetailModal}
                title="Product Details"
                size="lg"
            >
                {detailLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <LoadingSpinner size="lg" />
                    </div>
                ) : selectedRow ? (
                    <div className="space-y-6">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-sm text-neutral-500">Product Name</p>
                                <p className="font-medium">{selectedRow.name || 'N/A'}</p>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Code</p>
                                <p className="font-medium">{selectedRow.code || 'N/A'}</p>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Category</p>
                                <p className="font-medium">{selectedRow.category || 'N/A'}</p>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Current Quantity</p>
                                <p className={`text-xl font-bold ${selectedQuantity <= 0 ? 'text-error-600' :
                                        selectedQuantity <= 5 ? 'text-warning-600' : 'text-success-600'
                                    }`}>
                                    {selectedRow.quantity || 0}
                                </p>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Status</p>
                                <Badge variant={
                                    selectedQuantity <= 0 ? 'error' :
                                        selectedQuantity <= 5 ? 'warning' : 'success'
                                }>
                                    {selectedQuantity <= 0 ? 'Out of Stock' :
                                        selectedQuantity <= 5 ? 'Low Stock' : 'In Stock'}
                                </Badge>
                            </div>
                            <div>
                                <p className="text-sm text-neutral-500">Last Updated</p>
                                <p className="font-medium">
                                    {selectedRow.last_updated_at ? new Date(selectedRow.last_updated_at).toLocaleString() : 'N/A'}
                                </p>
                            </div>
                        </div>

                        <div>
                            <p className="text-sm text-neutral-500 mb-2">Stock by Shelf</p>
                            {shelfBreakdownLoading ? (
                                <div className="flex items-center py-4">
                                    <LoadingSpinner size="sm" />
                                </div>
                            ) : shelfBreakdown.length === 0 ? (
                                <p className="text-sm text-neutral-400 italic">
                                    Not currently on any shelf.
                                </p>
                            ) : (
                                <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100">
                                    {shelfBreakdown.map((s) => (
                                        <div key={s.id} className="flex items-center justify-between px-3 py-2">
                                            <span className="font-medium text-neutral-900">{s.name}</span>
                                            <span className="font-semibold text-primary-600">
                                                {s.available_quantity}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="text-center py-8">
                        <p className="text-neutral-500">No product details available</p>
                    </div>
                )}
            </Modal>
        </div>
    );
};

export default AllInventoryPage;
