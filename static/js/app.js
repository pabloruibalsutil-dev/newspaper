(() => {
    let currentCategory = "politics";
    let categories = [];
    let refreshTimer = null;
    const REFRESH_MS = 10 * 60 * 1000;

    const $nav = document.getElementById("category-nav");
    const $content = document.getElementById("news-content");
    const $date = document.getElementById("current-date");
    const $lastUpdate = document.getElementById("last-update");
    const root = document.documentElement;

    function formatDate() {
        return new Date().toLocaleDateString("en-US", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });
    }

    function timeAgo(dateStr) {
        if (!dateStr) return "";
        const diff = Date.now() - new Date(dateStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return "Just now";
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        const days = Math.floor(hrs / 24);
        return `${days}d ago`;
    }

    function applyTheme(theme) {
        if (!theme) return;
        root.style.setProperty("--bg", theme.bg || "#ffffff");
        root.style.setProperty("--nav-bg", theme.navBg || "rgba(255,255,255,0.92)");
        root.style.setProperty("--hero-bg", theme.heroBg || "#111111");
        root.style.setProperty("--hero-text", theme.heroText || "#ffffff");
        root.style.setProperty("--card-bg", theme.cardBg || "#111111");
        root.style.setProperty("--card-text", theme.cardText || "#ffffff");
        root.style.setProperty("--placeholder-bg", theme.placeholderBg || "#222222");
        root.style.setProperty("--divider-line", theme.dividerLine || "#dddddd");
    }

    function escapeHTML(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function articleReadUrl(article) {
        if (!article.url || article.url === "#") return "#";
        return `/read?url=${encodeURIComponent(article.url)}&cat=${currentCategory}`;
    }

    function buildHeroCard(article) {
        const title = escapeHTML(article.title);
        const desc = escapeHTML(article.description);
        const source = escapeHTML(article.source);
        const href = articleReadUrl(article);

        const imageHTML = article.image
            ? `<div class="hero-image-wrapper"><img class="hero-image" src="${article.image}" alt="" loading="lazy" onerror="this.parentElement.outerHTML='<div class=\\'hero-placeholder\\'>&#9783;</div>'"></div>`
            : `<div class="hero-placeholder">&#9783;</div>`;

        return `
            <a href="${href}" class="hero-card fade-in">
                ${imageHTML}
                <div class="hero-body">
                    <span class="hero-label">Featured</span>
                    <h2 class="hero-title">${title}</h2>
                    <p class="hero-description">${desc}</p>
                    <span class="hero-meta">${source} &middot; ${timeAgo(article.publishedAt)}</span>
                </div>
            </a>`;
    }

    function buildNewsCard(article) {
        const title = escapeHTML(article.title);
        const desc = escapeHTML(article.description);
        const source = escapeHTML(article.source);
        const href = articleReadUrl(article);

        const imageHTML = article.image
            ? `<div class="card-image-wrapper"><img class="card-image" src="${article.image}" alt="" loading="lazy" onerror="this.parentElement.outerHTML='<div class=\\'card-placeholder\\'>&#9783;</div>'"></div>`
            : `<div class="card-placeholder">&#9783;</div>`;

        return `
            <a href="${href}" class="news-card fade-in">
                ${imageHTML}
                <div class="card-body">
                    <span class="card-source">${source}</span>
                    <h3 class="card-title">${title}</h3>
                    <p class="card-description">${desc}</p>
                    <span class="card-meta">${timeAgo(article.publishedAt)}</span>
                </div>
            </a>`;
    }

    function switchCategory(catId) {
        if (catId === currentCategory) return;
        currentCategory = catId;

        const cat = categories.find((c) => c.id === catId);
        if (cat && cat.theme) applyTheme(cat.theme);

        $nav.querySelectorAll(".nav-btn").forEach((b) => {
            b.classList.toggle("active", b.dataset.cat === catId);
        });

        loadNews();
    }

    async function loadCategories() {
        try {
            const resp = await fetch("/api/categories");
            categories = await resp.json();

            $nav.innerHTML = categories
                .map(
                    (c) =>
                        `<button class="nav-btn${c.id === currentCategory ? " active" : ""}" data-cat="${c.id}">${escapeHTML(c.label)}</button>`
                )
                .join("");

            $nav.querySelectorAll(".nav-btn").forEach((btn) => {
                btn.addEventListener("click", () => switchCategory(btn.dataset.cat));
            });

            const initial = categories.find((c) => c.id === currentCategory);
            if (initial && initial.theme) applyTheme(initial.theme);
        } catch {
            $nav.innerHTML = `<span style="padding:1rem;color:#999;font-size:0.8rem">Could not load categories</span>`;
        }
    }

    async function loadNews() {
        $content.innerHTML = `<div class="loading"><div class="loading-spinner"></div><p>Loading latest news...</p></div>`;

        try {
            const resp = await fetch(`/api/news/${currentCategory}`);
            const data = await resp.json();

            if (!data.articles || data.articles.length === 0) {
                $content.innerHTML = `<div class="loading"><p>No articles available right now.</p></div>`;
                return;
            }

            const hero = data.articles[0];
            const rest = data.articles.slice(1, 9);

            let html = buildHeroCard(hero);
            html += `<div class="section-divider"><span>Latest Stories</span></div>`;
            html += `<div class="news-grid">`;
            rest.forEach((a) => (html += buildNewsCard(a)));
            html += `</div>`;

            $content.innerHTML = html;

            if (data.fetchedAt) {
                $lastUpdate.textContent = `Last updated: ${new Date(data.fetchedAt).toLocaleTimeString()}`;
            }
        } catch {
            $content.innerHTML = `<div class="loading"><p>Failed to load news. Retrying shortly...</p></div>`;
        }
    }

    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(() => loadNews(), REFRESH_MS);
    }

    function init() {
        $date.textContent = formatDate();
        loadCategories();
        loadNews();
        startAutoRefresh();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
