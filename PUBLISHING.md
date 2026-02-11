# Publishing Guide for qwenvert

This guide covers publishing qwenvert to PyPI and Homebrew so users can install with:
- `pip install qwenvert`
- `brew install qwenvert`

## Prerequisites

### PyPI Account Setup

**Option 1: OIDC Trusted Publisher (Recommended)**

No API tokens needed! PyPI trusts GitHub Actions directly.

1. Create PyPI account: https://pypi.org/account/register/
2. Set up 2FA (required)
3. Follow the **[PYPI_OIDC_SETUP.md](PYPI_OIDC_SETUP.md)** guide

**Option 2: API Tokens (Fallback)**

Only needed for TestPyPI or manual publishing.

1. Get TestPyPI token: https://test.pypi.org/manage/account/token/
2. Add to GitHub Secrets: `TEST_PYPI_API_TOKEN`

### Required Tools
```bash
# Install build tools
pip install build twine

# Install GitHub CLI (for releases)
brew install gh
```

## Publishing to PyPI

### Option 1: Automated with OIDC (Recommended)

**First time only:** Configure PyPI trusted publisher (see [PYPI_OIDC_SETUP.md](PYPI_OIDC_SETUP.md))

Then for every release:

```bash
# 1. Update version in pyproject.toml
vim pyproject.toml  # Change version = "0.1.0" to "0.1.1"

# 2. Create release
make release

# This will:
#   - Create git tag
#   - Create GitHub release (draft)
#   - You review and publish the release
#   - Workflow automatically publishes to PyPI (no tokens needed!)
```

The workflow will:
- Run all tests
- Build the package
- Publish to PyPI via OIDC (secure, no tokens!)
- Create release artifacts
- Verify installation

### Option 2: Manual Publishing
For testing or one-off releases:

```bash
# 1. Clean previous builds
rm -rf dist/ build/ *.egg-info

# 2. Build the package
python -m build

# This creates:
# - dist/qwenvert-0.1.0-py3-none-any.whl
# - dist/qwenvert-0.1.0.tar.gz

# 3. Test the build locally
pip install dist/qwenvert-0.1.0-py3-none-any.whl
qwenvert --help

# 4. Upload to TestPyPI (for testing)
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI:
pip install --index-url https://test.pypi.org/simple/ qwenvert

# 5. Upload to PyPI (production)
python -m twine upload dist/*

# Verify:
pip install qwenvert
qwenvert --help
```

### Version Numbering
Follow [Semantic Versioning](https://semver.org/):
- **0.1.0** → Initial alpha release
- **0.2.0** → Add features, breaking changes OK in 0.x
- **1.0.0** → First stable release
- **1.0.1** → Bug fixes only
- **1.1.0** → New features, backwards compatible
- **2.0.0** → Breaking changes

## Publishing to Homebrew

### Option 1: Homebrew Core (Official)
For widespread distribution, submit to [homebrew-core](https://github.com/Homebrew/homebrew-core):

**Requirements:**
- 30+ stars on GitHub
- 75+ forks OR 30+ watchers
- Stable 1.0.0+ version
- Active maintenance

**Steps:**
1. Publish to PyPI first
2. Create formula using `brew create`:
```bash
brew create https://files.pythonhosted.org/packages/.../qwenvert-0.1.0.tar.gz
```

3. Submit PR to homebrew-core
4. Wait for review (usually 1-2 weeks)

### Option 2: Personal Tap (Faster)
Create your own Homebrew tap for immediate availability:

```bash
# 1. Create tap repository
gh repo create homebrew-qwenvert --public --description "Homebrew tap for qwenvert"

# 2. Clone and add formula
git clone https://github.com/kmesiab/homebrew-qwenvert.git
cd homebrew-qwenvert
mkdir Formula
```

Create `Formula/qwenvert.rb`:
```ruby
class Qwenvert < Formula
  include Language::Python::Virtualenv

  desc "Local LLM adapter for Claude Code on Apple Silicon"
  homepage "https://github.com/kmesiab/qwenvert"
  url "https://files.pythonhosted.org/packages/source/q/qwenvert/qwenvert-0.1.0.tar.gz"
  sha256 "..." # Get from: shasum -a 256 dist/qwenvert-0.1.0.tar.gz
  license "Apache-2.0"

  depends_on "python@3.11"

  resource "click" do
    url "https://files.pythonhosted.org/packages/.../click-8.1.7.tar.gz"
    sha256 "..."
  end

  # Add all dependencies from pyproject.toml...

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/qwenvert", "--version"
  end
end
```

**Auto-generate formula:**
```bash
# Use homebrew-pypi-poet to generate resources
pip install homebrew-pypi-poet
poet qwenvert > Formula/qwenvert.rb
# Then manually add the header (class definition, desc, homepage, etc.)
```

```bash
# 3. Commit and push
git add Formula/qwenvert.rb
git commit -m "Add qwenvert formula"
git push

# 4. Users can now install with:
brew tap kmesiab/qwenvert
brew install qwenvert
```

### Updating the Formula
When you release a new version:

```bash
cd homebrew-qwenvert
brew bump-formula-pr --url=https://files.pythonhosted.org/packages/.../qwenvert-0.2.0.tar.gz
```

## Release Checklist

### Pre-Release
- [ ] All tests passing (`make test`)
- [ ] Linting clean (`make lint`)
- [ ] Type checking clean (`make typecheck`)
- [ ] Security tests passing (93 tests)
- [ ] Coverage ≥80%
- [ ] README updated
- [ ] CHANGELOG updated
- [ ] Version bumped in `pyproject.toml`
- [ ] No TODO or FIXME in critical code

### PyPI Release
- [ ] Tested on TestPyPI
- [ ] Tagged in git (`git tag v0.1.0`)
- [ ] GitHub release created
- [ ] PyPI package published
- [ ] Installation tested: `pip install qwenvert`
- [ ] CLI works: `qwenvert --help`

### Homebrew Release
- [ ] PyPI package available
- [ ] Formula created/updated
- [ ] Formula tested: `brew install qwenvert`
- [ ] Formula pushed to tap
- [ ] Installation verified on clean machine

### Post-Release
- [ ] Announcement on GitHub Discussions
- [ ] Update installation docs
- [ ] Tweet/social media announcement
- [ ] Close milestone on GitHub
- [ ] Start next milestone

## Troubleshooting

### PyPI Upload Fails
```bash
# Check package metadata
python -m twine check dist/*

# Verify token is correct
cat ~/.pypirc  # Should have [pypi] token = "pypi-..."
```

### Homebrew Formula Fails
```bash
# Test locally before pushing
brew install --build-from-source ./Formula/qwenvert.rb
brew test qwenvert
brew audit --strict qwenvert
```

### Version Conflicts
```bash
# If version already exists on PyPI:
# 1. You CANNOT delete/replace versions on PyPI
# 2. Must bump version and re-release
# 3. Use .post1, .post2 for post-release fixes:
version = "0.1.0.post1"  # Fix for 0.1.0
```

## References

- [PyPI Packaging Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Semantic Versioning](https://semver.org/)
- [PEP 440 Version Specifiers](https://peps.python.org/pep-0440/)
