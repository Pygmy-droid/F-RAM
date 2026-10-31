from __future__ import annotations
from pydantic import BaseModel
from typing import List, Dict, Any

class ClusterTrace(BaseModel):
    k: str
    features: Dict[str, float]
    logit: float | None = None
    conf_temp: float | None = None
    decision: str | None = None
    tau1: float | None = None
    tau2: float | None = None

class Trace(BaseModel):
    query_id: str
    proto_shortlist: Dict[str, int] = {}
    clusters: List[ClusterTrace] = []
    anchors: List[Dict[str, Any]] = []
    shards: List[Dict[str, Any]] = []
    coverage: Dict[str, Any] = {}
    rerank: Dict[str, Any] = {}
    budgets: Dict[str, float] = {}
    latency_ms: Dict[str, float] = {}
