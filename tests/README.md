# Test Suite

This directory contains all tests for the manga-recs project.

## Structure

```
tests/
├── unit/              # Unit tests (isolated, fast)
├── integration/       # Integration tests (multiple components)
├── e2e/              # End-to-end tests (full workflows)
├── fixtures/         # Shared test data and fixtures
└── conftest.py       # Shared pytest configuration
```

## Running Tests

### Run all tests
```bash
make test
# or
pytest tests/ -v
```

### Run specific test types
```bash
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-e2e          # End-to-end tests only
```

### Run with coverage
```bash
pytest tests/ --cov=manga_recs --cov-report=html
# Open htmlcov/index.html in browser to view coverage
```

### Run specific test file
```bash
pytest tests/unit/api/test_main.py -v
```

## Writing Tests

### Unit Tests
- Test individual functions/methods in isolation
- Use mocks for external dependencies
- Fast execution (<1s per test)
- Example: `tests/unit/data_engineering/test_clean.py`

### Integration Tests
- Test interactions between components
- May use real databases/files but isolate from external APIs
- Slower execution (1-10s per test)

### End-to-End Tests
- Test complete user workflows
- Use realistic data and scenarios
- Slowest execution (10s+ per test)

## Fixtures

Common fixtures are defined in `conftest.py`:
- `sample_manga_data`: Sample manga metadata
- `sample_user_data`: Sample user read data
- `temp_data_dir`: Temporary directory for file operations
- `mock_graphql_client`: Mocked GraphQL client

## Coverage Goals

- Minimum coverage: 80%
- Critical paths: 95%+
- New code: 90%+
