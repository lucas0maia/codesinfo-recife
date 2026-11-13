"""Generic WordPress REST API (/wp-json/wp/v2/) connector."""

import html
from typing import Dict, List, Optional

from ..models import RawEdital
from .base import (
    BaseConnector,
    extract_direct_edital_url,
    html_to_text,
    is_roundup_article,
    resolve_final_url,
    split_roundup_sections,
)

EDITAL_TITLE_KEYWORDS = (
    "edital", "editais", "chamada", "bolsa", "bolsas", "inscrições", "inscricoes",
    "seleção", "selecao", "fomento", "financiamento", "subvenção",
    "subvencao", "grant", "grants", "fellowship", "prêmio", "premio", "fundo",
)


class WordPressConnector(BaseConnector):
    """Fetches editais from any WordPress site exposing /wp-json/wp/v2/."""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        base_url: str,
        post_type: str = "posts",
        params: Optional[Dict[str, str]] = None,
        default_organizer: Optional[str] = None,
        force_journalism: bool = False,
        require_edital_keyword: bool = False,
        is_aggregator: bool = False,
        timeout: int = 15,
    ) -> None:
        super().__init__(timeout=timeout)
        self.source_id = source_id
        self.source_name = source_name
        self.base_url = base_url.rstrip("/")
        self.post_type = post_type
        self.params = params or {"per_page": "12"}
        self.default_organizer = default_organizer
        self.force_journalism = force_journalism
        self.require_edital_keyword = require_edital_keyword
        self.is_aggregator = is_aggregator

    def fetch(self) -> List[RawEdital]:
        endpoint = f"{self.base_url}/wp-json/wp/v2/{self.post_type}"
        resp = self.session.get(endpoint, params=self.params, timeout=self.timeout)
        resp.raise_for_status()
        posts = resp.json()

        results: List[RawEdital] = []
        for post in posts:
            title = html.unescape(post.get("title", {}).get("rendered", "")).strip()
            link = post.get("link", "").strip()
            content_html = post.get("content", {}).get("rendered", "") or post.get("excerpt", {}).get("rendered", "")
            raw_text = html_to_text(content_html)
            published_at = (post.get("date") or "")[:10] or None

            if not title or not link:
                continue

            if self.require_edital_keyword:
                title_low = title.lower()
                lead_low = raw_text[:300].lower()
                has_title_signal = any(kw in title_low for kw in EDITAL_TITLE_KEYWORDS)
                has_open_call_lead = "inscrições abertas" in lead_low or "inscricoes abertas" in lead_low
                if not (has_title_signal or has_open_call_lead):
                    continue

            if self.is_aggregator and is_roundup_article(title, content_html):
                split_items = split_roundup_sections(
                    content_html,
                    page_url=link,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    published_at=published_at,
                    force_journalism=self.force_journalism,
                )
                if split_items:
                    for it in split_items:
                        it.url = resolve_final_url(it.url, self.session)
                        results.append(it)
                    continue

            direct_url = extract_direct_edital_url(content_html, link, is_aggregator=self.is_aggregator)
            direct_url = resolve_final_url(direct_url, self.session)

            results.append(
                RawEdital(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=direct_url,
                    source_url=link,
                    raw_text=raw_text,
                    published_at=published_at,
                    default_organizer=self.default_organizer,
                    force_journalism=self.force_journalism,
                )
            )
        return results
