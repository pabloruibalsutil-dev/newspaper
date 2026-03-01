import hashlib
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import unquote

import requests
import trafilatura
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, abort

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("NEWS_API_KEY", "")
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_MINUTES", "10"))

CATEGORIES = {
    "politics": {
        "label": "Politics",
        "keywords": "European Union OR Westminster OR NATO OR European Commission OR European parliament OR Downing Street OR Brexit OR Elysee OR Bundestag OR prime minister Europe OR EU summit OR UK government",
        "theme": {
            "bg": "#ffffff",
            "navBg": "rgba(255,255,255,0.92)",
            "heroBg": "#111111",
            "heroText": "#ffffff",
            "cardBg": "#111111",
            "cardText": "#ffffff",
            "placeholderBg": "#222222",
            "dividerLine": "#dddddd",
        },
    },
    "technology": {
        "label": "Technology",
        "keywords": "NVIDIA OR AMD OR Intel OR Apple OR Google OR Microsoft OR Samsung OR GPU OR processor OR AI OR semiconductor OR chip",
        "domains": "theverge.com,arstechnica.com,techcrunch.com,wired.com,tomshardware.com,engadget.com,9to5google.com,macrumors.com,videocardz.com,techradar.com",
        "theme": {
            "bg": "#f0f0f0",
            "navBg": "rgba(240,240,240,0.92)",
            "heroBg": "#1a1a2e",
            "heroText": "#ffffff",
            "cardBg": "#e2e2e2",
            "cardText": "#1a1a1a",
            "placeholderBg": "#d5d5d5",
            "dividerLine": "#cccccc",
        },
    },
    "sports": {
        "label": "Sports",
        "keywords": "football OR \"Premier League\" OR \"Champions League\" OR \"La Liga\" OR \"Serie A\" OR Bundesliga OR FIFA OR UEFA OR soccer OR transfer",
        "domains": "bbc.co.uk,skysports.com,goal.com,espn.com,marca.com,90min.com,eurosport.com,theathletic.com,fourfourtwo.com,football-italia.net",
        "theme": {
            "bg": "#f0f7f0",
            "navBg": "rgba(240,247,240,0.92)",
            "heroBg": "#1a3a2a",
            "heroText": "#ffffff",
            "cardBg": "#ddeedd",
            "cardText": "#1a2e1a",
            "placeholderBg": "#c5ddc5",
            "dividerLine": "#bbd4bb",
        },
    },
    "culture": {
        "label": "Culture",
        "keywords": "(PlayStation OR Xbox OR Nintendo OR Steam OR gaming OR \"video game\" OR console OR RPG) OR (movie OR film OR cinema OR \"box office\" OR streaming)",
        "domains": "ign.com,kotaku.com,eurogamer.net,polygon.com,gamespot.com,pushsquare.com,nintendolife.com,hollywoodreporter.com,variety.com,deadline.com",
        "theme": {
            "bg": "#e8f0fb",
            "navBg": "rgba(232,240,251,0.92)",
            "heroBg": "#1b2a4a",
            "heroText": "#ffffff",
            "cardBg": "#d0dfef",
            "cardText": "#1a1a2e",
            "placeholderBg": "#b8ccdf",
            "dividerLine": "#c5d5ee",
        },
    },
}

news_cache = {}
cache_lock = threading.Lock()
last_fetched = {}
article_content_cache = {}
seen_urls = set()


def _call_newsapi(keywords, domains="", page_size=25, sort_by="publishedAt"):
    """Make a single NewsAPI /everything call and return raw article list."""
    params = {
        "q": keywords,
        "sortBy": sort_by,
        "pageSize": page_size,
        "language": "en",
        "apiKey": API_KEY,
    }
    if domains:
        params["domains"] = domains
    resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "ok" and data.get("articles"):
        return data["articles"]
    return []


def _parse_articles(raw_articles, limit=9):
    """Filter, deduplicate, and structure raw NewsAPI articles."""
    articles = []
    for art in raw_articles:
        if len(articles) >= limit:
            break
        art_url = art.get("url", "#")
        title = art.get("title", "")
        if not title or title == "[Removed]":
            continue
        if art_url in seen_urls:
            continue
        seen_urls.add(art_url)
        articles.append({
            "title": title,
            "description": art.get("description", "") or "",
            "url": art_url,
            "image": art.get("urlToImage", "") or "",
            "source": art.get("source", {}).get("name", "Unknown"),
            "publishedAt": art.get("publishedAt", ""),
            "author": art.get("author", "") or "",
            "content": art.get("content", "") or "",
        })
    return articles


