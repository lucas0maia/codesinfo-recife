"""Unit tests for the programmatic (non-AI) edital analyzer."""

from datetime import date

from src.analyzer import analyze_raw_edital, extract_value, is_noise, parse_deadline
from src.connectors.base import extract_direct_edital_url, split_roundup_sections
from src.models import RawEdital


def test_extract_value_handles_millions_and_currencies():
    assert extract_value("Edital de R$ 17,7 milhões para restauração") == "R$ 17,7 milhões"
    assert extract_value("Apoio de R$ 500 mil para OSCs") == "R$ 500 mil"
    assert extract_value("Grants up to US$ 10,000 for reporting") == "US$ 10,000"
    assert extract_value("Sem valor informado") is None


def test_parse_deadline_pt_br_and_rolling():
    ref = date(2026, 11, 13)
    raw, iso, status = parse_deadline("Inscrições até 15 de dezembro de 2026.", today=ref)
    assert iso == "2026-12-15"
    assert status == "aberto"

    raw2, iso2, status2 = parse_deadline("Prazo: 01/10/2026", today=ref)
    assert iso2 == "2026-10-01"
    assert status2 == "encerrado"

    raw3, iso3, status3 = parse_deadline("Applications accepted on a rolling basis.", today=ref)
    assert iso3 is None
    assert status3 == "fluxo_continuo"


def test_noise_filter_rejects_result_announcements():
    assert is_noise("Fundação Cargill anuncia 16 iniciativas selecionadas", "") is True
    assert is_noise("Conheça os 203 projetos selecionados na chamada", "") is True
    assert is_noise("Ambev abre edital de R$ 500 mil para OSCs", "") is False


def test_analyze_transversal_edital_generates_journalism_fit_tips():
    raw = RawEdital(
        source_id="abcr",
        source_name="ABCR",
        title="Edital Clima e Floresta apoia projetos de OSCs com R$ 200 mil",
        url="https://example.org/edital-clima",
        raw_text="Organizações da sociedade civil podem enviar propostas até 20/12/2026 para ações socioambientais.",
        published_at="2026-11-10",
    )
    ed = analyze_raw_edital(raw, today=date(2026, 11, 13))
    assert ed is not None
    assert ed.is_transversal is True
    assert ed.primary_area == "Socioambiental e Clima"
    assert ed.status == "aberto"
    assert ed.value_raw == "R$ 200 mil"
    assert any("proponente-âncora" in tip for tip in ed.journalism_fit_tips)


def test_extract_direct_edital_url_prefers_official_platform_over_social_and_aggregator():
    html_body = """
    <p>Compartilhe no <a href="https://twitter.com/share">Twitter</a>.</p>
    <p>Veja mais na <a href="https://captadores.org.br/noticias/outra">ABCR</a>.</p>
    <p>Inscreva-se pela <a href="https://prosas.com.br/editais/19524">plataforma Prosas</a>.</p>
    """
    direct = extract_direct_edital_url(
        html_body,
        "https://captadores.org.br/editais/ambev-abre-edital/",
        is_aggregator=True,
    )
    assert direct == "https://prosas.com.br/editais/19524"


def test_split_roundup_sections_extracts_individual_editais():
    html_roundup = """
    <p>Lista de bolsas:</p>
    <h3>Bolsa Alpha</h3>
    <p>Para jornalistas até 20 de dezembro de 2026. <a href="https://alpha.org/apply">Inscreva-se</a></p>
    <h3>Bolsa Beta</h3>
    <p>Inscrições abertas em fluxo contínuo. <a href="https://beta.org/edital.pdf">Edital</a></p>
    """
    items = split_roundup_sections(
        html_roundup,
        page_url="https://agregador.org/lista",
        source_id="ljr",
        source_name="LJR",
        force_journalism=True,
    )
    assert len(items) == 2
    assert items[0].title == "Bolsa Alpha"
    assert items[0].url == "https://alpha.org/apply"
    assert items[1].title == "Bolsa Beta"
    assert items[1].url == "https://beta.org/edital.pdf"

