"""Optional public-data research adapters."""

from .service import (
    PublicSearchProvider,
    ResearchScope,
    ResearchResult,
    ResearchService,
    SearchItem,
)
from .volcengine import (
    SearchConfigurationError,
    SearchProviderError,
    SearchRequestError,
    VolcengineGlobalSearchProvider,
    VolcengineSearchSettings,
)

__all__ = [
    "PublicSearchProvider",
    "ResearchScope",
    "ResearchResult",
    "ResearchService",
    "SearchConfigurationError",
    "SearchItem",
    "SearchProviderError",
    "SearchRequestError",
    "VolcengineGlobalSearchProvider",
    "VolcengineSearchSettings",
]
