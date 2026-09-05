import { PackageCheck } from 'lucide-react';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';

// Placeholder — Finished Goods is Phase 2 of the manufacturing costing
// expansion (RM -> WIP is Phase 1, built). Its own catalog/inventory tables
// don't exist yet (see docs/manufacturing-costing-notes.md). This page just
// holds the nav slot so the Inventory collection reads as complete; swap
// this out once FG inventory is actually designed and built.
const FinishedGoodsPage = () => {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-neutral-900">Finished Goods</h1>
                <p className="text-neutral-500 mt-1">Finished Goods inventory levels, once packing is built</p>
            </div>

            <Card className="p-6" hover={false}>
                <EmptyState
                    icon={<PackageCheck className="w-8 h-8 text-neutral-400" />}
                    title="Coming soon"
                    description="Finished Goods tracking arrives once the Packing stage (WIP → Finished Goods) is built. For now, use Raw Material and WIP under Inventory."
                />
            </Card>
        </div>
    );
};

export default FinishedGoodsPage;
