import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FlaskConical, SlidersHorizontal, X } from 'lucide-react';
import { useRecipes } from '../../hooks/useProduction';
import Table from '../../components/ui/Table';
import Button from '../../components/ui/Button';
import Modal from '../../components/ui/Modal';
import Input from '../../components/ui/Input';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Card from '../../components/ui/Card';
import FilterBar from '../../components/ui/FilterBar';
import Pagination from '../../components/ui/Pagination';
import InlineAlert from '../../components/ui/InlineAlert';
import EmptyState from '../../components/ui/EmptyState';
import RecipeStatusBadge from '../../components/production/RecipeStatusBadge';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

// Recipe list — Rewinding is the only recipe_type that exists so far, so
// the create form only collects name + description (recipe_type is sent as
// a fixed constant).
const RecipesPage = () => {
    const navigate = useNavigate();
    const { toast } = useToast();

    const [searchTerm, setSearchTerm] = useState('');
    const [showFilters, setShowFilters] = useState(false);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [formData, setFormData] = useState({ name: '', description: '' });
    const [formError, setFormError] = useState('');

    const {
        data: recipes, meta, page, setPage, loading, initialLoading, error,
        filters, setFilters, refetch, creating, create,
    } = useRecipes({});

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
                { value: 'under_processing', label: 'Under Processing' },
                { value: 'finished', label: 'Finished' },
            ],
        },
    ];

    const resetForm = () => {
        setFormData({ name: '', description: '' });
        setFormError('');
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        setFormError('');
        try {
            const created = await create({
                name: formData.name,
                description: formData.description,
                recipe_type: 'rewinding',
            });
            toast.success('Recipe created successfully');
            setShowCreateModal(false);
            resetForm();
            if (created?.id) {
                navigate(`/production/recipes/${created.id}`);
            }
        } catch (err) {
            setFormError(extractErrorMessage(err, 'Failed to create recipe'));
        }
    };

    const columns = [
        { key: 'recipe_number', label: 'Recipe #', width: '140px' },
        { key: 'name', label: 'Name' },
        {
            key: 'status',
            label: 'Status',
            width: '160px',
            render: (value) => <RecipeStatusBadge status={value} />,
        },
        {
            key: 'cost_per_unit',
            label: 'Cost / Unit',
            width: '120px',
            render: (value) => value == null ? '—' : parseFloat(value).toFixed(2),
        },
        {
            key: 'created_at',
            label: 'Created',
            width: '140px',
            render: (value) => value ? new Date(value).toLocaleDateString() : '—',
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                        <FlaskConical className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">Rewinding Recipes</h1>
                        <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                            Rewinding production batches — issue raw materials, record output, finish to lock in cost
                        </p>
                    </div>
                </div>
                <Button
                    onClick={() => {
                        resetForm();
                        setShowCreateModal(true);
                    }}
                    icon={Plus}
                >
                    New Rewinding Recipe
                </Button>
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1">
                        <SearchBar
                            onSearch={handleSearch}
                            placeholder="Search by recipe number or name..."
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

            <Card className="p-0 overflow-hidden" hover={false}>
                {recipes.length === 0 ? (
                    <EmptyState
                        icon={<FlaskConical className="w-8 h-8 text-neutral-400" />}
                        title="No rewinding recipes found"
                        description={searchTerm || Object.keys(filters).length > 0 ? 'Try adjusting your search or filters.' : 'Get started by creating your first rewinding recipe.'}
                    />
                ) : (
                    <div className={loading ? 'opacity-60 transition-opacity p-2' : 'transition-opacity p-2'}>
                        <Table
                            columns={columns}
                            data={recipes}
                            onRowClick={(row) => navigate(`/production/recipes/${row.id}`)}
                        />
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

            <Modal
                isOpen={showCreateModal}
                onClose={() => {
                    setShowCreateModal(false);
                    resetForm();
                }}
                title="New Rewinding Recipe"
            >
                <form onSubmit={handleCreate} className="space-y-4">
                    {formError && <InlineAlert variant="error" message={formError} />}
                    <Input
                        label="Name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="e.g. Rewinding batch — 40gsm"
                        required
                    />
                    <div>
                        <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                            Description
                            <span className="text-neutral-400 font-normal ml-1">(optional — can be added later)</span>
                        </label>
                        <textarea
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            rows={3}
                            placeholder="Describe this production batch"
                            className="w-full px-4 py-3 bg-white border border-neutral-200 rounded-xl focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 outline-none transition-all"
                        />
                    </div>
                    <div className="flex justify-end gap-3 pt-4">
                        <Button
                            type="button"
                            variant="secondary"
                            onClick={() => {
                                setShowCreateModal(false);
                                resetForm();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" loading={creating}>
                            Create
                        </Button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};

export default RecipesPage;
