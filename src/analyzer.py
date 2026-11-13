"""Programmatic (non-AI) analyzer for classifying and extracting edital metadata."""

import hashlib
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from .models import Edital, RawEdital

MONTHS_PT: Dict[str, int] = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

MONTHS_EN: Dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Noise patterns that indicate results/announcements rather than open calls.
NOISE_TITLE_PATTERNS = [
    r"\banuncia\s+\d*\s*(?:iniciativas|projetos|organizacoes|organizações|vencedores|selecionados)\b",
    r"\bconhe[çc]a\s+os\s+\d*\s*(?:projetos|selecionados|vencedores|finalistas)\b",
    r"\bprojetos\s+selecionados\b",
    r"\bresultado\s+(?:final|preliminar)\b",
    r"\bselecionou\s+\d+\b",
    r"\bforam\s+selecionad[oa]s\b",
    r"\bestudo\s+in[ée]dito\b",
    r"\bpublica[çc][ãa]o\s+in[ée]dita\b",
    r"\bparticipa\s+da\b",
    r"\bperguntas\s+que\s+voc[êe]\s+deve\s+se\s+fazer\b",
    r"\bcomo\s+preparar\s+sua\s+candidatura\b",
]

AREA_KEYWORDS: Dict[str, List[str]] = {
    "Jornalismo Direto": [
        "jornalismo", "jornalista", "jornalistas", "reportagem", "reportagens",
        "imprensa", "mídia independente", "midia independente", "redação", "redacao",
        "veículo", "veiculo", "investigativa", "investigativo", "reporting grant",
        "journalism", "journalist", "newsroom", "fellowship", "press", "podcast",
    ],
    "Socioambiental e Clima": [
        "clima", "climática", "climatica", "meio ambiente", "ambiental", "socioambiental",
        "amazônia", "amazonia", "cerrado", "bioma", "biodiversidade", "sustentabilidade",
        "resiliência", "resiliencia", "água", "agua", "oceano", "ocean", "climate",
        "transição energética", "transicao energetica", "ecologia", "floresta",
    ],
    "Cultura e Memória": [
        "cultura", "cultural", "memória", "memoria", "patrimônio", "patrimonio",
        "audiovisual", "documentário", "documentario", "arte", "artes", "acervo",
        "livro", "leitura", "literatura", "museu", "lei rouanet", "lei paulo gustavo",
        "pnab", "fotografia",
    ],
    "Educação e Ciência": [
        "educação", "educacao", "ensino", "escola", "escolar", "ciência", "ciencia",
        "científica", "cientifica", "pesquisa", "letramento", "alfabetização",
        "universidade", "jovens", "juventude", "infância", "infancia",
    ],
    "Direitos Humanos e Justiça": [
        "direitos humanos", "justiça", "justica", "racial", "antirracismo", "gênero",
        "genero", "mulheres", "indígena", "indigenas", "quilombola", "lgbtq",
        "periferia", "moradia", "trabalhadores", "democracia", "cidadania",
        "conflito", "conflict", "equidade", "inclusão", "inclusao",
    ],
    "Comunicação Comunitária e Mobilização": [
        "comunicação", "comunicacao", "comunitária", "comunitaria", "comunitário",
        "comunitario", "mobilização", "mobilizacao", "incidência", "incidencia",
        "advocacy", "território", "territorio", "base", "popular", "rádio comunitária",
        "educomunicação", "educomunicacao",
    ],
    "Tecnologia e Direitos Digitais": [
        "direitos digitais", "inteligência artificial", "artificial intelligence",
        "desinformação", "desinformacao", "dados abertos", "transparência",
        "transparencia", "tecnologia", "digital", "cibersegurança", "regulação",
    ],
}

