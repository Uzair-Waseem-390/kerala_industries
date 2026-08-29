import { PackageSearch } from 'lucide-react';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { purchasesApi } from '../../services/purchasesApi';
import Table from '../../components/ui/Table';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Badge from '../../components/ui/Badge';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';

// Product is now a frozen catalog of 4 fixed rows (Jumbo, Cores, Packing,
// Cartons), seeded by a management command — create/edit/delete were
// deliberately removed from both the backend and this page. This is a
// read-only list + filter view; nothing here mutates a Product.
const ProductsPage = () => {
    const { data, meta, page, setPage, loading, error, filters, setFilters, refetch } = usePaginatedList(
        (params) => purchasesApi.products.getAll(params),
        { search: '' }
    );

    const handleSearch = (value) => {
        setFilters({ ...filters, search: value });
    };

    const columns = [
        { key: 'code', label: 'Code', width: '120px' },
        { key: 'name', label: 'Name' },
        {
            key: 'is_deleted',
            label: 'Status',
            render: (value) => (
                <Badge variant={value ? 'error' : 'success'}>
                    {value ? 'Deleted' : 'Active'}
                </Badge>
            ),
        },
    ];

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-neutral-900">Products</h1>
                    <p className="text-neutral-500 mt-1">Fixed product catalog</p>
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

            {data.length === 0 ? (
                <EmptyState
                    title="No products found"
                    description="Try adjusting your search."
                    icon={<PackageSearch className="w-8 h-8 text-neutral-400" />}
                />
            ) : (
                <Table
                    columns={columns}
                    data={data}
                />
            )}

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

export default ProductsPage;
