# Radar de Editais — Jornalismo Independente (PoC Módulo 1)

Prova de conceito do **Módulo 1 (Mapeamento e Categorização de Editais)** para veículos de jornalismo independentes, com busca, coleta, extração e classificação **100% programáticas (sem uso de IA)**.

## Fontes Conectadas
- **ABCR (Captadores)** — `/wp-json/wp/v2/posts?categories=162`
- **GIFE (Rede de Editais)** — `/wp-json/wp/v2/posts?categories=25`
- **Fundo Brasil de Direitos Humanos** — `/wp-json/wp/v2/edital`
- **Fundo Casa Socioambiental** — `/wp-json/wp/v2/posts?search=chamada`
- **Agência Pública** — `/wp-json/wp/v2/posts?search=edital`
- **Latam Journalism Review (PT-BR)** — `/wp-json/wp/v2/posts?search=bolsa`
- **Pulitzer Center** — HTML scraping estruturado de `/grants-fellowships`
- **IJNet PT-BR** — Feed RSS `/pt-br/rss.xml`

## Como Executar

```bash
# 1. Coletar editais e armazenar em data/editais.db
python3 run.py collect

# 2. Ver estatísticas ou listar no terminal
python3 run.py stats
python3 run.py list --limit 15

# 3. Iniciar a interface web (http://127.0.0.1:8765)
python3 run.py serve

# 4. Rodar os testes automatizados
pytest -v
```

