import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PackagePlus } from 'lucide-react';
import { purchasesApi } from '../../services/purchasesApi';
import { useToast } from '../../context/ToastContext';
import Tabs from '../../components/ui/Tabs';
import Card from '../../components/ui/Card';
import PurchaseIntakeFormBase from '../../components/purchases/intake/PurchaseIntakeFormBase';
import JumboFields, { initialJumboData, validateJumbo, buildJumboPayload } from '../../components/purchases/intake/JumboFields';
import CoreFields, { initialCoreData, validateCore, buildCorePayload } from '../../components/purchases/intake/CoreFields';
import PackingFields, { initialPackingData, validatePacking, buildPackingPayload } from '../../components/purchases/intake/PackingFields';
import CartonFields, { initialCartonData, validateCarton, buildCartonPayload } from '../../components/purchases/intake/CartonFields';

// Config-driven: one entry per RM family, each pairing its fields component
// with the validate/build/create functions PurchaseIntakeFormBase needs.
// Adding a 5th family later is one entry here, not a new page.
const FAMILIES = [
    {
        value: 'jumbo',
        label: 'Jumbo',
        initialData: initialJumboData,
        validate: validateJumbo,
        buildPayload: buildJumboPayload,
        createApi: purchasesApi.jumboPurchases.create,
        Fields: JumboFields,
    },
    {
        value: 'core',
        label: 'Cores',
        initialData: initialCoreData,
        validate: validateCore,
        buildPayload: buildCorePayload,
        createApi: purchasesApi.corePurchases.create,
        Fields: CoreFields,
    },
    {
        value: 'packing',
        label: 'Packing',
        initialData: initialPackingData,
        validate: validatePacking,
        buildPayload: buildPackingPayload,
        createApi: purchasesApi.packingPurchases.create,
        Fields: PackingFields,
    },
    {
        value: 'carton',
        label: 'Cartons',
        initialData: initialCartonData,
        validate: validateCarton,
        buildPayload: buildCartonPayload,
        createApi: purchasesApi.cartonPurchases.create,
        Fields: CartonFields,
    },
];

const PurchaseIntakePage = () => {
    const navigate = useNavigate();
    const { toast } = useToast();
    const [activeTab, setActiveTab] = useState(FAMILIES[0].value);

    const activeFamily = FAMILIES.find((f) => f.value === activeTab) ?? FAMILIES[0];

    const searchSuppliers = async (query) => {
        const res = await purchasesApi.suppliers.getAll({ search: query });
        const results = res?.results ?? res ?? [];
        return results.map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }));
    };

    const handleCreated = (order) => {
        toast.success(`${activeFamily.label} purchase draft created`);
        // Created order is still a draft — hand off to the existing order
        // detail page for shelf allocation (put-away) + confirm.
        navigate(`/purchases/orders/${order.id}`);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-primary-600 to-accent-600 flex items-center justify-center shadow-lg shadow-primary-900/20 flex-shrink-0">
                    <PackagePlus className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900">New RM Purchase</h1>
                    <p className="text-neutral-500 mt-0.5 text-sm sm:text-base">
                        Record a Jumbo, Core, Packing, or Carton purchase. Creates a draft order — allocate shelves and confirm from the order detail page.
                    </p>
                </div>
            </div>

            <Tabs
                tabs={FAMILIES}
                activeTab={activeTab}
                onChange={setActiveTab}
                className="overflow-x-auto"
            />

            <Card className="p-6" hover={false}>
                <PurchaseIntakeFormBase
                    key={activeFamily.value}
                    initialFamilyData={activeFamily.initialData}
                    renderFamilyFields={(data, onChange) => <activeFamily.Fields data={data} onChange={onChange} />}
                    validateFamily={activeFamily.validate}
                    buildFamilyPayload={activeFamily.buildPayload}
                    createApi={activeFamily.createApi}
                    onSearchSuppliers={searchSuppliers}
                    onCreated={handleCreated}
                    submitLabel={`Create ${activeFamily.label} Purchase`}
                />
            </Card>
        </div>
    );
};

export default PurchaseIntakePage;
