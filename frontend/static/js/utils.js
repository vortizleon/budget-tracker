// ============================================================================
// Utility Functions
// ============================================================================

/**
 * English ordinal suffix for a day-of-month number (1 -> "st", 18 -> "th")
 * @param {number} day
 * @returns {string}
 */
function ordinalSuffix(day) {
    if (day % 10 === 1 && day % 100 !== 11) return 'st';
    if (day % 10 === 2 && day % 100 !== 12) return 'nd';
    if (day % 10 === 3 && day % 100 !== 13) return 'rd';
    return 'th';
}

/**
 * Format a number as currency
 * @param {number} amount - The amount to format
 * @param {string} currency - Currency code (CRC or USD)
 * @returns {string} Formatted currency string
 */
function formatCurrency(amount, currency) {
    const absAmount = Math.abs(amount);
    const formatted = absAmount.toFixed(2);

    if (currency === 'CRC') {
        return `₡${formatted}`;
    } else if (currency === 'USD') {
        return `$${formatted}`;
    }
    return formatted;
}

/**
 * Format a date string to a readable format
 * @param {string} dateString - ISO date string
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date string
 */
function formatDate(dateString, includeTime = false) {
    if (!dateString) return '';

    const date = new Date(dateString);
    const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    };

    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }

    return date.toLocaleDateString('en-US', options);
}

/**
 * Format a date for input fields (YYYY-MM-DD)
 * @param {Date} date - Date object
 * @returns {string} Formatted date string
 */
function formatDateForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Get relative time string (e.g., "2 days ago")
 * @param {string} dateString - ISO date string
 * @returns {string} Relative time string
 */
function getRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
}

/**
 * Truncate text to a maximum length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
}

/**
 * Get category icon or default
 * @param {object} category - Category object
 * @returns {string} Icon emoji
 */
function getCategoryIcon(category) {
    return category?.icon || '📁';
}

/**
 * Get category color or default
 * @param {object} category - Category object
 * @returns {string} Color hex code
 */
function getCategoryColor(category) {
    return category?.color || '#6B7280';
}

/**
 * Mask card number (show last 4 digits)
 * @param {string} lastFour - Last 4 digits
 * @returns {string} Masked card number
 */
function maskCardNumber(lastFour) {
    if (!lastFour) return '•••• •••• •••• ••••';
    return `•••• •••• •••• ${lastFour}`;
}

/**
 * Calculate percentage
 * @param {number} value - Current value
 * @param {number} total - Total value
 * @returns {number} Percentage
 */
function calculatePercentage(value, total) {
    if (total === 0) return 0;
    return (value / total) * 100;
}

/**
 * Debounce function to limit execution rate
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Show a toast notification - a small, auto-dismissing message in the
 * corner, instead of a blocking browser alert() dialog.
 * @param {string} message - Message to display
 * @param {string} type - Type of notification (success, error, info)
 */
function showNotification(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return; // Defensive - shouldn't happen, but never crash on feedback.

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    // Let the initial styles apply before animating in.
    requestAnimationFrame(() => toast.classList.add('toast-visible'));

    setTimeout(() => {
        toast.classList.remove('toast-visible');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, 3000);
}

/**
 * Get color contrast (light or dark) for text on colored background
 * @param {string} hexColor - Hex color code
 * @returns {string} 'light' or 'dark'
 */
function getColorContrast(hexColor) {
    // Convert hex to RGB
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);

    // Calculate luminance
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

    return luminance > 0.5 ? 'dark' : 'light';
}

/**
 * Group transactions by date
 * @param {Array} transactions - Array of transactions
 * @returns {Object} Transactions grouped by date
 */
function groupTransactionsByDate(transactions) {
    const grouped = {};

    transactions.forEach(transaction => {
        const dateKey = formatDate(transaction.transaction_date);
        if (!grouped[dateKey]) {
            grouped[dateKey] = [];
        }
        grouped[dateKey].push(transaction);
    });

    return grouped;
}

/**
 * Sort transactions by date (newest first)
 * @param {Array} transactions - Array of transactions
 * @returns {Array} Sorted transactions
 */
function sortTransactionsByDate(transactions) {
    return transactions.sort((a, b) => {
        return new Date(b.transaction_date) - new Date(a.transaction_date);
    });
}

/**
 * Filter transactions by search term
 * @param {Array} transactions - Array of transactions
 * @param {string} searchTerm - Search term
 * @returns {Array} Filtered transactions
 */
function filterTransactions(transactions, searchTerm) {
    if (!searchTerm) return transactions;

    const term = searchTerm.toLowerCase();
    return transactions.filter(t => {
        return t.merchant?.toLowerCase().includes(term) ||
               t.description?.toLowerCase().includes(term) ||
               t.category?.name?.toLowerCase().includes(term);
    });
}

/**
 * Get transaction type badge class
 * @param {string} type - Transaction type
 * @returns {string} CSS class name
 */
function getTransactionTypeBadge(type) {
    switch (type) {
        case 'purchase':
            return 'badge-danger';
        case 'payment':
            return 'badge-success';
        case 'refund':
            return 'badge-primary';
        default:
            return 'badge-secondary';
    }
}

/**
 * Get card gradient based on color
 * @param {string} color - Base color hex
 * @returns {string} CSS gradient string
 */
function getCardGradient(color) {
    // Create a subtle gradient from the base color
    return `linear-gradient(135deg, ${color} 0%, ${adjustColorBrightness(color, -20)} 100%)`;
}

/**
 * Adjust color brightness
 * @param {string} hexColor - Hex color code
 * @param {number} percent - Percent to adjust (-100 to 100)
 * @returns {string} Adjusted hex color
 */
function adjustColorBrightness(hexColor, percent) {
    const num = parseInt(hexColor.slice(1), 16);
    const amt = Math.round(2.55 * percent);
    const R = (num >> 16) + amt;
    const G = (num >> 8 & 0x00FF) + amt;
    const B = (num & 0x0000FF) + amt;

    return '#' + (
        0x1000000 +
        (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
        (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
        (B < 255 ? (B < 1 ? 0 : B) : 255)
    ).toString(16).slice(1);
}

/**
 * Get default card colors
 * @returns {Array} Array of color hex codes
 */
function getDefaultCardColors() {
    return [
        '#4F46E5', // Indigo
        '#7C3AED', // Purple
        '#DB2777', // Pink
        '#DC2626', // Red
        '#EA580C', // Orange
        '#D97706', // Amber
        '#059669', // Emerald
        '#0891B2', // Cyan
        '#2563EB', // Blue
        '#4338CA', // Violet
    ];
}

/**
 * Validate form field
 * @param {HTMLInputElement} field - Input field
 * @returns {boolean} Is valid
 */
function validateField(field) {
    if (field.hasAttribute('required') && !field.value.trim()) {
        return false;
    }

    if (field.type === 'email' && field.value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(field.value);
    }

    if (field.pattern && field.value) {
        const regex = new RegExp(field.pattern);
        return regex.test(field.value);
    }

    return true;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
