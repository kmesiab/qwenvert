# Publishing qwenvert

This guide covers publishing qwenvert so users can install with:
- `pip install qwenvert`
- `brew install qwenvert`

## Quick Start: Publish to PyPI

### One-Time Setup (3 minutes)

1. **Create PyPI account and enable 2FA:**
   - https://pypi.org/account/register/

2. **Create GitHub environment:**
   - Go to: https://github.com/kmesiab/qwenvert/settings/environments
   - Click "New environment"
   - Name: `pypi`
   - (Optional) Add required reviewers for extra safety

3. **Configure PyPI Trusted Publisher:**
   - Go to: https://pypi.org/manage/account/publishing/
   - Scroll to "Add a new pending publisher"
   - Fill in:
     ```
     PyPI Project Name:   qwenvert
     Owner:              kmesiab
     Repository name:    qwenvert
     Workflow name:      publish.yml
     Environment name:   pypi
     ```
   - Click "Add"

That's it! **No API tokens needed** - PyPI trusts your GitHub workflow via OIDC.

### Publishing a Release

```bash
# 1. Update version in pyproject.toml
vim pyproject.toml  # Change version = "0.1.0" to "0.1.1"

# 2. Update CHANGELOG.md
vim CHANGELOG.md

# 3. Run all checks
make check-all

# 4. Create and publish release
make release
```

The `make release` command will:
- Create a git tag (e.g., `v0.1.1`)
- Push the tag to GitHub
- Create a draft release with auto-generated notes

Then:
1. Review the draft release on GitHub
2. Edit release notes if needed
3. Click "Publish release"
4. GitHub Actions automatically publishes to PyPI
5. Done! Users can now `pip install qwenvert`

### How OIDC Works

```
┌──────────────────┐
│ Publish Release  │
│   on GitHub      │
└────────┬─────────┘
         │
         v
┌────────────────────────────┐
│ GitHub Actions Workflow    │
│ (environment: pypi)        │
└────────┬───────────────────┘
         │
         v
┌────────────────────────────┐
│ GitHub generates OIDC      │
│ token for this workflow    │
└────────┬───────────────────┘
         │
         v
┌────────────────────────────┐
│ PyPI verifies:             │
│ ✓ Repo: kmesiab/qwenvert   │
│ ✓ Workflow: publish.yml    │
│ ✓ Environment: pypi        │
└────────┬───────────────────┘
         │
         v
     ✅ Published!
```

## Homebrew

### Personal Tap (Recommended)

After publishing to PyPI:

```bash
# 1. Create tap repo
gh repo create homebrew-qwenvert --public \
  --description "Homebrew formulae for qwenvert"

# 2. Clone and setup
git clone https://github.com/kmesiab/homebrew-qwenvert.git
cd homebrew-qwenvert
mkdir Formula

# 3. Generate formula
pip install homebrew-pypi-poet
poet qwenvert > temp.rb

# 4. Create formula
cat > Formula/qwenvert.rb <<'EOF'
class Qwenvert < Formula
  include Language::Python::Virtualenv

  desc "Local LLM adapter for Claude Code on Apple Silicon"
  homepage "https://github.com/kmesiab/qwenvert"
  url "https://files.pythonhosted.org/packages/source/q/qwenvert/qwenvert-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA_FROM_PYPI"
  license "Apache-2.0"

  depends_on "python@3.11"

  # Add resources from temp.rb here

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Install Ollama and initialize qwenvert:
        brew install ollama
        qwenvert init --backend ollama
        qwenvert start
    EOS
  end

  test do
    assert_match "qwenvert", shell_output("#{bin}/qwenvert --version")
  end
end
EOF

# 5. Test and publish
brew install --build-from-source ./Formula/qwenvert.rb
brew test qwenvert
git add Formula/qwenvert.rb
git commit -m "Add qwenvert formula v0.1.0"
git push
```

Users can then install:
```bash
brew tap kmesiab/qwenvert
brew install qwenvert
```

### Homebrew Core

Submit to official homebrew-core after:
- ✅ 30+ GitHub stars
- ✅ Stable 1.0.0+ release
- ✅ Active maintenance

## Version Numbers

Follow [Semantic Versioning](https://semver.org/):

- `0.1.0` - Initial alpha
- `0.2.0` - Add features (breaking changes OK in 0.x)
- `1.0.0` - First stable release
- `1.0.1` - Bug fixes only
- `1.1.0` - New features, backwards compatible
- `2.0.0` - Breaking changes

## Release Checklist

Before every release:

```bash
# Run all checks
make check-all

# Verify security tests (93 tests)
pytest tests/security/ -v

# Check coverage
make coverage

# Update docs
vim CHANGELOG.md
vim README.md  # Update version if shown
```

Then:
- [ ] All tests passing
- [ ] Security tests passing (93 tests)
- [ ] Coverage ≥80%
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`
- [ ] No TODO/FIXME in critical code

## Manual Publishing (Fallback)

If automated workflow fails:

```bash
# Build
python -m pip install --upgrade build twine
python -m build

# Check
python -m twine check dist/*

# Upload (requires API token)
python -m twine upload dist/*
```

## Troubleshooting

### "Trusted publishing exchange failure"

Check PyPI trusted publisher settings match exactly:
- Repository: `kmesiab/qwenvert` (not `.git`)
- Workflow: `publish.yml` (exact filename)
- Environment: `pypi` (must match workflow)

### "Package already exists"

PyPI doesn't allow replacing versions. Bump version:
```bash
# In pyproject.toml:
version = "0.1.1"  # Or use .post1 for hotfixes
```

### Workflow doesn't run

- Check GitHub environment `pypi` exists
- Check release was published (not draft)
- Check workflow permissions in repo settings

## References

- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Semantic Versioning](https://semver.org/)
