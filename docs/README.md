# Documentation

Welcome to the Manga Recommendation System documentation!

## 📚 Documentation Structure

### Getting Started
- **[Setup Guide](guides/SETUP.md)** - Complete installation and configuration instructions
- **[README](../README.md)** - Project overview and quick start

### Architecture
- **[Architecture Overview](architecture/ARCHITECTURE.md)** - System design and data flow
- Component diagrams
- Technology stack details
- Scalability considerations

### API
- **[API Documentation](api/API.md)** - RESTful API endpoints
- Request/response examples
- Error handling
- OpenAPI schema

### Development
- **[Contributing Guidelines](../CONTRIBUTING.md)** - How to contribute
- Code style and standards
- Testing guidelines
- Pull request process

### Testing
- **[Test Documentation](../tests/README.md)** - Testing strategy and guidelines
- Running tests
- Writing tests
- Coverage requirements

## 🎯 Quick Links

| Topic | Link |
|-------|------|
| Installation | [Setup Guide](guides/SETUP.md) |
| API Endpoints | [API Docs](api/API.md) |
| System Design | [Architecture](architecture/ARCHITECTURE.md) |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) |

## 📖 Guides

### For Users
1. [Getting Started](guides/SETUP.md#installation-steps)
2. [Using the API](api/API.md)
3. [Running the Frontend](../README.md#frontend)

### For Developers
1. [Development Setup](guides/SETUP.md#development-workflow)
2. [Architecture Overview](architecture/ARCHITECTURE.md)
3. [Writing Tests](../tests/README.md)
4. [Code Standards](../CONTRIBUTING.md#code-standards)
5. [Making Changes](../CONTRIBUTING.md#pull-request-process)

### For Data Scientists
1. [Data Pipeline](architecture/ARCHITECTURE.md#1-data-ingestion-flow)
2. [Feature Engineering](architecture/ARCHITECTURE.md#2-ml-layer)
3. [Model Training](architecture/ARCHITECTURE.md#2-training-flow)
4. [MLflow Tracking](architecture/ARCHITECTURE.md#monitoring--observability)

## 🔧 Development

### Common Commands

```bash
# Setup
make install-dev        # Install development dependencies
make pre-commit        # Install git hooks

# Development
make run-api           # Start API server
make run-pipeline      # Run data pipeline
make train             # Train ML model

# Testing
make test              # Run all tests
make lint              # Check code quality
make format            # Format code

# Cleaning
make clean             # Remove build artifacts
```

### Project Structure

```
manga-recs/
├── src/manga_recs/     # Python package
├── frontend/           # Next.js frontend
├── tests/             # Test suite
├── docs/              # This documentation
├── notebooks/         # Jupyter notebooks
└── data/              # Data storage
```

## 🤝 Contributing

We welcome contributions! Please see:
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Good First Issues](https://github.com/mannkenn/manga-recs/labels/good%20first%20issue)

## 📝 Additional Resources

### External Documentation
- [AniList API](https://anilist.gitbook.io/anilist-apiv2-docs/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/docs)
- [scikit-learn](https://scikit-learn.org/stable/)
- [MLflow](https://mlflow.org/docs/latest/index.html)

### Related Projects
- [AniList](https://anilist.co/) - Source of manga data
- [MyAnimeList](https://myanimelist.net/) - Alternative data source

## ❓ Getting Help

- **Issues**: [GitHub Issues](https://github.com/mannkenn/manga-recs/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mannkenn/manga-recs/discussions)
- **Email**: emmanuelkim2004@gmail.com

## 📄 License

This project is licensed under the MIT License - see [LICENSE](../LICENSE) for details.
