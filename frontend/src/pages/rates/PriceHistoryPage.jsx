import { useParams, Link } from 'react-router-dom';
import { useRateHistory } from '../../hooks/useRates';
import PriceHistoryTable from '../../components/rates/PriceHistoryTable';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Card from '../../components/ui/Card';
import InlineAlert from '../../components/ui/InlineAlert';

const PriceHistoryPage = () => {
    const { productType, productId } = useParams();
    const { data, loading, error, refetch } = useRateHistory(productType, productId);

    // Product name/code come straight off the history rows themselves
    // (ProductRateHistorySerializer already includes them on every row) —
    // no separate product-detail fetch needed, and this works identically
    // for FG products, which have no dedicated detail-by-id endpoint.
    const product = data.length > 0 ? { name: data[0].product_name, code: data[0].product_code } : null;
    const currentPrice = data.length > 0 ? parseFloat(data[0].selling_price) : null;

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-neutral-900">Price History</h1>
                    <p className="text-neutral-500 mt-1">
                        Complete price change log for this product
                    </p>
                </div>
                <Link to="/rates">
                    <Button variant="secondary">
                        ← Back to Rates
                    </Button>
                </Link>
            </div>

            {error && <InlineAlert variant="error" message={error} onRetry={refetch} />}

            {/* Product Info */}
            {product && (
                <Card className="p-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                            <p className="text-sm text-neutral-500">Product Name</p>
                            <p className="font-medium text-neutral-900">{product.name}</p>
                        </div>
                        <div>
                            <p className="text-sm text-neutral-500">Product Code</p>
                            <p className="font-medium text-neutral-900">{product.code}</p>
                        </div>
                        <div>
                            <p className="text-sm text-neutral-500">Current Price</p>
                            <p className="font-medium text-primary-600 text-lg">
                                {currentPrice !== null ? `Rs. ${currentPrice.toFixed(2)}` : 'No price set'}
                            </p>
                        </div>
                    </div>
                </Card>
            )}

            {/* Price History Table */}
            <PriceHistoryTable
                history={data}
                loading={loading}
                currentPrice={currentPrice}
            />

            {/* Back Button at Bottom */}
            <div className="flex justify-center">
                <Link to="/rates">
                    <Button variant="secondary">
                        ← Back to Rates
                    </Button>
                </Link>
            </div>
        </div>
    );
};

export default PriceHistoryPage;