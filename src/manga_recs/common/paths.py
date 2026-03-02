from manga_recs.common.settings import settings

DATA_DIR = settings.paths.data_dir
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
FEATURES_DIR = DATA_DIR / "features"

ARTIFACTS_DIR = settings.paths.artifacts_dir
MODELS_DIR = ARTIFACTS_DIR / "models"