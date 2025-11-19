# BeatVegas API Flow Documentation
## Complete Request/Response Sequences & Data Flow

**Version**: 1.0.0-mvp  
**Last Updated**: 2025-11-08  
**Status**: Production

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Complete Data Pipeline](#2-complete-data-pipeline)
3. [Endpoint Specifications](#3-endpoint-specifications)
4. [Error Handling](#4-error-handling)
5. [Performance Characteristics](#5-performance-characteristics)
6. [OmniCore Integration](#6-omnicore-integration)

---

## 1. Architecture Overview

### 1.1 System Components

```mermaid
graph TB
    subgraph "Client Layer"
        FE[React Frontend]
        Mobile[Mobile Apps]
        API_Client[Third-party APIs]
    end
    
    subgraph "Gateway Layer (Future)"
        Kong[Kong API Gateway]
        Auth[Authentication]
        RateLimit[Rate Limiting]
    end
    
    subgraph "BeatVegas Backend"
        FastAPI[FastAPI Application]
        
        subgraph "Core Modules"
            Ingestion[Data Ingestion]
            Normalize[Normalization]
            Permute[Permutation Engine]
            AI[OmniEdge AI Stub]
        end
        
        subgraph "Cross-Cutting"
            Logger[Logging Layer]
            Monitor[Monitoring]
        end
    end
    
    subgraph "Data Layer"
        MongoDB[(MongoDB Atlas)]
        Cache[(Redis Cache)]
    end
    
    subgraph "External Services"
        OddsAPI[The Odds API]
        OmniCore[OmniCore Platform]
    end
    
    FE --> Kong
    Mobile --> Kong
    API_Client --> Kong
    Kong --> Auth
    Auth --> RateLimit
    RateLimit --> FastAPI
    
    FastAPI --> Ingestion
    Ingestion --> Normalize
    Normalize --> Permute
    Permute --> AI
    
    Ingestion -.log.-> Logger
    Normalize -.log.-> Logger
    Permute -.log.-> Logger
    AI -.log.-> Logger
    
    FastAPI --> Monitor
    
    Ingestion --> OddsAPI
    FastAPI --> MongoDB
    FastAPI -.cache.-> Cache
    Logger --> MongoDB
    Monitor --> OmniCore
    
    style FastAPI fill:#4CAF50
    style MongoDB fill:#47A248
    style OddsAPI fill:#FF9800
    style OmniCore fill:#2196F3
```

---

## 2. Complete Data Pipeline

### 2.1 End-to-End Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API as FastAPI Backend
    participant Ingestion
    participant Normalizer
    participant Permuter
    participant AI as OmniEdge AI
    participant Logger
    participant MongoDB
    participant OddsAPI as The Odds API
    
    User->>Frontend: Request NBA predictions
    Frontend->>API: GET /api/core/fetch-odds?sport=basketball_nba
    
    Note over API,Logger: Stage 1: Data Ingestion
    API->>Logger: log_stage("fetch_odds", "start")
    API->>Ingestion: fetch_odds(basketball_nba)
    Ingestion->>OddsAPI: GET /sports/basketball_nba/odds
    OddsAPI-->>Ingestion: Raw odds data [14 events]
    Ingestion-->>API: Parsed events
    API->>MongoDB: upsert_events("events", data)
    API->>Logger: log_stage("fetch_odds", "stored", {count: 14})
    API-->>Frontend: {status: "ok", count: 14}
    
    Frontend->>API: POST /api/core/normalize?limit=14
    
    Note over API,Logger: Stage 2: Normalization
    API->>MongoDB: find_events("events", limit=14)
    MongoDB-->>API: Raw events [14]
    API->>Normalizer: normalize_batch(events)
    Normalizer-->>API: Canonical events [14]
    API->>MongoDB: insert_many("normalized_data", events)
    API->>Logger: log_stage("normalize", "batch", {input: 14, output: 14})
    API-->>Frontend: {normalized: [...]}
    
    Frontend->>User: Display: 14 events normalized
    User->>Frontend: Select event_id: abc123
    
    Frontend->>API: POST /api/core/predict?event_id=abc123
    
    Note over API,Logger: Stage 3: Permutation Generation
    API->>MongoDB: find_events("normalized_data", {event_id: "abc123"})
    MongoDB-->>API: Normalized event
    API->>Permuter: run_permutations(odds, max_legs=2, top_n=5)
    Permuter-->>API: Top 5 combinations
    API->>Logger: log_stage("permutations", "generated", {count: 5})
    
    Note over API,Logger: Stage 4: AI Enhancement
    API->>AI: enhance_predictions(perms, confidence=0.45)
    AI-->>API: Enhanced predictions [5]
    API->>MongoDB: insert_many("predictions", data)
    API->>Logger: log_stage("predict", "enhanced", {count: 5})
    API-->>Frontend: {predictions: [...]}
    
    Frontend->>User: Display predictions with confidence scores
    
    User->>Frontend: View audit logs
    Frontend->>API: GET /api/core/logs?module=predict&limit=10
    API->>MongoDB: find_logs(module="predict", limit=10)
    MongoDB-->>API: Log entries [10]
    API-->>Frontend: {logs: [...]}
    Frontend->>User: Show transparency logs
```

### 2.2 Data Transformation Pipeline

```mermaid
graph LR
    A[Raw API Response] -->|Ingestion| B[Structured Events]
    B -->|Normalization| C[Canonical Schema]
    C -->|Permutation| D[Combinations]
    D -->|AI Enhancement| E[Predictions]
    
    B -.->|Log| L[logs_core_ai]
    C -.->|Log| L
    D -.->|Log| L
    E -.->|Log| L
    
    B -->|Store| DB1[events]
    C -->|Store| DB2[normalized_data]
    E -->|Store| DB3[predictions]
    
    style A fill:#FFE0B2
    style B fill:#BBDEFB
    style C fill:#C8E6C9
    style D fill:#F8BBD0
    style E fill:#D1C4E9
    style L fill:#CFD8DC
```

---

## 3. Endpoint Specifications

### 3.1 Fetch Odds Endpoint

**Endpoint**: `GET /api/core/fetch-odds`

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant OddsAPI
    participant Logger
    participant MongoDB
    
    Client->>FastAPI: GET /fetch-odds?sport=basketball_nba
    
    Note over FastAPI: Validate parameters
    FastAPI->>Logger: log_stage("fetch_odds", "start", input)
    Logger->>MongoDB: Insert log entry
    
    FastAPI->>OddsAPI: GET /sports/basketball_nba/odds
    alt Success (200 OK)
        OddsAPI-->>FastAPI: Raw events JSON
        FastAPI->>MongoDB: upsert_events("events", events)
        FastAPI->>Logger: log_stage("fetch_odds", "stored", output)
        FastAPI-->>Client: 200 {status: "ok", count: N}
    else API Error (401/403)
        OddsAPI-->>FastAPI: 401 Unauthorized
        FastAPI->>Logger: log_stage("fetch_odds", "error", error_details, level="ERROR")
        FastAPI-->>Client: 500 {detail: "API authentication failed"}
    else Timeout
        OddsAPI-->>FastAPI: Timeout
        FastAPI->>Logger: log_stage("fetch_odds", "error", timeout_details, level="ERROR")
        FastAPI-->>Client: 503 {detail: "Service timeout"}
    end
```

**Request**:
```http
GET /api/core/fetch-odds?sport=basketball_nba&region=us&markets=h2h,spreads HTTP/1.1
Host: api.beatvegas.com
X-API-Key: your_api_key
Accept: application/json
```

**Response (Success)**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-08T12:00:00.000Z",
  "count": 14,
  "meta": {
    "sport": "basketball_nba",
    "region": "us",
    "markets": ["h2h", "spreads"],
    "source": "odds_api_v4"
  }
}
```

**Response (Error)**:
```json
{
  "status": "error",
  "timestamp": "2025-11-08T12:00:00.000Z",
  "error": {
    "code": "ODDS_API_ERROR",
    "message": "The Odds API returned 401: Invalid API key",
    "details": "Check ODDS_API_KEY environment variable"
  }
}
```

---

### 3.2 Normalize Endpoint

**Endpoint**: `POST /api/core/normalize`

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Normalizer
    participant Logger
    participant MongoDB
    
    Client->>FastAPI: POST /normalize?limit=25
    
    FastAPI->>MongoDB: find_events("events", limit=25)
    MongoDB-->>FastAPI: Raw events [25]
    
    Note over FastAPI,Normalizer: Transform to canonical schema
    FastAPI->>Normalizer: normalize_batch(events)
    
    loop For each event
        Normalizer->>Normalizer: extract_teams(event)
        Normalizer->>Normalizer: flatten_odds(event)
        Normalizer->>Normalizer: calculate_confidence(event)
    end
    
    Normalizer-->>FastAPI: Canonical events [25]
    
    FastAPI->>MongoDB: insert_many("normalized_data", events)
    FastAPI->>Logger: log_stage("normalize", "batch", {input: 25, output: 25})
    
    FastAPI-->>Client: 200 {status: "ok", normalized: [...]}
```

**Request**:
```http
POST /api/core/normalize?limit=10 HTTP/1.1
Host: api.beatvegas.com
X-API-Key: your_api_key
Content-Type: application/json
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-08T12:01:00.000Z",
  "normalized": [
    {
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
        },
        {
          "bookmaker": "fanduel",
          "market": "spreads",
          "name": "Los Angeles Lakers",
          "price": 1.91,
          "point": -5.5
        }
      ],
      "confidence": 0.45,
      "timestamp": "2025-11-08T12:01:00.000Z",
      "source": "odds_api_v4",
      "version": "1.0.0"
    }
  ]
}
```

---

### 3.3 Run Permutations Endpoint

**Endpoint**: `POST /api/core/run-permutations`

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Permuter
    participant Logger
    participant MongoDB
    
    Client->>FastAPI: POST /run-permutations?event_id=abc123&max_legs=2&top_n=5
    
    FastAPI->>MongoDB: find_events("normalized_data", {event_id: "abc123"})
    
    alt Event Found
        MongoDB-->>FastAPI: Normalized event
        FastAPI->>Permuter: run_permutations(odds, max_legs=2, top_n=5)
        
        Note over Permuter: Generate all combinations
        Permuter->>Permuter: generate_combinations(odds, 2)
        Note over Permuter: C(n,2) = n!/(2!(n-2)!)
        
        Note over Permuter: Score each combination
        loop For each combination
            Permuter->>Permuter: score_combination(combo)
        end
        
        Note over Permuter: Sort and select top N
        Permuter->>Permuter: sort_by_score()
        Permuter->>Permuter: select_top_n(5)
        
        Permuter-->>FastAPI: Top 5 permutations
        FastAPI->>Logger: log_stage("permutations", "generated", {event_id, count: 5})
        FastAPI-->>Client: 200 {permutations: [...]}
        
    else Event Not Found
        MongoDB-->>FastAPI: Empty result
        FastAPI-->>Client: 404 {detail: "Normalized event not found"}
    end
```

**Request**:
```http
POST /api/core/run-permutations?event_id=abc123def456&max_legs=2&top_n=5 HTTP/1.1
Host: api.beatvegas.com
X-API-Key: your_api_key
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-08T12:02:00.000Z",
  "event_id": "abc123def456",
  "permutations": [
    {
      "combo": [
        {
          "bookmaker": "fanduel",
          "market": "h2h",
          "name": "Los Angeles Lakers",
          "price": 2.10,
          "point": null
        },
        {
          "bookmaker": "draftkings",
          "market": "spreads",
          "name": "Boston Celtics",
          "price": 1.90,
          "point": 5.5
        }
      ],
      "score": 0.0399
    }
  ],
  "meta": {
    "total_combinations": 45,
    "returned": 5,
    "algorithm": "naive_v1.0"
  }
}
```

---

### 3.4 Predict Endpoint

**Endpoint**: `POST /api/core/predict`

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Permuter
    participant AI
    participant Logger
    participant MongoDB
    
    Client->>FastAPI: POST /predict?event_id=abc123
    
    FastAPI->>MongoDB: find_events("normalized_data", {event_id: "abc123"})
    MongoDB-->>FastAPI: Normalized event
    
    Note over FastAPI,AI: Generate predictions pipeline
    FastAPI->>Permuter: run_permutations(odds, max_legs=2, top_n=5)
    Permuter-->>FastAPI: Permutations [5]
    
    FastAPI->>AI: enhance_predictions(perms, base_confidence=0.45)
    
    Note over AI: Apply AI model (stub)
    loop For each permutation
        AI->>AI: adjusted_conf = base * 0.6 + score * 0.4
    end
    
    AI-->>FastAPI: Enhanced predictions [5]
    
    FastAPI->>MongoDB: insert_many("predictions", predictions)
    FastAPI->>Logger: log_stage("predict", "enhanced", {event_id, count: 5})
    
    FastAPI-->>Client: 200 {predictions: [...]}
```

**Request**:
```http
POST /api/core/predict?event_id=abc123def456 HTTP/1.1
Host: api.beatvegas.com
X-API-Key: your_api_key
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-08T12:03:00.000Z",
  "event_id": "abc123def456",
  "predictions": [
    {
      "combo": [
        {
          "bookmaker": "fanduel",
          "market": "h2h",
          "name": "Los Angeles Lakers",
          "price": 2.10,
          "point": null
        }
      ],
      "base_score": 0.210,
      "adjusted_confidence": 0.354,
      "model_version": "stub_v1.0",
      "prediction_id": "pred_abc123_001"
    }
  ],
  "meta": {
    "base_confidence": 0.45,
    "algorithm": "omniedge_stub_v1.0",
    "processed_at": "2025-11-08T12:03:00.000Z"
  }
}
```

---

### 3.5 Logs Endpoint

**Endpoint**: `GET /api/core/logs`

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant MongoDB
    
    Client->>FastAPI: GET /logs?module=predict&limit=10
    
    Note over FastAPI: Build query filter
    FastAPI->>MongoDB: find("logs_core_ai", {module: "predict"}).sort({timestamp: -1}).limit(10)
    MongoDB-->>FastAPI: Log entries [10]
    
    Note over FastAPI: Sanitize sensitive data
    FastAPI->>FastAPI: remove_pii(logs)
    
    FastAPI-->>Client: 200 {logs: [...]}
```

**Request**:
```http
GET /api/core/logs?module=predict&level=INFO&limit=10 HTTP/1.1
Host: api.beatvegas.com
X-API-Key: admin_api_key
X-Admin-Token: jwt_token_here
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-11-08T12:04:00.000Z",
  "count": 10,
  "logs": [
    {
      "log_id": "log_uuid_001",
      "module": "predict",
      "stage": "enhanced",
      "level": "INFO",
      "timestamp": "2025-11-08T12:03:30.123Z",
      "request_id": "req_abc123",
      "input": {
        "event_id": "abc123def456",
        "permutation_count": 5
      },
      "output": {
        "prediction_count": 5,
        "avg_confidence": 0.354
      },
      "performance": {
        "duration_ms": 245.3,
        "memory_mb": 38.2
      }
    }
  ]
}
```

---

## 4. Error Handling

### 4.1 Error Response Format

```mermaid
graph TD
    A[Error Occurs] --> B{Error Type}
    B -->|Validation Error| C[400 Bad Request]
    B -->|Auth Error| D[401/403 Unauthorized]
    B -->|Not Found| E[404 Not Found]
    B -->|Rate Limit| F[429 Too Many Requests]
    B -->|External API Error| G[502 Bad Gateway]
    B -->|Timeout| H[504 Gateway Timeout]
    B -->|Internal Error| I[500 Internal Server Error]
    B -->|Service Unavailable| J[503 Service Unavailable]
    
    C --> K[Log Error]
    D --> K
    E --> K
    F --> K
    G --> K
    H --> K
    I --> K
    J --> K
    
    K --> L[Return JSON Error]
    L --> M[Client Receives Error]
```

### 4.2 Standard Error Schema

```json
{
  "status": "error",
  "timestamp": "2025-11-08T12:00:00.000Z",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": "Additional context or troubleshooting info",
    "request_id": "req_abc123",
    "trace_id": "trace_xyz789"
  }
}
```

### 4.3 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `AUTH_REQUIRED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `ODDS_API_ERROR` | 502 | The Odds API failure |
| `DATABASE_ERROR` | 500 | MongoDB connection/query failure |
| `TIMEOUT` | 504 | Operation timeout |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 5. Performance Characteristics

### 5.1 Latency Breakdown

```mermaid
gantt
    title Request Latency Distribution (p99)
    dateFormat X
    axisFormat %L ms
    
    section Fetch Odds
    Network to Odds API :0, 800
    Parse Response      :800, 200
    Database Write      :1000, 150
    Logging             :1150, 50
    
    section Normalize
    Database Read       :0, 50
    Transformation      :50, 80
    Database Write      :130, 40
    Logging             :170, 20
    
    section Permutations
    Database Read       :0, 30
    Compute Combos      :30, 50
    Logging             :80, 10
    
    section Predict
    Database Read       :0, 30
    Run Permutations    :30, 80
    AI Enhancement      :110, 90
    Database Write      :200, 40
    Logging             :240, 15
```

### 5.2 Throughput Benchmarks

| Endpoint | Concurrent Users | Requests/sec | Avg Latency | p99 Latency |
|----------|------------------|--------------|-------------|-------------|
| fetch-odds | 10 | 8 req/s | 1.2s | 1.8s |
| normalize | 50 | 52 req/s | 150ms | 280ms |
| run-permutations | 100 | 98 req/s | 78ms | 145ms |
| predict | 40 | 38 req/s | 245ms | 420ms |
| logs | 200 | 195 req/s | 48ms | 95ms |

---

## 6. OmniCore Integration

### 6.1 OmniCore Ingestion Flow

```mermaid
sequenceDiagram
    participant BeatVegas
    participant OmniGateway as OmniCore Gateway
    participant OmniStream as Stream Processor
    participant OmniAI as OmniEdge AI
    participant OmniData as Data Lake
    
    Note over BeatVegas,OmniData: Real-time Data Streaming
    
    loop Every 5 seconds
        BeatVegas->>OmniGateway: POST /logs/normalized (NDJSON stream)
        OmniGateway->>OmniStream: Forward log batch
        OmniStream->>OmniData: Store in data lake
        OmniStream->>OmniAI: Trigger model training pipeline
    end
    
    Note over OmniAI: Model Training (Batch)
    OmniAI->>OmniData: Query historical data
    OmniAI->>OmniAI: Train/fine-tune model
    OmniAI->>OmniGateway: Deploy new model version
    
    Note over BeatVegas,OmniGateway: Prediction Request
    BeatVegas->>OmniGateway: POST /ai/v1/predict
    OmniGateway->>OmniAI: Route to latest model
    OmniAI-->>OmniGateway: Prediction result
    OmniGateway-->>BeatVegas: Enhanced prediction
```

### 6.2 Log Stream Format (NDJSON)

**Endpoint**: `POST /omnicore/logs/normalized`

**Format**: Newline-delimited JSON (one JSON object per line)

```json
{"log_id":"log_001","module":"normalize","timestamp":"2025-11-08T12:00:00.000Z","input":{...},"output":{...}}
{"log_id":"log_002","module":"predict","timestamp":"2025-11-08T12:00:01.000Z","input":{...},"output":{...}}
```

### 6.3 OmniCore Naming Conventions

**Module Identifiers**:
```
omni.data.ingestion.beatvegas_odds
omni.data.normalization.sports_canonical
omni.ai.permutation.parlay_v1
omni.ai.prediction.omniedge_sports_v2
```

**Event Types**:
```
beatvegas.odds.fetched
beatvegas.data.normalized
beatvegas.permutation.generated
beatvegas.prediction.enhanced
```

---

## 7. API Versioning Strategy

### 7.1 Version Lifecycle

```mermaid
graph LR
    A[v1.0 - Current] -->|Deprecation Notice| B[v1.0 - Deprecated]
    B -->|6 months| C[v1.0 - End of Life]
    A -->|New Features| D[v1.1 - Beta]
    D -->|Stable| E[v1.1 - Current]
    E -->|Breaking Changes| F[v2.0 - Beta]
    F -->|Stable| G[v2.0 - Current]
```

### 7.2 Version Headers

**Request**:
```http
GET /api/core/fetch-odds HTTP/1.1
X-API-Version: v1
X-Schema-Version: 1.0.0
```

**Response**:
```http
HTTP/1.1 200 OK
X-API-Version: v1
X-Schema-Version: 1.0.0
X-Deprecated: false
```

---

## Appendix A: cURL Examples

### Fetch Odds
```bash
curl -X GET "https://api.beatvegas.com/api/core/fetch-odds?sport=basketball_nba&region=us&markets=h2h,spreads" \
  -H "X-API-Key: your_api_key"
```

### Normalize Data
```bash
curl -X POST "https://api.beatvegas.com/api/core/normalize?limit=10" \
  -H "X-API-Key: your_api_key"
```

### Run Permutations
```bash
curl -X POST "https://api.beatvegas.com/api/core/run-permutations?event_id=abc123&max_legs=2&top_n=5" \
  -H "X-API-Key: your_api_key"
```

### Generate Predictions
```bash
curl -X POST "https://api.beatvegas.com/api/core/predict?event_id=abc123" \
  -H "X-API-Key: your_api_key"
```

### View Logs
```bash
curl -X GET "https://api.beatvegas.com/api/core/logs?module=predict&limit=10" \
  -H "X-API-Key: admin_api_key" \
  -H "X-Admin-Token: jwt_token"
```

---

## Appendix B: Postman Collection

See `postman/BeatVegas_MVP.postman_collection.json` for complete collection.

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-11-08  
**Maintained By**: BeatVegas Engineering Team

**END OF DOCUMENT**
