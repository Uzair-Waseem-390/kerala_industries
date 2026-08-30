import { Layers, PackageSearch } from 'lucide-react';
import { useWipInventory } from '../../hooks/useProduction';
import Table from '../../components/ui/Table';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Card from '../../components/ui/Card';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';

// Simple read-only WIP overview — mirrors InventoryPage's basic table
// layout for RM, without the stat cards / shelf-breakdown modal (not the
// main focus of the Rewinding build).
const WipInventoryPage = () => {
    const {
        data: inventory, meta, setPage, loading, initialLoading, error, filters, setFilters, refetch,
    } = useWipInventory({});

    const handleSearch = (value) => {
        setFilters({ ...filters, search: value || undefined });
    };

    const columns = [
        {
            key: 'product',
            label: 'WIP Product',
            render: (value) => value?.name || 'N/A',
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
                    <Layers className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">WIP Inventory</h1>
                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                        Work-in-process stock produced by finished recipes
                    </p>
                </div>
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            <SearchBar
                onSearch={handleSearch}
                placeholder="Search WIP products..."
                className="w-full sm:max-w-md"
            />

            <Card className="p-0 overflow-hidden" hover={false}>
                {inventory.length === 0 ? (
                    <EmptyState
                        icon={<PackageSearch className="w-8 h-8 text-neutral-400" />}
                        title="No WIP inventory found"
                        description="Finish a recipe with breakdown items to see stock here."
                    />
                ) : (
                    <div className={loading ? 'opacity-60 transition-opacity p-2' : 'transition-opacity p-2'}>
                        <Table columns={columns} data={inventory} />
                    </div>
                )}
            </Card>

            {meta.totalPages > 1 && (
                <Pagination
                    currentPage={meta.currentPage}
                    totalPages={meta.totalPages}
                    onPageChange={setPage}
                />
            )}
        </div>
    );
};

export default WipInventoryPage;
