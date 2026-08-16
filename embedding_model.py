from functools import lru_cache
import os


MINIMUM_TORCH_VERSION = (2, 5)


def _version_tuple(version):
    """Return the numeric portion of versions such as ``2.5.1+cpu``."""
    parts = []
    for value in version.split("+")[0].split("."):
        digits = "".join(character for character in value if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


@lru_cache(maxsize=1)
def getEmbeddingModel():
    """Share one sentence-transformer instance across segmentation and scoring."""
    # Keep this import lazy so API startup and health checks stay lightweight.
    # Transformers 5 disables PyTorch when the installed version is too old,
    # then can fail later with the misleading message "nn is not defined".
    import torch

    if _version_tuple(torch.__version__) < MINIMUM_TORCH_VERSION:
        raise RuntimeError(
            "The installed PyTorch version is incompatible with Transformers. "
            f"Found torch {torch.__version__}; torch 2.5 or newer is required. "
            "Install requirements.txt and restart FastAPI."
        )

    from sentence_transformers import SentenceTransformer

    model_name = "all-MiniLM-L6-v2"
    try:
        # Prefer the cache even during local development. This avoids a network
        # request on every clean application start when the model is present.
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception as cached_model_error:
        offline = any(
            os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
            for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        )
        if offline:
            raise RuntimeError(
                "The embedding model is missing from this offline application image."
            ) from cached_model_error
        # A fresh native development environment may download the model once.
        return SentenceTransformer(model_name)
