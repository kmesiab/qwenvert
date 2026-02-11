# Quick Start: Publishing qwenvert

## 🚀 Fast Track to PyPI

### One-Time Setup (5 minutes)

1. **Create PyPI accounts:**
   - https://pypi.org/account/register/
   - https://test.pypi.org/account/register/

2. **Generate API tokens:**
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

3. **Add tokens to GitHub:**
   ```bash
   # Go to: https://github.com/kmesiab/qwenvert/settings/secrets/actions
   # Add secrets:
   #   PYPI_API_TOKEN
   #   TEST_PYPI_API_TOKEN
   ```

4. **Install tools:**
   ```bash
   pip install build twine
   brew install gh  # GitHub CLI
   ```

### Publishing Your First Release

```bash
# 1. Test on TestPyPI first
make publish-test

# 2. Install and verify
pip install --index-url https://test.pypi.org/simple/ qwenvert
qwenvert --version

# 3. If everything works, publish for real
make release

# This will:
#   - Run all tests
#   - Build the package
#   - Create git tag
#   - Create GitHub release (draft)
#   - Trigger automatic PyPI upload when you publish the release
```

### Publishing Flow

```
┌─────────────────┐
│  Update version │
│  pyproject.toml │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  make release   │  Creates tag + GitHub release
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Publish release │  Manually publish on GitHub
│   on GitHub     │  (review auto-generated notes)
└────────┬────────┘
         │
         v
┌─────────────────┐
│ GitHub Actions  │  Automatically:
│  runs tests     │  - Builds package
│  publishes to   │  - Runs tests
│     PyPI        │  - Publishes to PyPI
└────────┬────────┘
         │
         v
    ┌────────┐
    │  Done! │
    └────────┘
```

## 🍺 Homebrew Setup

### Option 1: Personal Tap (Recommended for now)

```bash
# 1. Create tap repo
gh repo create homebrew-qwenvert --public

# 2. Clone and setup
git clone https://github.com/kmesiab/homebrew-qwenvert.git
cd homebrew-qwenvert
mkdir Formula

# 3. Generate formula (after publishing to PyPI)
pip install homebrew-pypi-poet
poet qwenvert > Formula/qwenvert.rb

# 4. Add the header to Formula/qwenvert.rb
# (Copy from homebrew/qwenvert.rb in this repo)

# 5. Test locally
brew install --build-from-source ./Formula/qwenvert.rb
brew test qwenvert

# 6. Publish
git add Formula/qwenvert.rb
git commit -m "Add qwenvert formula v0.1.0"
git push

# Users can now install:
#   brew tap kmesiab/qwenvert
#   brew install qwenvert
```

### Option 2: Homebrew Core (After 1.0 release)

Requirements:
- 30+ GitHub stars
- Stable 1.0.0+ version
- Active maintenance

Then submit PR to homebrew-core.

## 📋 Pre-Release Checklist

Use this before every release:

```bash
# Run all checks
make check-all

# Verify security tests pass
pytest tests/security/ -v

# Check coverage
make coverage

# Update CHANGELOG.md
vim CHANGELOG.md

# Bump version
vim pyproject.toml  # Update version number
```

## 🔄 Version Numbers

Follow semantic versioning:

- `0.1.0` - First alpha release (current)
- `0.2.0` - Add features, breaking changes OK
- `1.0.0` - First stable release
- `1.0.1` - Bug fixes only
- `1.1.0` - New features, backwards compatible
- `2.0.0` - Breaking changes

## 🛠️ Commands Reference

```bash
# Build package locally
make build

# Test on TestPyPI
make publish-test

# Publish to production PyPI
make publish

# Create release + auto-publish
make release

# Clean build artifacts
make clean
```

## 🔍 Verification

After publishing to PyPI:

```bash
# Wait 60 seconds for PyPI to update, then:
pip install qwenvert
qwenvert --version
qwenvert --help
qwenvert hardware
```

After publishing Homebrew formula:

```bash
brew tap kmesiab/qwenvert
brew install qwenvert
qwenvert --version
```

## 🐛 Troubleshooting

### Version already exists on PyPI
PyPI doesn't allow replacing versions. Must bump version:
```bash
# In pyproject.toml, change:
version = "0.1.0"
# To:
version = "0.1.1"  # Or 0.1.0.post1 for hotfixes
```

### Homebrew formula fails
```bash
# Test locally
brew install --build-from-source ./Formula/qwenvert.rb
brew test qwenvert
brew audit --strict qwenvert

# Check logs
brew gist-logs qwenvert
```

### GitHub Actions fails
Check:
- Secrets are set correctly (`PYPI_API_TOKEN`)
- Version in pyproject.toml matches git tag
- All tests pass locally

## 📚 More Info

See `PUBLISHING.md` for comprehensive documentation.
