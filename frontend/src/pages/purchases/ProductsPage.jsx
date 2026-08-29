import { useState, useEffect } from 'react';
import { SlidersHorizontal, X, PackageSearch } from 'lucide-react';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { purchasesApi } from '../../services/purchasesApi';
import Table from '../../components/ui/Table';
import Button from '../../components/ui/Button';
import SearchBar from '../../components/ui/SearchBar';
import FilterBar from '../../components/ui/FilterBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Badge from '../../components/ui/Badge';
import Pagination from '../../components/ui/Pagination';
import EmptyState from '../../components/ui/EmptyState';
import InlineAlert from '../../components/ui/InlineAlert';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

// Product is now a frozen catalog of 4 fixed rows (Jumbo, Cores, Packing,
// Cartons), seeded by a management command — create/edit/delete were
// deliberately removed from both the backend and this page. This is a
// read-only list + filter view; nothing here mutates a Product.
const ProductsPage = () => {
    const { toast } = useToast();

    const { data, meta, page, setPage, loading, error, filters, setFilters, refetch } = usePaginatedList(
        (params) => purchasesApi.products.getAll(params),
        { search: '' }
    );

    // Family is a fixed/seeded lookup (Raw Material / WIP / Finished
    // Goods), read-only — no /products/ query param support for it, so
    // (like the old Category filter here) it's narrowed client-side over
    // whatever page the backend returned.
    const [families, setFamilies] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [familyFilter, setFamilyFilter] = useState('');
    const [showFilters, setShowFilters] = useState(false);
    const [activeFilters, setActiveFilters] = useState({});

    useEffect(() => {
        loadLookups();
    }, []);

    const loadLookups = async () => {
        try {
            const familiesRes = await purchasesApi.families.getAll();
            setFamilies(familiesRes.results || familiesRes);
        } catch (error) {
            console.error('Failed to load lookups:', error);
            toast.error(extractErrorMessage(error, 'Failed to load families'));
        }
    };

    // Search now goes to the backend (see handleSearch) — only family
    // is still narrowed client-side, over whatever page the backend returned.
    const filteredData = data.filter(item => {
        let matches = true;
        const familyId = activeFilters.family || familyFilter;
        if (familyId) {
            matches = matches && item.family?.id === parseInt(familyId);
        }
        return matches;
    });

    const handleSearch = (value) => {
        setSearchTerm(value);
        setFilters({ ...filters, search: value });
    };

    const handleApplyFilters = (filterValues) => {
        setActiveFilters(filterValues);
        setFamilyFilter(filterValues.family || '');
    };

    const handleResetFilters = () => {
        setActiveFilters({});
        setFamilyFilter('');
        setSearchTerm('');
        setFilters({ ...filters, search: '' });
    };

    const columns = [
        { key: 'code', label: 'Code', width: '120px' },
        { key: 'name', label: 'Name' },
        {
            key: 'family',
            label: 'Family',
            render: (value) => value?.name || 'N/A'
        },
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

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                    <SearchBar
                        onSearch={handleSearch}
                        placeholder="Search products..."
                        className="flex-1"
                    />
                    <div className="flex gap-3">
                        <Button
                            variant="secondary"
                            onClick={() => setShowFilters(!showFilters)}
                            icon={SlidersHorizontal}
                            className="flex-1 sm:flex-none"
                        >
                            {showFilters ? 'Hide Filters' : 'Filters'}
                        </Button>
                        {(Object.keys(activeFilters).length > 0 || searchTerm) && (
                            <Button variant="secondary" onClick={handleResetFilters} icon={X} className="flex-1 sm:flex-none">
                                Clear
                            </Button>
                        )}
                    </div>
                </div>

                {showFilters && (
                    <FilterBar
                        filters={[
                            {
                                name: 'family',
                                label: 'Family',
                                type: 'select',
                                options: [
                                    { value: '', label: 'All Families' },
                                    ...families.map(f => ({ value: f.id, label: f.name })),
                                ],
                            },
                        ]}
                        onApply={handleApplyFilters}
                        onReset={handleResetFilters}
                    />
                )}
            </div>

            {filteredData.length === 0 ? (
                <EmptyState
                    title="No products found"
                    description="Try adjusting your search or filters."
                    icon={<PackageSearch className="w-8 h-8 text-neutral-400" />}
                />
            ) : (
                <Table
                    columns={columns}
                    data={filteredData}
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
