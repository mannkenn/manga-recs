# Testing + CI/CD Setup Guide

## What We Built

You now have a **complete testing + CI/CD infrastructure** for your manga-recs project. Here's what was set up:

---

## 📁 What's New in Your Repo

### **1. Tests Directory** (`tests/`)
```
tests/
├── __init__.py
├── conftest.py                  # Shared test configuration & fixtures
├── api/
│   ├── __init__.py
│   └── test_recommendations.py  # API endpoint tests
└── ml/
    ├── __init__.py
    └── test_feature_engineering.py  # ML feature tests
```

### **2. Configuration Files**
- **`pytest.ini`** – Pytest configuration (test discovery, output format)
- **`requirements-dev.txt`** – Development dependencies (pytest, linting tools)
- **`.github/workflows/ci-cd.yml`** – GitHub Actions automation

---

## ✅ Tests You Now Have

### **API Tests** (`tests/api/test_recommendations.py`)
- ✅ Health check (API is running)
- ✅ Valid manga recommendation request
- ✅ Nonexistent manga handling
- ✅ Request schema validation

### **ML Tests** (`tests/ml/test_feature_engineering.py`)
- ✅ Weighted tag encoding with [3, 2] weights
- ✅ Simple binary encoding fallback
- ✅ Similarity matrix shape validation
- ✅ Similarity matrix symmetry checks

**Current Status: 10/10 tests passing ✅**

---

## 🚀 How to Use Testing Locally

### **Install dev dependencies once:**
```powershell
pip install -r requirements-dev.txt
```

### **Run all tests:**
```powershell
pytest tests/ -v
```

### **Run specific test file:**
```powershell
pytest tests/ml/test_feature_engineering.py -v
```

### **Run with coverage report:**
```powershell
pytest tests/ --cov=src --cov-report=html
# Opens coverage report in htmlcov/index.html
```

### **Run only failed tests from last run:**
```powershell
pytest tests/ --lf
```

---

## 🔄 How CI/CD Works (GitHub Actions)

When you push code to GitHub, this happens **automatically**:

```
Your commit pushed to GitHub
         ↓
GitHub detects change
         ↓
Runs automated tests (`.github/workflows/ci-cd.yml`)
         ↓
Tests fail?  →  Email notification, PR blocked
Tests pass?  →  PR approved, ready to merge
         ↓
(Later) Deploy to production (if configured)
```

### **What the CI Pipeline Does:**

#### **1. Test Job** (Tests across Python 3.10, 3.11, 3.12)
- Installs dependencies
- Runs linting (flake8) – catches style issues
- Type checking with mypy – catches type errors
- Runs unit tests (pytest)
- Uploads coverage reports to CodeCov

#### **2. Lint Job** (Code quality checks)
- Checks code formatting with Black
- Checks import sorting with isort
- Provides feedback on style issues

#### **3. Frontend Job** (Next.js validation)
- Installs npm dependencies
- Lints frontend code
- Builds frontend

#### **4. API Integration Job** (Full API testing)
- Runs after tests pass
- Full API integration tests

---

## 📝 Writing Your Own Tests

### **Test File Template:**
```python
import pytest
from your_module import your_function

class TestYourFeature:
    """Test suite for your_function"""
    
    def test_basic_case(self):
        """Test the happy path"""
        result = your_function("input")
        assert result == expected_value
    
    def test_edge_case(self):
        """Test edge cases"""
        with pytest.raises(ValueError):
            your_function(None)
```

### **Using Fixtures (Shared Test Data):**

Add to `tests/conftest.py`:
```python
@pytest.fixture
def sample_manga():
    return {
        'id': 1,
        'title': 'Naruto',
        'tags': ['action', 'shounen']
    }
```

Then use in tests:
```python
def test_with_fixture(sample_manga):
    result = recommend(sample_manga['title'])
    assert result is not None
```

---

## 🔧 Next Steps (Optional Improvements)

### **1. Add Pre-Commit Hooks** (auto-format before commit)
```bash
pip install pre-commit
pre-commit install
# Now every commit auto-formats code, runs linting
```

### **2. Increase Test Coverage**
- Goal: >80% test coverage
- Currently testing key functions
- Add tests for data loading, model training, etc.

### **3. Add Performance Tests**
```python
def test_recommendation_performance(benchmark):
    result = benchmark(recommend, "Naruto")
    # Ensures API responds in <100ms
```

### **4. Setup Deployment** (CD part)
- Create deployment workflow to push to cloud
- Auto-deploy when tests pass on `main` branch

---

## 🎯 Key Concepts

### **Unit Tests**
Tests one function in isolation. Example:
```python
def test_parse_release_year():
    result = parse_release_year(datetime(2020, 1, 1))
    assert result == 2020
```

### **Integration Tests**
Tests multiple components together. Example:
```python
def test_full_recommendation_pipeline():
    # Test data loading → feature engineering → inference
```

### **CI (Continuous Integration)**
- Runs tests **automatically** on every push/PR
- Prevents broken code from being merged
- Provides instant feedback to developers

### **CD (Continuous Deployment)**
- Automatically deploys code after tests pass
- Could auto-deploy to Azure, AWS, Heroku, etc.
- Not configured yet (optional)

---

## 🐛 Troubleshooting

### **Tests fail locally but pass in CI?**
→ Different Python version. CI tests 3.10, 3.11, 3.12

### **Import errors in tests?**
→ Install requirements: `pip install -r requirements.txt`

### **GitHub Actions not running?**
→ Ensure `.github/workflows/ci-cd.yml` is committed to `main` branch

### **Coverage too low?**
→ Add more tests: `pytest tests/ --cov=src --cov-report=term-missing`

---

## 📚 Resources

- [pytest docs](https://docs.pytest.org/)
- [GitHub Actions docs](https://docs.github.com/en/actions)
- [Test-Driven Development (TDD)](https://en.wikipedia.org/wiki/Test-driven_development)

---

## ✨ Summary

You now have:
- ✅ **10 passing unit tests**
- ✅ **Local test runner** (pytest)
- ✅ **Automated CI pipeline** (GitHub Actions)
- ✅ **Code quality checks** (linting, type checking)
- ✅ **Coverage reporting** (track test coverage)

**Next time you push code to GitHub, tests run automatically!** 🚀
