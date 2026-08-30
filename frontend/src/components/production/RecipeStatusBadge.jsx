import Badge from '../ui/Badge';

const RecipeStatusBadge = ({ status }) => {
    const variants = {
        under_processing: 'pending',
        finished: 'success',
    };

    const labels = {
        under_processing: 'Under Processing',
        finished: 'Finished',
    };

    return <Badge variant={variants[status] || 'default'}>{labels[status] || status}</Badge>;
};

export default RecipeStatusBadge;
