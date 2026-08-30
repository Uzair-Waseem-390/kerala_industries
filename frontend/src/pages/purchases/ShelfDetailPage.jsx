import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowRightLeft, LayoutGrid, PackageSearch } from 'lucide-react';
import { purchasesApi } from '../../services/purchasesApi';
import { useShelfStock } from '../../hooks/useInventory';
import Table from '../../components/ui/Table';
import Button from '../../components/ui/Button';
import BackLink from '../../components/ui/BackLink';
import Card from '../../components/ui/Card';
import SearchBar from '../../components/ui/SearchBar';
import Pagination from '../../components/ui/Pagination';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import InlineAlert from '../../components/ui/InlineAlert';
import EmptyState from '../../components/ui/EmptyState';
import Tabs from '../../components/ui/Tabs';
import MoveStockModal from '../../components/purchases/MoveStockModal';
import { extractErrorMessage } from '../../utils/errorMessage';

const FAMILY_TABS = [
    { value: 'rm', label: 'Raw Material' },
    { value: 'wip', label: 'WIP' },
];

const ShelfDetailPage = () => {
    const { id } = useParams();

    const [shelf, setShelf] = useState(null);
    const [shelfLoading, setShelfLoading] = useState(true);
    const [shelfError, setShelfError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [showMoveModal, setShowMoveModal] = useState(false);
    // Which stock table this shelf shows — RM ShelfStock (default, existing
    // behavior) or production.WipShelfStock. WIP now also has shelf-level
    // stock, since it reuses the same purchases.Shelf locations.
    const [activeFamily, setActiveFamily] = useState('rm');

    const fetchShelf = async () => {
        setShelfLoading(true);
        setShelfError('');
        try {
            const data = await purchasesApi.shelves.getById(id);
            setShelf(data);
        } catch (err) {
            setShelf(null);
            setShelfError(extractErrorMessage(err, 'Failed to load shelf.'));
        } finally {
            setShelfLoading(false);
        }
    };

    useEffect(() => {
        fetchShelf();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id]);

    const {
        data: stock, meta, page, setPage, loading, error: stockError, refetch,
    } = useShelfStock(id, searchTerm, activeFamily);

    const handleSearch = (value) => {
        setSearchTerm(value);
        setPage(1);
    };

    const handleFamilyChange = (value) => {
        setActiveFamily(value);
        setSearchTerm('');
        setPage(1);
    };

    const handleMoveSuccess = () => {
        setShowMoveModal(false);
        refetch();
    };

    const rmColumns = [
        {
            key: 'product_name',
            label: 'Product Name',
            render: (_value, row) => row.product?.name || 'N/A',
        },
        {
            key: 'product_code',
            label: 'Product Code',
            render: (_value, row) => row.product?.code || 'N/A',
        },
        {
            key: 'quantity',
            label: 'Quantity',
            render: (value) => <span className="font-semibold text-neutral-900">{value}</span>,
        },
        {
            key: 'last_updated_at',
            label: 'Last Updated',
            render: (value) => value ? new Date(value).toLocaleString() : 'N/A',
        },
    ];

    // WIP shelf stock has no product code — product.name is already fully
    // human-readable (mirrors WipInventoryPage's columns).
    const wipColumns = [
        {
            key: 'product_name',
            label: 'WIP Product',
            render: (_value, row) => row.product?.name || 'N/A',
        },
        {
            key: 'quantity',
            label: 'Quantity',
            render: (value) => <span className="font-semibold text-neutral-900">{value}</span>,
        },
        {
            key: 'last_updated_at',
            label: 'Last Updated',
            render: (value) => value ? new Date(value).toLocaleString() : 'N/A',
        },
    ];

    const columns = activeFamily === 'wip' ? wipColumns : rmColumns;

    if (shelfLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    if (!shelf) {
        return (
            <div className="space-y-4">
                <BackLink to="/purchases/shelves">Back to Shelves</BackLink>
                {shelfError ? (
                    <InlineAlert variant="error" message={shelfError} onRetry={fetchShelf} />
                ) : (
                    <div className="text-center py-12">
                        <h2 className="text-2xl font-semibold text-neutral-900">Shelf Not Found</h2>
                        <p className="text-neutral-500 mt-1">The shelf you&apos;re looking for doesn&apos;t exist.</p>
                    </div>
                )}
            </div>
        );
    }

    return (
        <>
            <MoveStockModal
                isOpen={showMoveModal}
                onClose={() => setShowMoveModal(false)}
                fromShelfId={id}
                onSuccess={handleMoveSuccess}
            />

            <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div>
                        <BackLink to="/purchases/shelves">Back to Shelves</BackLink>
                        <div className="flex items-center gap-3 mt-3">
                            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                                <LayoutGrid className="w-5 h-5 text-white" />
                            </div>
                            <div>
                                <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">{shelf.name}</h1>
                                {shelf.description && (
                                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">{shelf.description}</p>
                                )}
                            </div>
                        </div>
                    </div>
                    {activeFamily === 'rm' && (
                        <Button
                            onClick={() => setShowMoveModal(true)}
                            icon={ArrowRightLeft}
                            className="sm:flex-shrink-0"
                        >
                            Move Stock
                        </Button>
                    )}
                </div>

                <Card className="p-4 sm:p-6" hover={false}>
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-neutral-900">Products on this Shelf</h3>
                    </div>

                    <Tabs
                        tabs={FAMILY_TABS}
                        activeTab={activeFamily}
                        onChange={handleFamilyChange}
                        className="mb-4"
                    />

                    <div className="mb-4">
                        <SearchBar
                            key={activeFamily}
                            onSearch={handleSearch}
                            placeholder={activeFamily === 'wip' ? 'Search WIP products...' : 'Search by product name or code...'}
                            className="w-full"
                        />
                    </div>

                    {stockError && (
                        <div className="mb-4">
                            <InlineAlert variant="error" message={stockError} onRetry={refetch} />
                        </div>
                    )}

                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <LoadingSpinner size="lg" />
                        </div>
                    ) : stock.length === 0 ? (
                        <EmptyState
                            icon={<PackageSearch className="w-8 h-8 text-neutral-400" />}
                            title={activeFamily === 'wip' ? 'No WIP stock on this shelf' : 'No products on this shelf'}
                            description={searchTerm ? 'Try adjusting your search.' : (activeFamily === 'wip' ? 'Put away WIP stock here to see it listed.' : 'Move stock here to see it listed.')}
                        />
                    ) : (
                        <>
                            <Table columns={columns} data={stock} />

                            {meta.totalPages > 1 && (
                                <div className="mt-4">
                                    <Pagination
                                        currentPage={meta.currentPage}
                                        totalPages={meta.totalPages}
                                        onPageChange={setPage}
                                    />
                                </div>
                            )}
                        </>
                    )}
                </Card>
            </div>
        </>
    );
};

export default ShelfDetailPage;
