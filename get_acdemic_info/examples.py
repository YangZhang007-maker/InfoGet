"""Built-in selector examples for common academic layouts."""

EXAMPLE_CONFIGS = {
    "arxiv-list": {
        "item": "li.arxiv-result",
        "title": "p.title",
        "link": "p.list-title a",
        "authors": "p.authors",
        "abstract": "span.abstract-full",
        "date": "p.is-size-7",
        "citations": "",
        "downloads": "",
        "hot_label": "",
    },
    "springer-search": {
        "item": "li.app-card-open",
        "title": "h3",
        "link": "h3 a",
        "authors": ".c-article-author-list",
        "abstract": ".c-article-section__content",
        "date": "time",
        "citations": "[data-test='citation-count']",
        "downloads": "[data-test='download-count']",
        "hot_label": ".c-status-message",
    },
    "generic-schema-org": {
        "item": "article, [itemtype*='ScholarlyArticle']",
        "title": "h1, h2, h3, [itemprop='headline'], [itemprop='name']",
        "link": "a[href]",
        "authors": "[itemprop='author'], .authors, .author",
        "abstract": "[itemprop='abstract'], .abstract, .summary",
        "date": "time, [itemprop='datePublished'], .date, .published",
        "citations": ".citation-count, .cited-by",
        "downloads": ".download-count, .downloads",
        "hot_label": ".popular, .trending, .badge",
    },
}
