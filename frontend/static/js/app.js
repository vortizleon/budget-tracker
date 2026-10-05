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

// Everything JS builds (views, charts, tooltips) is translated when it is rendered, so a
// language change just re-renders the current view. (Not named "languagechange": browsers
// fire a native event with that name when the preferred languages change.)
window.addEventListener('i18n:change', () => {
    closeModal();   // modal titles/labels are set when a modal opens
    updateThemeToggleIcon(document.documentElement.getAttribute('data-theme') === 'dark');
    setPrivacyMode(document.body.classList.contains('privacy-mode'));
    showView(currentView, { push: false });
});

async function initializeApp() {
    setupNavigation();
    initTheme();
    initPrivacyMode();
    loadInitialData();
    showView(viewFromPath(), { push: false });
    startGmailWatch();
}

// ============================================================================
// Gmail token watch - warn as soon as the stored login stops working, instead
// of the user finding out when a sync fails.
// ============================================================================

const GMAIL_CHECK_MS = 30 * 60 * 1000;
let lastGmailCheck = 0;

function startGmailWatch() {
    checkGmailStatus();
    setInterval(checkGmailStatus, GMAIL_CHECK_MS);
    // Coming back to the tab after a while is when a dead token matters most.
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && Date.now() - lastGmailCheck > 5 * 60 * 1000) checkGmailStatus();
    });
}

async function checkGmailStatus() {
    lastGmailCheck = Date.now();
    try {
        const { status } = await API.Sync.getGmailStatus();
        setGmailBanner(status === 'needs_login');
    } catch (error) {
        console.error('Gmail status check failed:', error);   // server down etc. - say nothing
    }
}

function setGmailBanner(show) {
    let banner = document.getElementById('gmail-banner');
    if (!show) {
        if (banner) banner.remove();
        return;
    }
    if (banner) return;
    banner = document.createElement('div');
    banner.id = 'gmail-banner';
    banner.className = 'gmail-banner';
    banner.innerHTML = '<span class="gmail-banner-text"></span><button class="btn btn-primary" id="btn-gmail-banner"></button>';
    banner.querySelector('.gmail-banner-text').textContent = _t('Your Gmail login expired, so new transactions are not syncing.');
    const btn = banner.querySelector('button');
    btn.textContent = _t('Log in to Gmail');
    btn.addEventListener('click', reconnectFromBanner);
    document.querySelector('.main-content').prepend(banner);
}

async function reconnectFromBanner() {
    const btn = document.getElementById('btn-gmail-banner');
    btn.disabled = true;
    setLabel(btn, _t('Waiting for login...'));
    try {
        showNotification(_t('A Google login is opening in your browser...'), 'info');
        const result = await API.Sync.triggerSync();
        reportSyncResult(result);
        setGmailBanner(false);
        await showView(currentView);
    } catch (error) {
        console.error('Gmail login failed:', error);
        showNotification(_t('Sync failed: {error}', { error: _t(error.message) }), 'error');
        btn.disabled = false;
        setLabel(btn, _t('Log in to Gmail'));
    }
}

// ============================================================================
// URL routing - each view lives at its own path (/budgets, /analytics, ...)
// so a reload stays put. Keep VIEWS in sync with SPA_VIEWS in api.py.
// ============================================================================

const VIEWS = ['dashboard', 'budgets', 'transactions', 'analytics', 'forecast', 'categories', 'cards', 'debt', 'settings'];

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
    btn.title = isDark ? _t('Switch to light mode') : _t('Switch to dark mode');
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
    btn.title = hidden ? _t('Show amounts') : _t('Hide amounts');

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
        case 'debt':
            await loadDebt();
            break;
        case 'transactions':
            populateTransactionFilterOptions();
            await loadTransactions();
            break;
        case 'analytics':
            // Default to the current month the first time; afterwards keep whatever range was picked.
            if (analyticsRangeInitialized) await loadAnalytics(currentAnalyticsFilters);
            else await setAnalyticsPreset('month');
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
            `(${new Date().toLocaleString(I18N.locale(), { month: 'long', year: 'numeric' })})`;
        document.getElementById('all-time-caption').textContent = summary.oldest_transaction_date
            ? _t('(since {date})', { date: formatDate(summary.oldest_transaction_date) })
            : '';

        // Load recent transactions - excludes future-dated rows (e.g. an
        // upcoming installment charge) since "recent" means already happened.
        const today = formatDateForInput(new Date());
        const response = await API.Transactions.getAll({ end_date: today, limit: 10 });
        renderRecentTransactions(response.transactions || []);

    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showNotification(_t('Failed to load dashboard data'), 'error');
    }
}

function renderRecentTransactions(transactions) {
    const container = document.getElementById('recent-transactions');

    if (transactions.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No transactions yet')}</p>`;
        return;
    }

    container.innerHTML = transactions.map(t => `
        <div class="transaction-item">
            <div class="transaction-icon">${getCategoryIcon(t.category)}</div>
            <div class="transaction-details">
                <div class="transaction-merchant">${escapeHtml(t.commerce_name || _t('Unknown'))}</div>
                <div class="transaction-meta">
                    ${formatDate(t.date)} • ${t.category?.name ? escapeHtml(_tc(t.category.name)) : _t('Uncategorized')} • ${t.card?.name ? escapeHtml(t.card.name) : _t('No card')}
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
            `<p class="empty-state-text">${_t('Failed to load budgets')}</p>`;
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
    const incomeLabel = received > 0 && received >= base ? _t('Income received') : _t('Expected income');
    document.getElementById('budget-equation').innerHTML = `
        <div class="budget-eq-row"><span>${incomeLabel}</span>${crc(base)}</div>
        <div class="budget-eq-row"><span>− ${_t('Spent so far')}</span>${crc(spent)}</div>
        ${debt > 0 ? `<div class="budget-eq-row"><span>− ${_t('Card debt payment')}</span>${crc(debt)}</div>` : ''}
        <div class="budget-eq-row budget-eq-total"><span>= ${_t('Left to spend')}</span>${crc(left)}</div>
    `;

    // Where income goes: locked + other budgets + debt + savings = income.
    const locked = o.lines.filter(l => l.is_protected).reduce((a, l) => a + parseFloat(l.adjusted_amount), 0);
    const flexible = o.lines.filter(l => !l.is_protected).reduce((a, l) => a + parseFloat(l.adjusted_amount), 0);
    const savings = Math.max(parseFloat(o.unbudgeted), 0);
    const lockedNames = o.lines.filter(l => l.is_protected).map(l => _tc(l.category_name)).join(' & ') || _t('Locked budgets');
    const reduction = parseFloat(o.reduction_percentage);
    const parts = [
        { label: `🔒 ${escapeHtml(lockedNames)}`, value: locked, cls: 'plan-locked' },
        { label: _t('Other budgets'), value: flexible, cls: 'plan-flexible',
          note: reduction > 0 ? _t('cut {pct}% for debt', { pct: reduction.toFixed(1) }) : '' },
        { label: _t('Card debt'), value: debt, cls: 'plan-debt' },
        { label: _t('Savings (not budgeted)'), value: savings, cls: 'plan-savings' },
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
        ? `<span class="budget-over">${_t("Card debt is {amount} more than everything that isn't locked - lower the payment or unlock a budget.", { amount: crc(shortfall) })}</span>`
        : (unbudgeted < 0 ? `<span class="budget-over">${_t('Budgets add up to {amount} more than your income.', { amount: crc(-unbudgeted) })}</span>` : '');
}

// The month's payment plan per card (from the payoff plans). Shown on the Debt page.
function renderBudgetDebt(o) {
    const container = document.getElementById('budget-debt-list');
    if (o.debt_lines.length === 0) {
        container.innerHTML = `<p class="field-hint">${_t('No card debt this month. To plan paying one down, open Cards and click 💰 on the card.')}</p>`;
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
            const name = currency === 'CRC' ? _t('Colones') : _t('Dollars');
            const covers = [];
            if (usual > 0) covers.push(currency === 'CRC'
                ? _t('{amount} for your usual colón purchases on this card (monthly average)', { amount: money(usual) })
                : _t('{amount} for your usual dollar purchases on this card (monthly average)', { amount: money(usual) }));
            if (cuotas > 0) covers.push(_t("{amount} for this month's Tasa Cero cuotas", { amount: money(cuotas) }));
            let text = _t('You pay {amount}', { amount: money(payment) });
            if (charges > 0) {
                text += toDebt > 0
                    ? _t('. First {covers}, so {amount} is left to pay down the old balance', { covers: covers.join(' + '), amount: money(toDebt) })
                    : _t(', but it only covers {covers} - nothing is left to pay down the old balance', { covers: covers.join(' + ') });
            } else {
                text += _t(' - all of it pays down the old balance');
            }
            if (currency === 'USD' && toDebt > 0) text += ` (${money(toDebt * rate, 'CRC')})`;
            return `<div class="budget-debt-row"><strong>${name}:</strong> ${text}</div>`;
        }).join('');
        return `
            <div class="budget-debt-card">
                <div class="budget-debt-header">
                    <strong>💳 ${escapeHtml(d.card_name)}</strong>
                    <span><span class="budget-debt-amount money-value">${formatCurrency(d.amount, 'CRC')}</span> ${_t('toward old debt')}</span>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="showPayoffPlan(${d.card_id})">${_t('Edit plan')}</button>
                </div>
                ${rows}
            </div>
        `;
    }).join('') + `<p class="field-hint">${_t('Your usual purchases and cuotas are already counted in your category budgets, so here only the part of the payment that pays down the old balance counts as debt.')}</p>`;
}

function renderIncomeEntries(o) {
    const [year, month] = o.month.split('-').map(Number);
    document.getElementById('budget-income-caption').textContent =
        `(${new Date(year, month - 1, 1).toLocaleString(I18N.locale(), { month: 'long', year: 'numeric' })})`;

    const expectedInput = document.getElementById('budget-expected-income');
    const rateInput = document.getElementById('budget-usd-rate');
    expectedInput.value = o.settings.expected_monthly_income ? parseFloat(o.settings.expected_monthly_income) : '';
    rateInput.value = parseFloat(o.settings.usd_to_crc_rate);

    const container = document.getElementById('income-entries-list');
    if (o.income_entries.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No payments logged this month yet - click "+ Add Payment" when you get paid.')}</p>`;
        return;
    }

    container.innerHTML = o.income_entries.map(e => `
        <div class="plan-item">
            <div class="plan-info">
                <strong>${escapeHtml(e.description || _t('Payment'))}</strong>
                <span class="plan-meta">
                    ${formatDate(e.date)} -
                    <span class="money-value">${formatCurrency(e.amount, e.currency)}</span>
                    ${e.currency === 'USD' ? `(<span class="money-value">${formatCurrency(e.amount_crc, 'CRC')}</span>)` : ''}
                </span>
            </div>
            <button type="button" class="icon-btn" onclick="deleteIncome(${e.id})" title="${_t('Delete payment')}">🗑️</button>
        </div>
    `).join('');
}

