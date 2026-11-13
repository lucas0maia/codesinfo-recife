"""Pulitzer Center grants & fellowships HTML connector."""

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import RawEdital
from .base import BaseConnector, html_to_text


class PulitzerConnector(BaseConnector):
    """Scrapes open reporting grant pages from Pulitzer Center."""

    source_id = "pulitzer"
    source_name = "Pulitzer Center"
    INDEX_URL = "https://pulitzercenter.org/grants-fellowships"

    def fetch(self, max_items: int = 10) -> List[RawEdital]:
        resp = self.session.get(self.INDEX_URL, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        seen_urls = set()
        grant_urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/grants-fellowships/opportunities-journalists/" in href:
                full = urljoin("https://pulitzercenter.org", href.split("#")[0].split("?")[0])
                if full not in seen_urls:
                    seen_urls.add(full)
                    grant_urls.append(full)

        results: List[RawEdital] = []
        for url in grant_urls[:max_items]:
            try:
                page = self.session.get(url, timeout=self.timeout)
                page.raise_for_status()
            except Exception:
                continue

            psoup = BeautifulSoup(page.text, "lxml")
            h1 = psoup.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else url.rsplit("/", 1)[-1].replace("-", " ").title()
            main = psoup.find("main") or psoup.find("article") or psoup.body
            raw_text = html_to_text(str(main)) if main else ""
            raw_text = re.sub(r"\s+", " ", raw_text).strip()

            results.append(
                RawEdital(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=url,
                    raw_text=raw_text[:4000],
                    default_organizer="Pulitzer Center",
                    force_journalism=True,
                )
            )
        return results
