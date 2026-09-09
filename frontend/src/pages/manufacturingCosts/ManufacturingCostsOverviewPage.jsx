import { Link, useNavigate } from 'react-router-dom';
import { ShieldAlert, Users, Cog, Receipt, Wallet, ArrowRight, Factory, HardHat, Zap, CalendarClock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useManufacturingCostsStats } from '../../hooks/useManufacturingCosts';
import { useCashFlowStats } from '../../hooks/useCashFlow';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import InlineAlert from '../../components/ui/InlineAlert';
import StatCard from '../../components/dashboard/StatCard';
import StatCardSkeleton from '../../components/dashboard/StatCardSkeleton';

const navItems = [
    {
        to: '/manufacturing-costs/employees', title: 'Employees', icon: Users,
        description: 'Direct labor — salary, hours, and the computed rate/hour per employee.',
    },
    {
        to: '/manufacturing-costs/machines', title: 'Machines', icon: Cog,
        description: 'Factory overhead — machines, categories, and the Rent/Electricity setting.',
    },
    {
        to: '/manufacturing-costs/payable-entities', title: 'Payment Records', icon: Receipt,
        description: 'Every employee, machine, Rent, and Electricity — record payments here.',
    },
    {
        to: '/manufacturing-costs/payments', title: 'All Payments', icon: Wallet,
        description: 'Every payment ever recorded, searchable by reference number.',
    },
];

const ManufacturingCostsOverviewPage = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

    const { data: stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useManufacturingCostsStats();
    const { data: cashStats, loading: cashLoading } = useCashFlowStats();

    if (!isAdmin) {
        return (
            <div className="flex flex-col items-center justify-center text-center py-20">
                <div className="w-14 h-14 rounded-full bg-error-50 flex items-center justify-center mb-4">
                    <ShieldAlert className="w-7 h-7 text-error-500" />
                </div>
                <h2 className="text-2xl font-semibold text-neutral-900">Access Denied</h2>
                <p className="text-neutral-500 mt-2 max-w-sm">Only admins or superusers can view manufacturing costs.</p>
            </div>
        );
    }

    const loading = statsLoading || cashLoading;
    const goToEmployees = () => navigate('/manufacturing-costs/employees');
    const goToMachines = () => navigate('/manufacturing-costs/machines');
    const goToPayments = () => navigate('/manufacturing-costs/payments');

    return (
        <div className="space-y-8">
            <div className="flex items-start gap-4">
                <div className="hidden sm:flex w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-700 to-accent-600 items-center justify-center flex-shrink-0 shadow-lg shadow-primary-900/20">
                    <Factory className="w-6 h-6 text-white" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-neutral-900">Manufacturing Costs</h1>
                    <p className="text-neutral-500 mt-1">
                        Direct labor and factory overhead cost tracking, feeding the manufacturing cost of goods sold.
                    </p>
                </div>
            </div>

            {statsError && (
                <InlineAlert variant="error" message={statsError} onRetry={refetchStats} />
            )}

            {/* Resources — headcount + this month's budget picture, both O(1) reads off the stored stats singleton. */}
            <div className="space-y-4">
                <h2 className="text-lg font-semibold text-neutral-900">Resources & This Month's Estimate</h2>
                {loading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCardSkeleton color="blue" />
                        <StatCardSkeleton color="purple" />
                        <StatCardSkeleton color="amber" />
                        <StatCardSkeleton color="orange" />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            label="Total Employees"
                            value={stats?.total_employees}
                            icon={Users}
                            color="blue"
                            isCurrency={false}
                            subtitle="Active"
                            onClick={goToEmployees}
                        />
                        <StatCard
                            label="Total Machines"
                            value={stats?.total_machines}
                            icon={Cog}
                            color="purple"
                            isCurrency={false}
                            subtitle="Active"
                            onClick={goToMachines}
                        />
                        <StatCard
                            label="Estimated Monthly DL"
                            value={stats?.total_estimated_monthly_dl}
                            icon={HardHat}
                            color="amber"
                            subtitle="Σ employee salaries"
                            onClick={goToEmployees}
                        />
                        <StatCard
                            label="Estimated Monthly FOH"
                            value={stats?.total_estimated_monthly_foh}
                            icon={Zap}
                            color="orange"
                            subtitle="Machines + Rent + Electricity"
                            onClick={goToMachines}
                        />
                    </div>
                )}
            </div>

            {/* Payments — real cash already paid out, all-time (CashFlow) and last closed month (this app's own monthly snapshot). */}
            <div className="space-y-4">
                <h2 className="text-lg font-semibold text-neutral-900">Payments</h2>
                {loading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCardSkeleton color="green" />
                        <StatCardSkeleton color="green" />
                        <StatCardSkeleton color="red" />
                        <StatCardSkeleton color="red" />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            label="Total DL Paid"
                            value={cashStats?.total_direct_labor_paid}
                            icon={Wallet}
                            color="green"
                            subtitle="All-time"
                            onClick={goToPayments}
                        />
                        <StatCard
                            label="Total FOH Paid"
                            value={cashStats?.total_factory_overhead_paid}
                            icon={Wallet}
                            color="green"
                            subtitle="All-time"
                            onClick={goToPayments}
                        />
                        <StatCard
                            label="Last Month DL Paid"
                            value={stats?.last_month_dl_paid}
                            icon={CalendarClock}
                            color="red"
                            subtitle="Last closed month"
                            onClick={goToPayments}
                        />
                        <StatCard
                            label="Last Month FOH Paid"
                            value={stats?.last_month_foh_paid}
                            icon={CalendarClock}
                            color="red"
                            subtitle="Last closed month"
                            onClick={goToPayments}
                        />
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {navItems.map(({ to, title, icon: Icon, description }) => (
                    <Card key={to} className="p-6 flex flex-col">
                        <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 bg-primary-50">
                            <Icon className="w-5 h-5 text-primary-700" />
                        </div>
                        <h3 className="font-semibold text-neutral-900 mb-1.5">{title}</h3>
                        <p className="text-sm text-neutral-500 mb-4 flex-1">{description}</p>
                        <Link to={to}>
                            <Button variant="secondary" className="w-full sm:w-auto">
                                View {title}
                                <ArrowRight className="w-4 h-4" />
                            </Button>
                        </Link>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default ManufacturingCostsOverviewPage;