function renderBudgetLines(o) {
    const container = document.getElementById('budget-lines');

    const reduced = parseFloat(o.reduction_percentage) > 0;

    if (o.lines.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No budgets yet - add one below, or click "Reset to Suggested".')}</p>`;
    } else {
        container.innerHTML = `
            <div class="budget-line budget-line-head">
                <span>${_t('Category')}</span>
                <span>${_t('% of Income')}</span>
                <span>${_t('Amount (₡)')}</span>
                <span>${_t('Spent')}</span>
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
                ? `<span class="money-value">${formatCurrency(remaining, 'CRC')}</span> ${_t('left')}`
                : `<span class="money-value">${formatCurrency(remaining, 'CRC')}</span> ${_t('over')}`;
            return `
                <div class="budget-line">
                    <span class="budget-category">
                        <button type="button" class="icon-btn budget-lock ${l.is_protected ? 'locked' : ''}"
                            onclick="toggleBudgetProtected(${l.id}, ${!l.is_protected})"
                            title="${l.is_protected ? _t('Protected - never reduced for debt. Click to unlock.') : _t('Reduced to make room for debt payments. Click to protect.')}">${l.is_protected ? '🔒' : '🔓'}</button>
                        <span class="category-icon">${escapeHtml(l.category_icon || '')}</span>
                        ${escapeHtml(_tc(l.category_name))}
                    </span>
                    <span class="budget-input-wrap">
                        <input type="number" class="input budget-input ${l.anchor === 'percentage' ? 'anchored' : ''}"
                            value="${parseFloat(l.percentage)}" min="0" max="100" step="0.5"
                            title="${l.anchor === 'percentage' ? _t('You set this % - the amount follows your income') : _t('Calculated from the fixed amount')}"
                            onchange="updateBudget(${l.category_id}, 'percentage', this.value)">
                        <span class="budget-input-suffix">%</span>
                    </span>
                    <span class="budget-amount-wrap">
                        <input type="number" class="input budget-input money-value ${l.anchor === 'amount' ? 'anchored' : ''}"
                            value="${planned}" min="0" step="1000"
                            title="${l.anchor === 'amount' ? _t('Fixed amount - stays the same when income changes') : _t('Calculated from the %')}"
                            onchange="updateBudget(${l.category_id}, 'amount', this.value)">
                        ${reduced && !l.is_protected
                            ? `<span class="budget-after-debt">→ <span class="money-value">${formatCurrency(amount, 'CRC')}</span> ${_t('after debt')}</span>`
                            : ''}
                    </span>
                    <span class="budget-progress">
                        <span class="budget-progress-label">
                            <span class="money-value">${formatCurrency(spent, 'CRC')}</span>
                            <span class="${remaining < 0 ? 'budget-over' : ''}">${remainingText}</span>
                        </span>
                        <span class="budget-bar"><span class="budget-fill ${fillClass}" style="width: ${Math.min(ratio, 1) * 100}%"></span></span>
                    </span>
                    <button type="button" class="icon-btn" onclick="deleteBudget(${l.id})" title="${_t('Remove budget')}">🗑️</button>
                </div>
            `;
        }).join('');
    }

    const budgeted = new Set(o.lines.map(l => l.category_id));
    const available = allCategories.filter(c => c.category_type !== 'income' && !budgeted.has(c.id));
    const select = document.getElementById('budget-add-category');
    select.innerHTML = available.length
        ? available.map(c => `<option value="${c.id}">${escapeHtml(_tc(c.name))}</option>`).join('')
        : `<option value="">${_t('All categories have a budget')}</option>`;
}

async function updateBudget(categoryId, field, rawValue) {
    const value = parseFloat(rawValue);
    if (isNaN(value) || value < 0 || (field === 'percentage' && value > 100)) {
        showNotification(field === 'percentage' ? _t('Enter a % between 0 and 100') : _t('Enter a positive amount'), 'error');
        await loadBudgets();
        return;
    }

    try {
        await API.Budgets.upsert({ category_id: categoryId, [field]: value });
        await loadBudgets();
    } catch (error) {
        console.error('Failed to update budget:', error);
        showNotification(_t('Failed to update budget: {error}', { error: _t(error.message) }), 'error');
    }
}

async function toggleBudgetProtected(budgetId, isProtected) {
    try {
        await API.Budgets.setProtected(budgetId, isProtected);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to update budget:', error);
        showNotification(_t('Failed to update budget'), 'error');
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
        showNotification(_t('Failed to add budget: {error}', { error: _t(error.message) }), 'error');
    }
}

async function deleteBudget(budgetId) {
    try {
        await API.Budgets.delete(budgetId);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to delete budget:', error);
        showNotification(_t('Failed to delete budget'), 'error');
    }
}

async function resetBudgetsToSuggested() {
    if (!confirm(_t('Replace all your budgets with the suggested percentages?'))) return;

    try {
        await API.Budgets.resetToSuggested();
        showNotification(_t('Budgets reset to suggested'), 'success');
        await loadBudgets();
    } catch (error) {
        console.error('Failed to reset budgets:', error);
        showNotification(_t('Failed to reset budgets'), 'error');
    }
}

async function saveBudgetSettings() {
    const expected = document.getElementById('budget-expected-income').value;
    const rate = parseFloat(document.getElementById('budget-usd-rate').value);
    if (isNaN(rate) || rate <= 0) {
        showNotification(_t('Enter a valid USD → CRC rate'), 'error');
        return;
    }

    try {
        await API.Budgets.updateSettings({
            expected_monthly_income: expected === '' ? null : parseFloat(expected),
            usd_to_crc_rate: rate,
        });
        showNotification(_t('Budget settings saved'), 'success');
        await loadBudgets();
    } catch (error) {
        console.error('Failed to save budget settings:', error);
        showNotification(_t('Failed to save settings: {error}', { error: _t(error.message) }), 'error');
    }
}

function ordinal(n) {
    // Spanish: "1.er pago", "2.º pago" (masculine, before the noun).
    if (I18N.lang() === 'es') return n === 1 || n === 3 ? `${n}.er` : `${n}.º`;
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
    document.getElementById('income-description').value = _t('{ordinal} payment', { ordinal: ordinal(count + 1) });

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
        showNotification(_t('Payment added'), 'success');
        // Jump to the month the payment landed in so it's visible.
        document.getElementById('budget-month').value = data.date.slice(0, 7);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to add payment:', error);
        showNotification(_t('Failed to add payment: {error}', { error: _t(error.message) }), 'error');
    }
}

async function deleteIncome(incomeId) {
    if (!confirm(_t('Delete this payment?'))) return;

    try {
        await API.Income.delete(incomeId);
        await loadBudgets();
    } catch (error) {
        console.error('Failed to delete payment:', error);
        showNotification(_t('Failed to delete payment'), 'error');
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
        showNotification(_t('Failed to load cards'), 'error');
    }
}

// ============================================================================
// Debt view: where each card stands, report a payment, what the debt costs
// ============================================================================

async function loadDebt() {
    try {
        const [positions, payments, costOfDebt, cards, budgetOverview, statements] = await Promise.all([
            API.Debt.getPositions(),
            API.Debt.getPayments(),
            API.Analytics.getCostOfDebt().catch(() => null),
            API.Cards.getAll(),
            API.Budgets.getOverview().catch(() => null),
            API.Statements.getAll().catch(() => []),
        ]);
        allCards = cards;
        renderPositions(positions);
        if (budgetOverview) renderBudgetDebt(budgetOverview);
        renderPaymentForm(cards);
        renderPayments(payments);
        renderCostOfDebt(costOfDebt);
        renderStatementHistory(statements);
    } catch (error) {
        console.error('Failed to load debt:', error);
        showNotification(_t('Failed to load debt'), 'error');
    }
}

function renderPositions(list) {
    const el = document.getElementById('debt-positions');
    if (!list.length) {
        el.innerHTML = `<div class="debt-cost debt-cost-empty"><strong>${_t('Nothing to show yet')}</strong>
            <span class="field-hint">${_t('Upload your credit card statements in Settings to see what you owe on each card.')}</span>
            <a href="/settings" onclick="event.preventDefault(); showView('settings')">${_t('Go to Settings')}</a></div>`;
        return;
    }
    const money = (v, cur) => `<span class="money-value">${formatCurrency(v, cur)}</span>`;
    const row = (label, crc, usd, bold) => {
        if (parseFloat(crc) === 0 && parseFloat(usd) === 0 && !bold) return '';
        return `<tr${bold ? ' class="statement-row-strong"' : ''}><td>${label}</td><td>${money(crc, 'CRC')}</td><td>${money(usd, 'USD')}</td></tr>`;
    };
    el.innerHTML = list.map(p => {
        const due = p.cash_due_date ? formatDate(p.cash_due_date) : '';
        let chip;
        if (p.status === 'paid') {
            chip = `<span class="statement-badge ok">✓ ${_t('Paid in full')}</span>`;
        } else if (p.status === 'minimum_paid') {
            chip = `<span class="statement-badge review">${_t('Minimum covered - interest applies to the rest')}</span>`;
        } else {
            const late = p.days_left != null && p.days_left < 0;
            chip = `<span class="statement-badge ${late ? 'bad' : 'review'}">${late
                ? _t('Overdue since {date}', { date: due })
                : _t('Pay by {date}', { date: due })}</span>`;
        }
        const togo = (p.status === 'paid') ? '' : `
            ${row(_t('Still to pay in full'), p.remaining_cash_crc, p.remaining_cash_usd, true)}
            ${p.status === 'unpaid' ? row(_t('Of that, the minimum'), p.remaining_min_crc, p.remaining_min_usd) : ''}`;
        return `
        <div class="statement-item">
            <div class="statement-head">
                <strong>${escapeHtml(p.card_name)}</strong>
                <span class="field-hint">${_t('{period} statement', { period: p.period })}</span>
                ${chip}
            </div>
            <table class="statement-table">
                <tr><th></th><th>CRC</th><th>USD</th></tr>
                ${row(_t('Statement balance'), p.statement_balance_crc, p.statement_balance_usd)}
                ${row(_t('Paid since'), p.payments_since_crc, p.payments_since_usd)}
                ${row(_t('New purchases since'), p.purchases_since_crc, p.purchases_since_usd)}
                ${row(_t('Points redeemed (credited on the next statement)'), p.rewards_since_crc, p.rewards_since_usd)}
                ${row(_t('Owed now (estimate)'), p.balance_now_crc, p.balance_now_usd, true)}
                ${togo}
            </table>
        </div>`;
    }).join('');
}

function renderPaymentForm(cards) {
    const select = document.getElementById('payment-card');
    const previous = select.value;
    select.innerHTML = cards.filter(c => c.card_type !== 'debit')
        .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    if (previous) select.value = previous;
    const date = document.getElementById('payment-date');
    if (!date.value) date.value = formatDateForInput(new Date());
}

function renderPayments(list) {
    const el = document.getElementById('payments-list');
    if (!list.length) {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = `<table class="statement-table payments-table">
        <tr><th>${_t('Date')}</th><th>${_t('Card')}</th><th>${_t('Amount')}</th><th></th></tr>
        ${list.map(p => `<tr>
            <td>${formatDate(p.date)}</td>
            <td>${escapeHtml(p.card_name || '')}${p.notes ? ` <span class="field-hint">${escapeHtml(p.notes)}</span>` : ''}</td>
            <td><span class="money-value">${formatCurrency(p.amount, p.currency)}</span></td>
            <td>${p.logged_by_hand
                ? `<button class="icon-btn" onclick="removePayment(${p.id})" title="${_t('Delete')}">🗑️</button>`
                : `<span class="field-hint">${_t('from bank email')}</span>`}</td>
        </tr>`).join('')}
    </table>`;
}

// One row per imported statement: what it showed and what it cost. Warnings stay visible
// here, since a statement flagged on import is the one whose numbers to double-check.
function renderStatementHistory(list) {
    const section = document.getElementById('statement-history-section');
    section.style.display = list.length ? '' : 'none';
    if (!list.length) return;
    const both = (crc, usd) => {
        const parts = [];
        if (parseFloat(crc) > 0) parts.push(formatCurrency(crc, 'CRC'));
        if (parseFloat(usd) > 0) parts.push(formatCurrency(usd, 'USD'));
        return parts.length ? `<span class="money-value">${parts.join('<br>')}</span>` : '-';
    };
    const monthLabel = (period) => {
        const [y, m] = period.split('-').map(Number);
        return new Date(y, m - 1, 1).toLocaleString(I18N.locale(), { month: 'short', year: 'numeric' });
    };
    document.getElementById('statement-history').innerHTML = `<table class="statement-table statement-history-table">
        <tr><th>${_t('Month')}</th><th>${_t('Card')}</th><th>${_t('Balance at cut')}</th><th>${_t('Interest charged')}</th>
            <th>${_t('Insurance')}</th><th>${_t('Paid this cycle')}</th><th></th></tr>
        ${list.map(st => `<tr>
            <td>${escapeHtml(monthLabel(st.period))}</td>
            <td>${escapeHtml(st.card_name || '••••' + st.account_last4)}
                ${st.status !== 'ok' ? `<br><span class="statement-badge review">${_t('Needs review')}</span>` : ''}</td>
            <td>${both(st.closing_balance_crc, st.closing_balance_usd)}</td>
            <td>${both(st.interest_crc, st.interest_usd)}</td>
            <td>${both(st.insurance_crc, st.insurance_usd)}</td>
            <td>${both(st.payments_crc, st.payments_usd)}</td>
            <td><button class="icon-btn" onclick="removeStatement(${st.id})" title="${_t('Delete')}">🗑️</button></td>
        </tr>${st.status !== 'ok' ? `<tr><td colspan="7"><ul class="statement-warnings">${(st.warnings || []).map(w => `<li>${escapeHtml(_t(w))}</li>`).join('')}</ul></td></tr>` : ''}`).join('')}
    </table>`;
}

async function removeStatement(id) {
    if (!confirm(_t('Delete this statement? You can upload the PDF again from Settings.'))) return;
    try {
        await API.Statements.remove(id);
        await loadDebt();
    } catch (error) {
        console.error('Delete statement failed:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
    }
}

// The snapshot is a normal file download from the API (Content-Disposition: attachment).
function downloadSnapshot(format) {
    const withTransactions = document.getElementById('export-transactions').checked;
    window.location.href = `/api/export/snapshot?format=${format}&include_transactions=${withTransactions}`;
}

// Copy the snapshot as text, ready to paste into a conversation (no file involved).
async function copySnapshot() {
    const withTransactions = document.getElementById('export-transactions').checked;
    try {
        const response = await fetch(`/api/export/snapshot?format=md&include_transactions=${withTransactions}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        await navigator.clipboard.writeText(await response.text());
        showNotification(_t('Copied - paste it into the conversation'), 'success');
    } catch (error) {
        console.error('Copy snapshot failed:', error);
        showNotification(_t('Could not copy - use Download instead'), 'error');
    }
}