PROJECT_FIT_TEMPLATES: Dict[str, str] = {
    "Jornalismo Direto": (
        "Série de reportagens investigativas, dossiê multimídia, podcast documental "
        "ou cobertura especial de interesse público."
    ),
    "Socioambiental e Clima": (
        "Cobertura investigativa de conflitos socioambientais, monitoramento territorial com dados, "
        "podcast de justiça climática ou guia de educomunicação ambiental."
    ),
    "Cultura e Memória": (
        "Documentário jornalístico, acervo digital de memória local, revista/especial multimídia "
        "ou série de perfis sobre patrimônio e identidades territoriais."
    ),
    "Educação e Ciência": (
        "Reportagem explicativa sobre políticas educacionais, projeto de letramento midiático/informacional "
        "ou cobertura de divulgação científica acessível."
    ),
    "Direitos Humanos e Justiça": (
        "Investigação sobre violações de direitos, série de histórias de impacto em territórios vulnerabilizados "
        "ou observatório jornalístico de políticas públicas."
    ),
    "Comunicação Comunitária e Mobilização": (
        "Oficinas de comunicação popular, rede de correspondentes locais, boletim comunitário "
        "ou campanha informativa de mobilização territorial."
    ),
    "Tecnologia e Direitos Digitais": (
        "Investigação algorítmica/de dados, projeto de checagem contra desinformação, "
        "ferramenta cívica de transparência ou cobertura sobre regulação digital."
    ),
}

ELIGIBILITY_PATTERNS: List[Tuple[str, str]] = [
    ("OSC / Associação sem fins lucrativos", r"\b(?:oscs?|organiza[çc][õo]es\s+da\s+sociedade\s+civil|sem\s+fins\s+lucrativos|associa[çc][õo]es|ongs?|entidades\s+sem\s+fins)\b"),
    ("Veículos / Organizações de Mídia", r"\b(?:ve[íi]culos?\s+de\s+(?:comunica[çc][ãa]o|jornalismo|m[íi]dia)|m[íi]dia\s+independente|newsrooms?|media\s+organizations?|outlets?|reda[çc][õo]es)\b"),
    ("Jornalistas / Pessoa Física", r"\b(?:jornalistas?|rep[óo]rteres?|pessoa\s+f[íi]sica|profissionais\s+de\s+imprensa|freelance\s+journalists?|individual\s+journalists?)\b"),
    ("Coletivos / Grupos Informais", r"\b(?:coletivos?|grupos\s+informais|iniciativas\s+comunit[áa]rias|sem\s+cnpj)\b"),
    ("Empresas / MEI / Pessoa Jurídica", r"\b(?:pessoa\s+jur[íi]dica|mei\b|microempreendedor|empresas?|cnpj)\b"),
]


def make_id(url: str) -> str:
    """Return deterministic short ID from canonical URL."""
    clean = url.strip().rstrip("/")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def is_noise(title: str, text: str) -> bool:
    """Filter out post-selection result announcements unless an active call is mentioned."""
    t_low = title.lower()
    if "inscrições abertas" in t_low or "inscricoes abertas" in t_low:
        return False
    for pat in NOISE_TITLE_PATTERNS:
        if re.search(pat, t_low):
            return True
    return False


