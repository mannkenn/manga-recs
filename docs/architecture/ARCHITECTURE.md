# Project Architecture

## Overview

The Manga Recommendation System is built using a modular, scalable architecture that separates concerns across data engineering, machine learning, and application layers.

## System Components

### 1. Data Layer

```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                         │
├─────────────────────────────────────────────────────────┤
│  AniList GraphQL API                                    │
│  - Manga metadata (title, genres, tags, scores)        │
│  - User reading data (status, scores, progress)        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Data Engineering Pipeline                   │
├─────────────────────────────────────────────────────────┤
│  Extract (src/manga_recs/data_engineering/extract/)     │
│  ├── pull_manga.py      - Fetch manga metadata         │
│  └── pull_userdata.py   - Fetch user reading data      │
│                                                          │
│  Transform (src/manga_recs/data_engineering/transform/) │
│  ├── clean.py           - Data validation & cleaning   │
│  └── feature_engineering.py - Feature creation         │
│                                                          │
│  Load (src/manga_recs/data_engineering/load/)          │
│  └── s3.py              - AWS S3 storage operations    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Storage Layer                          │
├─────────────────────────────────────────────────────────┤
│  Local Storage          │  Cloud Storage (AWS S3)       │
│  - data/raw/           │  - Raw data backups           │
│  - data/cleaned/       │  - Processed datasets         │
│  - data/features/      │  - Feature matrices           │
│  - data/models/        │  - Model artifacts            │
└─────────────────────────────────────────────────────────┘
```

### 2. ML Layer

```
┌─────────────────────────────────────────────────────────┐
│                  Feature Engineering                     │
├─────────────────────────────────────────────────────────┤
│  Manga Features:                                        │
│  - One-hot encoded genres/tags                         │
│  - Normalized scores & popularity                      │
│  - Demographic encoding                                │
│                                                          │
│  User Features:                                         │
│  - Interaction matrix (user-item)                      │
│  - Status encoding (completed, reading, etc.)          │
│  - Score normalization                                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Model Training                         │
├─────────────────────────────────────────────────────────┤
│  Algorithm: Content-Based Filtering                    │
│  - Cosine similarity computation                       │
│  - Item-item similarity matrix                         │
│                                                          │
│  Tracking: MLflow                                       │
│  - Experiment logging                                  │
│  - Model versioning                                    │
│  - Metrics tracking                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Inference                            │
├─────────────────────────────────────────────────────────┤
│  Input: Manga title (fuzzy matched)                    │
│  Process:                                               │
│  1. Find manga in database                             │
│  2. Retrieve similarity scores                         │
│  3. Rank and filter results                            │
│  Output: Top-N similar manga                           │
└─────────────────────────────────────────────────────────┘
```

### 3. Application Layer

```
┌─────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                     │
├─────────────────────────────────────────────────────────┤
│  Endpoints:                                             │
│  - POST /api/recommendations                           │
│  - GET  /health                                        │
│  - GET  /docs (Swagger UI)                            │
│                                                          │
│  Features:                                              │
│  - Pydantic schema validation                          │
│  - Fuzzy title matching (RapidFuzz)                    │
│  - Model artifact loading                              │
│  - Error handling & logging                            │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────────────────────────────────────┐
│                  Frontend (Next.js)                     │
├─────────────────────────────────────────────────────────┤
│  Pages:                                                 │
│  - /          - Home & search interface                │
│  - /api/*     - API proxy to backend                   │
│                                                          │
│  Features:                                              │
│  - React 18 with TypeScript                            │
│  - Server-side rendering (SSR)                         │
│  - Responsive UI design                                │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Data Ingestion Flow

```
User Initiates Pipeline
       │
       ▼
┌──────────────────┐
│ run_ingestion.py │
└──────────────────┘
       │
       ├──► GraphQL Client ──► AniList API
       │         │
       │         ▼
       │    Rate Limiter (10 req/min)
       │         │
       │         ▼
       │    Retry Logic (exponential backoff)
       │         │
       │         ▼
       ├──► fetch_manga_data()
       │    ├─ Fetch by popularity
       │    └─ Paginate results
       │
       └──► fetch_user_data()
            ├─ Iterate user ID range
            ├─ Handle private users
            └─ Skip server errors
                 │
                 ▼
            Save to data/raw/
                 │
                 ▼
            Upload to S3
```

### 2. Training Flow

```
Load Cleaned Data
       │
       ▼
