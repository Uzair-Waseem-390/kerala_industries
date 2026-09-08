import { api } from '../utils/api';

export const manufacturingCostsApi = {
    employees: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/manufacturing-costs/employees/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/manufacturing-costs/employees/${id}/`),
        create: (data) => api.post('/manufacturing-costs/employees/', data),
        update: (id, data) => api.patch(`/manufacturing-costs/employees/${id}/`, data),
        delete: (id) => api.delete(`/manufacturing-costs/employees/${id}/`),
    },
    machines: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/manufacturing-costs/machines/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/manufacturing-costs/machines/${id}/`),
        create: (data) => api.post('/manufacturing-costs/machines/', data),
        update: (id, data) => api.patch(`/manufacturing-costs/machines/${id}/`, data),
        delete: (id) => api.delete(`/manufacturing-costs/machines/${id}/`),
    },
    factoryOverheadSetting: {
        get: () => api.get('/manufacturing-costs/factory-overhead-setting/'),
        update: (data) => api.patch('/manufacturing-costs/factory-overhead-setting/', data),
    },
    payableEntities: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/manufacturing-costs/payable-entities/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/manufacturing-costs/payable-entities/${id}/`),
        getStats: (id) => api.get(`/manufacturing-costs/payable-entities/${id}/stats/`),
        getPayments: (id, params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/manufacturing-costs/payable-entities/${id}/payments/${query ? `?${query}` : ''}`);
        },
        delete: (id) => api.delete(`/manufacturing-costs/payable-entities/${id}/delete/`),
    },
    payments: {
        getAll: (params = {}) => {
            const query = new URLSearchParams(params).toString();
            return api.get(`/manufacturing-costs/payments/${query ? `?${query}` : ''}`);
        },
        getById: (id) => api.get(`/manufacturing-costs/payments/${id}/`),
        create: (data) => api.post('/manufacturing-costs/payments/', data),
        delete: (id) => api.delete(`/manufacturing-costs/payments/${id}/`),
    },
};
