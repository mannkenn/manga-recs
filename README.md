# 📚 Manga Recommendation System

[![CI/CD](https://github.com/mannkenn/manga-recs/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/mannkenn/manga-recs/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end machine learning project for manga recommendations using data from the [AniList API](https://anilist.gitbook.io/anilist-apiv2-docs/). This system includes data ingestion, preprocessing, feature engineering, ML model training, and a FastAPI backend with Next.js frontend.

## ✨ Features

- 🔄 **Automated Data Pipeline**: Fetch and process manga metadata and user reading data from AniList
- 🤖 **ML-Powered Recommendations**: Content-based filtering using cosine similarity
- 🚀 **FastAPI Backend**: High-performance REST API for recommendations
- 💻 **Next.js Frontend**: Modern React-based UI for searching and discovering manga
- 📊 **MLflow Integration**: Experiment tracking and model versioning
- ☁️ **S3 Storage**: Cloud data persistence with AWS S3
- 🧪 **Comprehensive Testing**: Unit, integration, and E2E tests with CI/CD

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  AniList    │─────▶│  Data        │─────▶│   AWS S3    │
│  GraphQL API│      │  Pipeline    │      │   Storage   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   Feature    │
                     │ Engineering  │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐      ┌─────────────┐
                     │  ML Training │─────▶│   MLflow    │
                     │ (Similarity) │      │  Tracking   │
                     └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐      ┌─────────────┐
                     │   FastAPI    │◀─────│   Next.js   │
                     │   Backend    │      │  Frontend   │
                     └──────────────┘      └─────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- AWS credentials (for S3 storage)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mannkenn/manga-recs.git
   cd manga-recs
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials
   ```

4. **Install pre-commit hooks** (optional but recommended)
   ```bash
   make pre-commit
   ```

### Running the Application

#### Backend API

```bash
# Start the FastAPI server
make run-api
# Or manually:
uvicorn manga_recs.api.main:app --reload
```

API will be available at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

#### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev
```

Frontend will be available at `http://localhost:3000`

#### Data Pipeline

```bash
# Run the complete pipeline
make run-pipeline

# Or run individual steps:
make ingest          # Fetch data from AniList
make clean-data      # Clean and validate data
make build-features  # Generate ML features
make train           # Train recommendation model
```

## 📁 Project Structure

```
manga-recs/
├── src/manga_recs/          # Main Python package
│   ├── api/                 # FastAPI application
│   ├── data_engineering/    # ETL pipeline
│   │   ├── extract/         # Data fetching from AniList
│   │   ├── transform/       # Data cleaning & feature engineering
│   │   └── load/            # S3 storage operations
│   ├── ml/                  # Model training
│   ├── inference/           # Model inference
│   └── pipelines/           # Orchestration scripts
├── frontend/                # Next.js React application
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/                # End-to-end tests
├── notebooks/              # Jupyter notebooks for exploration
├── data/                   # Local data storage
│   ├── raw/               # Raw data from AniList
│   ├── cleaned/           # Processed data
│   ├── features/          # Engineered features
│   └── models/            # Trained models
├── docs/                   # Documentation
└── .github/workflows/      # CI/CD pipelines
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-e2e

# Check code quality
make lint
make format-check
```

## 📊 ML Pipeline

### 1. Data Ingestion
- Fetches manga metadata (title, genres, scores, popularity)
- Collects user reading data (status, scores, progress)
- Handles rate limiting and error recovery

### 2. Feature Engineering
- Processes manga attributes (genres, tags, demographics)
- Creates user-item interaction matrices
- Generates embeddings for content-based filtering

### 3. Model Training
- Trains cosine similarity-based recommender
- Tracks experiments with MLflow
- Saves artifacts to S3

### 4. Inference
- Provides real-time recommendations via API
- Fuzzy matching for manga title search
- Returns top-N similar manga

## 🛠️ Development

### Code Style

This project uses:
- **Black** for code formatting (line length: 100)
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
# Auto-format code
make format

# Check formatting
make format-check
```

### Pre-commit Hooks

Pre-commit hooks automatically format and lint code before commits:

```bash
make pre-commit       # Install hooks
pre-commit run --all-files  # Run manually
```

## 📖 API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Example API Request

```bash
curl -X POST http://localhost:8000/api/recommendations \
  -H "Content-Type: application/json" \
  -d '{"manga_title": "One Piece", "top_n": 5}'
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [AniList](https://anilist.co/) for providing the GraphQL API
- Built with FastAPI, Next.js, scikit-learn, and MLflow

## 📧 Contact

Manny Kim - [@mannkenn](https://github.com/mannkenn) - emmanuelkim2004@gmail.com

Project Link: [https://github.com/mannkenn/manga-recs](https://github.com/mannkenn/manga-recs)


