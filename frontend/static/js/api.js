// ============================================================================
// API Client - Wrapper for Backend API Calls
// ============================================================================

const API_BASE_URL = '';  // Empty for same-origin requests

/**
 * Generic API request handler
 * @param {string} endpoint - API endpoint
 * @param {object} options - Fetch options
 * @returns {Promise} Response data
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;

    const config = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    };

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        // Handle 204 No Content
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        throw error;
    }
}

// ============================================================================
// Cards API
// ============================================================================

const CardsAPI = {
    /**
     * Get all cards
     * @returns {Promise<Array>} List of cards
     */
    async getAll() {
        return apiRequest('/api/cards');
    },

    /**
     * Get a card by ID
     * @param {number} id - Card ID
     * @returns {Promise<object>} Card object
     */
    async getById(id) {
        return apiRequest(`/api/cards/${id}`);
    },

    /**
     * Create a new card
     * @param {object} cardData - Card data
     * @returns {Promise<object>} Created card
     */
    async create(cardData) {
        return apiRequest('/api/cards', {
            method: 'POST',
            body: JSON.stringify(cardData),
        });
    },

    /**
     * Update a card
     * @param {number} id - Card ID
     * @param {object} cardData - Updated card data
     * @returns {Promise<object>} Updated card
     */
    async update(id, cardData) {
        return apiRequest(`/api/cards/${id}`, {
            method: 'PUT',
            body: JSON.stringify(cardData),
        });
    },

    /**
     * Delete a card
     * @param {number} id - Card ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/cards/${id}`, {
            method: 'DELETE',
        });
    },

    /**
     * Get a card's statement cycles grouped by its cutoff day
     * @param {number} id - Card ID
     * @returns {Promise<Array>} List of billing cycles
     */
    async getBillingCycles(id) {
        return apiRequest(`/api/cards/${id}/billing-cycles`);
    },
};

// ============================================================================
// Installment Plans API ("tasa cero")
// ============================================================================

