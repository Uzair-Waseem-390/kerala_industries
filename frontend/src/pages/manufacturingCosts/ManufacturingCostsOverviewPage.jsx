import { Link } from 'react-router-dom';
import { ShieldAlert, Users, Cog, Receipt, Wallet, ArrowRight, Factory } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import InlineAlert from '../../components/ui/InlineAlert';

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
    const isAdmin = user?.role === 'admin' || user?.role === 'superuser';

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

    return (
        <div className="space-y-6">
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

            <InlineAlert
                variant="info"
                message="Stats for this overview are coming in a later phase — for now, use the sections below."
            />

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
