from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Literal

# GROUP 1 — Document Analyzer models

class UploadResponse(BaseModel):
    session_id: str
    document_type: str
    page_count: int
    key_terms: List[str]
    message: str

    model_config = ConfigDict(json_schema_extra={"example": {}})

class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=2, max_length=500)

    model_config = ConfigDict(json_schema_extra={"example": {}})

class RiskyClause(BaseModel):
    clause_type: str
    excerpt: str = Field(max_length=120)
    risk_level: Literal["high", "medium", "low"]
    plain_explanation: str

    model_config = ConfigDict(json_schema_extra={"example": {}})

class ClausesResponse(BaseModel):
    session_id: str
    clauses: List[RiskyClause]
    total_found: int

    model_config = ConfigDict(json_schema_extra={"example": {}})

# GROUP 2 — Product Comparator models

class CreditCardProduct(BaseModel):
    name: str
    annual_fee: float = Field(default=0)
    apr: float
    cashback_percent: float = Field(default=0)
    reward_points_per_100: float = Field(default=0)
    foreign_transaction_fee: float = Field(default=0)
    welcome_bonus: Optional[str] = None
    travel_insurance: bool = Field(default=False)
    lounge_access: bool = Field(default=False)

    model_config = ConfigDict(json_schema_extra={"example": {}})

class LoanProduct(BaseModel):
    name: str
    interest_rate: float
    processing_fee: float = Field(default=0)
    tenure_months: int
    emi_amount: Optional[float] = None
    prepayment_penalty_percent: float = Field(default=0)
    foreclosure_charges: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={"example": {}})

class InsuranceProduct(BaseModel):
    name: str
    coverage_amount: float
    annual_premium: float
    deductible: float = Field(default=0)
    exclusions: Optional[str] = None
    claim_settlement_ratio: float
    accidental_cover: bool = Field(default=False)
    international_cover: bool = Field(default=False)

    model_config = ConfigDict(json_schema_extra={"example": {}})

class CompareRequest(BaseModel):
    product_type: Literal["credit_card", "loan", "insurance"]
    product_a: Dict
    product_b: Dict

    model_config = ConfigDict(json_schema_extra={"example": {}})

class ComparisonRow(BaseModel):
    attribute: str
    value_a: str
    value_b: str
    winner: Literal["a", "b", "tie"]

    model_config = ConfigDict(json_schema_extra={"example": {}})

class CompareResponse(BaseModel):
    product_type: str
    comparison: List[ComparisonRow]
    gaps: List[str]
    summary: str

    model_config = ConfigDict(json_schema_extra={"example": {}})


# GROUP 4 — Market Explainer models

class MarketExplainResponse(BaseModel):
    query: str
    possible_reasons: List[str]
    background: str
    historical_context: str
    what_to_watch: List[str]
    sources_used: List[str]

    model_config = ConfigDict(json_schema_extra={"example": {}})

# GROUP 5 — News models

class NewsArticle(BaseModel):
    id: int
    headline: str
    source: str
    url: str
    published_at: str
    category: str
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = None
    summary: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={"example": {}})

class NewsResponse(BaseModel):
    articles: List[NewsArticle]
    total: int
    last_updated: str

    model_config = ConfigDict(json_schema_extra={"example": {}})

class NewsExplainRequest(BaseModel):
    headline: str
    url: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={"example": {}})