async function submitPayment(event) {
    event.preventDefault();
    const btn = document.getElementById('payment-submit');
    btn.disabled = true;
    try {
        await API.Debt.logPayment({
            card_id: parseInt(document.getElementById('payment-card').value),
            amount: document.getElementById('payment-amount').value,
            currency: document.getElementById('payment-currency').value,
            date: document.getElementById('payment-date').value,
            notes: document.getElementById('payment-notes').value || null,
        });
        document.getElementById('payment-amount').value = '';
        document.getElementById('payment-notes').value = '';
        showNotification(_t('Payment logged'), 'success');
        await loadDebt();
    } catch (error) {
        console.error('Log payment failed:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
    } finally {
        btn.disabled = false;
    }
}

async function removePayment(id) {
    try {
        await API.Debt.deletePayment(id);
        await loadDebt();
    } catch (error) {
        console.error('Delete payment failed:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
    }
}

// What card debt costs, from imported statements (interest + optional insurance).
function renderCostOfDebt(d) {
    const el = document.getElementById('debt-cost');
    if (!d) {
        el.innerHTML = '';
        return;
    }
    if (!d.has_data) {
        el.innerHTML = `<div class="debt-cost debt-cost-empty"><strong>${_t('What does your debt cost?')}</strong>
            <span class="field-hint">${_t('Upload your credit card statements in Settings to see how much interest and insurance you pay each month.')}</span>
            <a href="/settings" onclick="event.preventDefault(); showView('settings')">${_t('Go to Settings')}</a></div>`;
        return;
    }
    const money = (v) => `<span class="money-value">${formatCurrency(v, 'CRC')}</span>`;
    const pct = (v, digits = 1) => `${(parseFloat(v)).toFixed(digits)}%`;
    const tile = (label, value, hint) => `<div class="debt-tile"><div class="debt-tile-label">${label}</div>
        <div class="debt-tile-value">${value}</div>${hint ? `<div class="field-hint">${hint}</div>` : ''}</div>`;

    const tiles = [
        tile(_t('Total debt'), money(d.total_debt_crc),
            `${formatCurrency(d.debt_crc, 'CRC')} + ${formatCurrency(d.debt_usd, 'USD')}` +
            (parseFloat(d.paid_since_crc) > 0
                ? `<br>${_t('{statement} at the statement, less {paid} paid since', { statement: money(d.statement_debt_crc), paid: money(d.paid_since_crc) })}`
                : '')),
        tile(_t('Cost per year'), money(d.yearly_cost_crc), _t('if nothing changes')),
    ];
    if (d.cost_share_of_income != null) {
        tiles.push(tile(_t('Share of your income'), pct(parseFloat(d.cost_share_of_income) * 100), _t('goes to interest and insurance')));
    }
    if (d.average_rate != null) {
        tiles.push(tile(_t('Average interest rate'), pct(d.average_rate), _t('per year, weighted by balance')));
    }
    if (d.interest_share_of_minimum != null) {
        tiles.push(tile(_t('Minimum payment'), pct(parseFloat(d.interest_share_of_minimum) * 100, 0),
            _t('of it is just interest - paying only the minimum barely dents the debt')));
    }
    if (parseFloat(d.future_installments_crc) > 0) {
        tiles.push(tile(_t('0% installments still coming'), money(d.future_installments_crc), _t('not in the balance yet, but already committed')));
    }

    const advice = [];
    if (d.highest_rate_currency && d.apr_crc != null && d.apr_usd != null && parseFloat(d.apr_crc) !== parseFloat(d.apr_usd)) {
        const hi = d.highest_rate_currency;
        advice.push(_t('{hi} debt costs {hiRate} a year against {loRate} on {lo} - put extra money toward the {hi} balance first.', {
            hi, lo: hi === 'CRC' ? 'USD' : 'CRC',
            hiRate: pct(hi === 'CRC' ? d.apr_crc : d.apr_usd, 2), loRate: pct(hi === 'CRC' ? d.apr_usd : d.apr_crc, 2),
        }));
    }
    if (parseFloat(d.insurance_crc) > 0) {
        advice.push(_t('{amount} a month is optional insurance and services billed to the card - cancel what you did not choose on purpose.', { amount: money(d.insurance_crc) }));
    }
    if (d.statements_needing_review > 0) {
        advice.push(_t('{n} statement(s) were flagged when imported - these numbers may be incomplete. Upload the PDF again after fixing the card, or send it to be checked.', { n: d.statements_needing_review }));
    }

    // The statement's cost is history; this follows what you owe today, so paying down moves it.
    const projectedInterest = parseFloat(d.projected_interest_crc);
    const projectedCost = projectedInterest + parseFloat(d.insurance_crc);
    const statementCost = parseFloat(d.monthly_cost_crc);
    const projectedLine = `<div class="debt-projection">${_t('At what you owe now, it would be about {amount} a month going forward{change}.', {
        amount: money(projectedCost),
        change: Math.abs(projectedCost - statementCost) >= 1
            ? ` (${projectedCost < statementCost ? _t('{amount} less than the statement', { amount: money(statementCost - projectedCost) }) : _t('{amount} more than the statement', { amount: money(projectedCost - statementCost) })})`
            : '',
    })}</div>`;

    const cardRows = d.cards.map(c => `<tr><td>${escapeHtml(c.name)}</td><td>${money(c.debt_crc)}</td><td>${money(c.interest_crc)}</td></tr>`).join('');
    el.innerHTML = `
        <div class="debt-cost">
            <h3 class="debt-cost-headline">${_t('Your card debt costs {amount} a month', { amount: money(d.monthly_cost_crc) })}</h3>
            <div class="field-hint">${_t('Interest {interest} + insurance {insurance}, from your {period} statements. Dollars converted at ₡{rate}.', {
                interest: money(d.interest_crc), insurance: money(d.insurance_crc), period: d.period, rate: parseFloat(d.usd_to_crc_rate),
            })}</div>
            ${projectedLine}
            <div class="debt-tiles">${tiles.join('')}</div>
            ${advice.length ? `<ul class="debt-advice">${advice.map(a => `<li>${a}</li>`).join('')}</ul>` : ''}
            <table class="statement-table">
                <tr><th>${_t('Card')}</th><th>${_t('Owed (in colones)')}</th><th>${_t('Interest this month')}</th></tr>
                ${cardRows}
            </table>
            <div id="debt-cost-chart"></div>
        </div>`;

    if (d.history.length >= 2) {
        renderChart('#debt-cost-chart', {
            series: [
                { name: _t('Interest'), data: d.history.map(h => Math.round(parseFloat(h.interest_crc))) },
                { name: _t('Insurance'), data: d.history.map(h => Math.round(parseFloat(h.insurance_crc))) },
            ],
            chart: { type: 'bar', stacked: true, height: 240 },
            xaxis: { categories: d.history.map(h => h.period) },
            yaxis: { labels: { formatter: (v) => v.toLocaleString(I18N.locale()) } },
            dataLabels: { enabled: false },
            colors: ['#EF4444', '#F59E0B'],
        });
    } else {
        document.getElementById('debt-cost-chart').innerHTML =
            `<p class="field-hint">${_t('Upload more months of statements to see the trend - the goal is for this bar to shrink.')}</p>`;
    }
}

function renderCards(cards) {
    const container = document.getElementById('cards-grid');

    if (cards.length === 0) {
        container.innerHTML = `
            <div class="cards-empty">
                <div class="cards-empty-icon">💳</div>
                <div class="cards-empty-text">${_t('No cards yet')}</div>
                <button class="btn btn-primary" onclick="showAddCardModal()">${_t('Add Your First Card')}</button>
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
                    ${card.card_type !== 'debit' ? `<button class="card-action-btn" onclick="event.stopPropagation(); showPayoffPlan(${card.id})" title="${_t('Payoff Plan')}">💰</button>` : ''}
                    ${card.cutoff_day ? `<button class="card-action-btn" onclick="event.stopPropagation(); showBillingCycles(${card.id})" title="${_t('Billing Cycles')}">📅</button>` : ''}
                    <button class="card-action-btn" onclick="event.stopPropagation(); editCard(${card.id})" title="${_t('Edit')}">
                        ✏️
                    </button>
                    <button class="card-action-btn" onclick="event.stopPropagation(); deleteCard(${card.id})" title="${_t('Delete')}">
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
                        ${card.cutoff_day ? `<div class="card-due">${_t('Cuts on the {day}', { day: dayOrdinal(card.cutoff_day) })}</div>` : ''}
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

let currentPayoffStatement = null;
let currentPayoffAvgDays = 0;

function payoffSpendHintHtml(currency, asOf) {
    return _t('Recent average: {amount}/month (last {days} days, not counting Tasa Cero). Leave blank to use it.', {
        amount: `<span class="money-value">${formatCurrency(currentPayoffAvgSpend[currency], currency)}</span>`,
        days: currentPayoffAvgDays,
    }) + installmentsHint(currentPayoffInstallments[currency], asOf, currency);
}

async function showPayoffPlan(cardId) {
    try {
        const card = allCards.find(c => c.id === cardId) || await API.Cards.getById(cardId);
        let data = await API.Cards.getPayoffPlan(cardId);
        currentPayoffCardId = cardId;
        currentPayoffStatement = data.statement;

        // No plan yet but there is a statement: start from the bank's own numbers
        // (balance, interest rate, minimum payment) instead of a blank form.
        let plan = data.plan || {};
        let hint = '';
        if (!data.plan && data.statement) {
            plan = planFromStatement(data.statement, {});
            data = await API.Cards.getPayoffPlan(cardId, plan.balance_as_of);
            hint = _t('Filled in from your {period} statement: balance, interest rate and minimum payment. Change the payment to see what paying more does.', { period: data.statement.period });
        } else if (data.plan && data.statement && (data.statement.as_of || data.statement.cut_date) > data.plan.balance_as_of) {
            hint = `${_t('Your {period} statement is newer than this plan.', { period: data.statement.period })}
                <button type="button" class="btn btn-secondary" onclick="applyStatementToPayoff()">${_t('Update balance and rates from the statement')}</button>`;
        }
        document.getElementById('payoff-statement-hint').innerHTML = hint ? `<p class="field-hint">${hint}</p>` : '';

        currentPayoffAvgSpend = {
            CRC: parseFloat(data.avg_monthly_spend_crc),
            USD: parseFloat(data.avg_monthly_spend_usd),
        };
        currentPayoffInstallments = {
            CRC: data.scheduled_installments_crc.map(parseFloat),
            USD: data.scheduled_installments_usd.map(parseFloat),
        };
        currentPayoffAvgDays = data.avg_based_on_days;

        document.getElementById('payoff-modal-title').textContent = `${card.name} - ${_t('Payoff Plan')}`;
        document.getElementById('payoff-delete-btn').style.display = data.plan ? '' : 'none';

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
            document.getElementById(`payoff-spend-hint-${c}`).innerHTML = payoffSpendHintHtml(currency, plan.balance_as_of);
        }

        renderPayoffProjection();

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-payoff').style.display = 'block';
    } catch (error) {
        console.error('Failed to load payoff plan:', error);
        showNotification(_t('Failed to load payoff plan'), 'error');
    }
}

// A payoff-plan form state taken from a statement. `keep` supplies the payments/spend to
// preserve; with nothing to keep, the monthly payment starts at the statement's minimum.
function planFromStatement(st, keep) {
    const plan = {
        balance_as_of: st.as_of || st.cut_date,
        balance_crc: st.balance_crc, balance_usd: st.balance_usd,
        annual_rate_crc: st.annual_rate_crc, annual_rate_usd: st.annual_rate_usd,
        monthly_payment_crc: st.min_payment_crc, monthly_payment_usd: st.min_payment_usd,
        monthly_spend_crc: null, monthly_spend_usd: null,
    };
    return { ...plan, ...keep };
}

// "Update from statement" in an existing plan: take the new balance, rates and date,
// keep the payment and spending the user chose.
async function applyStatementToPayoff() {
    const st = currentPayoffStatement;
    if (!st) return;
    const keep = {};
    for (const c of ['crc', 'usd']) {
        keep[`monthly_payment_${c}`] = parseFloat(document.getElementById(`payoff-payment-${c}`).value) || 0;
        const spend = document.getElementById(`payoff-spend-${c}`).value;
        keep[`monthly_spend_${c}`] = spend === '' ? null : parseFloat(spend);
    }
    const plan = planFromStatement(st, keep);
    try {
        const data = await API.Cards.getPayoffPlan(currentPayoffCardId, plan.balance_as_of);
        currentPayoffInstallments = {
            CRC: data.scheduled_installments_crc.map(parseFloat),
            USD: data.scheduled_installments_usd.map(parseFloat),
        };
        document.getElementById('payoff-as-of').value = plan.balance_as_of;
        for (const currency of ['CRC', 'USD']) {
            const c = currency.toLowerCase();
            document.getElementById(`payoff-balance-${c}`).value = parseFloat(plan[`balance_${c}`]) || 0;
            document.getElementById(`payoff-rate-${c}`).value = parseFloat(plan[`annual_rate_${c}`]) || 0;
            document.getElementById(`payoff-spend-hint-${c}`).innerHTML = payoffSpendHintHtml(currency, plan.balance_as_of);
        }
        document.getElementById('payoff-statement-hint').innerHTML =
            `<p class="field-hint">${_t('Updated from your {period} statement. Save the plan to keep it.', { period: st.period })}</p>`;
        renderPayoffProjection();
    } catch (error) {
        console.error('Failed to apply statement:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
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
    const money = (v) => `<span class="money-value">${formatCurrency(v, currency)}</span>`;
    return '<br>' + _t('Plus {total} of remaining Tasa Cero cuotas ({first} in {firstMonth}, last one in {lastMonth}).', {
        total: money(total),
        first: money(installments[first]),
        firstMonth: payoffMonthLabel(asOf || formatDateForInput(new Date()), first + 1),
        lastMonth: payoffMonthLabel(asOf || formatDateForInput(new Date()), installments.length),
    });
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
        .toLocaleString(I18N.locale(), { month: 'long', year: 'numeric' });
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
            container.innerHTML = `<p class="field-hint">${_t('Nothing owed in this currency.')}</p>`;
            continue;
        }

        const firstInterest = inputs.balance * inputs.annualRate / 100 / 12;
        const result = simulatePayoff(inputs);
        let headline;

        if (result.months === null) {
            headline = `
                <div class="payoff-headline payoff-bad">${_t('Never paid off at this rate')}</div>
                <p class="payoff-detail">${_t('Each month adds {interest} interest + {spend} new spending{cuotas}, so you need to pay more than {needed}{plusCuotas} just for the balance to start going down.', {
                    interest: money(firstInterest),
                    spend: money(inputs.spend),
                    cuotas: cuotasLeft > 0 ? _t(' + Tasa Cero cuotas ({amount} this month)', { amount: money(inputs.installments[0] || 0) }) : '',
                    needed: money(firstInterest + inputs.spend),
                    plusCuotas: cuotasLeft > 0 ? _t(' plus cuotas') : '',
                })}</p>
            `;
        } else {
            const months = result.months;
            const laterCuotas = inputs.installments.slice(months).reduce((a, b) => a + b, 0);
            headline = `
                <div class="payoff-headline payoff-good">${_t('Paid off by {month}', { month: payoffMonthLabel(asOf, months) })}</div>
                ${laterCuotas > 0 ? `<p class="payoff-detail">${_t('After that, only 0% Tasa Cero cuotas are left ({amount} until {month}) - no more interest.', {
                    amount: money(laterCuotas),
                    month: payoffMonthLabel(asOf, inputs.installments.length),
                })}</p>` : ''}
                <p class="payoff-detail">${_tp(months, '{n} payment', '{n} payments')} -
                ${_t('{amount} total interest', { amount: money(result.totalInterest) })}
                ${inputs.payment > 0 ? _t('({pct}% of what you pay toward the debt)', { pct: Math.round(result.totalInterest / (inputs.balance + result.totalInterest) * 100) }) : ''}.</p>
            `;
        }

        const targets = [6, 12, 24].map(n => `
            <li>${_t('{n} months: {amount}/month', { n, amount: money(paymentToClearIn(n, inputs)) })}</li>
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

        const keeping = inputs.spendIsAverage
            ? (cuotasLeft > 0 ? _t('To be debt-free in (keeping your average spending, cuotas included):') : _t('To be debt-free in (keeping your average spending):'))
            : (cuotasLeft > 0 ? _t('To be debt-free in (keeping this spending, cuotas included):') : _t('To be debt-free in (keeping this spending):'));

        container.innerHTML = `
            ${headline}
            <p class="payoff-detail">${keeping}</p>
            <ul class="payoff-targets">${targets}</ul>
            <details class="payoff-schedule">
                <summary>${_t('Month-by-month')}</summary>
                <table>
                    <thead><tr><th>${_t('Month')}</th><th>${_t('New Charges')}</th><th>${_t('Interest')}</th><th>${_t('Payment')}</th><th>${_t('Owed After')}</th></tr></thead>
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
        showNotification(_t('Payoff plan saved'), 'success');
        if (currentView === 'budgets') await loadBudgets();
        if (currentView === 'debt') await loadDebt();
    } catch (error) {
        console.error('Failed to save payoff plan:', error);
        showNotification(_t('Failed to save payoff plan: {error}', { error: _t(error.message) }), 'error');
    }
}

async function deletePayoffPlan() {
    if (!confirm(_t('Delete this payoff plan?'))) return;

    try {
        await API.Cards.deletePayoffPlan(currentPayoffCardId);
        closeModal();
        showNotification(_t('Payoff plan deleted'), 'success');
        if (currentView === 'budgets') await loadBudgets();
        if (currentView === 'debt') await loadDebt();
    } catch (error) {
        console.error('Failed to delete payoff plan:', error);
        showNotification(_t('Failed to delete payoff plan'), 'error');
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
        showNotification(_t('Failed to load transactions'), 'error');
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
        return `<span class="transaction-totals-item"><strong class="money-value">${formatCurrency(total, currency)}</strong> ${_tp(count, 'across {n} transaction', 'across {n} transactions', { n: count })} (${currency})</span>`;
    }).join('');
}

function renderTransactionPagination(total, page) {
    const container = document.getElementById('transaction-pagination');
    const pageCount = Math.max(1, Math.ceil(total / TRANSACTIONS_PAGE_SIZE));
    const start = total === 0 ? 0 : page * TRANSACTIONS_PAGE_SIZE + 1;
    const end = Math.min(total, (page + 1) * TRANSACTIONS_PAGE_SIZE);

    container.innerHTML = `
        <span class="page-info">${_t('Showing {start}-{end} of {total}', { start, end, total })}</span>
        <button ${page <= 0 ? 'disabled' : ''} onclick="loadTransactions(currentFilters, ${page - 1})">${_t('Previous')}</button>
        <span class="page-info">${_t('Page {page} of {pages}', { page: page + 1, pages: pageCount })}</span>
        <button ${page >= pageCount - 1 ? 'disabled' : ''} onclick="loadTransactions(currentFilters, ${page + 1})">${_t('Next')}</button>
    `;
}

function renderTransactionsTable(transactions) {
    const container = document.getElementById('transactions-table');

    if (transactions.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No transactions found')}</p>`;
        return;
    }

    container.innerHTML = `
        <div class="transaction-table-row header">
            <div>${_t('Date')}</div>
            <div>${_t('Merchant')}</div>
            <div>${_t('Category')}</div>
            <div>${_t('Card')}</div>
            <div>${_t('Amount')}</div>
            <div>${_t('Type')}</div>
            <div>${_t('Actions')}</div>
        </div>
        ${transactions.map(t => `
            <div class="transaction-table-row">
                <div class="transaction-date">${formatDate(t.date)}${
                    t.date > formatDateForInput(new Date()) ? `<span class="badge badge-primary upcoming-badge">${_t('Upcoming')}</span>` : ''}</div>
                <div>${escapeHtml(t.commerce_name || _t('Unknown'))}</div>
                <div>
                    <select class="transaction-category-select"
                            onchange="updateTransactionCategory(${t.id}, this.value)">
                        <option value="" ${!t.category_id ? 'selected' : ''}>${_t('Uncategorized')}</option>
                        ${allCategories.map(c =>
                            `<option value="${c.id}" ${c.id === t.category_id ? 'selected' : ''}>${escapeHtml(_tc(c.name))}</option>`
                        ).join('')}
                    </select>
                </div>
                <div>
                    <select class="transaction-card-select"
                            onchange="updateTransactionCard(${t.id}, this.value)">
                        <option value="" ${!t.card_id ? 'selected' : ''}>${_t('No card')}</option>
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
                        ${escapeHtml(_t(t.transaction_type))}
                    </span>
                </div>
                <div class="transaction-actions">
                    ${!t.installment_plan_id ? `
                        <button class="icon-btn" onclick="splitTransactionIntoInstallments(${t.id})" title="${_t('Split into installments (Tasa Cero)')}">
                            📆
                        </button>
                    ` : ''}
                    <button class="icon-btn" onclick="deleteTransaction(${t.id})" title="${_t('Delete')}">
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
        showNotification(_t('Category updated'), 'success');
    } catch (error) {
        console.error('Failed to update category:', error);
        showNotification(_t('Failed to update category'), 'error');
    }
}

async function updateTransactionCard(transactionId, cardId) {
    try {
        await API.Transactions.update(transactionId, {
            card_id: cardId || null
        });
        showNotification(_t('Card updated'), 'success');
    } catch (error) {
        console.error('Failed to update card:', error);
        showNotification(_t('Failed to update card'), 'error');
    }
}

async function deleteTransaction(id) {
    if (!confirm(_t('Are you sure you want to delete this transaction?'))) return;

    try {
        await API.Transactions.delete(id);
        showNotification(_t('Transaction deleted'), 'success');
        await loadTransactions(currentFilters, currentPage);
    } catch (error) {
        console.error('Failed to delete transaction:', error);
        showNotification(_t('Failed to delete transaction'), 'error');
    }
}

// ---- Add a transaction by hand ----

function showAddTransactionModal() {
    document.getElementById('transaction-form').reset();
    document.getElementById('tx-date').value = formatDateForInput(new Date());

    document.getElementById('tx-card').innerHTML = `<option value="">${_t('No card')}</option>` +
        allCards.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    document.getElementById('tx-category').innerHTML = `<option value="">${_t('Automatic (by rules or card default)')}</option>` +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(_tc(c.name))}</option>`).join('');

    document.getElementById('modal-overlay').style.display = 'block';
    document.getElementById('modal-transaction').style.display = 'block';
    document.getElementById('tx-merchant').focus();
}

// A card that only handles one currency picks it, so the pair can't be mismatched.
function onTransactionCardChange() {
    const card = allCards.find(c => c.id === parseInt(document.getElementById('tx-card').value));
    if (!card) return;
    if (card.supports_crc && !card.supports_usd) document.getElementById('tx-currency').value = 'CRC';
    if (card.supports_usd && !card.supports_crc) document.getElementById('tx-currency').value = 'USD';
}

async function saveTransaction(event) {
    event.preventDefault();

    const amount = parseFloat(document.getElementById('tx-amount').value);
    if (isNaN(amount) || amount <= 0) {
        showNotification(_t('Enter an amount greater than 0'), 'error');
        return;
    }

    const cardId = document.getElementById('tx-card').value;
    const categoryId = document.getElementById('tx-category').value;
    const data = {
        date: document.getElementById('tx-date').value,
        amount,
        currency: document.getElementById('tx-currency').value,
        commerce_name: document.getElementById('tx-merchant').value.trim(),
        transaction_type: document.getElementById('tx-type').value,
        card_id: cardId ? parseInt(cardId) : null,
        category_id: categoryId ? parseInt(categoryId) : null,
        notes: document.getElementById('tx-notes').value.trim() || null,
    };

    try {
        await API.Transactions.create(data);
        closeModal();
        showNotification(_t('Transaction added'), 'success');
        // A future-dated one is hidden by the default "Until Today" scope - show everything so it isn't "lost".
        if (data.date > formatDateForInput(new Date()) && !showUpcomingTransactions) {
            setTransactionsScope(true);
        } else {
            await loadTransactions(currentFilters, 0);
        }
    } catch (error) {
        console.error('Failed to add transaction:', error);
        showNotification(_t('Failed to add transaction: {error}', { error: _t(error.message) }), 'error');
    }
}

function showFilters() {
    const panel = document.getElementById('transaction-filters');
    panel.style.display = panel.style.display === 'none' ? 'grid' : 'none';
}

function populateTransactionFilterOptions() {
    const categorySelect = document.getElementById('filter-category');
    const previousCategory = categorySelect.value;
    categorySelect.innerHTML = `<option value="">${_t('All')}</option>` +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(_tc(c.name))}</option>`).join('');
    categorySelect.value = previousCategory;

    const cardSelect = document.getElementById('filter-card');
    const previousCard = cardSelect.value;
    cardSelect.innerHTML = `<option value="">${_t('All')}</option>` +
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
let analyticsRangeInitialized = false;
let cachedOldestTransactionDate = null;

