# Request to ggml-org: Publish Checksums with Releases

**File this issue at**: https://github.com/ggml-org/llama.cpp/issues/new

---

## Title
Request: Publish SHA256 checksums with release binaries

## Body

### Problem

The llama.cpp releases currently do not include checksum files (SHA256SUMS, checksums.txt, etc.) for the binary artifacts. This makes it difficult for downstream tools to verify binary integrity.

### Impact

Without checksums, users cannot:
- Verify that downloaded binaries haven't been corrupted during transfer
- Detect potential supply chain attacks or tampering
- Implement fail-closed security policies that require verification

### Proposed Solution

Please publish a `SHA256SUMS` file with each release containing checksums for all binary artifacts.

Example format:
```
b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565  llama-b8054-bin-macos-arm64.tar.gz
d78ccc86d8d33afd7b365f9f3310b59621c09e4d4e6dcef4cdd6482c2af1100c  llama-b8054-bin-macos-x64.tar.gz
...
```

### Implementation

This can be automated in the release workflow:

```yaml
- name: Generate checksums
  run: |
    sha256sum *.tar.gz > SHA256SUMS

- name: Upload checksums
  uses: actions/upload-release-asset@v1
  with:
    asset_path: SHA256SUMS
    asset_name: SHA256SUMS
    asset_content_type: text/plain
```

### Use Case

We're building [qwenvert](https://github.com/kmesiab/qwenvert), a tool that provides zero-friction llama.cpp setup for Mac users. We want to verify binary integrity but currently cannot because checksums aren't published.

Temporary workaround: We're self-hosting verified checksums in our repo, but upstream checksums would be more trustworthy.

### Prior Art

Other projects that publish checksums:
- Rust releases: https://github.com/rust-lang/rust/releases
- Go releases: https://go.dev/dl/
- Node.js releases: https://nodejs.org/dist/

### References

- NIST guidelines on software verification: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf
- SLSA framework (Supply Chain Levels for Software Artifacts): https://slsa.dev/

---

### Labels
- enhancement
- release-process
- security

### CC
@ggerganov (if appropriate to tag maintainer)
