"""CLI entrypoint for collecting, inspecting, and serving editais."""

import argparse
import json
from pathlib import Path

from src.pipeline import run_collection
from src.server import serve_app
from src.storage import EditalStorage

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "data" / "editais.db"
WEB_DIR = ROOT_DIR / "web"


def main() -> None:
    parser = argparse.ArgumentParser(description="PoC Módulo 1 — Mapeamento Programático de Editais")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("collect", help="Coleta editais de todas as fontes programáticas e salva no SQLite")
    sub.add_parser("stats", help="Exibe estatísticas da base coletada")

    p_list = sub.add_parser("list", help="Lista editais armazenados")
    p_list.add_argument("--status", default=None)
    p_list.add_argument("--area", default=None)
    p_list.add_argument("--limit", type=int, default=15)

    p_serve = sub.add_parser("serve", help="Inicia o servidor web do dashboard")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)

    sub.add_parser("export-static", help="Exporta JSON estático em web/data/ para fac-símile online")

    args = parser.parse_args()
    storage = EditalStorage(DB_PATH)

    if args.cmd == "collect":
        report = run_collection(storage)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.cmd == "stats":
        print(json.dumps(storage.get_stats(), indent=2, ensure_ascii=False))
    elif args.cmd == "list":
        items = storage.list_editais(status=args.status, area=args.area)[: args.limit]
        for idx, item in enumerate(items, 1):
            print(
                f"{idx:02d}. [{item['status']}] ({item['relevance_score']} pts) {item['title']}\n"
                f"    Realizador: {item['organizer']} | Área: {item['primary_area']} | "
                f"Prazo: {item['deadline_raw'] or 'Verificar'} | Valor: {item['value_raw'] or 'Não informado'}\n"
                f"    URL: {item['url']}"
            )
    elif args.cmd == "serve":
        serve_app(storage, WEB_DIR, host=args.host, port=args.port)
    elif args.cmd == "export-static":
        out_dir = WEB_DIR / "data"
        out_dir.mkdir(parents=True, exist_ok=True)
        items = storage.list_editais()
        (out_dir / "editais.json").write_text(
            json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "stats.json").write_text(
            json.dumps(storage.get_stats(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Exported {len(items)} editais to {out_dir}")


if __name__ == "__main__":
    main()
