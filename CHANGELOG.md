# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite with unit, integration, and E2E tests
- Pre-commit hooks for code quality (Black, isort, flake8, mypy, bandit)
- GitHub Actions CI/CD pipeline
- Makefile for common development tasks
- Complete documentation (README, CONTRIBUTING, tests/README)
- Modern dependency management with pyproject.toml
- EditorConfig for consistent coding styles
- .env.example template for environment configuration
- Enhanced .gitignore with better organization

### Changed
- Restructured project for better organization
- Consolidated dependency management to pyproject.toml
- Updated requirements.txt to reference pyproject.toml
- Improved .gitignore to preserve directory structure

## [0.1.0] - 2026-02-28

### Added
- User-based data fetching with configurable ID ranges
- Enhanced error handling for private/unavailable users
- Retry logic with exponential backoff for API requests
- Rate limiting with header-aware delays
- Intelligent GraphQL client with resilience features

### Changed
- Refactored data fetching from global pagination to user ID range-based
- Updated GraphQL query from mediaId-based to userId-based
- Simplified user data schema to essential fields
- Improved data cleaning with type safety and validation
- Reduced rate limit from 30 to 10 requests/minute for stability

### Fixed
- Handling of AniList server errors (500, 502, 503, 504)
- Data type conversions for numeric fields
- Null value handling in user/media IDs

## [0.0.1] - Initial Development

### Added
- FastAPI backend for recommendations
- Next.js frontend UI
- Data ingestion pipeline from AniList API
- Data cleaning and feature engineering modules
- ML similarity model training
- MLflow experiment tracking
- S3 storage integration
- Basic project structure

---

## Release Types

- **Major version** (1.0.0): Breaking changes
- **Minor version** (0.1.0): New features, backward compatible
- **Patch version** (0.0.1): Bug fixes, backward compatible

## Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Features that will be removed
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements
