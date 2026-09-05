import { useState } from 'react';
import { Boxes, PackageCheck } from 'lucide-react';
import { useCombinedInventory } from '../../hooks/useInventory';
import Table from '../../components/ui/Table';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Card from '../../components/ui/Card';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';
import Tabs from '../../components/ui/Tabs';
import Badge from '../../components/ui/Badge';

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
// "covers everything" instead of separate RM/WIP screens.
const AllInventoryPage = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [activeType, setActiveType] = useState('all');

    const isFinishedGoodsView = activeType === 'finished_goods';
    const typeFilter = isFinishedGoodsView || activeType === 'all' ? undefined : activeType;

    const {
        data: rows, meta, page, setPage, loading, initialLoading, error, refetch,
    } = useCombinedInventory(searchTerm, typeFilter);

    const handleSearch = (value) => {
        setSearchTerm(value);
        setPage(1);
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
                    <span className={`font-semibold ${num <= 0 ? 'text-error-600' : 'text-success-600'}`}>
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

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                    <Boxes className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">All Inventory</h1>
                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                        Every product across Raw Material, WIP, and Finished Goods in one place
                    </p>
                </div>
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            <SearchBar
                onSearch={handleSearch}
                placeholder="Search products..."
                className="w-full sm:max-w-md"
            />

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
                        <Table columns={columns} data={rows} />
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
        </div>
    );
};

export default AllInventoryPage;