def _safe_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_deadline(text: str, published_at: Optional[str] = None, today: Optional[date] = None) -> Tuple[Optional[str], Optional[str], str]:
    """Extract deadline raw string, ISO date, and computed status."""
    ref_today = today or date.today()
    low = text.lower()

    if any(k in low for k in ["fluxo contínuo", "fluxo continuo", "rolling basis", "rolling deadline", "sem prazo determinado"]):
        return "Fluxo contínuo", None, "fluxo_continuo"

    default_year = ref_today.year
    if published_at and len(published_at) >= 4 and published_at[:4].isdigit():
        default_year = int(published_at[:4])

    candidates: List[Tuple[str, str]] = []

    # Pattern 1: DD/MM/YYYY
    for m in re.finditer(r"(?:at[ée]\s*(?:o\s*dia\s*)?|prazo[:\s]+|deadline[:\s]+|encerram(?:-se)?\s+em\s+)(\d{1,2})/(\d{1,2})/(\d{4})", low):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        iso = _safe_date(y, mo, d)
        if iso:
            candidates.append((f"{d:02d}/{mo:02d}/{y}", iso))

    # Pattern 2: DD de <mês> de YYYY
    month_names_pt = "|".join(MONTHS_PT.keys())
    for m in re.finditer(rf"(?:at[ée]\s*(?:o\s*dia\s*)?|prazo[:\s]+|inscri[çc][õo]es\s+at[ée]\s+)(\d{{1,2}})\s+de\s+({month_names_pt})(?:\s+de\s+(\d{{4}}))?", low):
        d = int(m.group(1))
        mo = MONTHS_PT[m.group(2)]
        y = int(m.group(3)) if m.group(3) else default_year
        iso = _safe_date(y, mo, d)
        if iso:
            candidates.append((m.group(0).strip(), iso))

    # Pattern 3: English Month DD, YYYY (e.g. December 15, 2026)
    month_names_en = "|".join(MONTHS_EN.keys())
    for m in re.finditer(rf"({month_names_en})\s+(\d{{1,2}}),?\s+(\d{{4}})", low):
        mo = MONTHS_EN[m.group(1)]
        d = int(m.group(2))
        y = int(m.group(3))
        iso = _safe_date(y, mo, d)
        if iso:
            candidates.append((m.group(0).strip(), iso))

    # Fallback: any DD/MM/YYYY near "inscri" or "prazo" or "edital"
    if not candidates:
        for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(202[5-9])\b", low):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            iso = _safe_date(y, mo, d)
            if iso:
                candidates.append((f"{d:02d}/{mo:02d}/{y}", iso))

    if not candidates:
        return None, None, "verificar_prazo"

    # Prefer the latest future date if multiple exist, otherwise the last extracted date
    future = [c for c in candidates if date.fromisoformat(c[1]) >= ref_today]
    chosen_raw, chosen_iso = future[-1] if future else candidates[-1]
    status = "aberto" if date.fromisoformat(chosen_iso) >= ref_today else "encerrado"
    return chosen_raw, chosen_iso, status