const InstallmentPlansAPI = {
    /**
     * Get all installment plans
     * @returns {Promise<Array>} List of plans
     */
    async getAll() {
        return apiRequest('/api/installment-plans');
    },

    /**
     * Create an installment plan (generates all its monthly charges)
     * @param {object} planData
     * @returns {Promise<object>} Created plan
     */
    async create(planData) {
        return apiRequest('/api/installment-plans', {
            method: 'POST',
            body: JSON.stringify(planData),
        });
    },

    /**
     * Delete an installment plan and all of its generated transactions
     * @param {number} id - Plan ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/installment-plans/${id}`, {
            method: 'DELETE',
        });
    },
};

// ============================================================================
// Accounts API
// ============================================================================

const AccountsAPI = {
    /**
     * Get all accounts
     * @returns {Promise<Array>} List of accounts
     */
    async getAll() {
        return apiRequest('/api/accounts');
    },

    /**
     * Create a new account
     * @param {object} accountData - Account data
     * @returns {Promise<object>} Created account
     */
    async create(accountData) {
        return apiRequest('/api/accounts', {
            method: 'POST',
            body: JSON.stringify(accountData),
        });
    },

    /**
     * Update an account
     * @param {number} id - Account ID
     * @param {object} accountData - Updated account data
     * @returns {Promise<object>} Updated account
     */
    async update(id, accountData) {
        return apiRequest(`/api/accounts/${id}`, {
            method: 'PUT',
            body: JSON.stringify(accountData),
        });
    },

    /**
     * Delete an account
     * @param {number} id - Account ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/accounts/${id}`, {
            method: 'DELETE',
        });
    },
};

// ============================================================================
// Categories API
// ============================================================================

const CategoriesAPI = {
    /**
     * Get all categories
     * @returns {Promise<Array>} List of categories
     */
    async getAll() {
        return apiRequest('/api/categories');
    },

    /**
     * Get a category by ID
     * @param {number} id - Category ID
     * @returns {Promise<object>} Category object
     */
    async getById(id) {
        return apiRequest(`/api/categories/${id}`);
    },

    /**
     * Create a new category
     * @param {object} categoryData - Category data
     * @returns {Promise<object>} Created category
     */
    async create(categoryData) {
        return apiRequest('/api/categories', {
            method: 'POST',
            body: JSON.stringify(categoryData),
        });
    },

    /**
     * Update a category
     * @param {number} id - Category ID
     * @param {object} categoryData - Updated category data
     * @returns {Promise<object>} Updated category
     */
    async update(id, categoryData) {
        return apiRequest(`/api/categories/${id}`, {
            method: 'PUT',
            body: JSON.stringify(categoryData),
        });
    },

    /**
     * Delete a category
     * @param {number} id - Category ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/categories/${id}`, {
            method: 'DELETE',
        });
    },
};

// ============================================================================
// Categorization Rules API
// ============================================================================

const CategorizationRulesAPI = {
    /**
     * Get categorization rules, optionally filtered by category
     * @param {number} categoryId - Category ID (optional)
     * @returns {Promise<Array>} List of rules
     */
    async getAll(categoryId) {
        const endpoint = categoryId
            ? `/api/categorization-rules?category_id=${categoryId}`
            : '/api/categorization-rules';
        return apiRequest(endpoint);
    },

    /**
     * Create a categorization rule
     * @param {object} ruleData - {match_type, value, category_id}
     * @returns {Promise<object>} Created rule
     */
    async create(ruleData) {
        return apiRequest('/api/categorization-rules', {
            method: 'POST',
            body: JSON.stringify(ruleData),
        });
    },

    /**
     * Delete a categorization rule
     * @param {number} id - Rule ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/categorization-rules/${id}`, {
            method: 'DELETE',
        });
    },
};

// ============================================================================
// Transactions API
// ============================================================================

const TransactionsAPI = {
    /**
     * Get transactions with optional filters
     * @param {object} filters - Filter parameters
     * @returns {Promise<Array>} List of transactions
     */
    async getAll(filters = {}) {
        const params = new URLSearchParams();

        Object.keys(filters).forEach(key => {
            const value = filters[key];
            if (value !== null && value !== undefined && value !== '') {
                params.append(key, value);
            }
        });

        const queryString = params.toString();
        const endpoint = queryString ? `/api/transactions?${queryString}` : '/api/transactions';

        return apiRequest(endpoint);
    },

    /**
     * Get a transaction by ID
     * @param {number} id - Transaction ID
     * @returns {Promise<object>} Transaction object
     */
    async getById(id) {
        return apiRequest(`/api/transactions/${id}`);
    },

    /**
     * Update a transaction
     * @param {number} id - Transaction ID
     * @param {object} transactionData - Updated transaction data
     * @returns {Promise<object>} Updated transaction
     */
    async update(id, transactionData) {
        return apiRequest(`/api/transactions/${id}`, {
            method: 'PUT',
            body: JSON.stringify(transactionData),
        });
    },

    /**
     * Delete a transaction
     * @param {number} id - Transaction ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/transactions/${id}`, {
            method: 'DELETE',
        });
    },

    /**
     * Bulk categorize transactions
     * @param {Array<number>} transactionIds - Array of transaction IDs
     * @param {number} categoryId - Category ID
     * @returns {Promise<object>} Result with count of updated transactions
     */
    async bulkCategorize(transactionIds, categoryId) {
        return apiRequest('/api/transactions/bulk-categorize', {
            method: 'POST',
            body: JSON.stringify({
                transaction_ids: transactionIds,
                category_id: categoryId,
            }),
        });
    },
};

// ============================================================================
// Analytics API
// ============================================================================

