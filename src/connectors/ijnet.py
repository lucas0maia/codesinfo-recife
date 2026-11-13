"""IJNet (International Journalists' Network) RSS connector."""

import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from typing import List

from ..models import RawEdital
from .base import BaseConnector, extract_direct_edital_url, html_to_text, resolve_final_url

OPPORTUNITY_TERMS = (
    "edital", "bolsa", "bolsas", "subsídio", "subsidio", "grant", "grants",
    "fellowship", "chamada", "oportunidade", "oportunidades", "prêmio", "premio",
    "financiamento", "fundo", "inscrições", "inscricoes",
)


class IjnetRssConnector(BaseConnector):
    """Fetches and filters journalism funding/fellowship opportunities from IJNet PT-BR RSS."""

    source_id = "ijnet"
    source_name = "IJNet (Rede de Jornalistas Internacionais)"
    FEED_URL = "https://ijnet.org/pt-br/rss.xml"

    def fetch(self) -> List[RawEdital]:
        resp = self.session.get(self.FEED_URL, timeout=self.timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        results: List[RawEdital] = []
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            raw_desc = item.findtext("description") or ""
            desc = html_to_text(raw_desc)
            pub_date_raw = item.findtext("pubDate") or ""

            combined_low = f"{title} {desc[:400]}".lower()
            if not any(term in combined_low for term in OPPORTUNITY_TERMS):
                continue

            pub_iso = None
            if pub_date_raw:
                try:
                    pub_dt = parsedate_to_datetime(pub_date_raw).date()
                    if pub_dt < (date.today() - timedelta(days=180)):
                        continue
                    pub_iso = pub_dt.isoformat()
                except Exception:
                    pub_iso = None

            direct_url = extract_direct_edital_url(raw_desc, link, is_aggregator=True)
            direct_url = resolve_final_url(direct_url, self.session)

            results.append(
                RawEdital(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=direct_url,
                    source_url=link,
                    raw_text=desc,
                    published_at=pub_iso,
                    force_journalism=True,
                )
            )
        return results
