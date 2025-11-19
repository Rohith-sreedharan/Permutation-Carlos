# BeatVegas Module Documentation
## Technical Specifications & Implementation Guide

**Version**: 1.0.0-mvp  
**Last Updated**: 2025-11-08  
**Status**: Production

---

## Table of Contents

1. [Module Architecture](#1-module-architecture)
2. [Data Ingestion Module](#2-data-ingestion-module)
3. [Normalization Module](#3-normalization-module)
4. [Permutation Engine Module](#4-permutation-engine-module)
5. [OmniEdge AI Stub Module](#5-omniedge-ai-stub-module)
6. [Logging Layer Module](#6-logging-layer-module)
7. [Data Persistence Module](#7-data-persistence-module)
8. [Dependencies & Integration](#8-dependencies--integration)

---

## 1. Module Architecture

### 1.1 System Overview

```mermaid
graph TB
    subgraph "External Layer"
        OddsAPI[The Odds API v4]
        OmniCore[OmniCore Platform]
    end
    
    subgraph "Application Layer"
        FastAPI[FastAPI Router]
        
        subgraph "Core Modules"
            Ingestion[Data Ingestion<br/>integrations/odds_api.py]
            Normalizer[Normalization<br/>services/normalization.py]
            Permuter[Permutation Engine<br/>core/permutation.py]
            AIStub[OmniEdge AI Stub<br/>core/ai_stub.py]
        end
        
        subgraph "Cross-Cutting Concerns"
            Logger[Logging Layer<br/>services/logger.py]
            DB[Data Persistence<br/>db/mongo.py]
        end
    end
    
    subgraph "Storage Layer"
        MongoDB[(MongoDB Atlas)]
        RedisCache[(Redis Cache)]
    end
    
    FastAPI --> Ingestion
    Ingestion --> OddsAPI
    Ingestion --> DB
    Ingestion -.log.-> Logger
    
    FastAPI --> Normalizer
    Normalizer --> DB
    Normalizer -.log.-> Logger
    
    FastAPI --> Permuter
    Permuter -.log.-> Logger
    
    FastAPI --> AIStub
    AIStub --> DB
    AIStub -.log.-> Logger
    
    Logger --> DB
    DB --> MongoDB
    FastAPI -.cache.-> RedisCache
    
    Logger -.stream.-> OmniCore
    
    style Ingestion fill:#BBDEFB
    style Normalizer fill:#C8E6C9
    style Permuter fill:#F8BBD0
    style AIStub fill:#D1C4E9
    style Logger fill:#FFE0B2
    style DB fill:#FFCCBC
```

### 1.2 Module Dependency Graph

```mermaid
graph LR
    A[integrations/odds_api.py] --> G[External: The Odds API]
    B[services/normalization.py] --> A
    C[core/permutation.py] --> B
    D[core/ai_stub.py] --> C
    E[services/logger.py] --> F[db/mongo.py]
    F --> H[MongoDB Atlas]
    
    A -.depends.-> E
    B -.depends.-> E
    C -.depends.-> E
    D -.depends.-> E
    D --> F
    
    I[routes/core_routes.py] --> A
    I --> B
    I --> C
    I --> D
    I --> E
    I --> F
    
    style A fill:#BBDEFB
    style B fill:#C8E6C9
    style C fill:#F8BBD0
    style D fill:#D1C4E9
    style E fill:#FFE0B2
    style F fill:#FFCCBC
```

---

## 2. Data Ingestion Module

**Module Name**: `omni.data.ingestion.odds_api_v4`  
**File**: `backend/integrations/odds_api.py`  
**Purpose**: Fetch real-time sports odds data from The Odds API (v4) and transform raw JSON responses into structured events.

### 2.1 Functionality Summary

- **Fetch Sports List**: Retrieve all available sports with metadata (active status, leagues, titles)
- **Fetch Odds**: Get live odds for specific sport with configurable markets (h2h, spreads, totals)
- **Fetch Scores**: Retrieve completed game scores for historical analysis (future feature)
- **Error Handling**: Custom `OddsApiError` exception with detailed error context

### 2.2 Input Schema

#### Function: `fetch_sports()`

**Parameters**: None

**HTTP Request**:
```http
GET https://api.the-odds-api.com/v4/sports
Authorization: apiKey {ODDS_API_KEY}
```

**Response**:
```json
[
  {
    "key": "basketball_nba",
    "active": true,
    "group": "Basketball",
    "description": "NBA",
    "title": "NBA",
    "has_outrights": false
  }
]
```

---

#### Function: `fetch_odds(sport_key, regions='us', markets='h2h')`

**Parameters**:
```python
sport_key: str         # Sport identifier (e.g., "basketball_nba")
regions: str           # Comma-separated regions (e.g., "us,uk,eu")
markets: str           # Comma-separated markets (e.g., "h2h,spreads,totals")
```

**HTTP Request**:
```http
GET https://api.the-odds-api.com/v4/sports/{sport_key}/odds?regions=us&markets=h2h
Authorization: apiKey {ODDS_API_KEY}
```

**Raw Response Example**:
```json
[
  {
    "id": "abc123def456",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2025-11-10T01:00:00Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Boston Celtics",
    "bookmakers": [
      {
        "key": "fanduel",
        "title": "FanDuel",
        "last_update": "2025-11-08T12:00:00Z",
        "markets": [
          {
            "key": "h2h",
            "last_update": "2025-11-08T12:00:00Z",
            "outcomes": [
              {
                "name": "Los Angeles Lakers",
                "price": 2.10
              },
              {
                "name": "Boston Celtics",
                "price": 1.80
              }
            ]
          }
        ]
      }
    ]
  }
]
```

### 2.3 Output Schema

#### Function: `fetch_odds()` - Structured Event

```python
{
    "event_id": "abc123def456",              # Unique event identifier
    "sport_key": "basketball_nba",           # Sport identifier
    "sport_title": "NBA",                    # Human-readable sport name
    "commence_time": "2025-11-10T01:00:00Z", # ISO 8601 UTC timestamp
    "home_team": "Los Angeles Lakers",       # Home team name
    "away_team": "Boston Celtics",           # Away team name
    "bookmakers": [...],                     # Full bookmaker data (nested)
    "fetched_at": "2025-11-08T12:00:00.000Z" # Ingestion timestamp
}
```

### 2.4 Key Functions

#### `fetch_sports() -> List[Dict]`

**Purpose**: Retrieve all available sports from The Odds API

**Returns**:
```python
[
    {
        "key": "basketball_nba",
        "active": True,
        "group": "Basketball",
        "description": "NBA",
        "title": "NBA",
        "has_outrights": False
    }
]
```

**Error Handling**:
```python
try:
    sports = fetch_sports()
except OddsApiError as e:
    # Handle API error
    logger.error(f"Odds API error: {e.status_code} - {e.message}")
```

---

#### `fetch_odds(sport_key: str, regions: str = 'us', markets: str = 'h2h') -> List[Dict]`

**Purpose**: Fetch live odds for specific sport with configurable markets

**Parameters**:
- `sport_key`: Sport identifier (e.g., "basketball_nba")
- `regions`: Comma-separated regions (default: "us")
- `markets`: Comma-separated markets (default: "h2h")

**Returns**: List of structured event dictionaries

**Rate Limiting**: 500 requests/month on free tier; 5 requests/second

**Timeout**: 30 seconds (configurable via ODDS_API_TIMEOUT)

**Caching**: Results cached in MongoDB `events` collection (TTL: 30 days)

---

### 2.5 Dependencies

```python
# External
import requests              # HTTP client
from typing import List, Dict, Optional

# Internal
from config import ODDS_API_KEY, ODDS_BASE_URL
from db.mongo import upsert_events
from services.logger import log_stage
```

### 2.6 Associated Endpoints

- `GET /api/odds/sports` (Legacy)
- `GET /api/odds/fetch` (Legacy)
- `GET /api/core/fetch-odds` (MVP)

### 2.7 Future OmniCore Integration

**Module Identifier**: `omni.data.ingestion.odds_api_v4`

**Event Types**:
- `beatvegas.odds.fetched`
- `beatvegas.odds.refresh_scheduled`

**Metrics**:
- `odds_api_requests_total` (counter)
- `odds_api_request_duration_seconds` (histogram)
- `odds_api_errors_total` (counter by status code)

**Configuration**:
```python
# .env.prod
ODDS_API_KEY=your_production_key
ODDS_BASE_URL=https://api.the-odds-api.com/v4
ODDS_API_TIMEOUT=30
ODDS_API_RETRY_COUNT=3
ODDS_API_RETRY_BACKOFF=2
```

---

## 3. Normalization Module

**Module Name**: `omni.data.normalization.sports_odds`  
**File**: `backend/services/normalization.py`  
**Purpose**: Transform heterogeneous odds data into canonical schema for cross-sport compatibility.

### 3.1 Functionality Summary

- **Event Normalization**: Convert raw API events to canonical schema
- **Batch Processing**: Efficiently normalize multiple events in one operation
- **Confidence Calculation**: Compute data quality score based on bookmaker/market diversity
- **Schema Versioning**: Track data schema version for backward compatibility

### 3.2 Input Schema

#### Function: `normalize_event(raw_event: Dict) -> Dict`

**Raw Event Structure**:
```python
{
    "id": "abc123def456",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2025-11-10T01:00:00Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Boston Celtics",
    "bookmakers": [
        {
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 2.10},
                        {"name": "Boston Celtics", "price": 1.80}
                    ]
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.91, "point": -5.5},
                        {"name": "Boston Celtics", "price": 1.91, "point": 5.5}
                    ]
                }
            ]
        },
        {
            "key": "draftkings",
            "title": "DraftKings",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 2.05},
                        {"name": "Boston Celtics", "price": 1.83}
                    ]
                }
            ]
        }
    ]
}
```

### 3.3 Output Schema (Canonical)

```python
{
    "event_id": "abc123def456",              # Unique event identifier
    "sport_key": "basketball_nba",           # Sport identifier
    "teams": [                               # Standardized team array
        "Los Angeles Lakers",
        "Boston Celtics"
    ],
    "odds": [                                # Flattened odds array
        {
            "bookmaker": "fanduel",          # Bookmaker key
            "market": "h2h",                 # Market type
            "name": "Los Angeles Lakers",    # Team/outcome name
            "price": 2.10,                   # Decimal odds
            "point": null                    # Spread/total point (if applicable)
        },
        {
            "bookmaker": "fanduel",
            "market": "spreads",
            "name": "Los Angeles Lakers",
            "price": 1.91,
            "point": -5.5
        },
        {
            "bookmaker": "draftkings",
            "market": "h2h",
            "name": "Los Angeles Lakers",
            "price": 2.05,
            "point": null
        }
    ],
    "confidence": 0.45,                      # Data quality score (0.0-1.0)
    "timestamp": "2025-11-08T12:00:00.000Z", # Normalization timestamp (UTC)
    "source": "odds_api_v4",                 # Data source identifier
    "version": "1.0.0"                       # Schema version
}
```

### 3.4 Confidence Calculation Algorithm

**Formula**:
```python
confidence = min(1.0, (unique_bookmakers * 0.05) + (unique_markets * 0.10))
```

**Rationale**:
- More bookmakers = higher market consensus
- More markets = broader coverage
- Cap at 1.0 for perfect confidence
- Linear scaling rewards data diversity

**Examples**:
```python
# Scenario 1: 3 bookmakers, 2 markets
confidence = min(1.0, (3 * 0.05) + (2 * 0.10)) = min(1.0, 0.35) = 0.35

# Scenario 2: 10 bookmakers, 5 markets
confidence = min(1.0, (10 * 0.05) + (5 * 0.10)) = min(1.0, 1.00) = 1.00

# Scenario 3: 5 bookmakers, 3 markets
confidence = min(1.0, (5 * 0.05) + (3 * 0.10)) = min(1.0, 0.55) = 0.55
```

### 3.5 Key Functions

#### `normalize_event(raw_event: Dict) -> Dict`

**Purpose**: Convert single raw event to canonical schema

**Algorithm**:
```python
def normalize_event(raw_event: Dict) -> Dict:
    # Extract teams
    teams = [raw_event["home_team"], raw_event["away_team"]]
    
    # Flatten odds
    odds = []
    unique_bookmakers = set()
    unique_markets = set()
    
    for bookmaker in raw_event.get("bookmakers", []):
        bookmaker_key = bookmaker["key"]
        unique_bookmakers.add(bookmaker_key)
        
        for market in bookmaker.get("markets", []):
            market_key = market["key"]
            unique_markets.add(market_key)
            
            for outcome in market.get("outcomes", []):
                odds.append({
                    "bookmaker": bookmaker_key,
                    "market": market_key,
                    "name": outcome["name"],
                    "price": outcome["price"],
                    "point": outcome.get("point")  # Optional
                })
    
    # Calculate confidence
    confidence = round(
        min(1.0, (len(unique_bookmakers) * 0.05 + len(unique_markets) * 0.10)),
        3
    )
    
    return {
        "event_id": raw_event["id"],
        "sport_key": raw_event["sport_key"],
        "teams": teams,
        "odds": odds,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "odds_api_v4",
        "version": "1.0.0"
    }
```

---

#### `normalize_batch(raw_events: List[Dict]) -> List[Dict]`

**Purpose**: Efficiently normalize multiple events

**Algorithm**:
```python
def normalize_batch(raw_events: List[Dict]) -> List[Dict]:
    return [normalize_event(event) for event in raw_events]
```

**Performance**: O(n*m) where n = events, m = avg bookmakers per event

**Optimization**: Future - parallel processing with `concurrent.futures`

### 3.6 Dependencies

```python
# Standard Library
from datetime import datetime, timezone
from typing import Dict, List

# Internal
from services.logger import log_stage
from db.mongo import insert_many
```

### 3.7 Associated Endpoints

- `POST /api/core/normalize` (MVP)

### 3.8 Future OmniCore Integration

**Module Identifier**: `omni.data.normalization.sports_canonical`

**Event Types**:
- `beatvegas.data.normalized`
- `beatvegas.data.validation_failed`

**Metrics**:
- `normalization_events_total` (counter)
- `normalization_duration_seconds` (histogram)
- `normalization_confidence_avg` (gauge)

**Configuration**:
```python
# .env.prod
NORMALIZATION_BATCH_SIZE=100
NORMALIZATION_TIMEOUT=60
CONFIDENCE_MIN_THRESHOLD=0.20
```

---

## 4. Permutation Engine Module

**Module Name**: `omni.ai.permutation.parlay_generator`  
**File**: `backend/core/permutation.py`  
**Purpose**: Generate optimal betting combinations (parlays) with risk-adjusted scoring.

### 4.1 Functionality Summary

- **Combination Generation**: Create n-leg parlays from normalized odds
- **Scoring Algorithm**: Rank combinations by normalized price product
- **Top-N Selection**: Return highest-scoring permutations
- **Configurable Legs**: Support 2-leg, 3-leg, or custom combinations

### 4.2 Input Schema

#### Function: `run_permutations(odds: List[Dict], max_legs: int, top_n: int) -> List[Dict]`

**Normalized Odds Array**:
```python
[
    {
        "bookmaker": "fanduel",
        "market": "h2h",
        "name": "Los Angeles Lakers",
        "price": 2.10,
        "point": null
    },
    {
        "bookmaker": "fanduel",
        "market": "spreads",
        "name": "Los Angeles Lakers",
        "price": 1.91,
        "point": -5.5
    },
    {
        "bookmaker": "draftkings",
        "market": "h2h",
        "name": "Boston Celtics",
        "price": 1.83,
        "point": null
    }
]
```

**Parameters**:
```python
odds: List[Dict]       # Normalized odds from canonical schema
max_legs: int          # Maximum combination size (default: 2)
top_n: int             # Number of top combinations to return (default: 5)
```

### 4.3 Output Schema

```python
[
    {
        "combo": [                          # Combination array
            {
                "bookmaker": "fanduel",
                "market": "h2h",
                "name": "Los Angeles Lakers",
                "price": 2.10,
                "point": null
            },
            {
                "bookmaker": "draftkings",
                "market": "h2h",
                "name": "Boston Celtics",
                "price": 1.83,
                "point": null
            }
        ],
        "score": 0.0385                     # Risk-adjusted score
    },
    {
        "combo": [...],
        "score": 0.0360
    }
]
```

### 4.4 Scoring Algorithm

**Formula**:
```python
score = product(normalized_price for price in combo)
normalized_price = min(price / 10.0, 1.0)
```

**Rationale**:
- Normalize prices to [0.0, 1.0] range (cap at 10.0 odds)
- Multiply normalized prices to get combination score
- Higher scores indicate better value combinations
- Favors moderate odds over extreme longshots

**Example**:
```python
# Combination: Lakers (2.10) + Celtics (1.83)
norm_lakers = min(2.10 / 10.0, 1.0) = 0.21
norm_celtics = min(1.83 / 10.0, 1.0) = 0.183
score = 0.21 * 0.183 = 0.03843
```

### 4.5 Key Functions

#### `run_permutations(odds: List[Dict], max_legs: int = 2, top_n: int = 5) -> List[Dict]`

**Purpose**: Generate and rank betting combinations

**Algorithm**:
```python
from itertools import combinations

def run_permutations(odds: List[Dict], max_legs: int = 2, top_n: int = 5) -> List[Dict]:
    # Generate all combinations of size max_legs
    combos = list(combinations(odds, max_legs))
    
    # Score each combination
    scored = []
    for combo in combos:
        score = score_combination(combo)
        scored.append({"combo": list(combo), "score": score})
    
    # Sort by score descending and return top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]
```

**Complexity**:
- Time: O(C(n, k) * k) where n = odds count, k = max_legs
- Space: O(C(n, k))
- For n=20, k=2: C(20,2) = 190 combinations

---

#### `score_combination(combo: List[Dict]) -> float`

**Purpose**: Calculate risk-adjusted score for combination

**Algorithm**:
```python
def score_combination(combo: List[Dict]) -> float:
    score = 1.0
    for odd in combo:
        price = odd["price"]
        normalized = min(price / 10.0, 1.0)
        score *= normalized
    return round(score, 5)
```

### 4.6 Dependencies

```python
# Standard Library
from itertools import combinations
from typing import List, Dict

# Internal
from services.logger import log_stage
```

### 4.7 Associated Endpoints

- `POST /api/core/run-permutations` (MVP)
- `POST /api/core/predict` (calls internally)

### 4.8 Future OmniCore Integration

**Module Identifier**: `omni.ai.permutation.parlay_generator`

**Event Types**:
- `beatvegas.permutation.generated`
- `beatvegas.permutation.optimized`

**Metrics**:
- `permutation_combos_generated_total` (counter)
- `permutation_duration_seconds` (histogram)
- `permutation_score_avg` (gauge)

**Configuration**:
```python
# .env.prod
PERMUTATION_MAX_LEGS=3
PERMUTATION_TOP_N=10
PERMUTATION_MIN_ODDS=1.20
PERMUTATION_MAX_ODDS=10.00
PERMUTATION_ALGORITHM=naive_v1  # Future: genetic_v2, ml_v3
```

---

## 5. OmniEdge AI Stub Module

**Module Name**: `omni.ai.prediction.omniedge_v1`  
**File**: `backend/core/ai_stub.py`  
**Purpose**: Placeholder for ML-powered prediction enhancement (to be replaced with trained OmniEdge AI model).

### 5.1 Functionality Summary

- **Confidence Enhancement**: Adjust base confidence using permutation scores
- **Model Versioning**: Track AI model version for A/B testing
- **Prediction IDs**: Generate unique identifiers for tracking
- **Future Ready**: Interface designed for seamless ML model integration

### 5.2 Input Schema

#### Function: `enhance_predictions(permutations: List[Dict], base_confidence: float) -> List[Dict]`

**Parameters**:
```python
permutations: List[Dict]  # Scored combinations from permutation engine
base_confidence: float    # Event base confidence from normalization (0.0-1.0)
```

**Permutations Array**:
```python
[
    {
        "combo": [
            {"bookmaker": "fanduel", "market": "h2h", "name": "Lakers", "price": 2.10},
            {"bookmaker": "draftkings", "market": "h2h", "name": "Celtics", "price": 1.83}
        ],
        "score": 0.0385
    }
]
```

### 5.3 Output Schema

```python
[
    {
        "combo": [...],                      # Original combination
        "base_score": 0.0385,                # Permutation score
        "adjusted_confidence": 0.2854,       # AI-adjusted confidence
        "model_version": "stub_v1.0",        # Model identifier
        "prediction_id": "pred_abc123_001"   # Unique prediction ID
    }
]
```

### 5.4 Enhancement Algorithm (Stub)

**Formula**:
```python
adjusted_confidence = (base_confidence * 0.6) + (base_score * 0.4)
```

**Rationale**:
- 60% weight on data quality (base_confidence)
- 40% weight on combination score
- Simple weighted average for MVP
- Future: Replace with trained ML model using historical performance

**Example**:
```python
# Inputs:
base_confidence = 0.45
base_score = 0.0385

# Calculation:
adjusted_confidence = (0.45 * 0.6) + (0.0385 * 0.4)
                    = 0.27 + 0.0154
                    = 0.2854
```

### 5.5 Key Functions

#### `enhance_predictions(permutations: List[Dict], base_confidence: float) -> List[Dict]`

**Purpose**: Apply AI enhancement to permutations

**Algorithm** (Stub):
```python
def enhance_predictions(permutations: List[Dict], base_confidence: float) -> List[Dict]:
    enhanced = []
    for idx, perm in enumerate(permutations):
        adjusted_confidence = round(
            (base_confidence * 0.6) + (perm["score"] * 0.4),
            4
        )
        
        enhanced.append({
            "combo": perm["combo"],
            "base_score": perm["score"],
            "adjusted_confidence": adjusted_confidence,
            "model_version": "stub_v1.0",
            "prediction_id": f"pred_{event_id}_{idx+1:03d}"
        })
    
    return enhanced
```

**Future Implementation** (OmniEdge AI):
```python
def enhance_predictions(permutations: List[Dict], event_context: Dict) -> List[Dict]:
    # Load trained ML model
    model = OmniEdgeModel.load("omniedge_sports_v2.pkl")
    
    # Feature engineering
    features = extract_features(permutations, event_context)
    
    # Model inference
    predictions = model.predict(features)
    
    # Ensemble with confidence score
    for perm, pred in zip(permutations, predictions):
        perm["adjusted_confidence"] = ensemble(
            base_confidence=event_context["confidence"],
            model_confidence=pred["confidence"],
            historical_performance=pred["historical_accuracy"]
        )
    
    return permutations
```

### 5.6 Dependencies

```python
# Standard Library
from typing import List, Dict

# Internal
from services.logger import log_stage
from db.mongo import insert_many

# Future ML Dependencies
# import torch
# import numpy as np
# from omniedge.models import SportsPredictor
```

### 5.7 Associated Endpoints

- `POST /api/core/predict` (MVP)

### 5.8 Future OmniCore Integration

**Module Identifier**: `omni.ai.prediction.omniedge_sports_v2`

**Event Types**:
- `beatvegas.prediction.enhanced`
- `beatvegas.model.inference_completed`

**Metrics**:
- `ai_predictions_total` (counter by model_version)
- `ai_inference_duration_seconds` (histogram)
- `ai_confidence_distribution` (histogram)

**Model Features** (Future):
```python
{
    "event_features": {
        "sport_key": "basketball_nba",
        "teams": ["Lakers", "Celtics"],
        "commence_time": "2025-11-10T01:00:00Z",
        "bookmaker_count": 10,
        "market_count": 5,
        "odds_variance": 0.12
    },
    "historical_features": {
        "team_win_rate_30d": 0.65,
        "head_to_head_last_5": [1, 0, 1, 1, 0],
        "avg_score_differential": 8.2
    },
    "market_features": {
        "line_movement_24h": -0.5,
        "public_betting_percentage": 0.58,
        "sharp_action_indicator": 0.32
    }
}
```

---

## 6. Logging Layer Module

**Module Name**: `omni.observability.structured_logging`  
**File**: `backend/services/logger.py`  
**Purpose**: Structured logging for pipeline transparency and OmniCore integration.

### 6.1 Functionality Summary

- **Stage Logging**: Track each pipeline stage (start, processing, completion)
- **Structured Format**: JSON logs with consistent schema
- **Request Tracing**: Correlation IDs for distributed tracing (future)
- **Performance Metrics**: Duration, memory, CPU usage per operation (future)

### 6.2 Input Schema

#### Function: `log_stage(module: str, stage: str, data: Dict, level: str = "INFO") -> None`

**Parameters**:
```python
module: str     # Module identifier (e.g., "fetch_odds", "normalize", "predict")
stage: str      # Stage name (e.g., "start", "stored", "enhanced")
data: Dict      # Input/output data to log
level: str      # Log level: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
```

**Example Call**:
```python
log_stage(
    module="normalize",
    stage="batch",
    data={
        "input": {"event_count": 14},
        "output": {"normalized_count": 14, "avg_confidence": 0.45}
    },
    level="INFO"
)
```

### 6.3 Output Schema (Log Entry)

**Current Schema** (MVP):
```python
{
    "module": "normalize",
    "stage": "batch",
    "level": "INFO",
    "timestamp": "2025-11-08T12:00:00.123Z",
    "input": {"event_count": 14},
    "output": {"normalized_count": 14, "avg_confidence": 0.45}
}
```

**Enhanced Schema** (OmniCore-compatible):
```python
{
    "log_id": "log_uuid_001",                # UUID for unique log identification
    "module": "omni.data.normalization.sports_canonical",
    "stage": "batch",
    "level": "INFO",
    "timestamp": "2025-11-08T12:00:00.123Z",
    "request_id": "req_abc123",              # Request correlation ID
    "trace_id": "trace_xyz789",              # Distributed trace ID
    "input": {"event_count": 14},
    "output": {"normalized_count": 14, "avg_confidence": 0.45},
    "performance": {
        "duration_ms": 152.3,                # Execution time
        "memory_mb": 38.2,                   # Memory usage
        "cpu_percent": 12.5                  # CPU utilization
    },
    "metadata": {
        "environment": "production",
        "version": "1.0.0",
        "host": "beatvegas-app-01",
        "pod": "beatvegas-7d9f8b-xyz123"
    }
}
```

### 6.4 Key Functions

#### `log_stage(module: str, stage: str, data: Dict, level: str = "INFO") -> None`

**Purpose**: Log pipeline stage with structured format

**Current Implementation**:
```python
from datetime import datetime, timezone
from db.mongo import insert_log_entry

def log_stage(module: str, stage: str, data: Dict, level: str = "INFO") -> None:
    log_entry = {
        "module": module,
        "stage": stage,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": data.get("input"),
        "output": data.get("output")
    }
    
    insert_log_entry("logs_core_ai", log_entry)
```

**Enhanced Implementation** (Future):
```python
import uuid
import time
import psutil
import socket

def log_stage(module: str, stage: str, data: Dict, level: str = "INFO", 
              request_id: str = None, trace_id: str = None) -> None:
    start_time = time.time()
    process = psutil.Process()
    
    log_entry = {
        "log_id": str(uuid.uuid4()),
        "module": module,
        "stage": stage,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id or f"req_{uuid.uuid4().hex[:8]}",
        "trace_id": trace_id or f"trace_{uuid.uuid4().hex[:8]}",
        "input": data.get("input"),
        "output": data.get("output"),
        "performance": {
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "cpu_percent": round(process.cpu_percent(interval=0.1), 2)
        },
        "metadata": {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "host": socket.gethostname(),
            "pod": os.getenv("POD_NAME", "local")
        }
    }
    
    insert_log_entry("logs_core_ai", log_entry)
```

### 6.5 Dependencies

```python
# Standard Library
from datetime import datetime, timezone
from typing import Dict

# Future Dependencies
# import uuid
# import time
# import psutil
# import socket

# Internal
from db.mongo import insert_log_entry
```

### 6.6 Associated Endpoints

- `GET /api/core/logs` (MVP)
- `POST /omnicore/logs/normalized` (NDJSON stream - future)

### 6.7 Future OmniCore Integration

**Module Identifier**: `omni.observability.structured_logging`

**Stream Format** (NDJSON):
```json
{"log_id":"log_001","module":"normalize","timestamp":"2025-11-08T12:00:00.000Z","input":{...},"output":{...}}
{"log_id":"log_002","module":"predict","timestamp":"2025-11-08T12:00:01.000Z","input":{...},"output":{...}}
```

**Configuration**:
```python
# .env.prod
LOG_FORMAT=json
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=14
OMNICORE_STREAM_ENABLED=true
OMNICORE_STREAM_URL=https://gateway.omnicore.com/logs/normalized
OMNICORE_STREAM_BATCH_SIZE=100
OMNICORE_STREAM_INTERVAL=5
```

---

## 7. Data Persistence Module

**Module Name**: `omni.data.persistence.mongodb_atlas`  
**File**: `backend/db/mongo.py`  
**Purpose**: MongoDB operations with Atlas-ready connection pooling and optimized indexes.

### 7.1 Functionality Summary

- **Index Management**: Automatic index creation on app startup
- **Batch Operations**: Efficient multi-document inserts
- **Event Upserts**: Idempotent event storage (avoid duplicates)
- **Log Queries**: Flexible log retrieval with filtering
- **TTL Indexes**: Automatic data expiration for logs

### 7.2 MongoDB Collections

#### Collection: `events`

**Purpose**: Store raw events from The Odds API

**Schema**:
```python
{
    "_id": ObjectId("..."),
    "event_id": "abc123def456",              # Unique event identifier
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2025-11-10T01:00:00Z",
    "home_team": "Los Angeles Lakers",
    "away_team": "Boston Celtics",
    "bookmakers": [...],                     # Full bookmaker nested data
    "fetched_at": "2025-11-08T12:00:00.000Z"
}
```

**Indexes**:
```python
# Unique index on event_id (prevent duplicates)
db.events.create_index([("event_id", 1)], unique=True)

# Compound index on sport_key + commence_time (query optimization)
db.events.create_index([("sport_key", 1), ("commence_time", -1)])

# TTL index (auto-delete after 30 days)
db.events.create_index([("fetched_at", 1)], expireAfterSeconds=2592000)
```

---

#### Collection: `normalized_data`

**Purpose**: Store canonical normalized events

**Schema**:
```python
{
    "_id": ObjectId("..."),
    "event_id": "abc123def456",
    "sport_key": "basketball_nba",
    "teams": ["Los Angeles Lakers", "Boston Celtics"],
    "odds": [
        {
            "bookmaker": "fanduel",
            "market": "h2h",
            "name": "Los Angeles Lakers",
            "price": 2.10,
            "point": null
        }
    ],
    "confidence": 0.45,
    "timestamp": "2025-11-08T12:00:00.000Z",
    "source": "odds_api_v4",
    "version": "1.0.0"
}
```

**Indexes**:
```python
# Descending timestamp (recent-first queries)
db.normalized_data.create_index([("timestamp", -1)])

# Confidence index (filter high-confidence events)
db.normalized_data.create_index([("confidence", -1)])

# Event ID index (lookup by event)
db.normalized_data.create_index([("event_id", 1)])
```

---

#### Collection: `predictions`

**Purpose**: Store AI-enhanced predictions

**Schema**:
```python
{
    "_id": ObjectId("..."),
    "prediction_id": "pred_abc123_001",
    "event_id": "abc123def456",
    "combo": [...],
    "base_score": 0.0385,
    "adjusted_confidence": 0.2854,
    "model_version": "stub_v1.0",
    "created_at": "2025-11-08T12:00:00.000Z"
}
```

**Indexes**:
```python
# Compound index on event_id + timestamp
db.predictions.create_index([("event_id", 1), ("created_at", -1)])

# Confidence index (filter high-confidence predictions)
db.predictions.create_index([("adjusted_confidence", -1)])
```

---

#### Collection: `logs_core_ai`

**Purpose**: Store structured pipeline logs

**Schema**:
```python
{
    "_id": ObjectId("..."),
    "log_id": "log_uuid_001",
    "module": "omni.data.normalization.sports_canonical",
    "stage": "batch",
    "level": "INFO",
    "timestamp": "2025-11-08T12:00:00.123Z",
    "request_id": "req_abc123",
    "trace_id": "trace_xyz789",
    "input": {...},
    "output": {...},
    "performance": {
        "duration_ms": 152.3,
        "memory_mb": 38.2,
        "cpu_percent": 12.5
    },
    "metadata": {...}
}
```

**Indexes**:
```python
# Compound index on module + timestamp
db.logs_core_ai.create_index([("module", 1), ("timestamp", -1)])

# Compound index on level + timestamp (filter by severity)
db.logs_core_ai.create_index([("level", 1), ("timestamp", -1)])

# TTL index (auto-delete after 14 days)
db.logs_core_ai.create_index([("timestamp", 1)], expireAfterSeconds=1209600)
```

### 7.3 Key Functions

#### `ensure_indexes() -> None`

**Purpose**: Create all optimized indexes on app startup

**Algorithm**:
```python
from pymongo import MongoClient, ASCENDING, DESCENDING

def ensure_indexes() -> None:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    # events collection
    db.events.create_index([("event_id", ASCENDING)], unique=True)
    db.events.create_index([("sport_key", ASCENDING), ("commence_time", DESCENDING)])
    db.events.create_index([("fetched_at", ASCENDING)], expireAfterSeconds=2592000)
    
    # normalized_data collection
    db.normalized_data.create_index([("timestamp", DESCENDING)])
    db.normalized_data.create_index([("confidence", DESCENDING)])
    db.normalized_data.create_index([("event_id", ASCENDING)])
    
    # predictions collection
    db.predictions.create_index([("event_id", ASCENDING), ("created_at", DESCENDING)])
    db.predictions.create_index([("adjusted_confidence", DESCENDING)])
    
    # logs_core_ai collection
    db.logs_core_ai.create_index([("module", ASCENDING), ("timestamp", DESCENDING)])
    db.logs_core_ai.create_index([("level", ASCENDING), ("timestamp", DESCENDING)])
    db.logs_core_ai.create_index([("timestamp", ASCENDING)], expireAfterSeconds=1209600)
```

---

#### `insert_many(collection_name: str, documents: List[Dict]) -> None`

**Purpose**: Batch insert multiple documents efficiently

**Algorithm**:
```python
def insert_many(collection_name: str, documents: List[Dict]) -> None:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    db[collection_name].insert_many(documents)
```

---

#### `upsert_events(collection_name: str, events: List[Dict]) -> None`

**Purpose**: Insert or update events (idempotent operation)

**Algorithm**:
```python
from pymongo import UpdateOne

def upsert_events(collection_name: str, events: List[Dict]) -> None:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    operations = [
        UpdateOne(
            {"event_id": event["event_id"]},
            {"$set": event},
            upsert=True
        )
        for event in events
    ]
    
    db[collection_name].bulk_write(operations)
```

---

#### `find_logs(module: str = None, level: str = None, limit: int = 100) -> List[Dict]`

**Purpose**: Query logs with flexible filtering

**Algorithm**:
```python
def find_logs(module: str = None, level: str = None, limit: int = 100) -> List[Dict]:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    filter_query = {}
    if module:
        filter_query["module"] = module
    if level:
        filter_query["level"] = level
    
    cursor = db.logs_core_ai.find(filter_query).sort("timestamp", DESCENDING).limit(limit)
    return list(cursor)
```

### 7.4 Dependencies

```python
# External
from pymongo import MongoClient, ASCENDING, DESCENDING, UpdateOne
from typing import List, Dict

# Internal
from config import MONGO_URI, DATABASE_NAME
```

### 7.5 Associated Endpoints

- All endpoints use data persistence module

### 7.6 Future OmniCore Integration

**Configuration**:
```python
# .env.prod
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/beatvegas_prod
DATABASE_NAME=beatvegas_prod
MONGO_MAX_POOL_SIZE=100
MONGO_MIN_POOL_SIZE=10
MONGO_CONNECT_TIMEOUT_MS=10000
MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
```

---

## 8. Dependencies & Integration

### 8.1 Python Dependencies

```text
# requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
requests==2.31.0
pymongo[srv]==4.6.1
python-dotenv==1.0.0
apscheduler==3.10.4
pydantic==2.5.3

# Future ML Dependencies
# torch==2.1.2
# numpy==1.26.3
# scikit-learn==1.4.0
# pandas==2.2.0
```

### 8.2 External API Integration

**The Odds API v4**:
- **Base URL**: https://api.the-odds-api.com/v4
- **Authentication**: API Key in query params
- **Rate Limits**: 500 requests/month (free tier), 5 requests/second
- **Endpoints Used**:
  - `GET /sports` - List available sports
  - `GET /sports/{sport_key}/odds` - Fetch live odds
  - `GET /sports/{sport_key}/scores` - Fetch completed scores (future)

### 8.3 MongoDB Atlas Integration

**Connection String**:
```
mongodb+srv://beatvegas_app:PASSWORD@beatvegas-prod.xxxxx.mongodb.net/beatvegas_prod?retryWrites=true&w=majority
```

**Features Used**:
- Replica sets for high availability
- Continuous backup (7-30 day retention)
- Performance monitoring
- Connection pooling (10-100 connections)
- Encryption at rest
- IP whitelist / VPC peering

### 8.4 OmniCore Platform Integration (Future)

**Gateway URL**: `https://gateway.omnicore.com`

**Endpoints**:
- `POST /logs/normalized` - NDJSON log stream
- `GET /ai/v1/models/{model_id}` - Fetch trained model
- `POST /ai/v1/predict` - Inference endpoint
- `GET /metrics/beatvegas` - Performance metrics

**Authentication**:
```http
Authorization: Bearer {OMNICORE_API_KEY}
X-Service-ID: beatvegas-mvp
```

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-11-08  
**Maintained By**: BeatVegas Engineering Team

**END OF DOCUMENT**