// ApexCharts ships only English UI strings in the main bundle (toolbar menu, tooltips),
// so the Spanish ones are supplied here.
const APEX_ES_LOCALE = {
    name: 'es',
    options: {
        toolbar: {
            exportToSVG: 'Descargar SVG',
            exportToPNG: 'Descargar PNG',
            exportToCSV: 'Descargar CSV',
            menu: 'Menú',
            selection: 'Selección',
            selectionZoom: 'Selección y zoom',
            zoomIn: 'Acercar',
            zoomOut: 'Alejar',
            pan: 'Desplazar',
            reset: 'Restablecer zoom',
        },
    },
};

function renderChart(containerId, options) {
    // Charts don't replace themselves on repeat renders by default, so
    // without clearing the container first, switching tabs/filters stacks
    // a new chart on top of the old one every time.
    const el = document.querySelector(containerId);
    el.innerHTML = '';

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    // English is ApexCharts' built-in locale; passing a `locales` list replaces the built-ins,
    // so the custom list is only supplied when it is actually needed.
    const localeOptions = I18N.lang() === 'es' ? { locales: [APEX_ES_LOCALE], defaultLocale: 'es' } : {};
    const themedOptions = {
        ...options,
        theme: { mode: isDark ? 'dark' : 'light', ...(options.theme || {}) },
        chart: { background: 'transparent', ...localeOptions, ...(options.chart || {}) },
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
            `<p class="empty-state-text">${_t('Failed to load the forecast')}</p>`;
    }
}

