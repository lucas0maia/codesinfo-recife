"""Connector registry for all programmatic edital sources."""

from typing import List

from .base import BaseConnector
from .ijnet import IjnetRssConnector
from .pulitzer import PulitzerConnector
from .wordpress import WordPressConnector


def build_default_connectors() -> List[BaseConnector]:
    """Instantiate all enabled programmatic connectors."""
    return [
        WordPressConnector(
            source_id="abcr",
            source_name="ABCR (Captadores)",
            base_url="https://captadores.org.br",
            post_type="posts",
            params={"categories": "162", "per_page": "15"},
            is_aggregator=True,
        ),
        WordPressConnector(
            source_id="gife",
            source_name="GIFE (Rede de Editais)",
            base_url="https://gife.org.br",
            post_type="posts",
            params={"categories": "25", "per_page": "15"},
            is_aggregator=True,
        ),
        WordPressConnector(
            source_id="fundobrasil",
            source_name="Fundo Brasil de Direitos Humanos",
            base_url="https://fundobrasil.org.br",
            post_type="edital",
            params={"per_page": "12"},
            default_organizer="Fundo Brasil de Direitos Humanos",
        ),
        WordPressConnector(
            source_id="casa",
            source_name="Fundo Casa Socioambiental",
            base_url="https://casa.org.br",
            post_type="posts",
            params={"search": "chamada", "per_page": "10"},
            default_organizer="Fundo Casa Socioambiental",
            require_edital_keyword=True,
        ),
        WordPressConnector(
            source_id="apublica",
            source_name="Agência Pública",
            base_url="https://apublica.org",
            post_type="posts",
            params={"search": "edital", "per_page": "8"},
            default_organizer="Agência Pública",
            force_journalism=True,
            require_edital_keyword=True,
        ),
        WordPressConnector(
            source_id="latam_jr",
            source_name="Latam Journalism Review",
            base_url="https://latamjournalismreview.org/pt-br",
            post_type="posts",
            params={"search": "bolsa", "per_page": "8"},
            force_journalism=True,
            require_edital_keyword=True,
            is_aggregator=True,
        ),
        PulitzerConnector(),
        IjnetRssConnector(),
    ]
