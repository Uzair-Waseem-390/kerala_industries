import { useState, useEffect } from 'react';
import { SlidersHorizontal, X, PackageSearch, Plus } from 'lucide-react';
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
import Modal from '../../components/ui/Modal';
import SearchableSelect from '../../components/ui/SearchableSelect';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

const searchCoreNames = async (query) => {
    const res = await purchasesApi.coreNames.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const searchCoreLengths = async (query) => {
    const res = await purchasesApi.coreLengths.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const searchCoreThicknesses = async (query) => {
    const res = await purchasesApi.coreThicknesses.getAll({ search: query, page_size: 25 });
    const results = res?.results ?? res ?? [];
    return results.map((n) => ({ value: n.id, label: n.value }));
};

const emptyCoreProductForm = {
    core_name_id: '', core_name_label: '',
    core_length_id: '', core_length_label: '',
    core_thickness_id: '', core_thickness_label: '',
};

// Search name -> search length -> search thickness -> Create. Builds one
// real Cores variant Product from that exact combination, no purchase
// involved — it stays out of Inventory/Rates until actually purchased,
// same as every other attribute-only variant (purchases.services
// .create_core_product).
const CreateCoreProductModal = ({ isOpen, onClose, onCreated }) => {
    const { toast } = useToast();
    const [form, setForm] = useState(emptyCoreProductForm);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const canSubmit = form.core_name_id && form.core_length_id && form.core_thickness_id;

    const handleClose = () => {
        setForm(emptyCoreProductForm);
        setError('');
        onClose();
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSubmitting(true);
        try {
            const product = await purchasesApi.products.createCore({
                core_name_id: parseInt(form.core_name_id, 10),
                core_length_id: parseInt(form.core_length_id, 10),
                core_thickness_id: parseInt(form.core_thickness_id, 10),
            });
            toast.success(`Core product '${product.name}' created`);
            setForm(emptyCoreProductForm);
            onCreated();
        } catch (err) {
            setError(extractErrorMessage(err, 'Failed to create core product'));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={handleClose} title="Create Core Product">
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <InlineAlert variant="error" message={error} />}
                <SearchableSelect
                    label="Core Name"
                    value={form.core_name_id}
                    selectedLabel={form.core_name_label}
                    onChange={(val, option) => setForm({ ...form, core_name_id: val, core_name_label: option?.label ?? '' })}
                    onSearch={searchCoreNames}
                    placeholder="Search core name..."
                    required
                />
                <SearchableSelect
                    label="Core Length (inches)"
                    value={form.core_length_id}
                    selectedLabel={form.core_length_label}
                    onChange={(val, option) => setForm({ ...form, core_length_id: val, core_length_label: option?.label ?? '' })}
                    onSearch={searchCoreLengths}
                    placeholder="Search core length..."
                    required
                />
                <SearchableSelect
                    label="Core Thickness (mm)"
                    value={form.core_thickness_id}
                    selectedLabel={form.core_thickness_label}
                    onChange={(val, option) => setForm({ ...form, core_thickness_id: val, core_thickness_label: option?.label ?? '' })}
                    onSearch={searchCoreThicknesses}
                    placeholder="Search core thickness..."
                    required
                />
                <div className="flex justify-end gap-3 pt-2">
                    <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
                    <Button type="submit" loading={submitting} disabled={!canSubmit}>Create</Button>
                </div>
            </form>
        </Modal>
    );
};

// Product is a frozen catalog of 4 fixed anchor rows (Jumbo, Cores,
// Packing, Cartons), seeded by a management command, plus their
// attribute-bearing variants — create/edit/delete of the anchors
// themselves stays off this page. The one exception (2026-09): Create
// Core Product below, a narrow, controlled way to build a Cores variant
// from a real attribute combination without going through a purchase.
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
    const [showCreateCore, setShowCreateCore] = useState(false);

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
                <Button icon={Plus} onClick={() => setShowCreateCore(true)}>
                    Create Core Product
                </Button>
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

            <CreateCoreProductModal
                isOpen={showCreateCore}
                onClose={() => setShowCreateCore(false)}
                onCreated={() => { setShowCreateCore(false); refetch(); }}
            />
        </div>
    );
};

export default ProductsPage;