function renderMonthForecast(f) {
    // Forecasts are estimates - whole colones, no false precision.
    const crc = (v) => `<span class="money-value">${v < 0 ? '-' : ''}₡${Math.round(Math.abs(v)).toLocaleString(I18N.locale())}</span>`;
    const num = parseFloat;
    const monthLabel = (ym, opts = { month: 'long' }) => {
        const [y, m] = ym.split('-').map(Number);
        return new Date(y, m - 1, 1).toLocaleString(I18N.locale(), opts);
    };
    const monthName = monthLabel(f.month);
    const left = num(f.projected_left);
    const debt = num(f.total_debt);

    // Usual-month range, e.g. "Aug–Sep".
    let usual = _t('your usual month');
    if (f.history_months > 0) {
        const [y, m] = f.month.split('-').map(Number);
        const last = `${new Date(y, m - 2, 1).getFullYear()}-${String(new Date(y, m - 2, 1).getMonth() + 1).padStart(2, '0')}`;
        const short = { month: 'short' };
        usual = f.history_months === 1
            ? _t('your usual month ({month})', { month: monthLabel(f.history_start, short) })
            : _t('your usual month ({from}–{to} average)', { from: monthLabel(f.history_start, short), to: monthLabel(last, short) });
    }

    document.getElementById('forecast-caption').textContent = `(${monthName})`;

    const leftEl = document.getElementById('forecast-left');
    leftEl.innerHTML = left < 0 ? _t('{amount} short', { amount: crc(-left) }) : _t('{amount} left', { amount: crc(left) });
    leftEl.classList.toggle('budget-over', left < 0);
    document.getElementById('forecast-sentence').innerHTML = left < 0
        ? _t("If the rest of {month} goes like {pace}, you'll spend <strong>{amount} more than you earn</strong>.", { month: monthName, pace: f.history_months ? _t('your usual month') : _t('it has so far'), amount: crc(-left) })
        : _t("If the rest of {month} goes like {pace}, you'll end with <strong>{amount} to spare</strong>.", { month: monthName, pace: f.history_months ? _t('your usual month') : _t('it has so far'), amount: crc(left) });
    document.getElementById('forecast-equation').innerHTML = `
        <div class="budget-eq-row"><span>${_t('Expected income')}</span>${crc(num(f.income_base))}</div>
        <div class="budget-eq-row"><span>− ${_t('Likely spending')}</span>${crc(num(f.projected_spend))}</div>
        ${debt > 0 ? `<div class="budget-eq-row"><span>− ${_t('Card debt payment')}</span>${crc(debt)}</div>` : ''}
        <div class="budget-eq-row budget-eq-total"><span>${left < 0 ? _t('= Short at month end') : _t('= Left at month end')}</span>${crc(left)}</div>
    `;

    // How much to trust it: pace share grows with the month.
    const pacePct = Math.round(num(f.pace_weight) * 100);
    document.getElementById('forecast-confidence').innerHTML = f.history_months > 0 ? `
        <div class="forecast-confidence-text">
            <strong>${_t('Day {day} of {days}.', { day: f.days_elapsed, days: f.days_in_month })}</strong>
            ${_t("This forecast is <strong>{usualPct}% based on {usual}</strong> and {pacePct}% on how you've spent so far in {month}.", { usualPct: 100 - pacePct, usual, pacePct, month: monthName })}
            ${pacePct < 40 ? _t(`It's early, so treat it as "what happens if this month looks like the last ones" - it gets more accurate as {month} goes on.`, { month: monthName }) : _t("It's leaning on this month's real spending now, so it should be fairly close.")}
        </div>
        <div class="forecast-confidence-bar" title="${_t("{usualPct}% usual month, {pacePct}% this month's pace", { usualPct: 100 - pacePct, pacePct })}">
            <span class="forecast-conf-usual" style="width: ${100 - pacePct}%"></span>
            <span class="forecast-conf-pace" style="width: ${pacePct}%"></span>
        </div>
        <div class="forecast-confidence-labels"><span>${_t('Your usual month')}</span><span>${_t("This month's pace")}</span></div>
    ` : `<div class="forecast-confidence-text"><strong>${_t('Day {day} of {days}.', { day: f.days_elapsed, days: f.days_in_month })}</strong> ${_t("There's no full past month to compare with yet, so this is based only on how you've spent so far in {month}.", { month: monthName })}</div>`;

    const statusText = (l) => {
        const projected = num(l.projected);
        const budget = l.budget === null ? null : num(l.budget);
        switch (l.status) {
            case 'over': return `<span class="forecast-status status-over">${_t('⛔ Already {amount} over budget', { amount: crc(num(l.spent_so_far) - budget) })}</span>`;
            case 'at_risk': return `<span class="forecast-status status-risk">${_t('⚠ Likely to go {amount} over', { amount: crc(projected - budget) })}</span>`;
            case 'on_track': return budget - projected < Math.max(1000, budget * 0.01)
                ? `<span class="forecast-status status-ok">${_t('✓ Right at budget')}</span>`
                : `<span class="forecast-status status-ok">${_t('✓ On track, about {amount} to spare', { amount: crc(budget - projected) })}</span>`;
            default: return `<span class="forecast-status status-none">${_t('No budget set')}</span>`;
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
            restHow = _t("You usually spend {typical} here in a month and few, larger purchases (like bills) make the daily pace meaningless, so it's your usual month minus what you've already spent.", { typical: crc(typical) });
        } else if (l.basis === 'pace') {
            restHow = _t("No past month to compare with, so it's this month's pace: {pace} a month at the rate you're going.", { pace: crc(num(l.pace_month)) });
        } else {
            restHow = `${_t('A mix of two guesses:')}
                <ul>
                    <li>${_t('<strong>Your usual month:</strong> you typically spend {typical} → {rest} still to go <span class="forecast-weight">(counts {pct}%)</span>', { typical: crc(typical), rest: crc(num(l.rest_from_typical)), pct: 100 - w })}</li>
                    <li>${_t(`<strong>This month's pace:</strong> at your current rate it'd be {pace} for the month → {rest} still to go <span class="forecast-weight">(counts {pct}%)</span>`, { pace: crc(num(l.pace_month)), rest: crc(num(l.rest_from_pace)), pct: w })}</li>
                </ul>`;
        }

        return `
            <div class="forecast-explain">
                <div class="budget-eq-row"><span>${_t('Spent so far')}</span>${crc(spent)}</div>
                <div class="budget-eq-row"><span>+ ${_t('Expected rest of month')}</span>${crc(rest)}</div>
                <div class="forecast-explain-how">${restHow}</div>
                ${scheduled > 0 ? `<div class="budget-eq-row"><span>+ ${_t('Tasa Cero cuotas still to be charged')}</span>${crc(scheduled)}</div>` : ''}
                <div class="budget-eq-row budget-eq-total"><span>= ${_t('Likely total')}</span>${crc(projected)}</div>
                ${budget !== null ? `<div class="budget-eq-row"><span>${_t('Budget (after card debt)')}</span>${crc(budget)}</div>` : ''}
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
            { cls: 'forecast-spent', value: spent, title: _t('Spent so far: {amount}', { amount: `₡${Math.round(spent).toLocaleString(I18N.locale())}` }) },
            { cls: 'forecast-rest', value: rest, title: _t('Expected rest of month: {amount}', { amount: `₡${Math.round(rest).toLocaleString(I18N.locale())}` }) },
            { cls: 'forecast-cuotas', value: scheduled, title: _t('Tasa Cero cuotas still to be charged: {amount}', { amount: `₡${Math.round(scheduled).toLocaleString(I18N.locale())}` }) },
        ].filter(seg => seg.value > 0);
        return `
            <details class="forecast-line">
                <summary>
                    <span class="budget-category">
                        <span class="forecast-chevron">▸</span>
                        <span class="category-icon">${escapeHtml(l.category_icon || '')}</span>
                        ${escapeHtml(_tc(l.category_name))}
                    </span>
                    <span class="forecast-bar">
                        ${segments.map(seg => `<span class="${seg.cls}" style="width: ${seg.value / scale * 100}%" title="${seg.title}"></span>`).join('')}
                        ${budget !== null ? `<span class="forecast-tick" style="left: ${budget / scale * 100}%" title="${_t('Budget: {amount}', { amount: `₡${Math.round(budget).toLocaleString(I18N.locale())}` })}"></span>` : ''}
                    </span>
                    <span class="forecast-numbers">
                        <span>${_t('Likely {amount}', { amount: crc(projected) })}${budget !== null ? _t(' of {amount} budget', { amount: crc(budget) }) : ''}</span>
                        ${statusText(l)}
                    </span>
                </summary>
                ${explain(l)}
            </details>
        `;
    };

    const groups = [
        { title: _t('⚠ Needs attention'), lines: f.lines.filter(l => l.status === 'over' || l.status === 'at_risk') },
        { title: _t('✓ On track'), lines: f.lines.filter(l => l.status === 'on_track') },
        { title: _t('No budget'), lines: f.lines.filter(l => l.status === 'no_budget'),
          hint: _t('Not in any budget, but still counted in your likely spending above.') },
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
            API.Analytics.getSpendingByCard({ start_date, end_date }),
        ]);

        renderDailySpendingChart(dailyCrc, dailyUsd);
        renderMonthlyTrendsChart(monthlyData);
        renderCategoryPieChart(categoryCrc, '#chart-category-pie-crc', 'CRC');
        renderCategoryPieChart(categoryUsd, '#chart-category-pie-usd', 'USD');
        renderTopMerchantsChart(merchantsCrc, '#chart-top-merchants-crc', 'CRC');
        renderTopMerchantsChart(merchantsUsd, '#chart-top-merchants-usd', 'USD');
        renderSpendingByCardChart(cardData);
    } catch (error) {
        console.error('Failed to load analytics:', error);
        showNotification(_t('Failed to load analytics'), 'error');
    }
}

