# PyPI Trusted Publisher Setup (OIDC)

PyPI's trusted publisher feature (OIDC) allows GitHub Actions to publish packages **without storing API tokens**. This is more secure and easier to manage.

## One-Time Setup

### Step 1: Create GitHub Environment

1. Go to: https://github.com/kmesiab/qwenvert/settings/environments
2. Click "New environment"
3. Name it: `pypi` (must match workflow)
4. (Optional) Add protection rules:
   - ✅ Required reviewers (recommended)
   - ✅ Deployment branches: Only `main` branch

### Step 2: Configure PyPI Trusted Publisher

1. Go to: https://pypi.org/manage/account/publishing/
2. Scroll to "Add a new pending publisher"
3. Fill in the form:

```
PyPI Project Name:    qwenvert
Owner:                kmesiab
Repository name:      qwenvert
Workflow name:        publish.yml
Environment name:     pypi
```

4. Click "Add"

That's it! No API tokens needed.

## How It Works

```
┌─────────────────┐
│ GitHub Release  │
│   Published     │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│ GitHub Actions Workflow Runs    │
│ (publish.yml in environment:    │
│  pypi)                           │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│ GitHub generates OIDC token     │
│ with workflow identity          │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│ PyPI verifies:                  │
│ - Repository: kmesiab/qwenvert  │
│ - Workflow: publish.yml         │
│ - Environment: pypi             │
│ - Token signature valid         │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│ ✅ Package published to PyPI    │
└─────────────────────────────────┘
```

## First Release

The first time you publish:

1. **Configure the pending publisher on PyPI** (see Step 2 above)
   - This creates a "reservation" for the `qwenvert` package
   - The reservation is tied to your GitHub repo and workflow

2. **Create your first release:**
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   gh release create v0.1.0 --title "qwenvert v0.1.0" --generate-notes
   ```

3. **Publish the release on GitHub:**
   - Go to: https://github.com/kmesiab/qwenvert/releases
   - Edit the draft release
   - Click "Publish release"

4. **The workflow runs automatically and:**
   - Creates the `qwenvert` project on PyPI (first time only)
   - Converts the "pending publisher" to a regular publisher
   - Publishes your package

## Subsequent Releases

After the first release, the process is the same:

```bash
# Bump version in pyproject.toml
vim pyproject.toml

# Create release
make release
```

The workflow will automatically publish to PyPI.

## Security Benefits

### With API Tokens (Old Way):
- ❌ Token stored as GitHub secret
- ❌ Token has full account access
- ❌ Token can be leaked if secret is exposed
- ❌ Token doesn't expire automatically
- ❌ Must be rotated manually

### With OIDC (New Way):
- ✅ No secrets stored anywhere
- ✅ Token only valid for this specific workflow
- ✅ Token expires after 1 hour
- ✅ Token can't be reused outside GitHub Actions
- ✅ PyPI verifies exact repository + workflow
- ✅ Can require environment protection rules

## Environment Protection (Recommended)

Add protection rules to the `pypi` environment:

1. Go to: https://github.com/kmesiab/qwenvert/settings/environments/pypi
2. Enable "Required reviewers"
   - Add yourself and trusted maintainers
   - Prevents accidental releases
3. Enable "Deployment branches"
   - Select "Protected branches" or "Selected branches"
   - Only allow `main` branch to publish

Now every release requires manual approval before publishing to PyPI!

## Troubleshooting

### "Trusted publishing exchange failure"

**Cause:** PyPI can't verify the OIDC token.

**Fix:** Check that PyPI trusted publisher settings match:
- Repository: `kmesiab/qwenvert` (not `kmesiab/qwenvert.git`)
- Workflow name: `publish.yml` (exact filename)
- Environment: `pypi` (must match workflow)

### "Package name already taken"

**Cause:** Someone else created the package before your workflow ran.

**Fix:** Package names are first-come, first-served. Choose a different name.

### "Environment not found"

**Cause:** GitHub environment `pypi` doesn't exist.

**Fix:** Create it at https://github.com/kmesiab/qwenvert/settings/environments

### First release fails with "pending publisher not found"

**Cause:** You didn't configure the pending publisher on PyPI.

**Fix:** Go to https://pypi.org/manage/account/publishing/ and add it.

## Testing with TestPyPI

For TestPyPI, you still need an API token (TestPyPI doesn't support OIDC yet).

1. Get token: https://test.pypi.org/manage/account/token/
2. Add secret: `TEST_PYPI_API_TOKEN` to GitHub
3. Run: Manual workflow dispatch with "test_pypi" option

## References

- [PyPI Trusted Publishers Guide](https://docs.pypi.org/trusted-publishers/)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish)
