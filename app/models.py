"""
Data models and schemas for No Wrong Door
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class AdapterResponse:
    source_name: str
    status: str  # 'ok', 'degraded', 'failed'
    records: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    error_message: Optional[str] = None
    http_status: Optional[int] = None
    latency_ms: float = 0.0
    attempts_made: int = 1
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class MatchConfidence:
    score: float
    level: str  # 'HIGH', 'MEDIUM', 'UNMATCHED'
    reasons: List[str] = field(default_factory=list)

@dataclass
class MatchedBenefit:
    ref: str
    name: str
    born: str
    addr: str
    town: str
    benefit_code: str
    review_due: str
    match_confidence: MatchConfidence

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['match_confidence'] = asdict(self.match_confidence)
        return d

@dataclass
class UnifiedResident:
    id: str
    first_name: str
    last_name: str
    date_of_birth: str
    address_line: str
    city: str
    phone: str
    program_status: str
    last_contact: str
    benefits: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
