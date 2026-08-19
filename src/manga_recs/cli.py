import argparse
import logging
import os

# constants imports nothing heavy, so the parser can be built on a serving-only
# install that has neither boto3 nor requests.
from manga_recs.common.constants import DATASETS


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # boto3 is extremely chatty at INFO.
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _run_api(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run("manga_recs.api.main:app", host=host, port=port, reload=reload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manga-recs", description="Manga Recs CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Stages that read and write a dated partition in the object store.
    stage_parsers: dict[str, argparse.ArgumentParser] = {}
    for name, help_text in (
        ("clean", "Normalize raw data into validated Parquet"),
        ("features", "Build model-ready feature matrices"),
        ("pipeline", "Run ingest -> clean -> features"),
        ("train", "Train the similarity model"),
        ("evaluate", "Score the model against held-out user history"),
    ):
        stage = subparsers.add_parser(name, help=help_text)
        stage.add_argument(
            "--partition",
            help="Date partition (YYYY-MM-DD). Defaults to today for writes, latest for reads.",
        )
        stage_parsers[name] = stage

    # Opt-in so that reading the numbers stays separate from acting on them: an
    # ad-hoc `evaluate` should print and exit 0, while a scheduled run asks to
    # fail loudly on a regression.
    evaluate_parser = stage_parsers["evaluate"]
    evaluate_parser.add_argument(
        "--gate",
        action="store_true",
        help="Exit non-zero unless the content model beats the popularity baseline.",
    )
    evaluate_parser.add_argument(
        "--min-recall",
        type=float,
        default=0.0,
        help="Additional absolute recall@k floor, only enforced together with --gate.",
    )

    ingest_parser = subparsers.add_parser("ingest", help="Fetch raw data from AniList")
    ingest_parser.add_argument(
        "--partition",
        help="Date partition (YYYY-MM-DD). Defaults to today for writes, latest for reads.",
    )
    ingest_parser.add_argument(
        "--datasets",
        nargs="+",
        choices=DATASETS,
        default=list(DATASETS),
        help=(
            "Which datasets to fetch. User read lists take far longer than manga "
            "metadata, so a media-only schema change can re-ingest just 'manga'."
        ),
    )

    recommend_parser = subparsers.add_parser("recommend", help="Get recommendations for a title")
    recommend_parser.add_argument("title", help="Manga title to search for")
    recommend_parser.add_argument("--top-n", type=int, default=None, help="How many to return")

    subparsers.add_parser("status", help="Show the configured storage backend and its partitions")

    bundle_parser = subparsers.add_parser(
        "bundle", help="Copy serving artifacts locally so an image can bake them in"
    )
    bundle_parser.add_argument(
        "--partition", help="Date partition to bundle (YYYY-MM-DD). Defaults to the latest."
    )

    api_parser = subparsers.add_parser("api", help="Start FastAPI server")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host for API server")
    api_parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port for API server (defaults to $PORT, else 8000)",
    )
    api_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    return parser


def _show_status() -> None:
    from manga_recs.common.constants import (
        CLEANED_STATUS,
        FEATURES_STATUS,
        METRICS_STATUS,
        MODELS_STATUS,
        RAW_STATUS,
    )
    from manga_recs.data.load import ObjectStoreError, describe_backend, list_partitions

    print(f"Storage backend: {describe_backend()}\n")
    for status in (RAW_STATUS, CLEANED_STATUS, FEATURES_STATUS, MODELS_STATUS, METRICS_STATUS):
        try:
            partitions = list_partitions(status)
        except ObjectStoreError as exc:
            print(f"  {status:<10} error: {exc}")
            continue
        newest = partitions[-1] if partitions else "-"
        print(f"  {status:<10} {len(partitions):>3} partition(s), latest: {newest}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(getattr(args, "verbose", False))

    partition = getattr(args, "partition", None)

    if args.command == "ingest":
        from manga_recs.data.ingestion import ingest_data

        ingest_data(partition=partition, datasets=args.datasets)
    elif args.command == "clean":
        from manga_recs.data.cleaning import clean_data

        clean_data(partition=partition)
    elif args.command == "features":
        from manga_recs.data.features import build_features

        build_features(partition=partition)
    elif args.command == "pipeline":
        from manga_recs.pipelines.orchestrator import run_pipeline

        run_pipeline(partition=partition)
    elif args.command == "train":
        from manga_recs.models.train_similarity import train

        train(partition=partition)
    elif args.command == "evaluate":
        from manga_recs.models.evaluate import (
            PromotionGateError,
            check_promotion,
            format_report,
            run_evaluation,
        )

        metrics = run_evaluation(partition=partition)
        print(format_report(metrics))
        if args.gate:
            try:
                check_promotion(metrics, min_recall=args.min_recall)
            except PromotionGateError as exc:
                # The partition stays published either way; promotion to the
                # serving bundle is a separate, manual step. Failing here is the
                # signal not to take it.
                raise SystemExit(f"\nQuality gate failed: {exc}") from exc
            print("\nQuality gate passed.")
    elif args.command == "recommend":
        from manga_recs.serving.recommender import get_recommender

        match, recommendations = get_recommender().recommend(args.title, args.top_n)
        print(f"\nMatched '{args.title}' -> '{match.title}' (score {match.score:.0f})\n")
        for rank, rec in enumerate(recommendations, start=1):
            print(f"{rank:>2}. {rec['title']}  ({rec['similarity']:.3f})")
    elif args.command == "status":
        _show_status()
    elif args.command == "bundle":
        from manga_recs.serving.artifacts import build_bundle

        resolved = build_bundle(partition=partition)
        print(f"\nBundled serving artifacts into {resolved.model_path.parent}")
        for name, info in (resolved.manifest or {}).get("files", {}).items():
            print(f"  {name:<40} {info['bytes'] / 1_000_000:.2f} MB")
    elif args.command == "api":
        _run_api(host=args.host, port=args.port, reload=not args.no_reload)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
