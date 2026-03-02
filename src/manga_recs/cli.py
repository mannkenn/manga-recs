import argparse


def _run_api(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run("manga_recs.api.main:app", host=host, port=port, reload=reload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manga-recs", description="Manga Recs CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Run data ingestion")
    subparsers.add_parser("clean", help="Run data cleaning")
    subparsers.add_parser("features", help="Run feature engineering")
    subparsers.add_parser("pipeline", help="Run full data pipeline")
    subparsers.add_parser("train", help="Train similarity model")

    api_parser = subparsers.add_parser("api", help="Start FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host for API server")
    api_parser.add_argument("--port", type=int, default=8000, help="Port for API server")
    api_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        from manga_recs.data.ingestion import ingest_data

        ingest_data()
    elif args.command == "clean":
        from manga_recs.data.cleaning import clean_data

        clean_data()
    elif args.command == "features":
        from manga_recs.data.features import build_features

        build_features()
    elif args.command == "pipeline":
        from manga_recs.pipelines.orchestrator import run_pipeline

        run_pipeline()
    elif args.command == "train":
        from manga_recs.models.train_similarity import train

        train()
    elif args.command == "api":
        _run_api(host=args.host, port=args.port, reload=not args.no_reload)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()