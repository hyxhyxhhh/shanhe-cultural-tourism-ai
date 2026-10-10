from __future__ import annotations

import os
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from backend.auth import AuthenticatedUser, require_session


_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]*$")
_MAX_MODEL_ID_LENGTH = 200


class ModelCatalogConfigurationError(RuntimeError):
    pass


def parse_allowed_models(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None or not raw_value:
        raise ModelCatalogConfigurationError("CCODE_ALLOWED_MODELS must be configured")

    models = raw_value.split(",")
    if any(not model for model in models):
        raise ModelCatalogConfigurationError("CCODE_ALLOWED_MODELS contains an empty entry")
    if any(model != model.strip() for model in models):
        raise ModelCatalogConfigurationError(
            "CCODE_ALLOWED_MODELS entries must not contain surrounding whitespace"
        )
    if len(models) != len(set(models)):
        raise ModelCatalogConfigurationError("CCODE_ALLOWED_MODELS contains duplicate entries")
    if any(
        len(model) > _MAX_MODEL_ID_LENGTH or _MODEL_ID_PATTERN.fullmatch(model) is None
        for model in models
    ):
        raise ModelCatalogConfigurationError("CCODE_ALLOWED_MODELS contains an invalid model ID")
    return tuple(models)


def get_allowed_models() -> tuple[str, ...]:
    return parse_allowed_models(os.environ.get("CCODE_ALLOWED_MODELS"))


def require_allowed_models() -> tuple[str, ...]:
    try:
        return get_allowed_models()
    except ModelCatalogConfigurationError as exc:
        raise model_catalog_configuration_error(exc) from exc


class ModelCatalogDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[str]


CurrentUser = Annotated[AuthenticatedUser, Depends(require_session)]
AllowedModels = Annotated[tuple[str, ...], Depends(require_allowed_models)]

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=ModelCatalogDTO)
def list_models(_: CurrentUser, allowed_models: AllowedModels) -> ModelCatalogDTO:
    return ModelCatalogDTO(models=list(allowed_models))


def model_catalog_configuration_error(exc: ModelCatalogConfigurationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "MODEL_CATALOG_NOT_CONFIGURED",
            "message": "The model catalog is not configured correctly",
        },
    )