def _call_headlines(country, category, page_size=20):
    """Fetch top headlines for a given country and category."""
    params = {
        "country": country,
        "category": category,
        "pageSize": page_size,
        "apiKey": API_KEY,
    }
    resp = requests.get("https://newsapi.org/v2/top-headlines", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "ok" and data.get("articles"):
        return data["articles"]
    return []


def fetch_news_for_category(category_id, category_config):
    """Fetch news using headlines + keyword queries to fill 9 articles."""
    if not API_KEY:
        return generate_placeholder_news(category_id, category_config)

    try:
        articles = []

        headlines_cfg = category_config.get("use_headlines")
        if headlines_cfg and len(articles) < 9:
            raw = _call_headlines(headlines_cfg["country"], headlines_cfg["category"])
            articles.extend(_parse_articles(raw, limit=9))

        if len(articles) < 9:
            remaining = 9 - len(articles)
            domains = category_config.get("domains", "")
            sort_by = category_config.get("sort", "publishedAt")
            raw = _call_newsapi(category_config["keywords"], domains, page_size=25, sort_by=sort_by)
            articles.extend(_parse_articles(raw, limit=remaining))

        if len(articles) < 9:
            return articles or generate_placeholder_news(category_id, category_config)

        return articles

    except Exception as e:
        print(f"[{datetime.now()}] Error fetching {category_id}: {e}")
        return generate_placeholder_news(category_id, category_config)


def generate_placeholder_news(category_id, category_config):
    """Generate placeholder articles when no API key is configured."""
    label = category_config["label"]
    placeholders = []

    headlines = {
        "politics": [
            ("Breaking: Major Policy Reform Announced", "Government officials unveiled a comprehensive reform package today that aims to address key issues facing the nation. The proposal includes significant changes to existing regulations."),
            ("Senate Passes Historic Bill", "In a landmark vote, the senate approved legislation that could reshape the political landscape for years to come."),
            ("Election Results Shake Up Local Government", "Voters turned out in record numbers as several unexpected candidates claimed victory in yesterday's municipal elections."),
            ("International Summit Yields New Agreement", "World leaders gathered for a three-day summit that concluded with a groundbreaking multilateral agreement on trade."),
            ("Supreme Court to Hear Landmark Case", "The highest court has agreed to review a case that could have far-reaching implications for civil rights."),
            ("Governor Signs Executive Order on Education", "The governor signed an executive order today aimed at reforming the state's education system and increasing funding."),
            ("Foreign Policy Debate Intensifies", "Lawmakers from both parties clashed over the direction of foreign policy during a heated committee hearing."),
            ("New Poll Shows Shifting Voter Priorities", "A comprehensive nationwide survey reveals significant changes in what voters consider the most pressing issues."),
            ("Budget Proposal Draws Mixed Reactions", "The latest federal budget proposal has been met with both praise and criticism from different political factions."),
        ],
        "technology": [
            ("AI Breakthrough: New Model Sets Records", "Researchers have unveiled a new artificial intelligence model that surpasses all previous benchmarks in natural language understanding and reasoning."),
            ("Tech Giant Announces Revolutionary Chip", "A major semiconductor company revealed its next-generation processor that promises a quantum leap in computing performance."),
            ("Cybersecurity Alert: Major Vulnerability Found", "Security researchers discovered a critical flaw affecting millions of devices worldwide, prompting an urgent patch release."),
            ("Space Tech Startup Secures Billion-Dollar Contract", "A private space company has won a major government contract to develop next-generation satellite communication systems."),
            ("Electric Vehicle Sales Surge Past Projections", "The electric vehicle market continues to exceed expectations as new models and improved infrastructure drive adoption."),
            ("Open Source Project Reaches Major Milestone", "A widely-used open source framework released a major version update that introduces significant performance improvements."),
            ("Quantum Computing Achieves New Breakthrough", "Scientists have demonstrated quantum advantage in a practical application for the first time, marking a historic achievement."),
            ("Social Media Platform Introduces New Privacy Features", "A leading social media company rolled out enhanced privacy controls following increased regulatory pressure."),
            ("Robotics Company Unveils Humanoid Assistant", "A robotics firm demonstrated its latest humanoid robot capable of performing complex household and workplace tasks."),
        ],
        "sports": [
            ("Championship Final Goes to Overtime", "An electrifying championship final kept fans on the edge of their seats as both teams battled through overtime in a historic contest."),
            ("Star Player Signs Record-Breaking Contract", "One of the league's most valuable players has agreed to a record-breaking multi-year contract extension worth hundreds of millions."),
            ("Olympic Committee Announces Host City", "The International Olympic Committee revealed the host city for the upcoming games, sparking celebrations across the winning nation."),
            ("Underdog Team Stuns Defending Champions", "In one of the biggest upsets of the season, a last-place team defeated the reigning champions in a thrilling comeback."),
            ("Tennis Legend Announces Retirement", "A beloved tennis icon announced their retirement from professional competition after a decorated career spanning two decades."),
            ("World Cup Qualifiers Deliver Surprises", "Several powerhouse nations stumbled during the latest round of World Cup qualifying matches, reshaping the tournament picture."),
            ("NFL Draft Prospects Impress at Combine", "Top college prospects showcased their skills at the annual scouting combine, with several athletes posting record-breaking numbers."),
            ("Formula 1 Unveils New Season Calendar", "The motorsport governing body released next season's race calendar featuring new circuits and the return of fan-favorite tracks."),
            ("Basketball Phenom Breaks Scoring Record", "A rising basketball star shattered a decades-old scoring record in a dominant performance that captivated audiences worldwide."),
        ],
        "culture": [
            ("Anticipated RPG Launches to Rave Reviews", "The highly anticipated open-world RPG has finally launched, earning near-perfect scores from critics and overwhelming player enthusiasm."),
            ("E-Sports Tournament Sets Viewership Record", "The world championship finals attracted over 100 million concurrent viewers, establishing a new record for competitive gaming."),
            ("Blockbuster Film Breaks Box Office Records", "The latest entry in a beloved franchise has shattered opening weekend records across multiple international markets."),
            ("Indie Game Becomes Surprise Hit", "A small studio's passion project has exploded in popularity, selling millions of copies within its first week."),
            ("Acclaimed Director Announces New Film Project", "Fans are celebrating after a legendary director revealed an ambitious new film that promises to push creative boundaries."),
            ("Music Festival Lineup Draws Global Attention", "The festival announced a star-studded lineup featuring headliners from across genres, sparking massive ticket demand."),
            ("Streaming Platform Renews Hit Series", "A popular streaming service has renewed its most-watched original series for multiple additional seasons."),
            ("Gaming Accessibility Features Win Industry Award", "New accessibility innovations in recent titles have been recognized for making gaming more inclusive than ever."),
            ("Cultural Exhibition Draws Record Attendance", "A major museum exhibition exploring the intersection of art and technology has drawn unprecedented visitor numbers."),
        ],
    }

    for i, (title, desc) in enumerate(headlines.get(category_id, headlines["politics"])):
        placeholders.append({
            "title": title,
            "description": desc,
            "url": "#",
            "image": "",
            "source": f"{label} Daily",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "author": "Staff Reporter",
            "content": desc,
        })

    return placeholders


def scrape_article_content(url):
    """Scrape full article text from a URL using trafilatura."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    if url_hash in article_content_cache:
        return article_content_cache[url_hash]

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )

        if text:
            article_content_cache[url_hash] = text
        return text

    except Exception as e:
        print(f"[{datetime.now()}] Scrape error for {url}: {e}")
        return None


def find_article_in_cache(url):
    """Look up an article's metadata across all cached categories."""
    with cache_lock:
        for cat_id, articles in news_cache.items():
            for art in articles:
                if art.get("url") == url:
                    return art, cat_id
    return None, None


def fetch_all_news():
    """Fetch news for every registered category and update the cache."""
    global seen_urls
    print(f"[{datetime.now()}] Fetching news for all categories...")
    seen_urls = set()
    for cat_id, cat_config in CATEGORIES.items():
        articles = fetch_news_for_category(cat_id, cat_config)
        with cache_lock:
            news_cache[cat_id] = articles
            last_fetched[cat_id] = datetime.now(timezone.utc).isoformat()
    print(f"[{datetime.now()}] News fetch complete.")


def background_fetcher():
    """Background thread that periodically fetches news."""
    while True:
        time.sleep(FETCH_INTERVAL * 60)
        fetch_all_news()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/read")
def read_article():
    article_url = request.args.get("url", "")
    category = request.args.get("cat", "politics")

    if not article_url or article_url == "#":
        abort(404)

    article_url = unquote(article_url)
    article_meta, found_cat = find_article_in_cache(article_url)

    if found_cat:
        category = found_cat

    theme = CATEGORIES.get(category, {}).get("theme", CATEGORIES["politics"]["theme"])

    title = article_meta["title"] if article_meta else "Article"
    description = article_meta.get("description", "") if article_meta else ""
    image = article_meta.get("image", "") if article_meta else ""
    source = article_meta.get("source", "") if article_meta else ""
    author = article_meta.get("author", "") if article_meta else ""
    published = article_meta.get("publishedAt", "") if article_meta else ""
    api_content = article_meta.get("content", "") if article_meta else ""

    full_text = scrape_article_content(article_url)

    if not full_text and api_content:
        full_text = api_content

    if not full_text:
        full_text = description or "Could not retrieve article content. Visit the original source below."

    paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]

    return render_template(
        "article.html",
        title=title,
        description=description,
        image=image,
        source=source,
        author=author,
        published=published,
        paragraphs=paragraphs,
        original_url=article_url,
        category=category,
        theme=theme,
    )


@app.route("/api/categories")
def get_categories():
    cats = [{"id": k, "label": v["label"], "theme": v.get("theme", {})} for k, v in CATEGORIES.items()]
    return jsonify(cats)


@app.route("/api/news/<category>")
def get_news(category):
    if category not in CATEGORIES:
        return jsonify({"error": "Category not found"}), 404

    with cache_lock:
        articles = news_cache.get(category, [])
        fetched_at = last_fetched.get(category, "")

    return jsonify({
        "category": category,
        "label": CATEGORIES[category]["label"],
        "articles": articles,
        "fetchedAt": fetched_at,
    })


if __name__ == "__main__":
    fetch_all_news()

    fetcher_thread = threading.Thread(target=background_fetcher, daemon=True)
    fetcher_thread.start()

    port = int(os.getenv("PORT", "5000"))
    print(f"Server running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