function applyAnalyticsFilters() {
    loadAnalytics({
        start_date: document.getElementById('analytics-start-date').value,
        end_date: document.getElementById('analytics-end-date').value,
    });
}

function clearAnalyticsFilters() {
    setAnalyticsPreset('month');   // back to the default range
}

async function setAnalyticsPreset(preset) {
    analyticsRangeInitialized = true;
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
    await loadAnalytics({ start_date: start, end_date: end });
}

function renderCategoryPieChart(data, containerId, currency) {
    if (data.length === 0) {
        document.querySelector(containerId).innerHTML = `<p class="empty-state-text">${_t('No {currency} spending in this range', { currency })}</p>`;
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
        labels: data.map(d => _tc(d.category_name)),
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
            { title: { text: 'CRC' }, labels: { formatter: (v) => v.toLocaleString(I18N.locale()) } },
            { opposite: true, title: { text: 'USD' }, labels: { formatter: (v) => v.toLocaleString(I18N.locale()) } },
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
        document.querySelector(containerId).innerHTML = `<p class="empty-state-text">${_t('No {currency} spending in this range', { currency })}</p>`;
        return;
    }

    renderChart(containerId, {
        series: [{
            name: _t('Spent ({currency})', { currency }),
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

function renderSpendingByCardChart(data) {
    renderChart("#chart-spending-by-card", {
        series: [
            { name: _t('Spent (CRC)'), data: data.map(d => parseFloat(d.spent_crc)) },
            { name: _t('Spent (USD)'), data: data.map(d => parseFloat(d.spent_usd)) }
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
        // CRC amounts dwarf USD ones, so each currency gets its own axis (CRC left,
        // USD right) - on a shared axis the USD bars are invisible.
        yaxis: [
            {
                seriesName: _t('Spent (CRC)'),
                title: { text: 'CRC', style: { color: '#4F46E5' } },
                labels: { formatter: (val) => val.toLocaleString(I18N.locale()) }
            },
            {
                seriesName: _t('Spent (USD)'),
                opposite: true,
                title: { text: 'USD', style: { color: '#10B981' } },
                labels: { formatter: (val) => val.toLocaleString(I18N.locale()) }
            }
        ],
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
        showNotification(_t('Failed to load categories'), 'error');
    }
}

function renderCategories(categories) {
    const container = document.getElementById('categories-list');

    if (categories.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No categories yet')}</p>`;
        return;
    }

    container.innerHTML = categories.map(cat => `
        <div class="category-item">
            <div class="category-info">
                <div class="category-color-dot" style="background-color: ${safeColor(cat.color)}"></div>
                <div class="category-icon">${escapeHtml(cat.icon)}</div>
                <div class="category-name">${escapeHtml(_tc(cat.name))}</div>
            </div>
            <div class="category-actions">
                <button class="icon-btn" onclick="editCategory(${cat.id})" title="${_t('Edit')}">✏️</button>
                <button class="icon-btn" onclick="deleteCategory(${cat.id})" title="${_t('Delete')}">🗑️</button>
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
        showNotification(_t('Failed to load settings'), 'error');
    }
}

function renderEmailSources(sources) {
    const container = document.getElementById('email-sources-list');

    if (sources.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No email sources configured')}</p>`;
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
    const lastSync = status.last_sync ? formatDate(status.last_sync, true) : _t('Never');
    document.getElementById('last-sync-time').textContent = _t('Last sync: {when}', { when: lastSync });
}

function reportSyncResult(result) {
    if (!result.success) {
        showNotification(_t((result.errors && result.errors[0]) || result.message), 'error');
        return;
    }
    showNotification(
        _t('{new} new, {skipped} already had it, from {sources} source(s)', { new: result.new_transactions, skipped: result.skipped_duplicates, sources: result.sources_synced }),
        'success'
    );
}

async function triggerSync() {
    const btn = document.getElementById('btn-sync-now');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    setLabel(btn, _t('Syncing...'));
    try {
        showNotification(_t('Sync started - this can take a minute...'), 'info');
        const result = await API.Sync.triggerSync();
        reportSyncResult(result);
        await loadSettings();
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Sync failed:', error);
        showNotification(_t('Sync failed: {error}', { error: _t(error.message) }), 'error');
    } finally {
        btn.disabled = false;
        setLabel(btn, originalLabel);
    }
}

async function triggerSyncRange() {
    const startDate = document.getElementById('sync-range-start').value;
    const endDate = document.getElementById('sync-range-end').value;
    if (!startDate || !endDate) {
        showNotification(_t('Pick a start and end date first'), 'error');
        return;
    }

    const btn = document.getElementById('btn-sync-range');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    setLabel(btn, _t('Syncing...'));
    try {
        showNotification(_t('Sync started - this can take a minute...'), 'info');
        const result = await API.Sync.triggerSyncRange(startDate, endDate);
        reportSyncResult(result);
        await loadSettings();
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Sync failed:', error);
        showNotification(_t('Sync failed: {error}', { error: _t(error.message) }), 'error');
    } finally {
        btn.disabled = false;
        setLabel(btn, originalLabel);
    }
}

async function triggerRecategorize() {
    const btn = document.getElementById('btn-recategorize');
    const originalLabel = btn.textContent;
    btn.disabled = true;
    setLabel(btn, _t('Working...'));
    try {
        const result = await API.Maintenance.recategorize();
        showNotification(_t('Checked {checked}, recategorized {updated}', { checked: result.checked, updated: result.updated }), 'success');
        if (currentView !== 'settings') {
            await showView(currentView);
        }
    } catch (error) {
        console.error('Recategorize failed:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
    } finally {
        btn.disabled = false;
        setLabel(btn, originalLabel);
    }
}

function renderCredentialsStatus(status) {
    const el = document.getElementById('credentials-status');
    if (!el) return;
    if (!status) {
        el.textContent = _t('Could not check the credentials file.');
    } else if (!status.has_credentials) {
        el.textContent = _t('✗ No Google file yet - upload it below to connect Gmail.');
    } else if (!status.has_token) {
        el.textContent = _t('✓ Google file in place. Click "Sync Now" to log in to Gmail.');
    } else {
        el.textContent = _t('✓ Google file in place and Gmail connected.');
    }
}

// ============================================================================
// Bank statements (estado de cuenta PDFs)
// ============================================================================

async function handleStatementFiles(files) {
    const input = document.getElementById('statement-file');
    try {
        for (const file of Array.from(files || [])) {
            try {
                const rows = await API.Statements.upload(file);
                const flagged = rows.filter(r => r.status !== 'ok').length;
                showNotification(
                    flagged
                        ? _t('Read {n} statement(s) from {file} - {flagged} need review', { n: rows.length, file: file.name, flagged })
                        : _t('Read {n} statement(s) from {file}', { n: rows.length, file: file.name }),
                    flagged ? 'info' : 'success'
                );
                // Statements are no longer listed in Settings, so say what's wrong right here.
                rows.filter(r => r.status !== 'ok').forEach(r => {
                    (r.warnings || []).slice(0, 3).forEach(w => showNotification(`${r.card_name || r.account_last4}: ${_t(w)}`, 'error'));
                });
            } catch (error) {
                console.error('Statement upload failed:', error);
                showNotification(_t('{file}: {error}', { file: file.name, error: _t(error.message) }), 'error');
            }
        }
    } finally {
        if (input) input.value = '';
    }
}

function handleStatementDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');
    handleStatementFiles(event.dataTransfer.files);
}

async function handleCredentialsFile(file) {
    if (!file) return;
    try {
        const content = await file.text();
        const result = await API.Credentials.upload(content);
        showNotification(
            result.token_removed
                ? _t('Credentials replaced - click "Sync Now" to log in again')
                : _t('Credentials saved - click "Sync Now" to log in to Gmail'),
            'success'
        );
        renderCredentialsStatus(await API.Credentials.getStatus());
    } catch (error) {
        console.error('Credentials upload failed:', error);
        showNotification(_t(error.message), 'error');
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
    setLabel(btn, _t('Working...'));
    try {
        await API.Maintenance.reconnectGmail();
        showNotification(_t('Done - click "Sync Now" to log in to Gmail again'), 'success');
    } catch (error) {
        console.error('Reconnect failed:', error);
        showNotification(_t('Failed: {error}', { error: _t(error.message) }), 'error');
    } finally {
        btn.disabled = false;
        setLabel(btn, originalLabel);
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
    document.getElementById('modal-transaction').style.display = 'none';
    document.getElementById('modal-payoff').style.display = 'none';
    currentCard = null;
    currentCategory = null;
    splitSourceTransaction = null;
}

function showAddCardModal() {
    currentCard = null;
    document.getElementById('card-modal-title').textContent = _t('Add Card');
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
    select.innerHTML = `<option value="">${_t('None')}</option>`;

    allCategories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = `${cat.icon} ${_tc(cat.name)}`;
        select.appendChild(option);
    });
}

async function editCard(id) {
    try {
        const card = await API.Cards.getById(id);
        currentCard = card;

        document.getElementById('card-modal-title').textContent = _t('Edit Card');
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
        showNotification(_t('Failed to load card'), 'error');
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
            showNotification(_t('Card updated'), 'success');
        } else {
            await API.Cards.create(cardData);
            showNotification(_t('Card created'), 'success');
        }

        closeModal();
        await loadCards();
    } catch (error) {
        console.error('Failed to save card:', error);
        showNotification(_t('Failed to save card'), 'error');
    }
}

async function deleteCard(id) {
    if (!confirm(_t('Are you sure you want to delete this card?'))) return;

    try {
        await API.Cards.delete(id);
        showNotification(_t('Card deleted'), 'success');
        await loadCards();
    } catch (error) {
        console.error('Failed to delete card:', error);
        showNotification(_t('Failed to delete card'), 'error');
    }
}

// ============================================================================
// Billing Cycles
// ============================================================================

async function showBillingCycles(cardId) {
    try {
        const card = allCards.find(c => c.id === cardId) || await API.Cards.getById(cardId);
        const cycles = await API.Cards.getBillingCycles(cardId);

        document.getElementById('billing-cycles-title').textContent = `${card.name} - ${_t('Billing Cycles')}`;
        renderBillingCycles(cycles);

        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal-billing-cycles').style.display = 'block';
    } catch (error) {
        console.error('Failed to load billing cycles:', error);
        showNotification(_t('Failed to load billing cycles'), 'error');
    }
}

function renderBillingCycles(cycles) {
    const container = document.getElementById('billing-cycles-list');

    if (cycles.length === 0) {
        container.innerHTML = `<p class="empty-state-text">${_t('No cycles yet')}</p>`;
        return;
    }

    container.innerHTML = cycles.map(c => `
        <div class="billing-cycle-item ${c.is_current ? 'current' : ''}">
            <div class="billing-cycle-dates">
                <strong>${formatDate(c.cycle_start)} - ${formatDate(c.cycle_end)}</strong>
                ${c.is_current ? `<span class="badge badge-primary">${_t('Current')}</span>` : ''}
            </div>
            <div class="billing-cycle-due">${_t('Due {date}', { date: formatDate(c.due_date) })}</div>
            <div class="billing-cycle-totals">
                ${parseFloat(c.total_crc) > 0 ? `<span>${formatCurrency(c.total_crc, 'CRC')}</span>` : ''}
                ${parseFloat(c.total_usd) > 0 ? `<span>${formatCurrency(c.total_usd, 'USD')}</span>` : ''}
                <span class="billing-cycle-count">${_tp(c.transaction_count, '{n} txn', '{n} txns')}</span>
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
    categorySelect.innerHTML = `<option value="">${_t('Uncategorized')}</option>` +
        allCategories.map(c => `<option value="${c.id}">${escapeHtml(_tc(c.name))}</option>`).join('');

    const modalTitle = document.querySelector('#modal-installment-plan .modal-header h3');
    const submitBtn = document.querySelector('#installment-plan-form button[type="submit"]');

    if (prefill) {
        modalTitle.textContent = _t('Split Into Installments');
        submitBtn.textContent = _t('Split Transaction');
        document.getElementById('plan-description').value = prefill.commerce_name || '';
        document.getElementById('plan-total-amount').value = prefill.amount;
        document.getElementById('plan-currency').value = prefill.currency;
        document.getElementById('plan-first-month').value = prefill.date.slice(0, 7);
        if (prefill.card_id) cardSelect.value = prefill.card_id;
        if (prefill.category_id) categorySelect.value = prefill.category_id;
    } else {
        modalTitle.textContent = _t('Tasa Cero (Installment Plan)');
        submitBtn.textContent = _t('Create Plan');
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
        showNotification(_t('Failed to load transaction'), 'error');
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
        container.innerHTML = `<p class="empty-state-text">${_t('No installment plans yet')}</p>`;
        return;
    }

    container.innerHTML = plans.map(p => {
        const card = allCards.find(c => c.id === p.card_id);
        return `
            <div class="plan-item">
                <div class="plan-info">
                    <strong>${escapeHtml(p.description)}</strong>
                    <span class="plan-meta">
                        ${_t('{amount} over {n} months ({paid}/{n} paid) - {card}', { amount: formatCurrency(p.total_amount, p.currency), n: p.num_installments, paid: p.installments_paid, card: escapeHtml(card?.name || _t('Unknown card')) })}
                    </span>
                </div>
                <button type="button" class="icon-btn" onclick="deleteInstallmentPlan(${p.id})" title="${_t('Delete plan and its charges')}">🗑️</button>
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
            showNotification(_t('Transaction split into installments'), 'success');
        } else {
            showNotification(_t('Installment plan created'), 'success');
        }

        document.getElementById('installment-plan-form').reset();
        await loadInstallmentPlans();
        if (currentView === 'transactions') {
            await loadTransactions(currentFilters, currentPage);
        }
    } catch (error) {
        console.error('Failed to create installment plan:', error);
        showNotification(_t('Failed to create installment plan'), 'error');
    }
}

async function deleteInstallmentPlan(id) {
    if (!confirm(_t('Delete this plan and all of its generated charges (past and future)?'))) return;

    try {
        await API.InstallmentPlans.delete(id);
        showNotification(_t('Installment plan deleted'), 'success');
        await loadInstallmentPlans();
        if (currentView === 'transactions') {
            await loadTransactions(currentFilters, currentPage);
        }
    } catch (error) {
        console.error('Failed to delete installment plan:', error);
        showNotification(_t('Failed to delete installment plan'), 'error');
    }
}

function showAddCategoryModal() {
    currentCategory = null;
    document.getElementById('category-modal-title').textContent = _t('Add Category');
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

        document.getElementById('category-modal-title').textContent = _t('Edit Category');
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
        showNotification(_t('Failed to load category'), 'error');
    }
}

async function loadCategoryRules(categoryId) {
    try {
        const rules = await API.CategorizationRules.getAll(categoryId);
        renderCategoryRules(rules);
    } catch (error) {
        console.error('Failed to load rules:', error);
        showNotification(_t('Failed to load rules'), 'error');
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
        container.innerHTML = `<p class="empty-state-text">${_t("No rules yet - transactions won't be auto-categorized here.")}</p>`;
        return;
    }

    container.innerHTML = rules.map(r => `
        <div class="rule-item">
            <span class="rule-text">${_t(RULE_MATCH_LABELS[r.match_type] || r.match_type)} "${escapeHtml(r.value)}"</span>
            <button type="button" class="icon-btn" onclick="deleteCategorizationRule(${r.id})" title="${_t('Delete rule')}">🗑️</button>
        </div>
    `).join('');
}

async function addCategorizationRule() {
    const matchType = document.getElementById('new-rule-match-type').value;
    const value = document.getElementById('new-rule-value').value.trim();

    if (!value) {
        showNotification(_t('Enter text for the rule to match'), 'error');
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
        showNotification(_t('Rule added'), 'success');
    } catch (error) {
        console.error('Failed to add rule:', error);
        showNotification(_t('Failed to add rule'), 'error');
    }
}

async function deleteCategorizationRule(ruleId) {
    if (!confirm(_t('Delete this rule?'))) return;

    try {
        await API.CategorizationRules.delete(ruleId);
        await loadCategoryRules(currentCategory.id);
        showNotification(_t('Rule deleted'), 'success');
    } catch (error) {
        console.error('Failed to delete rule:', error);
        showNotification(_t('Failed to delete rule'), 'error');
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
            showNotification(_t('Category updated'), 'success');
        } else {
            await API.Categories.create(categoryData);
            showNotification(_t('Category created'), 'success');
        }

        closeModal();
        await loadCategories();
        await loadInitialData(); // Reload for dropdowns
    } catch (error) {
        console.error('Failed to save category:', error);
        showNotification(_t('Failed to save category'), 'error');
    }
}

async function deleteCategory(id) {
    if (!confirm(_t('Are you sure you want to delete this category?'))) return;

    try {
        await API.Categories.delete(id);
        showNotification(_t('Category deleted'), 'success');
        await loadCategories();
        await loadInitialData();
    } catch (error) {
        console.error('Failed to delete category:', error);
        showNotification(_t('Failed to delete category'), 'error');
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
        showNotification(_t('Email source added'), 'success');
        closeModal();
        await loadSettings();
    } catch (error) {
        console.error('Failed to save email source:', error);
        showNotification(_t('Failed to save email source'), 'error');
    }
}

// Make functions globally accessible
window.showView = showView;
window.triggerSync = triggerSync;
window.triggerSyncRange = triggerSyncRange;
window.triggerRecategorize = triggerRecategorize;
window.triggerReconnectGmail = triggerReconnectGmail;
window.handleCredentialsFile = handleCredentialsFile;
window.handleStatementFiles = handleStatementFiles;
window.submitPayment = submitPayment;
window.downloadSnapshot = downloadSnapshot;
window.copySnapshot = copySnapshot;
window.removeStatement = removeStatement;
window.removePayment = removePayment;
window.handleStatementDrop = handleStatementDrop;
window.applyStatementToPayoff = applyStatementToPayoff;
window.handleCredentialsDrop = handleCredentialsDrop;
window.closeModal = closeModal;
window.showAddCardModal = showAddCardModal;
window.showAddTransactionModal = showAddTransactionModal;
window.onTransactionCardChange = onTransactionCardChange;
window.saveTransaction = saveTransaction;
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