Feature Engineering
       ├──► create_manga_features()
       │    ├─ MultiLabelBinarizer (genres/tags)
       │    ├─ StandardScaler (numerical)
       │    └─ Output: feature matrix
       │
       └──► create_user_features()
            ├─ Status encoding
            ├─ Score normalization
            └─ Output: user-item matrix
                 │
                 ▼
       Compute Similarity Matrix
            ├─ sklearn.cosine_similarity
            └─ Shape: (n_items, n_items)
                 │
                 ▼
            MLflow Logging
            ├─ Log parameters
            ├─ Log metrics
            └─ Log artifacts
                 │
                 ▼
            Save Model & Metadata
            ├─ joblib.dump()
            └─ Upload to S3
```

### 3. Inference Flow

```
User Request (manga_title, top_n)
       │
       ▼
FastAPI Endpoint
       │
       ├──► Validate Input (Pydantic)
       │
       ├──► Load Artifacts
       │    ├─ Similarity matrix
       │    ├─ Manga metadata
       │    └─ Feature mappings
       │
       ├──► Fuzzy Match Title
       │    └─ RapidFuzz.process()
       │
       ├──► Retrieve Similarity Scores
       │    └─ similarity_matrix[manga_id]
       │
       ├──► Rank & Filter
       │    ├─ Sort by score
       │    ├─ Remove duplicates
       │    └─ Take top_n
       │
       └──► Format Response
            └─ JSON with recommendations
                 │
                 ▼
            Return to Client
```

## Technology Stack

### Backend
- **Python 3.10+**: Core language
- **FastAPI**: Web framework
- **Pydantic**: Data validation
- **scikit-learn**: ML algorithms
- **pandas/numpy**: Data processing
- **joblib**: Model serialization
- **MLflow**: Experiment tracking
- **boto3**: AWS S3 integration
- **RapidFuzz**: Fuzzy string matching

### Frontend
- **Next.js 16**: React framework
- **React 18**: UI library
- **TypeScript**: Type safety

### Infrastructure
- **AWS S3**: Object storage
- **GitHub Actions**: CI/CD
- **Docker**: Containerization (optional)

### Development Tools
- **pytest**: Testing framework
- **Black**: Code formatter
- **isort**: Import sorter
- **flake8**: Linting
- **mypy**: Type checking
- **pre-commit**: Git hooks

## Design Patterns

### 1. Pipeline Pattern
Data processing follows a clear ETL (Extract-Transform-Load) pipeline with distinct stages.

### 2. Repository Pattern
Data access is abstracted through utility functions in `data_engineering/load/`.

### 3. Dependency Injection
FastAPI's dependency injection system manages resource lifecycle.

### 4. Factory Pattern
GraphQL client and rate limiter are created through factory functions.

## Scalability Considerations

### Current Scale
- **Data Volume**: ~1000 users, ~10000 manga
- **API Rate**: 10 requests/minute to AniList
- **Model Size**: ~100MB (similarity matrix)

### Scaling Options

1. **Horizontal Scaling**
   - Deploy multiple API instances behind load balancer
   - Use Redis for shared caching

2. **Data Partitioning**
   - Partition user data by ID ranges
   - Use Apache Spark for large-scale processing

3. **Model Optimization**
   - Sparse matrix representation
   - Approximate nearest neighbors (Annoy, FAISS)
   - Model compression

4. **Caching Strategy**
   - Cache popular recommendations
   - Pre-compute for trending manga

## Security Considerations

- **Environment Variables**: Secrets stored in .env (never committed)
- **API Keys**: AWS credentials with minimal required permissions
- **Input Validation**: Pydantic schemas validate all inputs
- **Rate Limiting**: Protect external API and backend
- **CORS**: Configured for frontend origin only

## Monitoring & Observability

- **MLflow**: Track experiments and model performance
- **GitHub Actions**: CI/CD pipeline status
- **Logs**: Structured logging throughout pipeline
- **Tests**: 80%+ code coverage requirement

## Future Enhancements

1. **Collaborative Filtering**: Add user-based recommendations
2. **Hybrid Model**: Combine content and collaborative filtering
3. **Real-time Updates**: Stream new manga as released
4. **User Accounts**: Personalized recommendations
5. **A/B Testing**: Experiment with different algorithms
6. **Caching Layer**: Redis for frequently accessed data
7. **Containerization**: Docker deployment
