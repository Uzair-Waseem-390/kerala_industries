import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useUnpricedProducts } from '../../hooks/useRates';
import { ratesApi } from '../../services/ratesApi';
import RateTable from '../../components/rates/RateTable';
import RateFormModal from '../../components/rates/RateFormModal';
import SearchBar from '../../components/ui/SearchBar';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Pagination from '../../components/ui/Pagination';
import BackLink from '../../components/ui/BackLink';
import { useNavigate } from 'react-router-dom';

const UnpricedProductsPage = () => {
    const { user } = useAuth();
    const { toast } = useToast();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';
    const navigate = useNavigate();

    const {
        data: products, meta, page, setPage, loading,
        filters, setFilters, refetch,
    } = useUnpricedProducts();
    const data = products.map(product => ({ product, rate: null }));

    const [showModal, setShowModal] = useState(false);
    const [selectedProduct, setSelectedProduct] = useState(null);
    const [formLoading, setFormLoading] = useState(false);

    const handleSearch = (value) => {
        setFilters({ ...filters, search: value });
    };

    const handleResetFilters = () => {
        setFilters({});
    };

    const handleEdit = (product) => {
        setSelectedProduct(product);
        setShowModal(true);
    };

    const handleViewHistory = (product) => {
        navigate(`/rates/history/${product.id}`);
    };

    const handleSubmit = async (formData) => {
        setFormLoading(true);
        try {
            await ratesApi.create({
                product_id: selectedProduct.id,
                selling_price: formData.selling_price,
                note: formData.note,
            });
            await refetch();
            setShowModal(false);
            setSelectedProduct(null);
            toast.success('Price set successfully');
        } catch (error) {
            console.error('Failed to save rate:', error);
            throw error; // Re-thrown so RateFormModal can show field/generic errors and stay open
        } finally {
            setFormLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <BackLink to="/rates">Back to Product Rates</BackLink>
                <h1 className="text-3xl font-bold text-neutral-900 mt-1">
                    Unpriced Products {meta.count ? `(${meta.count})` : ''}
                </h1>
                <p className="text-neutral-500 mt-1">
                    Products that don't have a selling price set yet
                </p>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-4">
                <SearchBar
                    onSearch={handleSearch}
                    placeholder="Search by product name or code..."
                    className="flex-1"
                />
                {(Object.keys(filters).length > 0) && (
                    <button
                        onClick={handleResetFilters}
                        className="px-4 py-2.5 bg-neutral-100 text-neutral-700 rounded-xl hover:bg-neutral-200 transition-colors"
                    >
                        Clear Filters
                    </button>
                )}
            </div>

            <RateTable
                rates={data}
                isAdmin={isAdmin}
                onEdit={handleEdit}
                onViewHistory={handleViewHistory}
                loading={loading}
            />

            {meta.totalPages > 1 && (
                <Pagination
                    currentPage={meta.currentPage}
                    totalPages={meta.totalPages}
                    onPageChange={setPage}
                />
            )}

            <RateFormModal
                isOpen={showModal}
                onClose={() => {
                    setShowModal(false);
                    setSelectedProduct(null);
                }}
                onSubmit={handleSubmit}
                product={selectedProduct}
                existingRate={null}
                loading={formLoading}
            />
        </div>
    );
};

export default UnpricedProductsPage;
