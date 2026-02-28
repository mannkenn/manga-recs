# Contributing to Manga Recommendation System

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## 🤝 Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/manga-recs.git
cd manga-recs
```

### 2. Set Up Development Environment

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
make install-dev

# Install pre-commit hooks
make pre-commit
```

### 3. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or a bugfix branch
git checkout -b fix/bug-description
```

## 🔄 Development Workflow

### Branch Naming Conventions

- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring
- `test/*` - Test additions or modifications
- `chore/*` - Maintenance tasks

### Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(api): add fuzzy search for manga titles

fix(pipeline): handle rate limiting errors gracefully

docs(readme): update installation instructions

test(data): add unit tests for cleaning functions
```

## 📏 Code Standards

### Python Code Style

- **Line length**: 100 characters
- **Formatter**: Black
- **Import sorting**: isort
- **Linter**: flake8
- **Type hints**: Encouraged (checked with mypy)

```bash
# Format code
make format

# Check code quality
make lint
```

### Type Hints

Use type hints for function signatures:

```python
from typing import List, Dict, Optional

def fetch_user_data(
    client: GraphQLClient,
    query: str,
    per_page: int = 50,
    max_pages: Optional[int] = None
) -> List[Dict]:
    """Fetch user data from API."""
    pass
```

### Documentation

- **Docstrings**: Use Google-style docstrings
- **Comments**: Explain "why", not "what"
- **API docs**: Update OpenAPI schemas when changing endpoints

Example docstring:
```python
def create_manga_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Create feature matrix for manga recommendation model.
    
    Args:
        data: Cleaned manga metadata DataFrame containing genres,
              tags, and demographic information.
    
    Returns:
        Feature matrix with one-hot encoded categorical variables
        and scaled numerical features.
    
    Raises:
        ValueError: If required columns are missing from input data.
    """
    pass
```

## 🧪 Testing Guidelines

### Writing Tests

- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test component interactions
- **E2E tests**: Test complete workflows

### Test Structure

```python
import pytest

class TestFeatureName:
    """Tests for feature X."""
    
    def test_normal_case(self):
        """Test the normal/expected behavior."""
        pass
    
    def test_edge_case(self):
        """Test edge cases and boundary conditions."""
        pass
    
    def test_error_handling(self):
        """Test error handling and validation."""
        pass
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/api/test_main.py -v

# Run with coverage
make test
# Coverage report in htmlcov/index.html
```

### Coverage Requirements

- Minimum overall coverage: **80%**
- New code coverage: **90%+**
- Critical paths: **95%+**

## 📥 Pull Request Process

### Before Submitting

1. **Update your branch**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run tests**
   ```bash
   make test
   make lint
   ```

3. **Update documentation**
   - Update README if adding features
   - Add docstrings to new functions
   - Update CHANGELOG.md

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature-name
   ```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Review Process

1. **Automated checks**: CI/CD must pass
2. **Code review**: At least one maintainer approval required
3. **Testing**: Verify tests cover new functionality
4. **Documentation**: Ensure docs are updated

### After Approval

Maintainers will:
- Merge using "Squash and merge" for clean history
- Delete the feature branch
- Update version numbers if needed

## 🐛 Reporting Bugs

### Before Reporting

1. Check existing issues
2. Verify it's reproducible
3. Test on the latest version

### Bug Report Template

```markdown
**Describe the bug**
Clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Run command '...'
3. See error

**Expected behavior**
What you expected to happen.

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.2]
- Package version: [e.g., 0.1.0]

**Additional context**
Logs, screenshots, etc.
```

## 💡 Suggesting Features

### Feature Request Template

```markdown
**Problem Statement**
What problem does this feature solve?

**Proposed Solution**
Describe your proposed solution.

**Alternatives Considered**
Other approaches you've considered.

**Additional Context**
Mockups, examples, etc.
```

## 🎯 Good First Issues

Look for issues labeled:
- `good first issue` - Great for newcomers
- `help wanted` - Contributions especially welcome
- `documentation` - Documentation improvements

## 📚 Additional Resources

- [Python Style Guide (PEP 8)](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)

## ❓ Questions?

Feel free to:
- Open a discussion on GitHub
- Reach out to maintainers
- Ask in pull request comments

Thank you for contributing! 🎉
