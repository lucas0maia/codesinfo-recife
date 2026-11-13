"""Base connector and HTML/HTTP utilities."""

import html
import re
from abc import ABC, abstractmethod
from typing import List, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..models import RawEdital

SOCIAL_AND_NOISE_DOMAINS = (
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
    "youtube.com", "youtu.be", "whatsapp.com", "wa.me", "t.me", "pinterest.com",
    "creativecommons.org", "wordpress.org", "w3.org",
)

DIRECT_URL_HINTS = (
    "prosas.com.br", "editais", "edital", "chamada", "inscric", "forms.",
    "docs.google.com/forms", "typeform.com", "jotform.com", "powerappsportals",
    "survey", "apply", "grant", "bolsa", "oportunidade", ".pdf",
)

ANCHOR_TEXT_HINTS = (
    "edital", "inscri", "acesse", "clique aqui", "neste link", "aqui",
    "plataforma", "prosas", "formulário", "formulario", "saiba mais",
    "página", "pagina", "site oficial", "apply", "application", "regulamento",
)


SHORTENER_DOMAINS = ("bit.ly", "tinyurl.com", "ow.ly", "is.gd", "cutt.ly", "rebrand.ly", "e2ma.net")

ROUNDUP_TITLE_HINTS = (
    "confira editais",
    "editais com inscrições abertas",
    "editais com inscricoes abertas",
    "estas são algumas bolsas",
    "estas sao algumas bolsas",
    "confira oportunidades",
    "lista de editais",
)


def resolve_final_url(url: str, session: requests.Session, timeout: int = 8) -> str:
    """Follow redirects for URL shorteners or tracking links."""
    host = urlparse(url).netloc.lower().lstrip("www.")
    if not any(s in host for s in SHORTENER_DOMAINS):
        return url
    try:
        resp = session.head(url, allow_redirects=True, timeout=timeout)
        if resp.url and resp.url.startswith(("http://", "https://")):
            return resp.url
    except Exception:
        pass
    return url


GUIDE_TITLE_HINTS = (
    "perguntas que você deve",
    "perguntas que voce deve",
    "como preparar",
    "dicas para",
)


def is_roundup_article(title: str, raw_html: str) -> bool:
    """Detect whether an article aggregates multiple distinct editais/fellowships."""
    t_low = title.lower()
    if any(g in t_low for g in GUIDE_TITLE_HINTS):
        return False
    if any(h in t_low for h in ROUNDUP_TITLE_HINTS):
        return True
    soup = BeautifulSoup(raw_html or "", "lxml")
    h3s = soup.find_all("h3")
    return len(h3s) >= 4


def split_roundup_sections(
    raw_html: str,
    page_url: str,
    source_id: str,
    source_name: str,
    published_at: str | None = None,
    force_journalism: bool = False,
) -> List[RawEdital]:
    """Split a multi-opportunity roundup HTML post into individual RawEdital items."""
    soup = BeautifulSoup(raw_html or "", "lxml")
    items: List[RawEdital] = []

    # Strategy A: sections headed by <h3>
    h3_tags = soup.find_all("h3")
    if len(h3_tags) >= 2:
        for h3 in h3_tags:
            sec_title = h3.get_text(" ", strip=True)
            if not sec_title or len(sec_title) < 6:
                continue
            chunk_html_parts = []
            for sib in h3.find_next_siblings():
                if sib.name in ("h2", "h3"):
                    break
                chunk_html_parts.append(str(sib))
            chunk_html = "\n".join(chunk_html_parts)
            direct_url = extract_direct_edital_url(chunk_html, page_url, is_aggregator=True)
            if direct_url == page_url:
                continue
            items.append(
                RawEdital(
                    source_id=source_id,
                    source_name=source_name,
                    title=sec_title,
                    url=direct_url,
                    source_url=page_url,
                    raw_text=html_to_text(chunk_html),
                    published_at=published_at,
                    force_journalism=force_journalism,
                )
            )
        if items:
            return items

    # Strategy B: GIFE-style <p><strong>Title</strong>...</p> followed by link paragraphs
    strong_blocks = [
        p for p in soup.find_all("p")
        if p.find("strong") and len(p.find("strong").get_text(strip=True)) >= 8
    ]
    if len(strong_blocks) >= 2:
        for idx, p in enumerate(strong_blocks):
            sec_title = p.find("strong").get_text(" ", strip=True)
            next_p = strong_blocks[idx + 1] if idx + 1 < len(strong_blocks) else None
            chunk_html_parts = [str(p)]
            for sib in p.find_next_siblings():
                if sib == next_p:
                    break
                chunk_html_parts.append(str(sib))
            chunk_html = "\n".join(chunk_html_parts)
            direct_url = extract_direct_edital_url(chunk_html, page_url, is_aggregator=True)
            if direct_url == page_url:
                continue
            items.append(
                RawEdital(
                    source_id=source_id,
                    source_name=source_name,
                    title=sec_title,
                    url=direct_url,
                    source_url=page_url,
                    raw_text=html_to_text(chunk_html),
                    published_at=published_at,
                    force_journalism=force_journalism,
                )
            )
    return items


def extract_direct_edital_url(raw_html: str, page_url: str, is_aggregator: bool = True) -> str:
    """Extract the direct official edital/application URL from an aggregator post HTML."""
    if not raw_html or not is_aggregator:
        return page_url

    soup = BeautifulSoup(raw_html, "lxml")
    page_host = urlparse(page_url).netloc.lower().lstrip("www.")
    candidates: List[Tuple[int, str]] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href.startswith(("http://", "https://")):
            continue

        parsed = urlparse(href)
        host = parsed.netloc.lower().lstrip("www.")
        if not host or host == page_host:
            continue
        if any(dom in host for dom in SOCIAL_AND_NOISE_DOMAINS):
            continue

        anchor_txt = a.get_text(" ", strip=True).lower()
        href_low = href.lower()

        score = 15
        if any(hint in href_low for hint in DIRECT_URL_HINTS):
            score += 40
        if any(hint in anchor_txt for hint in ANCHOR_TEXT_HINTS):
            score += 30
        # Slight penalty for generic homepage-only URLs when a deeper path exists
        if parsed.path in ("", "/") and score < 45:
            score -= 5

        candidates.append((score, href))

    if not candidates:
        return page_url

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def html_to_text(raw_html: str) -> str:
    """Convert HTML fragment into clean plain text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class BaseConnector(ABC):
    """Abstract base class for programmatic edital source connectors."""

    source_id: str = "base"
    source_name: str = "Base Source"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            }
        )

    @abstractmethod
    def fetch(self) -> List[RawEdital]:
        """Fetch raw edital records from the source."""
        raise NotImplementedError