const AnalyticsAPI = {
    /**
     * Get dashboard summary
     * @param {object} filters - Date filters
     * @returns {Promise<object>} Dashboard summary data
     */
    async getDashboardSummary(filters = {}) {
        const params = new URLSearchParams();

        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);

        const queryString = params.toString();
        const endpoint = queryString ? `/api/analytics/dashboard-summary?${queryString}` : '/api/analytics/dashboard-summary';

        return apiRequest(endpoint);
    },

    /**
     * Get spending by category
     * @param {object} filters - Date filters
     * @returns {Promise<Array>} Spending by category data
     */
    async getSpendingByCategory(filters = {}) {
        const params = new URLSearchParams();

        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.currency) params.append('currency', filters.currency);

        const queryString = params.toString();
        const endpoint = queryString ? `/api/analytics/spending-by-category?${queryString}` : '/api/analytics/spending-by-category';

        return apiRequest(endpoint);
    },

    /**
     * Get daily spending totals over a date range
     * @param {object} filters - {start_date, end_date, currency}
     * @returns {Promise<Array>} Daily spending data
     */
    async getDailySpending(filters = {}) {
        const params = new URLSearchParams();

        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.currency) params.append('currency', filters.currency);

        const queryString = params.toString();
        const endpoint = queryString ? `/api/analytics/daily-spending?${queryString}` : '/api/analytics/daily-spending';

        return apiRequest(endpoint);
    },

    /**
     * Get monthly trends
     * @param {number} months - Number of months to fetch
     * @returns {Promise<Array>} Monthly trends data
     */
    async getMonthlyTrends(months = 6) {
        return apiRequest(`/api/analytics/monthly-trends?months_back=${months}`);
    },

    /**
     * Get top merchants
     * @param {object} filters - Date, currency, and limit filters
     * @returns {Promise<Array>} Top merchants data
     */
    async getTopMerchants(filters = {}) {
        const params = new URLSearchParams();

        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);
        if (filters.currency) params.append('currency', filters.currency);
        if (filters.limit) params.append('limit', filters.limit);

        const queryString = params.toString();
        const endpoint = queryString ? `/api/analytics/top-merchants?${queryString}` : '/api/analytics/top-merchants';

        return apiRequest(endpoint);
    },

    /**
     * Get card utilization
     * @returns {Promise<Array>} Card utilization data
     */
    async getCardUtilization() {
        return apiRequest('/api/analytics/card-utilization');
    },
};

// ============================================================================
// Email Sources API
// ============================================================================

const EmailSourcesAPI = {
    /**
     * Get all email sources
     * @returns {Promise<Array>} List of email sources
     */
    async getAll() {
        return apiRequest('/api/email-sources');
    },

    /**
     * Create a new email source
     * @param {object} sourceData - Email source data
     * @returns {Promise<object>} Created email source
     */
    async create(sourceData) {
        return apiRequest('/api/email-sources', {
            method: 'POST',
            body: JSON.stringify(sourceData),
        });
    },

    /**
     * Update an email source
     * @param {number} id - Email source ID
     * @param {object} sourceData - Updated email source data
     * @returns {Promise<object>} Updated email source
     */
    async update(id, sourceData) {
        return apiRequest(`/api/email-sources/${id}`, {
            method: 'PUT',
            body: JSON.stringify(sourceData),
        });
    },

    /**
     * Delete an email source
     * @param {number} id - Email source ID
     * @returns {Promise<null>}
     */
    async delete(id) {
        return apiRequest(`/api/email-sources/${id}`, {
            method: 'DELETE',
        });
    },
};

// ============================================================================
// Sync API
// ============================================================================

const SyncAPI = {
    /**
     * Trigger Gmail sync
     * @returns {Promise<object>} Sync result
     */
    async triggerSync() {
        return apiRequest('/api/sync/gmail', {
            method: 'POST',
        });
    },

    /**
     * Get sync status
     * @returns {Promise<object>} Sync status
     */
    async getStatus() {
        return apiRequest('/api/sync/status');
    },
};

// Export API objects for use in app.js
window.API = {
    Cards: CardsAPI,
    InstallmentPlans: InstallmentPlansAPI,
    Accounts: AccountsAPI,
    Categories: CategoriesAPI,
    CategorizationRules: CategorizationRulesAPI,
    Transactions: TransactionsAPI,
    Analytics: AnalyticsAPI,
    EmailSources: EmailSourcesAPI,
    Sync: SyncAPI,
};
