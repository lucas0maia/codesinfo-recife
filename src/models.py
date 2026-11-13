"""Data models for the Editais Journalism PoC."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class RawEdital:
    """Raw opportunity item returned by a source connector before analysis."""

    source_id: str
    source_name: str
    title: str
    url: str
    raw_text: str
    source_url: Optional[str] = None
    published_at: Optional[str] = None
    default_organizer: Optional[str] = None
    force_journalism: bool = False


@dataclass
class Edital:
    """Normalized, categorized, and scored edital record stored in SQLite."""

    id: str
    source_id: str
    source_name: str
    title: str
    url: str
    source_url: Optional[str]
    organizer: str
    is_transversal: bool
    primary_area: str
    areas: List[str] = field(default_factory=list)
    eligibility: List[str] = field(default_factory=list)
    deadline_raw: Optional[str] = None
    deadline_iso: Optional[str] = None
    status: str = "verificar_prazo"  # aberto | fluxo_continuo | encerrado | verificar_prazo
    value_raw: Optional[str] = None
    relevance_score: int = 0
    journalism_fit_tips: List[str] = field(default_factory=list)
    summary: str = ""
    published_at: Optional[str] = None
    collected_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
