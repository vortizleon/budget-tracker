// ============================================================================
// i18n - English / Spanish
//
// The English source text IS the key: _t('Sync Now') returns the Spanish text from
// locales/es.js when the language is Spanish, and 'Sync Now' otherwise. A missing
// entry just falls back to English, so a half-translated string never breaks the UI.
//
//   _t('Checked {checked}', { checked: 5 })     - {name} placeholders
//   _tp(n, '{n} day ago', '{n} days ago')       - singular / plural
//   _tc(category.name)                          - default category names ("Food" -> "Comida");
//                                                 custom names pass through untouched
//
// The helpers are called _t/_tp/_tc (not t) because `t` is used as a local variable
// (transactions.map(t => ...)) all over app.js and would silently shadow a global t().
//
// Static text in index.html is translated in place: every text node, placeholder,
// title and aria-label is recorded once at startup (with its English original) and
// re-rendered on every language change. Elements marked data-i18n-html are translated
// as a whole (their innerHTML is the key) - use that for sentences with inline tags.
// Content rendered later by JS is NOT touched here; it calls _t() when it is built,
// so user data (merchant names, category names) is never rewritten by accident.
// ============================================================================
(function () {
    'use strict';

    const SUPPORTED = ['en', 'es'];
    const LOCALES = { en: 'en-US', es: 'es-419' };   // es-419: neutral Latin American Spanish
    const STORAGE_KEY = 'lang';
    const dictionaries = { es: window.I18N_ES || {} };

    function detectLanguage() {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (SUPPORTED.includes(saved)) return saved;
        } catch (error) {
            // localStorage unavailable - fall through to the browser language.
        }
        const browser = (navigator.languages && navigator.languages[0]) || navigator.language || 'en';
        return browser.toLowerCase().startsWith('es') ? 'es' : 'en';
    }

    let lang = detectLanguage();

    const normalize = (s) => s.replace(/\s+/g, ' ').trim();

    function lookup(key) {
        const table = dictionaries[lang];
        if (!table) return key;
        if (table[key] !== undefined) return table[key];
        const flat = normalize(key);
        return table[flat] !== undefined ? table[flat] : key;
    }

    function interpolate(text, params) {
        if (!params) return text;
        return text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? params[name] : match));
    }

    function t(key, params) {
        return interpolate(lookup(String(key)), params);
    }

    function tp(n, one, other, params) {
        return t(n === 1 ? one : other, Object.assign({ n }, params));
    }

    // Category names are user data: only the seeded defaults have a "category:<name>"
    // entry, so anything else (including renamed or custom categories) is shown as typed.
    function tc(name) {
        if (!name) return name;
        const key = 'category:' + name;
        const translated = lookup(key);
        return translated === key ? name : translated;
    }

    // ------------------------------------------------------------------
    // Static page translation
    // ------------------------------------------------------------------
    const textRecords = [];    // { node, raw }
    const attrRecords = [];    // { el, attr, raw }
    const htmlRecords = [];    // { el, raw }
    const TRANSLATABLE_ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
    const hasLetters = (s) => /[A-Za-z]{2}/.test(s);

    function collectStatic(root) {
        root.querySelectorAll('[data-i18n-html]').forEach((el) => {
            htmlRecords.push({ el, raw: el.innerHTML });
        });

        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                const parent = node.parentElement;
                if (!parent || !hasLetters(node.nodeValue)) return NodeFilter.FILTER_REJECT;
                if (parent.closest('script, style, textarea, [data-i18n-html], [data-i18n-skip]')) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            },
        });
        while (walker.nextNode()) {
            textRecords.push({ node: walker.currentNode, raw: walker.currentNode.nodeValue });
        }

        root.querySelectorAll('*').forEach((el) => {
            TRANSLATABLE_ATTRS.forEach((attr) => {
                const value = el.getAttribute(attr);
                if (value && hasLetters(value)) attrRecords.push({ el, attr, raw: value });
            });
        });
    }

    function renderStatic() {
        textRecords.forEach(({ node, raw }) => {
            const lead = raw.match(/^\s*/)[0];
            const trail = raw.match(/\s*$/)[0];
            node.nodeValue = lead + lookup(normalize(raw)) + trail;
        });
        attrRecords.forEach(({ el, attr, raw }) => el.setAttribute(attr, lookup(normalize(raw))));
        htmlRecords.forEach(({ el, raw }) => { el.innerHTML = lookup(normalize(raw)); });
    }

    function updateSwitcher() {
        document.querySelectorAll('[data-lang-btn]').forEach((btn) => {
            const active = btn.dataset.langBtn === lang;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-pressed', String(active));
        });
    }

    function setLang(next) {
        if (!SUPPORTED.includes(next) || next === lang) return;
        lang = next;
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (error) {
            // Won't persist across reloads - still works for this session.
        }
        document.documentElement.lang = lang;
        renderStatic();
        updateSwitcher();
        window.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang } }));
    }

    function init() {
        document.documentElement.lang = lang;
        collectStatic(document.body);
        renderStatic();
        updateSwitcher();
    }

    // Registered before app.js's own DOMContentLoaded handler (script order), so the
    // static page is already in the right language before the first view renders.
    document.addEventListener('DOMContentLoaded', init);

    window.I18N = { t, tp, tc, setLang, lang: () => lang, locale: () => LOCALES[lang], SUPPORTED };
    window._t = t;
    window._tp = tp;
    window._tc = tc;
})();