def extract_value(text: str) -> Optional[str]:
    """Extract monetary grant/prize value if present."""
    patterns = [
        r"(?:R\$|BRL)\s*\d[\d.,]*(?:\s*(?:bilh[õo]es|bilh[ãa]o|milh[õo]es|milh[ãa]o|mil|bi))?",
        r"(?:US\$|USD|\$)\s*\d[\d.,]*(?:\s*(?:billion|million|thousand|[kMB]))?",
        r"(?:€|EUR)\s*\d[\d.,]*(?:\s*(?:billion|million|thousand|mil|[kMB]))?",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()
    return None


def extract_eligibility(text: str, force_journalism: bool = False) -> List[str]:
    """Identify eligible applicant profiles via regex."""
    low = text.lower()
    found: List[str] = []
    for label, pat in ELIGIBILITY_PATTERNS:
        if re.search(pat, low):
            found.append(label)
    if force_journalism and "Veículos / Organizações de Mídia" not in found and "Jornalistas / Pessoa Física" not in found:
        found.append("Jornalistas / Organizações de Mídia")
    if not found:
        found.append("Verificar edital (OSC / PJ / Coletivos)")
    return found


def extract_organizer(title: str, text: str, default_source: str) -> str:
    """Extract realizador/organizer from title or lead text."""
    combined = f"{title}. {text[:400]}"
    m = re.search(
        r"\b((?:Instituto|Funda[çc][ãa]o|Fundo|Programa|Minist[ée]rio|Secretaria)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç-]*(?:\s+(?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç-]*)){0,4})",
        combined,
    )
    if m:
        org = m.group(1).strip(" .,:;-")
        if len(org) >= 5:
            return org
    return default_source


def classify_areas(title: str, text: str, force_journalism: bool = False) -> Tuple[str, List[str], bool]:
    """Classify edital into primary and secondary areas using weighted keyword counts."""
    title_low = title.lower()
    body_low = text.lower()
    scores: Dict[str, int] = {}

    for area, keywords in AREA_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in title_low:
                score += 4
            if kw in body_low:
                score += 1
        if score > 0:
            scores[area] = score

    if force_journalism:
        scores["Jornalismo Direto"] = scores.get("Jornalismo Direto", 0) + 6

    if not scores:
        return "Transversal / Impacto Social", ["Transversal / Impacto Social"], True

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    areas = [a for a, _ in ranked[:3]]
    primary = areas[0]
    is_transversal = primary != "Jornalismo Direto"
    return primary, areas, is_transversal


def compute_relevance_and_fit(
    primary_area: str,
    areas: List[str],
    eligibility: List[str],
    status: str,
    value_raw: Optional[str],
) -> Tuple[int, List[str]]:
    """Compute deterministic relevance score (0-100) and journalism project fit tips."""
    score = 35
    if "Jornalismo Direto" in areas:
        score += 30
    if any("Veículos" in e or "Jornalistas" in e for e in eligibility):
        score += 15
    elif any("OSC" in e or "Coletivos" in e for e in eligibility):
        score += 10
    if status == "aberto":
        score += 15
    elif status == "fluxo_continuo":
        score += 12
    elif status == "encerrado":
        score -= 25
    if value_raw:
        score += 5

    score = max(0, min(100, score))

    tips: List[str] = []
    for area in areas:
        tip = PROJECT_FIT_TEMPLATES.get(area)
        if tip and tip not in tips:
            tips.append(tip)

    if not any("Veículos" in e for e in eligibility) and any("OSC" in e for e in eligibility):
        tips.append(
            "Dica de elegibilidade: se o veículo for empresa/MEI e o edital exigir OSC sem fins lucrativos, "
            "avalie submeter em parceria com uma associação/instituto parceiro (proponente-âncora)."
        )

    return score, tips


def analyze_raw_edital(raw: RawEdital, today: Optional[date] = None) -> Optional[Edital]:
    """Transform a RawEdital into a structured Edital, or return None if filtered as noise."""
    if is_noise(raw.title, raw.raw_text):
        return None

    clean_text = re.sub(r"\s+", " ", raw.raw_text).strip()
    combined_for_meta = f"{raw.title} {clean_text}"
    deadline_raw, deadline_iso, status = parse_deadline(combined_for_meta, raw.published_at, today=today)
    if status == "verificar_prazo" and re.search(r"\b202[0-5]\b", raw.title):
        status = "encerrado"
    value_raw = extract_value(combined_for_meta)
    eligibility = extract_eligibility(combined_for_meta, force_journalism=raw.force_journalism)
    organizer = raw.default_organizer or extract_organizer(raw.title, clean_text, raw.source_name)
    primary_area, areas, is_transversal = classify_areas(raw.title, clean_text, force_journalism=raw.force_journalism)
    score, tips = compute_relevance_and_fit(primary_area, areas, eligibility, status, value_raw)

    summary = clean_text[:280].rsplit(" ", 1)[0] + "..." if len(clean_text) > 280 else clean_text

    return Edital(
        id=make_id(raw.url),
        source_id=raw.source_id,
        source_name=raw.source_name,
        title=raw.title.strip(),
        url=raw.url.strip(),
        source_url=(raw.source_url or raw.url).strip(),
        organizer=organizer,
        is_transversal=is_transversal,
        primary_area=primary_area,
        areas=areas,
        eligibility=eligibility,
        deadline_raw=deadline_raw,
        deadline_iso=deadline_iso,
        status=status,
        value_raw=value_raw,
        relevance_score=score,
        journalism_fit_tips=tips,
        summary=summary,
        published_at=raw.published_at,
        collected_at=datetime.now().isoformat(timespec="seconds"),
    )
