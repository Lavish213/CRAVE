from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------
# Core Constants
# ---------------------------------------------------------

DEFAULT_CURRENCY = "USD"

SOURCE_PROVIDER = "provider"
SOURCE_API = "api"
SOURCE_GRAPHQL = "graphql"
SOURCE_HTML = "html"
SOURCE_JSONLD = "jsonld"
SOURCE_HYDRATION = "hydration"
SOURCE_IFRAME = "iframe"
SOURCE_JS_BUNDLE = "js_bundle"
SOURCE_PDF = "pdf"


# ---------------------------------------------------------
# Extraction Layer
# Raw items returned from any extractor
# ---------------------------------------------------------

@dataclass(slots=True)
class ExtractedMenuItem:

    # identity
    name: str
    section: Optional[str] = None

    # pricing (STRUCTURED — critical fix)
    price_cents: Optional[int] = None
    min_price_cents: Optional[int] = None
    max_price_cents: Optional[int] = None
    currency: Optional[str] = DEFAULT_CURRENCY

    # metadata
    description: Optional[str] = None
    image_url: Optional[str] = None

    # provider tracking (CRITICAL)
    provider: Optional[str] = None
    provider_item_id: Optional[str] = None

    # flags (from parser)
    is_available: Optional[bool] = None
    badges: List[str] = field(default_factory=list)

    # extraction metadata
    source_type: Optional[str] = None
    source_url: Optional[str] = None

    # modifiers (future-safe)
    modifiers: List[Dict[str, Any]] = field(default_factory=list)

    raw: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class ExtractedMenu:

    items: List[ExtractedMenuItem] = field(default_factory=list)

    source_url: Optional[str] = None
    provider: Optional[str] = None
    source_type: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# Normalization Layer
# After cleaning + price normalization
# ---------------------------------------------------------

@dataclass(slots=True)
class NormalizedMenuItem:

    name: str
    section: str

    price_cents: Optional[int]
    currency: str = DEFAULT_CURRENCY

    description: Optional[str] = None
    image_url: Optional[str] = None

    # fingerprint (dedupe backbone)
    fingerprint: str = ""

    # passthrough
    provider: Optional[str] = None
    provider_item_id: Optional[str] = None

    source_url: Optional[str] = None
    source_type: Optional[str] = None

    # flags
    is_available: Optional[bool] = None
    badges: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# Claim Payload
# Object used for database ingestion
# ---------------------------------------------------------

@dataclass(slots=True)
class MenuClaimPayload:

    fingerprint: str

    name: str
    section: str

    price_cents: Optional[int]
    currency: str

    description: Optional[str] = None
    image_url: Optional[str] = None

    source_url: Optional[str] = None

    provider: Optional[str] = None
    provider_item_id: Optional[str] = None
    source_type: Optional[str] = None

    external_menu_id: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# Canonical Menu Objects
# Final merged menu used by app
# ---------------------------------------------------------

@dataclass(slots=True)
class CanonicalMenuItem:

    fingerprint: str

    name: str
    section: str

    price_cents: Optional[int]
    currency: Optional[str]

    description: Optional[str] = None
    image_url: Optional[str] = None

    # 🔥 ALIGNED WITH DB
    confidence_score: float = 0.0

    # lineage
    provider: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalMenuSection:

    name: str
    items: List[CanonicalMenuItem] = field(default_factory=list)

    order: Optional[int] = None


@dataclass(slots=True)
class CanonicalMenu:

    sections: List[CanonicalMenuSection] = field(default_factory=list)

    item_count: int = 0

    source_url: Optional[str] = None
    provider: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# Endpoint Discovery Contracts
# ---------------------------------------------------------

@dataclass(slots=True)
class EndpointCandidate:

    url: str
    method: str = "GET"

    headers: Optional[Dict[str, str]] = None
    payload: Optional[Dict[str, Any]] = None

    confidence: float = 0.0
    source: Optional[str] = None


@dataclass(slots=True)
class GraphQLCandidate:

    endpoint: str

    operation_name: Optional[str] = None
    query: Optional[str] = None

    variables: Optional[Dict[str, Any]] = None
    persisted_hash: Optional[str] = None

    confidence: float = 0.0


@dataclass(slots=True)
class JSBundle:

    url: str
    content: Optional[str] = None

    discovered_endpoints: List[EndpointCandidate] = field(default_factory=list)


# ---------------------------------------------------------
# Extraction Result Ranking
# ---------------------------------------------------------

@dataclass(slots=True)
class ExtractionResult:

    extractor: str
    items: List[ExtractedMenuItem]

    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------
# Request Replay Contracts
# ---------------------------------------------------------

@dataclass(slots=True)
class ReplayRequest:

    url: str
    method: str = "GET"

    headers: Optional[Dict[str, str]] = None
    payload: Optional[Any] = None


@dataclass(slots=True)
class ReplayResponse:

    status_code: int

    body: Optional[str] = None
    json: Optional[Any] = None

    headers: Optional[Dict[str, str]] = None


# ---------------------------------------------------------
# Worker / Ingestion Contracts
# ---------------------------------------------------------

@dataclass(slots=True)
class MenuExtractionJob:

    url: str
    html: Optional[str] = None
    provider_hint: Optional[str] = None


@dataclass(slots=True)
class MenuExtractionResult:

    url: str
    items: List[ExtractedMenuItem]

    extractor: Optional[str] = None
    provider: Optional[str] = None

    item_count: int = 0