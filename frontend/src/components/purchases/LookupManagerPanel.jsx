import { useState } from 'react';
import PropTypes from 'prop-types';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { useCRUD } from '../../hooks/usePurchases';
import Table from '../ui/Table';
import Button from '../ui/Button';
import Modal from '../ui/Modal';
import Input from '../ui/Input';
import SearchBar from '../ui/SearchBar';
import LoadingSpinner from '../ui/LoadingSpinner';
import Badge from '../ui/Badge';
import Card from '../ui/Card';
import ConfirmDialog from '../ui/ConfirmDialog';
import InlineAlert from '../ui/InlineAlert';
import EmptyState from '../ui/EmptyState';
import Pagination from '../ui/Pagination';
import { useToast } from '../../context/ToastContext';
import { extractErrorMessage } from '../../utils/errorMessage';

// One tab's worth of CRUD for a plain {id, value} lookup resource (Jumbo
// Name/Binding, Core Length/Thickness, Packing/Carton Size). All 6 share
// this exact shape, so one component drives every tab on ProductAttributesPage
// instead of 6 near-identical copies of CategoriesPage.
const LookupManagerPanel = ({ resource, label, isAdmin }) => {
    const { toast } = useToast();

    const { data, meta, page, setPage, loading, error, create, update, delete: deleteItem, refetch } = useCRUD(resource);

    const [searchTerm, setSearchTerm] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [editingItem, setEditingItem] = useState(null);
    const [formValue, setFormValue] = useState('');
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [deleteLoading, setDeleteLoading] = useState(false);

    const filteredData = data.filter(item =>
        item.value.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const resetForm = () => {
        setFormValue('');
        setEditingItem(null);
        setFormError('');
    };

    const handleEdit = (item) => {
        setEditingItem(item);
        setFormValue(item.value);
        setFormError('');
        setShowModal(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormLoading(true);
        setFormError('');
        try {
            if (editingItem) {
                await update(editingItem.id, { value: formValue });
                toast.success(`${label} updated successfully`);
            } else {
                await create({ value: formValue });
                toast.success(`${label} created successfully`);
            }
            setShowModal(false);
            resetForm();
        } catch (err) {
            setFormError(extractErrorMessage(err, `Failed to save ${label.toLowerCase()}.`));
        } finally {
            setFormLoading(false);
        }
    };

    const handleDelete = async (id) => {
        setDeleteLoading(true);
        try {
            await deleteItem(id);
            toast.success(`${label} deleted successfully`);
            setDeleteConfirm(null);
        } catch (err) {
            toast.error(extractErrorMessage(err, `Failed to delete ${label.toLowerCase()}.`));
        } finally {
            setDeleteLoading(false);
        }
    };

    const columns = [
        { key: 'id', label: 'ID', width: '80px' },
        { key: 'value', label: 'Value' },
        {
            key: 'is_deleted',
            label: 'Status',
            width: '110px',
            render: (value) => (
                <Badge variant={value ? 'error' : 'success'}>
                    {value ? 'Deleted' : 'Active'}
                </Badge>
            ),
        },
        {
            key: 'actions',
            label: 'Actions',
            width: '100px',
            render: (_, row) => isAdmin && !row.is_deleted && (
                <div className="flex items-center gap-1">
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            handleEdit(row);
                        }}
                        title={`Edit ${label.toLowerCase()}`}
                        aria-label={`Edit ${label.toLowerCase()}`}
                        className="p-2 rounded-lg text-neutral-500 hover:text-primary-700 hover:bg-primary-50 transition-colors"
                    >
                        <Pencil className="w-4 h-4" />
                    </button>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirm(row);
                        }}
                        title={`Delete ${label.toLowerCase()}`}
                        aria-label={`Delete ${label.toLowerCase()}`}
                        className="p-2 rounded-lg text-neutral-500 hover:text-error-600 hover:bg-error-50 transition-colors"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            ),
        },
    ];

    if (loading && data.length === 0) {
        return (
            <div className="flex items-center justify-center py-16">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <SearchBar
                    onSearch={setSearchTerm}
                    placeholder={`Search ${label.toLowerCase()} values...`}
                    className="w-full sm:max-w-md"
                />
                {isAdmin && (
                    <Button
                        onClick={() => {
                            resetForm();
                            setShowModal(true);
                        }}
                        icon={Plus}
                        className="w-full sm:w-auto"
                    >
                        Add {label}
                    </Button>
                )}
            </div>

            {error && (
                <InlineAlert variant="error" message={error} onRetry={refetch} />
            )}

            <Card className="p-0 overflow-hidden" hover={false}>
                {filteredData.length === 0 ? (
                    <EmptyState
                        title={`No ${label.toLowerCase()} values found`}
                        description={searchTerm ? 'Try adjusting your search.' : `Get started by adding your first ${label.toLowerCase()}.`}
                    />
                ) : (
                    <div className="p-2">
                        <Table columns={columns} data={filteredData} />
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
                isOpen={showModal}
                onClose={() => {
                    setShowModal(false);
                    resetForm();
                }}
                title={editingItem ? `Edit ${label}` : `Create ${label}`}
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    {formError && <InlineAlert variant="error" message={formError} />}
                    <Input
                        label="Value"
                        value={formValue}
                        onChange={(e) => setFormValue(e.target.value)}
                        placeholder={`Enter ${label.toLowerCase()} value`}
                        required
                    />
                    <div className="flex justify-end gap-3 pt-4">
                        <Button
                            type="button"
                            variant="secondary"
                            onClick={() => {
                                setShowModal(false);
                                resetForm();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" loading={formLoading}>
                            {editingItem ? 'Update' : 'Create'}
                        </Button>
                    </div>
                </form>
            </Modal>

            <ConfirmDialog
                isOpen={!!deleteConfirm}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => handleDelete(deleteConfirm?.id)}
                title={`Delete ${label}`}
                message={`Are you sure you want to delete "${deleteConfirm?.value}"? This action cannot be undone.`}
                confirmText="Delete"
                variant="danger"
                loading={deleteLoading}
            />
        </div>
    );
};

LookupManagerPanel.propTypes = {
    resource: PropTypes.shape({
        getAll: PropTypes.func.isRequired,
        create: PropTypes.func.isRequired,
        update: PropTypes.func.isRequired,
        delete: PropTypes.func.isRequired,
    }).isRequired,
    label: PropTypes.string.isRequired,
    isAdmin: PropTypes.bool.isRequired,
};

export default LookupManagerPanel;
