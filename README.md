# The Daily Wire — Newspaper Website

A minimalistic, auto-updating newspaper website with category-based news browsing.

## Categories

| Category   | Theme                    |
|------------|--------------------------|
| Politics   | White background, black cards |
| Technology | Soft grey background     |
| Gaming     | Subtle blue background   |

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Get a free API key from [NewsAPI.org](https://newsapi.org/register) and add it to `.env`:

```
NEWS_API_KEY=your_key_here
```

> Without an API key the site works with placeholder articles.

3. Run the server:

```bash
python server.py
```

4. Open **http://localhost:5000** in your browser.

## Adding New Categories

Edit the `CATEGORIES` dictionary in `server.py`:

```python
CATEGORIES = {
    # ...existing categories...
    "sports": {
        "label": "Sports",
        "query": "sports",
        "newsapi_category": "sports",
        "keywords": "sports OR football OR basketball OR soccer",
    },
}
```

The frontend picks up new categories automatically — no HTML or JS changes needed.
