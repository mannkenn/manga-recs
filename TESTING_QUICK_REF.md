## Quick Reference: Testing + CI/CD Commands

### Local Testing
```powershell
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/ml/test_feature_engineering.py -v

# Run with coverage
pytest tests/ --cov=src

# Run only failed tests
pytest tests/ --lf
```

### Install Dependencies
```powershell
# One time setup
pip install -r requirements-dev.txt
```

### What Happens on Git Push

1. **Tests run automatically** on GitHub (`.github/workflows/ci-cd.yml`)
2. **If tests fail** → PR blocked, you need to fix it
3. **If tests pass** → PR approved, ready to merge
4. **Status badge** shows in your GitHub repo

---

## Files Created

| File | Purpose |
|------|---------|
| `tests/` | All test files |
| `tests/conftest.py` | Shared test data (fixtures) |
| `pytest.ini` | Test configuration |
| `requirements-dev.txt` | Dev dependencies |
| `.github/workflows/ci-cd.yml` | GitHub Actions automation |
| `TESTING_GUIDE.md` | Full documentation |

---

## Add More Tests

1. Create `tests/module_name/test_*.py`
2. Write test functions: `def test_something():`
3. Run: `pytest tests/ -v`
4. Push to GitHub → auto-run

---

✅ **Your repo is now production-ready!**
