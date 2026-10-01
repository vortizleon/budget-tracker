// ============================================================================
// Main Application Logic
// ============================================================================

// Global state
let currentView = 'dashboard';
let currentCard = null;
let currentCategory = null;
let currentFilters = {};
let currentPage = 0;
const TRANSACTIONS_PAGE_SIZE = 50;
let allCategories = [];
let allCards = [];

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    setupNavigation();
    initTheme();
    initPrivacyMode();
    loadInitialData();
    showView('dashboard');
}

// ============================================================================
// Theme (dark/light mode)
// ============================================================================

function initTheme() {
    // The inline <script> in <head> already applied the right data-theme
    // attribute before first paint (to avoid a flash) - this just syncs the
    // toggle button's icon to match.
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    updateThemeToggleIcon(isDark);
}

function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const next = !isDark;

    if (next) {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    updateThemeToggleIcon(next);

    try {
        localStorage.setItem('theme', next ? 'dark' : 'light');
    } catch (error) {
        // Ignore - just won't persist across reloads.
    }

    // Charts bake their colors in at render time, so they need a fresh
    // render to pick up the new theme - everything else is pure CSS.
    if (currentView === 'analytics') {
        loadAnalytics(currentAnalyticsFilters);
    }
}

function updateThemeToggleIcon(isDark) {
    document.getElementById('theme-icon-moon').classList.toggle('theme-icon-off', isDark);
    document.getElementById('theme-icon-sun').classList.toggle('theme-icon-off', !isDark);

    const btn = document.getElementById('theme-toggle');
    btn.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
}

// ============================================================================
// Privacy Mode (hide/show money amounts)
// ============================================================================

function initPrivacyMode() {
    let hidden = false;
    try {
        hidden = localStorage.getItem('privacyMode') === 'true';
    } catch (error) {
        // localStorage can be unavailable (private browsing, etc.) - default to shown.
    }
    setPrivacyMode(hidden);
}

function togglePrivacyMode() {
    setPrivacyMode(!document.body.classList.contains('privacy-mode'));
}

function setPrivacyMode(hidden) {
    document.body.classList.toggle('privacy-mode', hidden);

    const btn = document.getElementById('privacy-toggle');
    btn.textContent = hidden ? '🙈' : '👁️';
    btn.classList.toggle('active', hidden);
    btn.title = hidden ? 'Show amounts' : 'Hide amounts';

    try {
        localStorage.setItem('privacyMode', hidden);
    } catch (error) {
        // Ignore - just won't persist across reloads.
    }
}

/**
 * Load initial data needed across the app
 */
async function loadInitialData() {
    try {
        [allCategories, allCards] = await Promise.all([
            API.Categories.getAll(),
            API.Cards.getAll(),
        ]);
    } catch (error) {
        console.error('Failed to load initial data:', error);
    }
}

// ============================================================================
// Navigation
// ============================================================================

function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = link.getAttribute('data-view');
            showView(view);
        });
    });
}

