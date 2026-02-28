# Setup Guide

This guide will walk you through setting up the Manga Recommendation System for development.

## Prerequisites

### Required Software
- **Python 3.10 or higher** ([Download](https://www.python.org/downloads/))
- **Node.js 18 or higher** ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/))

### Optional Software
- **AWS CLI** (for S3 operations) ([Install Guide](https://aws.amazon.com/cli/))
- **Docker** (for containerization) ([Install Guide](https://docs.docker.com/get-docker/))

### AWS Account
You'll need AWS credentials with S3 access for data storage:
1. Create an AWS account (if you don't have one)
2. Create an IAM user with S3 permissions
3. Generate access keys

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/mannkenn/manga-recs.git
cd manga-recs
```

### 2. Set Up Python Environment

#### Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

#### Install Dependencies
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Or just production dependencies
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import manga_recs; print('Success!')"
```

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```bash
# Required - AWS credentials
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-2

# Optional - customize these if needed
# MLFLOW_TRACKING_URI=file:./mlruns
# USER_START_ID=1
# USER_END_ID=1000
```

### 4. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Return to project root
cd ..
```

### 5. Install Development Tools (Optional but Recommended)

```bash
# Install pre-commit hooks
make pre-commit

# This will run code formatting and linting automatically on commit
```

## Verify Setup

### Test Backend

```bash
# Run tests
make test

# Check code quality
make lint

# Start the API server
make run-api
```

Visit `http://localhost:8000/docs` to see the API documentation.

### Test Frontend

```bash
# Start the development server
cd frontend
npm run dev
```

Visit `http://localhost:3000` to see the frontend.

## Common Setup Issues

### Python Version Issues

**Problem:** `python: command not found` or wrong version

**Solution:**
```bash
# Check Python version
python --version
# or
python3 --version

# If you have multiple versions, use python3.10 explicitly
python3.10 -m venv .venv
```

### Virtual Environment Not Activating

**Problem:** Virtual environment doesn't activate

**Solution:**
```bash
# On Windows PowerShell, you may need to enable scripts:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate:
.venv\Scripts\Activate.ps1
```

### Dependency Installation Failures

**Problem:** `pip install` fails with compilation errors

**Solution:**
```bash
# Update pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

# Install dependencies again
pip install -r requirements-dev.txt
```

### AWS Credentials Issues

**Problem:** S3 operations fail with authentication errors

**Solution:**
1. Verify credentials in `.env` file
2. Test AWS access:
   ```bash
   aws s3 ls --profile default
   ```
3. Ensure IAM user has S3 permissions

### Port Already in Use

**Problem:** `Address already in use` when starting servers

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # On Linux/macOS
netstat -ano | findstr :8000  # On Windows

# Kill the process or use a different port:
uvicorn manga_recs.api.main:app --port 8001
```

### Node.js Issues

**Problem:** `npm install` fails

**Solution:**
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json

# Reinstall
npm install
```

## Next Steps

After setup is complete:

1. **Run the Data Pipeline** (optional - pre-processed data may be available):
   ```bash
   make run-pipeline
   ```

2. **Train the Model** (optional - pre-trained model may be available):
   ```bash
   make train
   ```

3. **Start Development**:
   ```bash
   # Terminal 1: Backend
   make run-api
   
   # Terminal 2: Frontend
   cd frontend && npm run dev
   ```

4. **Read the Documentation**:
   - [Architecture](../architecture/ARCHITECTURE.md)
   - [API Documentation](../api/API.md)
   - [Contributing Guidelines](../../CONTRIBUTING.md)

## Development Workflow

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature

# 2. Make changes
# ... edit files ...

# 3. Format code (happens automatically with pre-commit)
make format

# 4. Run tests
make test

# 5. Commit changes
git add .
git commit -m "feat: your feature description"

# 6. Push to GitHub
git push origin feature/your-feature

# 7. Create Pull Request on GitHub
```

## IDE Setup Recommendations

### VS Code

Install recommended extensions:
- Python
- Pylance
- Black Formatter
- isort
- ESLint
- Prettier

Settings (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Black formatter in Settings → Tools → Black
3. Enable flake8 in Settings → Tools → External Tools

## Getting Help

If you encounter issues:
1. Check the [FAQ](../../README.md#faq) (if available)
2. Search [existing issues](https://github.com/mannkenn/manga-recs/issues)
3. Create a [new issue](https://github.com/mannkenn/manga-recs/issues/new)
4. Ask in discussions

## Resources

- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [pytest Documentation](https://docs.pytest.org/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
