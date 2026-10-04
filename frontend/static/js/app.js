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
    showView(viewFromPath(), { push: false });
}

// ============================================================================
// URL routing - each view lives at its own path (/budgets, /analytics, ...)
// so a reload stays put. Keep VIEWS in sync with SPA_VIEWS in api.py.
// ============================================================================

const VIEWS = ['dashboard', 'budgets', 'transactions', 'analytics', 'forecast', 'categories', 'cards', 'settings'];

function viewFromPath() {
    const name = window.location.pathname.replace(/^\/+|\/+$/g, '');
    return VIEWS.includes(name) ? name : 'dashboard';
}

function pathForView(viewName) {
    return viewName === 'dashboard' ? '/' : `/${viewName}`;
}

window.addEventListener('popstate', () => showView(viewFromPath(), { push: false }));

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
            // Let cmd/ctrl/middle-click open the view in a new tab.
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
            e.preventDefault();
            const view = link.getAttribute('data-view');
            showView(view);
        });
    });
}

async function showView(viewName, { push = true } = {}) {
    if (push && window.location.pathname !== pathForView(viewName)) {
        history.pushState({ view: viewName }, '', pathForView(viewName));
    }

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
        case 'budgets':
            await loadBudgets();
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
        case 'forecast':
            await loadMonthForecast();
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
        const today = formatDateForInput(new Date());
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
// Budgets View
// ============================================================================

let currentBudgetOverview = null;

function getBudgetMonth() {
    const input = document.getElementById('budget-month');
    if (!input.value) {
        input.value = formatDateForInput(new Date()).slice(0, 7);
    }
    return input.value;
}

async function loadBudgets() {
    try {
        const overview = await API.Budgets.getOverview(getBudgetMonth());
        currentBudgetOverview = overview;
        renderBudgetSummary(overview);
        renderIncomeEntries(overview);
        renderBudgetLines(overview);
    } catch (error) {
        console.error('Failed to load budgets:', error);
        document.getElementById('budget-lines').innerHTML =
            '<p class="empty-state-text">Failed to load budgets</p>';
    }
}

function renderBudgetSummary(o) {
    const crc = (v) => `<span class="money-value">${v < 0 ? '-' : ''}${formatCurrency(v, 'CRC')}</span>`;
    const received = parseFloat(o.income_received);
    const base = parseFloat(o.income_base);
    const debt = parseFloat(o.total_debt);
    const spent = parseFloat(o.total_spent) + parseFloat(o.unbudgeted_spent);
    const left = base - spent - debt;

    // Left to spend: income - spent - card debt.
    const leftEl = document.getElementById('budget-left');
    leftEl.textContent = `${left < 0 ? '-' : ''}${formatCurrency(left, 'CRC')}`;
    leftEl.classList.toggle('budget-over', left < 0);
    const incomeLabel = received > 0 && received >= base ? 'Income received' : 'Expected income';
    document.getElementById('budget-equation').innerHTML = `
        <div class="budget-eq-row"><span>${incomeLabel}</span>${crc(base)}</div>
        <div class="budget-eq-row"><span>− Spent so far</span>${crc(spent)}</div>
        ${debt > 0 ? `<div class="budget-eq-row"><span>− Card debt payment</span>${crc(debt)}</div>` : ''}
        <div class="budget-eq-row budget-eq-total"><span>= Left to spend</span>${crc(left)}</div>
    `;

    // Where income goes: locked + other budgets + debt + savings = income.
    const locked = o.lines.filter(l => l.is_protected).reduce((a, l) => a + parseFloat(l.adjusted_amount), 0);
    const flexible = o.lines.filter(l => !l.is_protected).reduce((a, l) => a + parseFloat(l.adjusted_amount), 0);
    const savings = Math.max(parseFloat(o.unbudgeted), 0);
    const lockedNames = o.lines.filter(l => l.is_protected).map(l => l.category_name).join(' & ') || 'Locked budgets';
    const reduction = parseFloat(o.reduction_percentage);
    const parts = [
        { label: `🔒 ${escapeHtml(lockedNames)}`, value: locked, cls: 'plan-locked' },
        { label: 'Other budgets', value: flexible, cls: 'plan-flexible',
          note: reduction > 0 ? `cut ${reduction.toFixed(1)}% for debt` : '' },
        { label: 'Card debt', value: debt, cls: 'plan-debt' },
        { label: 'Savings (not budgeted)', value: savings, cls: 'plan-savings' },
    ].filter(p => p.value > 0);
    const total = Math.max(base, parts.reduce((a, p) => a + p.value, 0)) || 1;

    document.getElementById('budget-plan-bar').innerHTML = parts.map(p =>
        `<span class="${p.cls}" style="width: ${p.value / total * 100}%" title="${p.label}"></span>`
    ).join('');
    document.getElementById('budget-plan-legend').innerHTML = parts.map(p => `
        <div class="budget-legend-row">
            <span class="budget-legend-swatch ${p.cls}"></span>
            <span class="budget-legend-label">${p.label}${p.note ? ` <span class="budget-legend-note">(${p.note})</span>` : ''}</span>
            ${crc(p.value)}
            <span class="budget-legend-pct">${base > 0 ? Math.round(p.value / base * 100) : 0}%</span>
        </div>
    `).join('');

    const shortfall = parseFloat(o.debt_shortfall);
    const unbudgeted = parseFloat(o.unbudgeted);
    document.getElementById('budget-plan-note').innerHTML = shortfall > 0
        ? `<span class="budget-over">Card debt is ${crc(shortfall)} more than everything that isn't locked - lower the payment or unlock a budget.</span>`
        : (unbudgeted < 0 ? `<span class="budget-over">Budgets add up to ${crc(-unbudgeted)} more than your income.</span>` : '');

    renderBudgetDebt(o);
}

function renderBudgetDebt(o) {
    const container = document.getElementById('budget-debt-list');
    if (o.debt_lines.length === 0) {
        container.innerHTML = '<p class="field-hint">No card debt this month. To plan paying one down, open Cards and click 💰 on the card.</p>';
        return;
    }

    const rate = parseFloat(o.settings.usd_to_crc_rate);
    container.innerHTML = o.debt_lines.map(d => {
        const rows = ['CRC', 'USD'].map(currency => {
            const c = currency.toLowerCase();
            const payment = parseFloat(d[`payment_${c}`]);
            if (!(payment > 0)) return '';
            const totalCharges = parseFloat(d[`spend_${c}`]);
            const cuotas = parseFloat(d[`installments_${c}`]);
            const usual = totalCharges - cuotas;
            const charges = Math.min(totalCharges, payment);
            const toDebt = payment - charges;
            const money = (v, cur = currency) => `<span class="money-value">${formatCurrency(v, cur)}</span>`;
            const name = currency === 'CRC' ? 'Colones' : 'Dollars';
            const covers = [];
            if (usual > 0) covers.push(`${money(usual)} for your usual ${currency === 'CRC' ? 'colón' : 'dollar'} purchases on this card (monthly average)`);
            if (cuotas > 0) covers.push(`${money(cuotas)} for this month's Tasa Cero cuotas`);
            let text = `You pay ${money(payment)}`;
            if (charges > 0) {
                text += toDebt > 0
                    ? `. First ${covers.join(' + ')}, so ${money(toDebt)} is left to pay down the old balance`
                    : `, but it only covers ${covers.join(' + ')} - nothing is left to pay down the old balance`;
            } else {
                text += ` - all of it pays down the old balance`;
            }
            if (currency === 'USD' && toDebt > 0) text += ` (${money(toDebt * rate, 'CRC')})`;
            return `<div class="budget-debt-row"><strong>${name}:</strong> ${text}</div>`;
        }).join('');
        return `
            <div class="budget-debt-card">
                <div class="budget-debt-header">
                    <strong>💳 ${escapeHtml(d.card_name)}</strong>
                    <span><span class="budget-debt-amount money-value">${formatCurrency(d.amount, 'CRC')}</span> toward old debt</span>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="showPayoffPlan(${d.card_id})">Edit plan</button>
                </div>
                ${rows}
            </div>
        `;
    }).join('') + '<p class="field-hint">Your usual purchases and cuotas are already counted in your category budgets below, so here only the part of the payment that pays down the old balance counts as debt.</p>';
}

function renderIncomeEntries(o) {
    const [year, month] = o.month.split('-').map(Number);
    document.getElementById('budget-income-caption').textContent =
        `(${new Date(year, month - 1, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' })})`;

    const expectedInput = document.getElementById('budget-expected-income');
    const rateInput = document.getElementById('budget-usd-rate');
    expectedInput.value = o.settings.expected_monthly_income ? parseFloat(o.settings.expected_monthly_income) : '';
    rateInput.value = parseFloat(o.settings.usd_to_crc_rate);

    const container = document.getElementById('income-entries-list');
    if (o.income_entries.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No payments logged this month yet - click "+ Add Payment" when you get paid.</p>';
        return;
    }

    container.innerHTML = o.income_entries.map(e => `
        <div class="plan-item">
            <div class="plan-info">
                <strong>${escapeHtml(e.description || 'Payment')}</strong>
                <span class="plan-meta">
                    ${formatDate(e.date)} -
                    <span class="money-value">${formatCurrency(e.amount, e.currency)}</span>
                    ${e.currency === 'USD' ? `(<span class="money-value">${formatCurrency(e.amount_crc, 'CRC')}</span>)` : ''}
                </span>
            </div>
            <button type="button" class="icon-btn" onclick="deleteIncome(${e.id})" title="Delete payment">🗑️</button>
        </div>
    `).join('');
}

function renderBudgetLines(o) {
    const container = document.getElementById('budget-lines');

    const reduced = parseFloat(o.reduction_percentage) > 0;

    if (o.lines.length === 0) {
        container.innerHTML = '<p class="empty-state-text">No budgets yet - add one below, or click "Reset to Suggested".</p>';
    } else {
        container.innerHTML = `
            <div class="budget-line budget-line-head">
                <span>Category</span>
                <span>% of Income</span>
                <span>Amount (₡)</span>
                <span>Spent</span>
                <span></span>
            </div>
        ` + o.lines.map(l => {
            const amount = parseFloat(l.adjusted_amount);
            const planned = parseFloat(l.amount);
            const spent = parseFloat(l.spent);
            const remaining = parseFloat(l.remaining);
            const ratio = amount > 0 ? spent / amount : (spent > 0 ? 1 : 0);
            const fillClass = ratio > 1 ? 'critical' : (ratio > 0.85 ? 'high' : '');
            const remainingText = remaining >= 0
                ? `<span class="money-value">${formatCurrency(remaining, 'CRC')}</span> left`
                : `<span class="money-value">${formatCurrency(remaining, 'CRC')}</span> over`;
            return `
                <div class="budget-line">
                    <span class="budget-category">
                        <button type="button" class="icon-btn budget-lock ${l.is_protected ? 'locked' : ''}"
                            onclick="toggleBudgetProtected(${l.id}, ${!l.is_protected})"
                            title="${l.is_protected ? 'Protected - never reduced for debt. Click to unlock.' : 'Reduced to make room for debt payments. Click to protect.'}">${l.is_protected ? '🔒' : '🔓'}</button>
                        <span class="category-icon">${escapeHtml(l.category_icon || '')}</span>
                        ${escapeHtml(l.category_name)}
                    </span>
                    <span class="budget-input-wrap">
                        <input type="number" class="input budget-input ${l.anchor === 'percentage' ? 'anchored' : ''}"
                            value="${parseFloat(l.percentage)}" min="0" max="100" step="0.5"
                            title="${l.anchor === 'percentage' ? 'You set this % - the amount follows your income' : 'Calculated from the fixed amount'}"
                            onchange="updateBudget(${l.category_id}, 'percentage', this.value)">
                        <span class="budget-input-suffix">%</span>
                    </span>
                    <span class="budget-amount-wrap">
                        <input type="number" class="input budget-input money-value ${l.anchor === 'amount' ? 'anchored' : ''}"
                            value="${planned}" min="0" step="1000"
                            title="${l.anchor === 'amount' ? 'Fixed amount - stays the same when income changes' : 'Calculated from the %'}"
                            onchange="updateBudget(${l.category_id}, 'amount', this.value)">
                        ${reduced && !l.is_protected
                            ? `<span class="budget-after-debt">→ <span class="money-value">${formatCurrency(amount, 'CRC')}</span> after debt</span>`
                            : ''}
                    </span>
                    <span class="budget-progress">
                        <span class="budget-progress-label">
                            <span class="money-value">${formatCurrency(spent, 'CRC')}</span>
                            <span class="${remaining < 0 ? 'budget-over' : ''}">${remainingText}</span>
                        </span>
                        <span class="budget-bar"><span class="budget-fill ${fillClass}" style="width: ${Math.min(ratio, 1) * 100}%"></span></span>
                    </span>
                    <button type="button" class="icon-btn" onclick="deleteBudget(${l.id})" title="Remove budget">🗑️</button>
                </div>
            `;
        }).join('');
    }

    const budgeted = new Set(o.lines.map(l => l.category_id));
    const available = allCategories.filter(c => c.category_type !== 'income' && !budgeted.has(c.id));
    const select = document.getElementById('budget-add-category');
    select.innerHTML = available.length
        ? available.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')
        : '<option value="">All categories have a budget</option>';
}

async function updateBudget(categoryId, field, rawValue) {
    const value = parseFloat(rawValue);
    if (isNaN(value) || value < 0 || (field === 'percentage' && value > 100)) {
        showNotification(field === 'percentage' ? 'Enter a % between 0 and 100' : 'Enter a positive amount', 'error');
        await loadBudgets();
        return;
    }

    try {
        await API.Budgets.upsert({ category_id: categoryId, [field]: value });
        await loadBudgets();
    } catch (error) {
        console.error('Failed to update budget:', error);
        showNotification(`Failed to update budget: ${error.message}`, 'error');
    }
}

async function toggleBudgetProtected(budgetId, isProtected) {
    try {
        await API.Budgets.setProtected(budgetId, isProtected);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to update budget:', error);
        showNotification('Failed to update budget', 'error');
    }
}

async function addBudgetCategory() {
    const categoryId = parseInt(document.getElementById('budget-add-category').value);
    if (!categoryId) return;

    try {
        await API.Budgets.upsert({ category_id: categoryId, percentage: 0 });
        await loadBudgets();
    } catch (error) {
        console.error('Failed to add budget:', error);
        showNotification(`Failed to add budget: ${error.message}`, 'error');
    }
}

async function deleteBudget(budgetId) {
    try {
        await API.Budgets.delete(budgetId);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to delete budget:', error);
        showNotification('Failed to delete budget', 'error');
    }
}

async function resetBudgetsToSuggested() {
    if (!confirm('Replace all your budgets with the suggested percentages?')) return;

    try {
        await API.Budgets.resetToSuggested();
        showNotification('Budgets reset to suggested', 'success');
        await loadBudgets();
    } catch (error) {
        console.error('Failed to reset budgets:', error);
        showNotification('Failed to reset budgets', 'error');
    }
}

async function saveBudgetSettings() {
    const expected = document.getElementById('budget-expected-income').value;
    const rate = parseFloat(document.getElementById('budget-usd-rate').value);
    if (isNaN(rate) || rate <= 0) {
        showNotification('Enter a valid USD → CRC rate', 'error');
        return;
    }

    try {
        await API.Budgets.updateSettings({
            expected_monthly_income: expected === '' ? null : parseFloat(expected),
            usd_to_crc_rate: rate,
        });
        showNotification('Budget settings saved', 'success');
        await loadBudgets();
    } catch (error) {
        console.error('Failed to save budget settings:', error);
        showNotification(`Failed to save settings: ${error.message}`, 'error');
    }
}

function ordinal(n) {
    const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[n % 100 >= 11 && n % 100 <= 13 ? 0 : n % 10] || 'th';
    return `${n}${suffix}`;
}

function showIncomeModal() {
    document.getElementById('income-form').reset();

    // Default the date into the month being viewed (today if it's the current month).
    const today = formatDateForInput(new Date());
    const month = getBudgetMonth();
    document.getElementById('income-date').value = today.startsWith(month) ? today : `${month}-01`;

    const count = currentBudgetOverview ? currentBudgetOverview.income_entries.length : 0;
    document.getElementById('income-description').value = `${ordinal(count + 1)} payment`;

    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-income').style.display = 'block';
}

async function saveIncome(event) {
    event.preventDefault();

    const data = {
        date: document.getElementById('income-date').value,
        amount: parseFloat(document.getElementById('income-amount').value),
        currency: document.getElementById('income-currency').value,
        description: document.getElementById('income-description').value || null,
    };

    try {
        await API.Income.create(data);
        closeModal();
        showNotification('Payment added', 'success');
        // Jump to the month the payment landed in so it's visible.
        document.getElementById('budget-month').value = data.date.slice(0, 7);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to add payment:', error);
        showNotification(`Failed to add payment: ${error.message}`, 'error');
    }
}

async function deleteIncome(incomeId) {
    if (!confirm('Delete this payment?')) return;

    try {
        await API.Income.delete(incomeId);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to delete payment:', error);
        showNotification('Failed to delete payment', 'error');
    }
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
                    ${card.card_type !== 'debit' ? `<button class="card-action-btn" onclick="event.stopPropagation(); showPayoffPlan(${card.id})" title="Payoff Plan">💰</button>` : ''}
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
// Card Payoff Plan
// ============================================================================

const PAYOFF_MAX_MONTHS = 600;
let currentPayoffCardId = null;
let currentPayoffAvgSpend = { CRC: 0, USD: 0 };
let currentPayoffInstallments = { CRC: [], USD: [] };

async function showPayoffPlan(cardId) {
    try {
        const card = allCards.find(c => c.id === cardId) || await API.Cards.getById(cardId);
        const data = await API.Cards.getPayoffPlan(cardId);
        currentPayoffCardId = cardId;
        currentPayoffAvgSpend = {
            CRC: parseFloat(data.avg_monthly_spend_crc),
            USD: parseFloat(data.avg_monthly_spend_usd),
        };
        currentPayoffInstallments = {
            CRC: data.scheduled_installments_crc.map(parseFloat),
            USD: data.scheduled_installments_usd.map(parseFloat),
        };

        document.getElementById('payoff-modal-title').textContent = `${card.name} - Payoff Plan`;
        document.getElementById('payoff-delete-btn').style.display = data.plan ? '' : 'none';

        const plan = data.plan || {};
        document.getElementById('payoff-as-of').value = plan.balance_as_of || formatDateForInput(new Date());

        for (const currency of ['CRC', 'USD']) {
            const c = currency.toLowerCase();
            const num = (v) => (v === null || v === undefined) ? '' : parseFloat(v);
            document.getElementById(`payoff-balance-${c}`).value = num(plan[`balance_${c}`]) || 0;
            document.getElementById(`payoff-rate-${c}`).value = num(plan[`annual_rate_${c}`]) || 0;
            document.getElementById(`payoff-payment-${c}`).value = num(plan[`monthly_payment_${c}`]) || 0;

            const spendInput = document.getElementById(`payoff-spend-${c}`);
            spendInput.value = num(plan[`monthly_spend_${c}`]);
            spendInput.placeholder = currentPayoffAvgSpend[currency].toFixed(2);
            document.getElementById(`payoff-spend-hint-${c}`).innerHTML =
                `Recent average: <span class="money-value">${formatCurrency(currentPayoffAvgSpend[currency], currency)}</span>/month ` +
                `(last ${data.avg_based_on_days} days, not counting Tasa Cero). Leave blank to use it.` +
                installmentsHint(currentPayoffInstallments[currency], plan.balance_as_of, currency);
        }

        renderPayoffProjection();

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-payoff').style.display = 'block';
    } catch (error) {
        console.error('Failed to load payoff plan:', error);
        showNotification('Failed to load payoff plan', 'error');
    }
}

function readPayoffInputs(currency) {
    const c = currency.toLowerCase();
    const val = (id) => parseFloat(document.getElementById(id).value);
    const spendRaw = document.getElementById(`payoff-spend-${c}`).value;
    return {
        balance: val(`payoff-balance-${c}`) || 0,
        annualRate: val(`payoff-rate-${c}`) || 0,
        payment: val(`payoff-payment-${c}`) || 0,
        spend: spendRaw === '' ? currentPayoffAvgSpend[currency] : (parseFloat(spendRaw) || 0),
        spendIsAverage: spendRaw === '',
        installments: currentPayoffInstallments[currency],
    };
}

function installmentsHint(installments, asOf, currency) {
    const total = installments.reduce((a, b) => a + b, 0);
    if (total <= 0) return '';
    const first = installments.findIndex(v => v > 0);
    return `<br>Plus <span class="money-value">${formatCurrency(total, currency)}</span> of remaining Tasa Cero cuotas ` +
        `(<span class="money-value">${formatCurrency(installments[first], currency)}</span> in ` +
        `${payoffMonthLabel(asOf || formatDateForInput(new Date()), first + 1)}, last one in ` +
        `${payoffMonthLabel(asOf || formatDateForInput(new Date()), installments.length)}).`;
}

/**
 * Month-by-month projection: each month the balance accrues interest, new
 * spending is added, then the payment comes off. Month 1 is the month of
 * the "as of" date (keep in sync with project_payments() in payoff.py).
 * installments[i] = Tasa Cero charges in month i+1, on top of `spend`.
 * "Paid off" = the interest-bearing balance reaches zero; any cuotas after
 * that are 0% and just get paid as they come (payoff.py keeps simulating
 * them, which nets to zero debt for budgets).
 * @returns {{months: number|null, totalInterest: number, schedule: Array}}
 *          months=null if the balance never reaches zero.
 */
function simulatePayoff({ balance, annualRate, payment, spend, installments = [] }) {
    const r = annualRate / 100 / 12;
    const schedule = [];
    let totalInterest = 0;

    for (let month = 1; month <= PAYOFF_MAX_MONTHS; month++) {
        const interest = balance * r;
        totalInterest += interest;
        const charges = spend + (installments[month - 1] || 0);
        const owed = balance + interest + charges;
        const paid = Math.min(payment, owed);
        const prevBalance = balance;
        balance = owed - paid;
        schedule.push({ month, interest, charges, paid, balance });

        const cuotasDone = month >= installments.length;
        if (balance <= 0.005) {
            return { months: month, totalInterest, schedule };
        }
        // Not shrinking with no cuotas left to end - it never will at this payment.
        if (balance >= prevBalance && cuotasDone && month > installments.length) {
            return { months: null, totalInterest, schedule };
        }
    }
    return { months: null, totalInterest, schedule };
}

/** Fixed monthly payment that clears the balance in `n` months, covering
 *  new spending and Tasa Cero cuotas along the way (binary search, since
 *  uneven cuotas rule out a closed-form formula). */
function paymentToClearIn(n, inputs) {
    const cleared = (payment) => {
        const result = simulatePayoff({ ...inputs, payment });
        return result.months !== null && result.months <= n;
    };
    let low = 0;
    let high = inputs.balance + (inputs.spend + Math.max(0, ...(inputs.installments || [0]))) * n * 2 + 1;
    for (let i = 0; i < 60; i++) {
        const mid = (low + high) / 2;
        if (cleared(mid)) high = mid; else low = mid;
    }
    return high;
}

function payoffMonthLabel(asOf, monthsAhead) {
    const d = parseDate(asOf);
    return new Date(d.getFullYear(), d.getMonth() + monthsAhead - 1, 1)
        .toLocaleString('en-US', { month: 'long', year: 'numeric' });
}

function renderPayoffProjection() {
    const asOf = document.getElementById('payoff-as-of').value || formatDateForInput(new Date());

    for (const currency of ['CRC', 'USD']) {
        const c = currency.toLowerCase();
        const container = document.getElementById(`payoff-result-${c}`);
        const inputs = readPayoffInputs(currency);
        const money = (v) => `<span class="money-value">${formatCurrency(v, currency)}</span>`;

        const cuotasLeft = inputs.installments.reduce((a, b) => a + b, 0);
        if (inputs.balance <= 0 && cuotasLeft <= 0) {
            container.innerHTML = '<p class="field-hint">Nothing owed in this currency.</p>';
            continue;
        }

        const firstInterest = inputs.balance * inputs.annualRate / 100 / 12;
        const result = simulatePayoff(inputs);
        let headline;

        if (result.months === null) {
            headline = `
                <div class="payoff-headline payoff-bad">Never paid off at this rate</div>
                <p class="payoff-detail">Each month adds ${money(firstInterest)} interest + ${money(inputs.spend)} new spending${
                    cuotasLeft > 0 ? ` + Tasa Cero cuotas (${money(inputs.installments[0] || 0)} this month)` : ''},
                so you need to pay more than ${money(firstInterest + inputs.spend)}${cuotasLeft > 0 ? ' plus cuotas' : ''} just for the balance to start going down.</p>
            `;
        } else {
            const months = result.months;
            const laterCuotas = inputs.installments.slice(months).reduce((a, b) => a + b, 0);
            headline = `
                <div class="payoff-headline payoff-good">Paid off by ${payoffMonthLabel(asOf, months)}</div>
                ${laterCuotas > 0 ? `<p class="payoff-detail">After that, only 0% Tasa Cero cuotas are left
                    (${money(laterCuotas)} until ${payoffMonthLabel(asOf, inputs.installments.length)}) - no more interest.</p>` : ''}
                <p class="payoff-detail">${months} payment${months === 1 ? '' : 's'} -
                ${money(result.totalInterest)} total interest
                ${inputs.payment > 0 ? `(${Math.round(result.totalInterest / (inputs.balance + result.totalInterest) * 100)}% of what you pay toward the debt)` : ''}.</p>
            `;
        }

        const targets = [6, 12, 24].map(n => `
            <li>${n} months: ${money(paymentToClearIn(n, inputs))}/month</li>
        `).join('');

        const rows = result.schedule.slice(0, 60).map(s => `
            <tr>
                <td>${payoffMonthLabel(asOf, s.month)}</td>
                <td class="money-value">${formatCurrency(s.charges, currency)}</td>
                <td class="money-value">${formatCurrency(s.interest, currency)}</td>
                <td class="money-value">${formatCurrency(s.paid, currency)}</td>
                <td class="money-value">${formatCurrency(Math.max(s.balance, 0), currency)}</td>
            </tr>
        `).join('');

        container.innerHTML = `
            ${headline}
            <p class="payoff-detail">To be debt-free in (keeping ${inputs.spendIsAverage ? 'your average' : 'this'} spending${cuotasLeft > 0 ? ', cuotas included' : ''}):</p>
            <ul class="payoff-targets">${targets}</ul>
            <details class="payoff-schedule">
                <summary>Month-by-month</summary>
                <table>
                    <thead><tr><th>Month</th><th>New Charges</th><th>Interest</th><th>Payment</th><th>Owed After</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </details>
        `;
    }
}

async function savePayoffPlan(event) {
    event.preventDefault();

    const planData = { balance_as_of: document.getElementById('payoff-as-of').value };
    for (const currency of ['CRC', 'USD']) {
        const c = currency.toLowerCase();
        const inputs = readPayoffInputs(currency);
        planData[`balance_${c}`] = inputs.balance;
        planData[`annual_rate_${c}`] = inputs.annualRate;
        planData[`monthly_payment_${c}`] = inputs.payment;
        planData[`monthly_spend_${c}`] = inputs.spendIsAverage ? null : inputs.spend;
    }

    try {
        await API.Cards.savePayoffPlan(currentPayoffCardId, planData);
        closeModal();
        showNotification('Payoff plan saved', 'success');
        if (currentView === 'budgets') await loadBudgets();
    } catch (error) {
        console.error('Failed to save payoff plan:', error);
        showNotification(`Failed to save payoff plan: ${error.message}`, 'error');
    }
}

async function deletePayoffPlan() {
    if (!confirm('Delete this payoff plan?')) return;

    try {
        await API.Cards.deletePayoffPlan(currentPayoffCardId);
        closeModal();
        showNotification('Payoff plan deleted', 'success');
        if (currentView === 'budgets') await loadBudgets();
    } catch (error) {
        console.error('Failed to delete payoff plan:', error);
        showNotification('Failed to delete payoff plan', 'error');
    }
}

// ============================================================================
// Transactions View
// ============================================================================

// "Until today" (default) hides future-dated rows like upcoming Tasa Cero
// cuotas; "All" shows them too.
let showUpcomingTransactions = false;

function setTransactionsScope(showUpcoming) {
    showUpcomingTransactions = showUpcoming;
    document.getElementById('tx-scope-today').classList.toggle('active', !showUpcoming);
    document.getElementById('tx-scope-all').classList.toggle('active', showUpcoming);
    loadTransactions(currentFilters, 0);
}

async function loadTransactions(filters = {}, page = 0) {
    try {
        currentFilters = filters;
        currentPage = page;
        const query = { ...filters };
        if (!showUpcomingTransactions) {
            const today = formatDateForInput(new Date());
            if (!query.end_date || query.end_date > today) query.end_date = today;
        }
        const response = await API.Transactions.getAll({
            ...query,
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
                <div class="transaction-date">${formatDate(t.date)}${
                    t.date > formatDateForInput(new Date()) ? '<span class="badge badge-primary upcoming-badge">Upcoming</span>' : ''}</div>
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

async function loadMonthForecast() {
    try {
        renderMonthForecast(await API.Analytics.getMonthForecast());
    } catch (error) {
        console.error('Failed to load forecast:', error);
        document.getElementById('forecast-lines').innerHTML =
            '<p class="empty-state-text">Failed to load the forecast</p>';
    }
}

function renderMonthForecast(f) {
    // Forecasts are estimates - whole colones, no false precision.
    const crc = (v) => `<span class="money-value">${v < 0 ? '-' : ''}₡${Math.round(Math.abs(v)).toLocaleString('en-US')}</span>`;
    const num = parseFloat;
    const monthLabel = (ym, opts = { month: 'long' }) => {
        const [y, m] = ym.split('-').map(Number);
        return new Date(y, m - 1, 1).toLocaleString('en-US', opts);
    };
    const monthName = monthLabel(f.month);
    const left = num(f.projected_left);
    const debt = num(f.total_debt);

    // Usual-month range, e.g. "Aug–Sep".
    let usual = 'your usual month';
    if (f.history_months > 0) {
        const [y, m] = f.month.split('-').map(Number);
        const last = `${new Date(y, m - 2, 1).getFullYear()}-${String(new Date(y, m - 2, 1).getMonth() + 1).padStart(2, '0')}`;
        const short = { month: 'short' };
        usual = f.history_months === 1
            ? `your usual month (${monthLabel(f.history_start, short)})`
            : `your usual month (${monthLabel(f.history_start, short)}–${monthLabel(last, short)} average)`;
    }

    document.getElementById('forecast-caption').textContent = `(${monthName})`;

    const leftEl = document.getElementById('forecast-left');
    leftEl.innerHTML = left < 0 ? `${crc(-left)} short` : `${crc(left)} left`;
    leftEl.classList.toggle('budget-over', left < 0);
    document.getElementById('forecast-sentence').innerHTML = left < 0
        ? `If the rest of ${monthName} goes like ${f.history_months ? 'your usual month' : 'it has so far'}, you'll spend <strong>${crc(-left)} more than you earn</strong>.`
        : `If the rest of ${monthName} goes like ${f.history_months ? 'your usual month' : 'it has so far'}, you'll end with <strong>${crc(left)} to spare</strong>.`;
    document.getElementById('forecast-equation').innerHTML = `
        <div class="budget-eq-row"><span>Expected income</span>${crc(num(f.income_base))}</div>
        <div class="budget-eq-row"><span>− Likely spending</span>${crc(num(f.projected_spend))}</div>
        ${debt > 0 ? `<div class="budget-eq-row"><span>− Card debt payment</span>${crc(debt)}</div>` : ''}
        <div class="budget-eq-row budget-eq-total"><span>= ${left < 0 ? 'Short' : 'Left'} at month end</span>${crc(left)}</div>
    `;

    // How much to trust it: pace share grows with the month.
    const pacePct = Math.round(num(f.pace_weight) * 100);
    document.getElementById('forecast-confidence').innerHTML = f.history_months > 0 ? `
        <div class="forecast-confidence-text">
            <strong>Day ${f.days_elapsed} of ${f.days_in_month}.</strong>
            This forecast is <strong>${100 - pacePct}% based on ${usual}</strong> and ${pacePct}% on how you've spent so far in ${monthName}.
            ${pacePct < 40 ? `It's early, so treat it as "what happens if this month looks like the last ones" - it gets more accurate as ${monthName} goes on.` : `It's leaning on this month's real spending now, so it should be fairly close.`}
        </div>
        <div class="forecast-confidence-bar" title="${100 - pacePct}% usual month, ${pacePct}% this month's pace">
            <span class="forecast-conf-usual" style="width: ${100 - pacePct}%"></span>
            <span class="forecast-conf-pace" style="width: ${pacePct}%"></span>
        </div>
        <div class="forecast-confidence-labels"><span>Your usual month</span><span>This month's pace</span></div>
    ` : `<div class="forecast-confidence-text"><strong>Day ${f.days_elapsed} of ${f.days_in_month}.</strong> There's no full past month to compare with yet, so this is based only on how you've spent so far in ${monthName}.</div>`;

    const statusText = (l) => {
        const projected = num(l.projected);
        const budget = l.budget === null ? null : num(l.budget);
        switch (l.status) {
            case 'over': return `<span class="forecast-status status-over">⛔ Already ${crc(num(l.spent_so_far) - budget)} over budget</span>`;
            case 'at_risk': return `<span class="forecast-status status-risk">⚠ Likely to go ${crc(projected - budget)} over</span>`;
            case 'on_track': return budget - projected < Math.max(1000, budget * 0.01)
                ? '<span class="forecast-status status-ok">✓ Right at budget</span>'
                : `<span class="forecast-status status-ok">✓ On track, about ${crc(budget - projected)} to spare</span>`;
            default: return '<span class="forecast-status status-none">No budget set</span>';
        }
    };

    const explain = (l) => {
        const spent = num(l.spent_so_far);
        const rest = num(l.rest);
        const scheduled = num(l.scheduled);
        const projected = num(l.projected);
        const budget = l.budget === null ? null : num(l.budget);
        const typical = l.typical_month === null ? null : num(l.typical_month);
        const w = Math.round(num(l.pace_weight) * 100);

        let restHow;
        if (l.basis === 'history') {
            restHow = `You usually spend ${crc(typical)} here in a month and few, larger purchases (like bills) make the daily pace meaningless, so it's your usual month minus what you've already spent.`;
        } else if (l.basis === 'pace') {
            restHow = `No past month to compare with, so it's this month's pace: ${crc(num(l.pace_month))} a month at the rate you're going.`;
        } else {
            restHow = `A mix of two guesses:
                <ul>
                    <li><strong>Your usual month:</strong> you typically spend ${crc(typical)} → ${crc(num(l.rest_from_typical))} still to go <span class="forecast-weight">(counts ${100 - w}%)</span></li>
                    <li><strong>This month's pace:</strong> at your current rate it'd be ${crc(num(l.pace_month))} for the month → ${crc(num(l.rest_from_pace))} still to go <span class="forecast-weight">(counts ${w}%)</span></li>
                </ul>`;
        }

        return `
            <div class="forecast-explain">
                <div class="budget-eq-row"><span>Spent so far</span>${crc(spent)}</div>
                <div class="budget-eq-row"><span>+ Expected rest of month</span>${crc(rest)}</div>
                <div class="forecast-explain-how">${restHow}</div>
                ${scheduled > 0 ? `<div class="budget-eq-row"><span>+ Tasa Cero cuotas still to be charged</span>${crc(scheduled)}</div>` : ''}
                <div class="budget-eq-row budget-eq-total"><span>= Likely total</span>${crc(projected)}</div>
                ${budget !== null ? `<div class="budget-eq-row"><span>Budget (after card debt)</span>${crc(budget)}</div>` : ''}
            </div>
        `;
    };

    const row = (l) => {
        const spent = num(l.spent_so_far);
        const projected = num(l.projected);
        const scheduled = num(l.scheduled);
        const rest = Math.max(projected - spent - scheduled, 0);
        const budget = l.budget === null ? null : num(l.budget);
        const scale = Math.max(projected, budget || 0) * 1.08 || 1;
        const segments = [
            { cls: 'forecast-spent', value: spent, title: `Spent so far: ₡${Math.round(spent).toLocaleString('en-US')}` },
            { cls: 'forecast-rest', value: rest, title: `Expected rest of month: ₡${Math.round(rest).toLocaleString('en-US')}` },
            { cls: 'forecast-cuotas', value: scheduled, title: `Tasa Cero cuotas still to be charged: ₡${Math.round(scheduled).toLocaleString('en-US')}` },
        ].filter(seg => seg.value > 0);
        return `
            <details class="forecast-line">
                <summary>
                    <span class="budget-category">
                        <span class="forecast-chevron">▸</span>
                        <span class="category-icon">${escapeHtml(l.category_icon || '')}</span>
                        ${escapeHtml(l.category_name)}
                    </span>
                    <span class="forecast-bar">
                        ${segments.map(seg => `<span class="${seg.cls}" style="width: ${seg.value / scale * 100}%" title="${seg.title}"></span>`).join('')}
                        ${budget !== null ? `<span class="forecast-tick" style="left: ${budget / scale * 100}%" title="Budget: ₡${Math.round(budget).toLocaleString('en-US')}"></span>` : ''}
                    </span>
                    <span class="forecast-numbers">
                        <span>Likely ${crc(projected)}${budget !== null ? ` of ${crc(budget)} budget` : ''}</span>
                        ${statusText(l)}
                    </span>
                </summary>
                ${explain(l)}
            </details>
        `;
    };

    const groups = [
        { title: '⚠ Needs attention', lines: f.lines.filter(l => l.status === 'over' || l.status === 'at_risk') },
        { title: '✓ On track', lines: f.lines.filter(l => l.status === 'on_track') },
        { title: 'No budget', lines: f.lines.filter(l => l.status === 'no_budget'),
          hint: 'Not in any budget, but still counted in your likely spending above.' },
    ].filter(g => g.lines.length > 0);

    document.getElementById('forecast-lines').innerHTML = groups.map(g => `
        <div class="forecast-group">
            <h4>${g.title} <span class="section-caption">(${g.lines.length})</span></h4>
            ${g.hint ? `<p class="field-hint">${g.hint}</p>` : ''}
            ${g.lines.map(row).join('')}
        </div>
    `).join('');
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
    const fmt = formatDateForInput;
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

    // ApexCharts draws a white border between donut slices by default,
    // which shows up as bright lines against dark-mode cards - match the
    // slice border to the card background instead so it blends in.
    const cardBg = getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim();

    renderChart(containerId, {
        series: data.map(d => parseFloat(d.total_amount)),
        chart: {
            type: 'donut',
            height: 320
        },
        labels: data.map(d => d.category_name),
        colors: data.map(d => d.category_color || '#6B7280'),
        stroke: {
            colors: [cardBg]
        },
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
        const [emailSources, syncStatus, credStatus] = await Promise.all([
            API.EmailSources.getAll(),
            API.Sync.getStatus().catch(() => ({ last_sync: null })),
            API.Credentials.getStatus().catch(() => null),
        ]);

        renderEmailSources(emailSources);
        renderSyncStatus(syncStatus);
        renderCredentialsStatus(credStatus);
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

function reportSyncResult(result) {
    if (!result.success) {
        showNotification((result.errors && result.errors[0]) || result.message, 'error');
        return;
    }
    showNotification(
        `${result.new_transactions} new, ${result.skipped_duplicates} already had it, from ${result.sources_synced} source(s)`,
        'success'
    );
}

async function triggerSync() {
    const btn = document.getElementById('btn-sync-now');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Syncing...';
    try {
        showNotification('Sync started - this can take a minute...', 'info');
        const result = await API.Sync.triggerSync();
        reportSyncResult(result);
        await loadSettings();
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Sync failed:', error);
        showNotification('Sync failed: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

async function triggerSyncRange() {
    const startDate = document.getElementById('sync-range-start').value;
    const endDate = document.getElementById('sync-range-end').value;
    if (!startDate || !endDate) {
        showNotification('Pick a start and end date first', 'error');
        return;
    }

    const btn = document.getElementById('btn-sync-range');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Syncing...';
    try {
        showNotification('Sync started - this can take a minute...', 'info');
        const result = await API.Sync.triggerSyncRange(startDate, endDate);
        reportSyncResult(result);
        await loadSettings();
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Sync failed:', error);
        showNotification('Sync failed: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

async function triggerRecategorize() {
    const btn = document.getElementById('btn-recategorize');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Working...';
    try {
        const result = await API.Maintenance.recategorize();
        showNotification(`Checked ${result.checked}, recategorized ${result.updated}`, 'success');
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Recategorize failed:', error);
        showNotification('Failed: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

function renderCredentialsStatus(status) {
    const el = document.getElementById('credentials-status');
    if (!el) return;
    if (!status) {
        el.textContent = 'Could not check the credentials file.';
    } else if (!status.has_credentials) {
        el.textContent = '✗ No Google file yet - upload it below to connect Gmail.';
    } else if (!status.has_token) {
        el.textContent = '✓ Google file in place. Click "Sync Now" to log in to Gmail.';
    } else {
        el.textContent = '✓ Google file in place and Gmail connected.';
    }
}

async function handleCredentialsFile(file) {
    if (!file) return;
    try {
        const content = await file.text();
        const result = await API.Credentials.upload(content);
        showNotification(
            result.token_removed
                ? 'Credentials replaced - click "Sync Now" to log in again'
                : 'Credentials saved - click "Sync Now" to log in to Gmail',
            'success'
        );
        renderCredentialsStatus(await API.Credentials.getStatus());
    } catch (error) {
        console.error('Credentials upload failed:', error);
        showNotification(error.message, 'error');
    } finally {
        const input = document.getElementById('credentials-file');
        if (input) input.value = '';
    }
}

function handleCredentialsDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');
    handleCredentialsFile(event.dataTransfer.files[0]);
}

async function triggerReconnectGmail() {
    const btn = document.getElementById('btn-reconnect-gmail');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Working...';
    try {
        await API.Maintenance.reconnectGmail();
        showNotification('Done - click "Sync Now" to log in to Gmail again', 'success');
    } catch (error) {
        console.error('Reconnect failed:', error);
        showNotification('Failed: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
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
    document.getElementById('modal-income').style.display = 'none';
    document.getElementById('modal-payoff').style.display = 'none';
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
window.triggerSyncRange = triggerSyncRange;
window.triggerRecategorize = triggerRecategorize;
window.triggerReconnectGmail = triggerReconnectGmail;
window.handleCredentialsFile = handleCredentialsFile;
window.handleCredentialsDrop = handleCredentialsDrop;
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