async function showView(viewName) {
    // Hide all views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });

    // Show selected view
    const view = document.getElementById(`view-${viewName}`);
    if (view) {
        view.classList.add('active');
    }

    // Update navigation active state
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    const activeLink = document.querySelector(`.nav-link[data-view="${viewName}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }

    currentView = viewName;

    // Load view-specific data
    switch (viewName) {
        case 'dashboard':
            await loadDashboard();
            break;
        case 'cards':
            await loadCards();
            break;
        case 'transactions':
            populateTransactionFilterOptions();
            await loadTransactions();
            break;
        case 'analytics':
            await loadAnalytics(currentAnalyticsFilters);
            break;
        case 'categories':
            await loadCategories();
            break;
        case 'settings':
            await loadSettings();
            break;
    }
}

// ============================================================================
// Dashboard View
// ============================================================================

async function loadDashboard() {
    try {
        // Load dashboard summary
        const summary = await API.Analytics.getDashboardSummary();

        // Update summary cards
        document.getElementById('summary-spent-crc').textContent = formatCurrency(summary.total_spent_crc, 'CRC');
        document.getElementById('summary-spent-usd').textContent = formatCurrency(summary.total_spent_usd, 'USD');
        document.getElementById('summary-transactions').textContent = summary.total_transactions;
        document.getElementById('summary-cards').textContent = summary.active_cards;

        document.getElementById('this-month-crc').textContent = formatCurrency(summary.this_month_spent_crc, 'CRC');
        document.getElementById('this-month-usd').textContent = formatCurrency(summary.this_month_spent_usd, 'USD');
        document.getElementById('uncategorized-count').textContent = summary.uncategorized_count;
        document.getElementById('oldest-date').textContent = summary.oldest_transaction_date ? formatDate(summary.oldest_transaction_date) : '-';

        document.getElementById('this-month-label').textContent =
            `(${new Date().toLocaleString('default', { month: 'long', year: 'numeric' })})`;
        document.getElementById('all-time-caption').textContent = summary.oldest_transaction_date
            ? `(since ${formatDate(summary.oldest_transaction_date)})`
            : '';

        // Load recent transactions - excludes future-dated rows (e.g. an
        // upcoming installment charge) since "recent" means already happened.
        const today = new Date().toISOString().split('T')[0];
        const response = await API.Transactions.getAll({ end_date: today, limit: 10 });
        renderRecentTransactions(response.transactions || []);

    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showNotification('Failed to load dashboard data', 'error');
    }
}

function renderRecentTransactions(transactions) {
    const container = document.getElementById('recent-transactions');

    if (transactions.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No transactions yet</p>';
        return;
    }

    container.innerHTML = transactions.map(t => `
        <div class="transaction-item">
            <div class="transaction-icon">${getCategoryIcon(t.category)}</div>
            <div class="transaction-details">
                <div class="transaction-merchant">${escapeHtml(t.commerce_name || 'Unknown')}</div>
                <div class="transaction-meta">
                    ${formatDate(t.date)} • ${t.category?.name || 'Uncategorized'} • ${t.card?.name || 'No card'}
                </div>
            </div>
            <div class="transaction-amount">
                <div class="transaction-amount-value money-value ${t.transaction_type === 'purchase' ? 'negative' : 'positive'}">
                    ${formatCurrency(t.amount, t.currency)}
                </div>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// Cards View
// ============================================================================

async function loadCards() {
    try {
        const cards = await API.Cards.getAll();
        allCards = cards;
        renderCards(cards);
    } catch (error) {
        console.error('Failed to load cards:', error);
        showNotification('Failed to load cards', 'error');
    }
}

function renderCards(cards) {
    const container = document.getElementById('cards-grid');

    if (cards.length === 0) {
        container.innerHTML = `
            <div class="cards-empty">
                <div class="cards-empty-icon">💳</div>
                <div class="cards-empty-text">No cards yet</div>
                <button class="btn btn-primary" onclick="showAddCardModal()">Add Your First Card</button>
            </div>
        `;
        return;
    }

    container.innerHTML = cards.map(card => {
        const cardGradient = getCardGradient(card.color);
        const currencies = [];
        if (card.supports_crc) currencies.push('CRC');
        if (card.supports_usd) currencies.push('USD');

        return `
            <div class="credit-card" style="background: ${cardGradient};" onclick="editCard(${card.id})">
                <div class="card-actions">
                    ${card.cutoff_day ? `<button class="card-action-btn" onclick="event.stopPropagation(); showBillingCycles(${card.id})" title="Billing Cycles">📅</button>` : ''}
                    <button class="card-action-btn" onclick="event.stopPropagation(); editCard(${card.id})" title="Edit">
                        ✏️
                    </button>
                    <button class="card-action-btn" onclick="event.stopPropagation(); deleteCard(${card.id})" title="Delete">
                        🗑️
                    </button>
                </div>
                <div class="card-header">
                    <div class="card-type">${escapeHtml(card.card_type || 'credit')}</div>
                    <div class="card-bank">${escapeHtml(card.bank || '')}</div>
                </div>
                <div class="card-number-section">
                    <div class="card-number">${maskCardNumber(card.last_four)}</div>
                </div>
                <div class="card-footer">
                    <div class="card-name">${escapeHtml(card.name)}</div>
                    <div class="card-meta">
                        ${card.cutoff_day ? `<div class="card-due">Cuts on the ${card.cutoff_day}${ordinalSuffix(card.cutoff_day)}</div>` : ''}
                        <div class="card-currencies">
                            ${currencies.map(c => `<span class="currency-badge">${c}</span>`).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================================
// Transactions View
// ============================================================================

async function loadTransactions(filters = {}, page = 0) {
    try {
        currentFilters = filters;
        currentPage = page;
        const response = await API.Transactions.getAll({
            ...filters,
            skip: page * TRANSACTIONS_PAGE_SIZE,
            limit: TRANSACTIONS_PAGE_SIZE,
        });
        renderTransactionsTable(response.transactions || []);
        renderTransactionPagination(response.total || 0, page);
        renderTransactionTotals(response.totals_by_currency || {});
    } catch (error) {
        console.error('Failed to load transactions:', error);
        showNotification('Failed to load transactions', 'error');
    }
}

function renderTransactionTotals(totalsByCurrency) {
    const container = document.getElementById('transaction-totals');
    const currencies = Object.keys(totalsByCurrency);

    if (currencies.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = currencies.map(currency => {
        const { total, count } = totalsByCurrency[currency];
        return `<span class="transaction-totals-item"><strong class="money-value">${formatCurrency(total, currency)}</strong> across ${count} transaction${count === 1 ? '' : 's'} (${currency})</span>`;
    }).join('');
}

function renderTransactionPagination(total, page) {
    const container = document.getElementById('transaction-pagination');
    const pageCount = Math.max(1, Math.ceil(total / TRANSACTIONS_PAGE_SIZE));
    const start = total === 0 ? 0 : page * TRANSACTIONS_PAGE_SIZE + 1;
    const end = Math.min(total, (page + 1) * TRANSACTIONS_PAGE_SIZE);

    container.innerHTML = `
        <span class="page-info">Showing ${start}-${end} of ${total}</span>
        <button ${page <= 0 ? 'disabled' : ''} onclick="loadTransactions(currentFilters, ${page - 1})">Previous</button>
        <span class="page-info">Page ${page + 1} of ${pageCount}</span>
        <button ${page >= pageCount - 1 ? 'disabled' : ''} onclick="loadTransactions(currentFilters, ${page + 1})">Next</button>
    `;
}

function renderTransactionsTable(transactions) {
    const container = document.getElementById('transactions-table');

    if (transactions.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No transactions found</p>';
        return;
    }

    container.innerHTML = `
        <div class="transaction-table-row header">
            <div>Date</div>
            <div>Merchant</div>
            <div>Category</div>
            <div>Card</div>
            <div>Amount</div>
            <div>Type</div>
            <div>Actions</div>
        </div>
        ${transactions.map(t => `
            <div class="transaction-table-row">
                <div class="transaction-date">${formatDate(t.date)}</div>
                <div>${escapeHtml(t.commerce_name || 'Unknown')}</div>
                <div>
                    <select class="transaction-category-select"
                            onchange="updateTransactionCategory(${t.id}, this.value)">
                        <option value="" ${!t.category_id ? 'selected' : ''}>Uncategorized</option>
                        ${allCategories.map(c =>
                            `<option value="${c.id}" ${c.id === t.category_id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`
                        ).join('')}
                    </select>
                </div>
                <div>
                    <select class="transaction-card-select"
                            onchange="updateTransactionCard(${t.id}, this.value)">
                        <option value="" ${!t.card_id ? 'selected' : ''}>No card</option>
                        ${allCards.map(c =>
                            `<option value="${c.id}" ${c.id === t.card_id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="money-value ${t.transaction_type === 'purchase' ? 'negative' : 'positive'}">
                    ${formatCurrency(t.amount, t.currency)}
                </div>
                <div>
                    <span class="badge ${getTransactionTypeBadge(t.transaction_type)}">
                        ${escapeHtml(t.transaction_type)}
                    </span>
                </div>
                <div class="transaction-actions">
                    ${!t.installment_plan_id ? `
                        <button class="icon-btn" onclick="splitTransactionIntoInstallments(${t.id})" title="Split into installments (Tasa Cero)">
                            📆
                        </button>
                    ` : ''}
                    <button class="icon-btn" onclick="deleteTransaction(${t.id})" title="Delete">
                        🗑️
                    </button>
                </div>
            </div>
        `).join('')}
    `;
}

async function updateTransactionCategory(transactionId, categoryId) {
    try {
        await API.Transactions.update(transactionId, {
            category_id: categoryId || null
        });
        showNotification('Category updated', 'success');
    } catch (error) {
        console.error('Failed to update category:', error);
        showNotification('Failed to update category', 'error');
    }
}

async function updateTransactionCard(transactionId, cardId) {
    try {
        await API.Transactions.update(transactionId, {
            card_id: cardId || null
        });
        showNotification('Card updated', 'success');
    } catch (error) {
        console.error('Failed to update card:', error);
        showNotification('Failed to update card', 'error');
    }
}

async function deleteTransaction(id) {
    if (!confirm('Are you sure you want to delete this transaction?')) return;

    try {
        await API.Transactions.delete(id);
        showNotification('Transaction deleted', 'success');
        await loadTransactions(currentFilters, currentPage);
    } catch (error) {
        console.error('Failed to delete transaction:', error);
        showNotification('Failed to delete transaction', 'error');
    }
}

function showFilters() {
    const panel = document.getElementById('transaction-filters');
    panel.style.display = panel.style.display === 'none' ? 'grid' : 'none';
}

function populateTransactionFilterOptions() {
    const categorySelect = document.getElementById('filter-category');
    const previousCategory = categorySelect.value;
    categorySelect.innerHTML = '<option value="">All</option>' +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    categorySelect.value = previousCategory;

    const cardSelect = document.getElementById('filter-card');
    const previousCard = cardSelect.value;
    cardSelect.innerHTML = '<option value="">All</option>' +
        allCards.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    cardSelect.value = previousCard;
}

function applyFilters() {
    const filters = {
        start_date: document.getElementById('filter-start-date').value,
        end_date: document.getElementById('filter-end-date').value,
        search: document.getElementById('filter-search').value,
        currency: document.getElementById('filter-currency').value,
        category_ids: document.getElementById('filter-category').value,
        card_ids: document.getElementById('filter-card').value,
    };

    loadTransactions(filters, 0);
}

function clearFilters() {
    document.getElementById('filter-start-date').value = '';
    document.getElementById('filter-end-date').value = '';
    document.getElementById('filter-search').value = '';
    document.getElementById('filter-currency').value = '';
    document.getElementById('filter-category').value = '';
    document.getElementById('filter-card').value = '';
    loadTransactions({}, 0);
}

// ============================================================================
// Analytics View
// ============================================================================

let currentAnalyticsFilters = {};
let cachedOldestTransactionDate = null;

function renderChart(containerId, options) {
    // Charts don't replace themselves on repeat renders by default, so
    // without clearing the container first, switching tabs/filters stacks
    // a new chart on top of the old one every time.
    const el = document.querySelector(containerId);
    el.innerHTML = '';

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const themedOptions = {
        ...options,
        theme: { mode: isDark ? 'dark' : 'light', ...(options.theme || {}) },
        chart: { background: 'transparent', ...(options.chart || {}) },
    };

    const chart = new ApexCharts(el, themedOptions);
    chart.render();
}

async function loadAnalytics(filters = {}) {
    try {
        currentAnalyticsFilters = filters;
        const { start_date, end_date } = filters;

        // CRC and USD are fetched and rendered as separate series/charts
        // everywhere - summing them together isn't meaningful (different
        // currencies), so no single-currency toggle is needed.
        const [
            dailyCrc, dailyUsd,
            monthlyData,
            categoryCrc, categoryUsd,
            merchantsCrc, merchantsUsd,
            cardData,
        ] = await Promise.all([
            API.Analytics.getDailySpending({ currency: 'CRC', start_date, end_date }),
            API.Analytics.getDailySpending({ currency: 'USD', start_date, end_date }),
            API.Analytics.getMonthlyTrends(6),
            API.Analytics.getSpendingByCategory({ currency: 'CRC', start_date, end_date }),
            API.Analytics.getSpendingByCategory({ currency: 'USD', start_date, end_date }),
            API.Analytics.getTopMerchants({ currency: 'CRC', start_date, end_date, limit: 10 }),
            API.Analytics.getTopMerchants({ currency: 'USD', start_date, end_date, limit: 10 }),
            API.Analytics.getCardUtilization(),
        ]);

        renderDailySpendingChart(dailyCrc, dailyUsd);
        renderMonthlyTrendsChart(monthlyData);
        renderCategoryPieChart(categoryCrc, '#chart-category-pie-crc', 'CRC');
        renderCategoryPieChart(categoryUsd, '#chart-category-pie-usd', 'USD');
        renderTopMerchantsChart(merchantsCrc, '#chart-top-merchants-crc', 'CRC');
        renderTopMerchantsChart(merchantsUsd, '#chart-top-merchants-usd', 'USD');
        renderCardUtilizationChart(cardData);
    } catch (error) {
        console.error('Failed to load analytics:', error);
        showNotification('Failed to load analytics', 'error');
    }
}

function applyAnalyticsFilters() {
    loadAnalytics({
        start_date: document.getElementById('analytics-start-date').value,
        end_date: document.getElementById('analytics-end-date').value,
    });
}

function clearAnalyticsFilters() {
    document.getElementById('analytics-start-date').value = '';
    document.getElementById('analytics-end-date').value = '';
    loadAnalytics({});
}

async function setAnalyticsPreset(preset) {
    const fmt = (d) => d.toISOString().split('T')[0];
    const today = new Date();
    let start;
    const end = fmt(today);

    if (preset === 'month') {
        start = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
    } else if (preset === '30d') {
        const d = new Date(today);
        d.setDate(d.getDate() - 29);
        start = fmt(d);
    } else if (preset === '3m') {
        const d = new Date(today);
        d.setMonth(d.getMonth() - 3);
        start = fmt(d);
    } else if (preset === 'all') {
        if (!cachedOldestTransactionDate) {
            try {
                const summary = await API.Analytics.getDashboardSummary();
                cachedOldestTransactionDate = summary.oldest_transaction_date || end;
            } catch (error) {
                console.error('Failed to load oldest transaction date:', error);
                cachedOldestTransactionDate = end;
            }
        }
        start = cachedOldestTransactionDate;
    }

    document.getElementById('analytics-start-date').value = start;
    document.getElementById('analytics-end-date').value = end;
    loadAnalytics({ start_date: start, end_date: end });
}

function renderCategoryPieChart(data, containerId, currency) {
    if (data.length === 0) {
        document.querySelector(containerId).innerHTML = `<p class="empty-state-text">No ${currency} spending in this range</p>`;
        return;
    }

    renderChart(containerId, {
        series: data.map(d => parseFloat(d.total_amount)),
        chart: {
            type: 'donut',
            height: 320
        },
        labels: data.map(d => d.category_name),
        colors: data.map(d => d.category_color || '#6B7280'),
        legend: {
            position: 'bottom'
        },
        responsive: [{
            breakpoint: 480,
            options: {
                chart: {
                    height: 280
                },
                legend: {
                    position: 'bottom'
                }
            }
        }]
    });
}

function renderDailySpendingChart(dailyCrc, dailyUsd) {
    renderChart("#chart-daily-spending", {
        series: [
            { name: 'CRC', data: dailyCrc.map(d => parseFloat(d.total)) },
            { name: 'USD', data: dailyUsd.map(d => parseFloat(d.total)) },
        ],
        chart: {
            type: 'area',
            height: 350
        },
        xaxis: {
            categories: dailyCrc.map(d => d.date),
            labels: { rotate: -45 }
        },
        yaxis: [
            { title: { text: 'CRC' }, labels: { formatter: (v) => v.toLocaleString() } },
            { opposite: true, title: { text: 'USD' }, labels: { formatter: (v) => v.toLocaleString() } },
        ],
        stroke: {
            curve: 'smooth'
        },
        colors: ['#4F46E5', '#10B981']
    });
}

function renderMonthlyTrendsChart(data) {
    renderChart("#chart-monthly-trends", {
        series: [{
            name: 'CRC',
            data: data.map(d => parseFloat(d.total_crc))
        }, {
            name: 'USD',
            data: data.map(d => parseFloat(d.total_usd))
        }],
        chart: {
            type: 'line',
            height: 350
        },
        xaxis: {
            categories: data.map(d => d.month)
        },
        yaxis: [
            { title: { text: 'CRC' } },
            { opposite: true, title: { text: 'USD' } },
        ],
        stroke: {
            curve: 'smooth'
        },
        colors: ['#4F46E5', '#10B981']
    });
}

function renderTopMerchantsChart(data, containerId, currency) {
    if (data.length === 0) {
        document.querySelector(containerId).innerHTML = `<p class="empty-state-text">No ${currency} spending in this range</p>`;
        return;
    }

    renderChart(containerId, {
        series: [{
            name: `Spent (${currency})`,
            data: data.map(d => parseFloat(d.total_amount))
        }],
        chart: {
            type: 'bar',
            height: 320
        },
        plotOptions: {
            bar: {
                horizontal: true
            }
        },
        xaxis: {
            categories: data.map(d => d.commerce_name)
        },
        colors: ['#4F46E5']
    });
}

function renderCardUtilizationChart(data) {
    renderChart("#chart-card-utilization", {
        series: [
            { name: 'Spent (CRC)', data: data.map(d => parseFloat(d.spent_crc)) },
            { name: 'Spent (USD)', data: data.map(d => parseFloat(d.spent_usd)) }
        ],
        chart: {
            type: 'bar',
            height: 350
        },
        plotOptions: {
            bar: {
                horizontal: false
            }
        },
        dataLabels: {
            enabled: false
        },
        xaxis: {
            categories: data.map(d => d.card_name),
            labels: {
                rotate: -45,
                trim: false
            }
        },
        yaxis: {
            labels: {
                formatter: (val) => val.toLocaleString()
            }
        },
        colors: ['#4F46E5', '#10B981']
    });
}

// ============================================================================
// Categories View
// ============================================================================

async function loadCategories() {
    try {
        const categories = await API.Categories.getAll();
        allCategories = categories;
        renderCategories(categories);
    } catch (error) {
        console.error('Failed to load categories:', error);
        showNotification('Failed to load categories', 'error');
    }
}

function renderCategories(categories) {
    const container = document.getElementById('categories-list');

    if (categories.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No categories yet</p>';
        return;
    }

    container.innerHTML = categories.map(cat => `
        <div class="category-item">
            <div class="category-info">
                <div class="category-color-dot" style="background-color: ${cat.color}"></div>
                <div class="category-icon">${cat.icon}</div>
                <div class="category-name">${escapeHtml(cat.name)}</div>
            </div>
            <div class="category-actions">
                <button class="icon-btn" onclick="editCategory(${cat.id})" title="Edit">✏️</button>
                <button class="icon-btn" onclick="deleteCategory(${cat.id})" title="Delete">🗑️</button>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// Settings View
// ============================================================================

async function loadSettings() {
    try {
        const [emailSources, syncStatus] = await Promise.all([
            API.EmailSources.getAll(),
            API.Sync.getStatus().catch(() => ({ last_sync: null })),
        ]);

        renderEmailSources(emailSources);
        renderSyncStatus(syncStatus);
    } catch (error) {
        console.error('Failed to load settings:', error);
        showNotification('Failed to load settings', 'error');
    }
}

function renderEmailSources(sources) {
    const container = document.getElementById('email-sources-list');

    if (sources.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No email sources configured</p>';
        return;
    }

    container.innerHTML = sources.map(source => `
        <div class="email-source-item">
            <div class="email-source-name">${escapeHtml(source.name)}</div>
            <div class="email-source-email">${escapeHtml(source.sender_email)}</div>
        </div>
    `).join('');
}

function renderSyncStatus(status) {
    const lastSync = status.last_sync ? formatDate(status.last_sync, true) : 'Never';
    document.getElementById('last-sync-time').textContent = `Last sync: ${lastSync}`;
}

async function triggerSync() {
    try {
        showNotification('Sync started...', 'info');
        const result = await API.Sync.triggerSync();
        showNotification(`Sync completed: ${result.transactions_found} transactions found`, 'success');

        // Reload current view
        await showView(currentView);
    } catch (error) {
        console.error('Sync failed:', error);
        showNotification('Sync failed: ' + error.message, 'error');
    }
}

// ============================================================================
// Modal Management
// ============================================================================

function closeModal() {
    document.getElementById('modal-overlay').style.display = 'none';
    document.getElementById('modal-card').style.display = 'none';
    document.getElementById('modal-category').style.display = 'none';
    document.getElementById('modal-email-source').style.display = 'none';
    document.getElementById('modal-billing-cycles').style.display = 'none';
    document.getElementById('modal-installment-plan').style.display = 'none';
    currentCard = null;
    currentCategory = null;
    splitSourceTransaction = null;
}

function showAddCardModal() {
    currentCard = null;
    document.getElementById('card-modal-title').textContent = 'Add Card';
    document.getElementById('card-form').reset();
    document.getElementById('card-id').value = '';
    document.getElementById('card-color').value = '#4F46E5';

    // Populate category dropdown
    populateCardCategoryDropdown();

    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-card').style.display = 'block';
}

function populateCardCategoryDropdown() {
    const select = document.getElementById('card-default-category');
    select.innerHTML = '<option value="">None</option>';

    allCategories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = `${cat.icon} ${cat.name}`;
        select.appendChild(option);
    });
}

async function editCard(id) {
    try {
        const card = await API.Cards.getById(id);
        currentCard = card;

        document.getElementById('card-modal-title').textContent = 'Edit Card';
        document.getElementById('card-id').value = card.id;
        document.getElementById('card-name').value = card.name;
        document.getElementById('card-last-four').value = card.last_four || '';
        document.getElementById('card-bank').value = card.bank || '';
        document.getElementById('card-type').value = card.card_type || 'credit';
        document.getElementById('card-color').value = card.color || '#4F46E5';
        document.getElementById('card-supports-crc').checked = card.supports_crc;
        document.getElementById('card-supports-usd').checked = card.supports_usd;
        document.getElementById('card-cutoff-day').value = card.cutoff_day || '';

        // Populate category dropdown and set value
        populateCardCategoryDropdown();
        document.getElementById('card-default-category').value = card.default_category_id || '';

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-card').style.display = 'block';
    } catch (error) {
        console.error('Failed to load card:', error);
        showNotification('Failed to load card', 'error');
    }
}

async function saveCard(event) {
    event.preventDefault();

    const defaultCategoryValue = document.getElementById('card-default-category').value;

    const cutoffDayValue = document.getElementById('card-cutoff-day').value;

    const cardData = {
        name: document.getElementById('card-name').value,
        last_four: document.getElementById('card-last-four').value || null,
        bank: document.getElementById('card-bank').value || null,
        card_type: document.getElementById('card-type').value,
        color: document.getElementById('card-color').value,
        default_category_id: defaultCategoryValue ? parseInt(defaultCategoryValue) : null,
        supports_crc: document.getElementById('card-supports-crc').checked,
        supports_usd: document.getElementById('card-supports-usd').checked,
        cutoff_day: cutoffDayValue ? parseInt(cutoffDayValue) : null,
    };

    try {
        const cardId = document.getElementById('card-id').value;

        if (cardId) {
            await API.Cards.update(parseInt(cardId), cardData);
            showNotification('Card updated', 'success');
        } else {
            await API.Cards.create(cardData);
            showNotification('Card created', 'success');
        }

        closeModal();
        await loadCards();
    } catch (error) {
        console.error('Failed to save card:', error);
        showNotification('Failed to save card', 'error');
    }
}

async function deleteCard(id) {
    if (!confirm('Are you sure you want to delete this card?')) return;

    try {
        await API.Cards.delete(id);
        showNotification('Card deleted', 'success');
        await loadCards();
    } catch (error) {
        console.error('Failed to delete card:', error);
        showNotification('Failed to delete card', 'error');
    }
}

// ============================================================================
// Billing Cycles
// ============================================================================

async function showBillingCycles(cardId) {
    try {
        const card = allCards.find(c => c.id === cardId) || await API.Cards.getById(cardId);
        const cycles = await API.Cards.getBillingCycles(cardId);

        document.getElementById('billing-cycles-title').textContent = `${card.name} - Billing Cycles`;
        renderBillingCycles(cycles);

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-billing-cycles').style.display = 'block';
    } catch (error) {
        console.error('Failed to load billing cycles:', error);
        showNotification('Failed to load billing cycles', 'error');
    }
}

function renderBillingCycles(cycles) {
    const container = document.getElementById('billing-cycles-list');

    if (cycles.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No cycles yet</p>';
        return;
    }

    container.innerHTML = cycles.map(c => `
        <div class="billing-cycle-item ${c.is_current ? 'current' : ''}">
            <div class="billing-cycle-dates">
                <strong>${formatDate(c.cycle_start)} - ${formatDate(c.cycle_end)}</strong>
                ${c.is_current ? '<span class="badge badge-primary">Current</span>' : ''}
            </div>
            <div class="billing-cycle-due">Due ${formatDate(c.due_date)}</div>
            <div class="billing-cycle-totals">
                ${parseFloat(c.total_crc) > 0 ? `<span>${formatCurrency(c.total_crc, 'CRC')}</span>` : ''}
                ${parseFloat(c.total_usd) > 0 ? `<span>${formatCurrency(c.total_usd, 'USD')}</span>` : ''}
                <span class="billing-cycle-count">${c.transaction_count} txn${c.transaction_count === 1 ? '' : 's'}</span>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// Installment Plans ("tasa cero")
// ============================================================================

let splitSourceTransaction = null;

function showInstallmentPlanModal(prefill = null) {
    splitSourceTransaction = prefill;

    document.getElementById('installment-plan-form').reset();
    document.getElementById('plan-charge-day').value = 18;
    document.getElementById('plan-num-installments').value = 12;
    document.getElementById('plan-starting-installment').value = 1;

    const cardSelect = document.getElementById('plan-card');
    cardSelect.innerHTML = allCards.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');

    const categorySelect = document.getElementById('plan-category');
    categorySelect.innerHTML = '<option value="">Uncategorized</option>' +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');

    const modalTitle = document.querySelector('#modal-installment-plan .modal-header h3');
    const submitBtn = document.querySelector('#installment-plan-form button[type="submit"]');

    if (prefill) {
        modalTitle.textContent = 'Split Into Installments';
        submitBtn.textContent = 'Split Transaction';
        document.getElementById('plan-description').value = prefill.commerce_name || '';
        document.getElementById('plan-total-amount').value = prefill.amount;
        document.getElementById('plan-currency').value = prefill.currency;
        document.getElementById('plan-first-month').value = prefill.date.slice(0, 7);
        if (prefill.card_id) cardSelect.value = prefill.card_id;
        if (prefill.category_id) categorySelect.value = prefill.category_id;
    } else {
        modalTitle.textContent = 'Tasa Cero (Installment Plan)';
        submitBtn.textContent = 'Create Plan';
        const now = new Date();
        document.getElementById('plan-first-month').value =
            `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    }

    loadInstallmentPlans();

    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-installment-plan').style.display = 'block';
}

async function splitTransactionIntoInstallments(transactionId) {
    try {
        const transaction = await API.Transactions.getById(transactionId);
        showInstallmentPlanModal(transaction);
    } catch (error) {
        console.error('Failed to load transaction:', error);
        showNotification('Failed to load transaction', 'error');
    }
}

async function loadInstallmentPlans() {
    try {
        const plans = await API.InstallmentPlans.getAll();
        renderInstallmentPlansList(plans);
    } catch (error) {
        console.error('Failed to load installment plans:', error);
    }
}

function renderInstallmentPlansList(plans) {
    const container = document.getElementById('installment-plans-list');

    if (plans.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No installment plans yet</p>';
        return;
    }

    container.innerHTML = plans.map(p => {
        const card = allCards.find(c => c.id === p.card_id);
        return `
            <div class="plan-item">
                <div class="plan-info">
                    <strong>${escapeHtml(p.description)}</strong>
                    <span class="plan-meta">
                        ${formatCurrency(p.total_amount, p.currency)} over ${p.num_installments} months
                        (${p.installments_paid}/${p.num_installments} paid) - ${escapeHtml(card?.name || 'Unknown card')}
                    </span>
                </div>
                <button type="button" class="icon-btn" onclick="deleteInstallmentPlan(${p.id})" title="Delete plan and its charges">🗑️</button>
            </div>
        `;
    }).join('');
}

async function saveInstallmentPlan(event) {
    event.preventDefault();

    const planData = {
        description: document.getElementById('plan-description').value,
        total_amount: parseFloat(document.getElementById('plan-total-amount').value),
        currency: document.getElementById('plan-currency').value,
        num_installments: parseInt(document.getElementById('plan-num-installments').value),
        starting_installment_number: parseInt(document.getElementById('plan-starting-installment').value),
        charge_day: parseInt(document.getElementById('plan-charge-day').value),
        first_charge_month: document.getElementById('plan-first-month').value,
        card_id: parseInt(document.getElementById('plan-card').value),
        category_id: document.getElementById('plan-category').value
            ? parseInt(document.getElementById('plan-category').value) : null,
    };

    try {
        await API.InstallmentPlans.create(planData);

        if (splitSourceTransaction) {
            // Replace the single full-amount purchase with the installments.
            await API.Transactions.delete(splitSourceTransaction.id);
            splitSourceTransaction = null;
            showNotification('Transaction split into installments', 'success');
        } else {
            showNotification('Installment plan created', 'success');
        }

        document.getElementById('installment-plan-form').reset();
        await loadInstallmentPlans();
        if (currentView === 'transactions') {
            await loadTransactions(currentFilters, currentPage);
        }
    } catch (error) {
        console.error('Failed to create installment plan:', error);
        showNotification('Failed to create installment plan', 'error');
    }
}

async function deleteInstallmentPlan(id) {
    if (!confirm('Delete this plan and all of its generated charges (past and future)?')) return;

    try {
        await API.InstallmentPlans.delete(id);
        showNotification('Installment plan deleted', 'success');
        await loadInstallmentPlans();
        if (currentView === 'transactions') {
            await loadTransactions(currentFilters, currentPage);
        }
    } catch (error) {
        console.error('Failed to delete installment plan:', error);
        showNotification('Failed to delete installment plan', 'error');
    }
}

function showAddCategoryModal() {
    currentCategory = null;
    document.getElementById('category-modal-title').textContent = 'Add Category';
    document.getElementById('category-form').reset();
    document.getElementById('category-id').value = '';
    document.getElementById('category-color').value = '#6B7280';
    document.getElementById('category-icon').value = '📁';
    document.getElementById('category-rules-section').hidden = true;
    document.getElementById('category-rules-list').innerHTML = '';
    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-category').style.display = 'block';
}

async function editCategory(id) {
    try {
        const category = await API.Categories.getById(id);
        currentCategory = category;

        document.getElementById('category-modal-title').textContent = 'Edit Category';
        document.getElementById('category-id').value = category.id;
        document.getElementById('category-name').value = category.name;
        document.getElementById('category-type').value = category.category_type || 'expense';
        document.getElementById('category-icon').value = category.icon || '📁';
        document.getElementById('category-color').value = category.color || '#6B7280';

        document.getElementById('category-rules-section').hidden = false;
        document.getElementById('new-rule-value').value = '';
        await loadCategoryRules(category.id);

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-category').style.display = 'block';
    } catch (error) {
        console.error('Failed to load category:', error);
        showNotification('Failed to load category', 'error');
    }
}

async function loadCategoryRules(categoryId) {
    try {
        const rules = await API.CategorizationRules.getAll(categoryId);
        renderCategoryRules(rules);
    } catch (error) {
        console.error('Failed to load rules:', error);
        showNotification('Failed to load rules', 'error');
    }
}

const RULE_MATCH_LABELS = {
    starts_with: 'Starts with',
    contains: 'Contains',
    ends_with: 'Ends with',
    exact: 'Exactly',
    regex: 'Matches regex',
};

function renderCategoryRules(rules) {
    const container = document.getElementById('category-rules-list');

    if (rules.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No rules yet - transactions won\'t be auto-categorized here.</p>';
        return;
    }

    container.innerHTML = rules.map(r => `
        <div class="rule-item">
            <span class="rule-text">${RULE_MATCH_LABELS[r.match_type] || r.match_type} "${escapeHtml(r.value)}"</span>
            <button type="button" class="icon-btn" onclick="deleteCategorizationRule(${r.id})" title="Delete rule">🗑️</button>
        </div>
    `).join('');
}

async function addCategorizationRule() {
    const matchType = document.getElementById('new-rule-match-type').value;
    const value = document.getElementById('new-rule-value').value.trim();

    if (!value) {
        showNotification('Enter text for the rule to match', 'error');
        return;
    }
    if (!currentCategory) return;

    try {
        await API.CategorizationRules.create({
            match_type: matchType,
            value,
            category_id: currentCategory.id,
        });
        document.getElementById('new-rule-value').value = '';
        await loadCategoryRules(currentCategory.id);
        showNotification('Rule added', 'success');
    } catch (error) {
        console.error('Failed to add rule:', error);
        showNotification('Failed to add rule', 'error');
    }
}

async function deleteCategorizationRule(ruleId) {
    if (!confirm('Delete this rule?')) return;

    try {
        await API.CategorizationRules.delete(ruleId);
        await loadCategoryRules(currentCategory.id);
        showNotification('Rule deleted', 'success');
    } catch (error) {
        console.error('Failed to delete rule:', error);
        showNotification('Failed to delete rule', 'error');
    }
}

async function saveCategory(event) {
    event.preventDefault();

    const categoryData = {
        name: document.getElementById('category-name').value,
        category_type: document.getElementById('category-type').value,
        icon: document.getElementById('category-icon').value || '📁',
        color: document.getElementById('category-color').value,
    };

    try {
        const categoryId = document.getElementById('category-id').value;

        if (categoryId) {
            await API.Categories.update(parseInt(categoryId), categoryData);
            showNotification('Category updated', 'success');
        } else {
            await API.Categories.create(categoryData);
            showNotification('Category created', 'success');
        }

        closeModal();
        await loadCategories();
        await loadInitialData(); // Reload for dropdowns
    } catch (error) {
        console.error('Failed to save category:', error);
        showNotification('Failed to save category', 'error');
    }
}

async function deleteCategory(id) {
    if (!confirm('Are you sure you want to delete this category?')) return;

    try {
        await API.Categories.delete(id);
        showNotification('Category deleted', 'success');
        await loadCategories();
        await loadInitialData();
    } catch (error) {
        console.error('Failed to delete category:', error);
        showNotification('Failed to delete category', 'error');
    }
}

function showAddEmailSourceModal() {
    document.getElementById('email-source-form').reset();
    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-email-source').style.display = 'block';
}

async function saveEmailSource(event) {
    event.preventDefault();

    const sourceData = {
        name: document.getElementById('source-name').value,
        sender_email: document.getElementById('source-email').value,
    };

    try {
        await API.EmailSources.create(sourceData);
        showNotification('Email source added', 'success');
        closeModal();
        await loadSettings();
    } catch (error) {
        console.error('Failed to save email source:', error);
        showNotification('Failed to save email source', 'error');
    }
}

// Make functions globally accessible
window.showView = showView;
window.triggerSync = triggerSync;
window.closeModal = closeModal;
window.showAddCardModal = showAddCardModal;
window.editCard = editCard;
window.saveCard = saveCard;
window.deleteCard = deleteCard;
window.showAddCategoryModal = showAddCategoryModal;
window.editCategory = editCategory;
window.saveCategory = saveCategory;
window.deleteCategory = deleteCategory;
window.showAddEmailSourceModal = showAddEmailSourceModal;
window.saveEmailSource = saveEmailSource;
window.updateTransactionCategory = updateTransactionCategory;
window.deleteTransaction = deleteTransaction;
window.showFilters = showFilters;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
