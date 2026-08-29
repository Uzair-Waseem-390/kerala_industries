import { useState } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { purchasesApi } from '../../services/purchasesApi';
import LookupManagerPanel from '../../components/purchases/LookupManagerPanel';
import Tabs from '../../components/ui/Tabs';
import { useAuth } from '../../context/AuthContext';

// 6 near-identical lookup tables (Jumbo Name/Binding, Core Length/Thickness,
// Packing/Carton Size) — free-text tag values, prep for a future
// production/recipe feature. Not attached to Product, not 6 separate
// domains, so one page with tabs beats 6 near-duplicate pages + 6 nav
// entries: same nav footprint as one page, same CRUD component reused per
// tab (LookupManagerPanel), and switching between them is a click instead
// of a full page navigation.
const TABS = [
    { value: 'jumbo-names', label: 'Jumbo Names', singular: 'Jumbo Name', resourceKey: 'jumboNames' },
    { value: 'core-names', label: 'Core Names', singular: 'Core Name', resourceKey: 'coreNames' },
    { value: 'core-lengths', label: 'Core Lengths', singular: 'Core Length', resourceKey: 'coreLengths' },
    { value: 'core-thicknesses', label: 'Core Thicknesses', singular: 'Core Thickness', resourceKey: 'coreThicknesses' },
    { value: 'packing-sizes', label: 'Packing Sizes', singular: 'Packing Size', resourceKey: 'packingSizes' },
    { value: 'carton-sizes', label: 'Carton Sizes', singular: 'Carton Size', resourceKey: 'cartonSizes' },
];

const ProductAttributesPage = () => {
    const { user } = useAuth();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';
    const [activeTab, setActiveTab] = useState(TABS[0].value);

    const activeTabConfig = TABS.find((t) => t.value === activeTab) ?? TABS[0];

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                    <SlidersHorizontal className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">Product Attributes</h1>
                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                        Manage lookup values used to describe products
                    </p>
                </div>
            </div>

            <Tabs
                tabs={TABS}
                activeTab={activeTab}
                onChange={setActiveTab}
                className="overflow-x-auto"
            />

            <LookupManagerPanel
                key={activeTabConfig.value}
                resource={purchasesApi[activeTabConfig.resourceKey]}
                label={activeTabConfig.singular}
                isAdmin={isAdmin}
            />
        </div>
    );
};

export default ProductAttributesPage;
