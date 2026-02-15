# llama.cpp Release Checksums

This directory contains verified SHA256 checksums for llama.cpp releases from ggml-org.

## Why Self-Host Checksums?

As of February 2025, ggml-org/llama.cpp does not publish checksum files with their releases. To maintain security, qwenvert self-hosts verified checksums here.

## File Format

Each release has a file named `{version}.txt` with format:
```
# llama.cpp release {version} checksums
# Verified: YYYY-MM-DD
checksum  filename
```

Example (`b8054.txt`):
```
# llama.cpp release b8054 checksums
# Verified: 2025-02-14
abc123...def  llama-b8054-bin-macos-arm64.tar.gz
789xyz...456  llama-b8054-bin-macos-x64.tar.gz
```

## How to Add Checksums

### Step 1: Download and Verify
```bash
# Download the release binary
wget https://github.com/ggml-org/llama.cpp/releases/download/b8054/llama-b8054-bin-macos-arm64.tar.gz

# Calculate SHA256
shasum -a 256 llama-b8054-bin-macos-arm64.tar.gz

# IMPORTANT: Verify the binary works before adding checksum!
tar -xzf llama-b8054-bin-macos-arm64.tar.gz
./bin/llama-server --version
```

### Step 2: Add to Checksum File
```bash
cd qwenvert/checksums
echo "# llama.cpp release b8054 checksums" > b8054.txt
echo "# Verified: $(date +%Y-%m-%d)" >> b8054.txt
shasum -a 256 /path/to/llama-b8054-bin-macos-arm64.tar.gz | awk '{print $1 "  llama-b8054-bin-macos-arm64.tar.gz"}' >> b8054.txt
```

### Step 3: Test
```bash
# Test that qwenvert finds the checksum
python3 -c "
from qwenvert.binary_manager import BinaryManager
bm = BinaryManager()
checksum = bm._get_bundled_checksum('b8054', 'llama-b8054-bin-macos-arm64.tar.gz')
print(f'Found checksum: {checksum}')
"
```

### Step 4: Commit
```bash
git add qwenvert/checksums/b8054.txt
git commit -m "Add verified checksums for llama.cpp b8054 release"
```

## Security Notes

- **Only add checksums for binaries you've personally verified**
- Always test the binary executes correctly before committing checksum
- Include verification date in the checksum file
- Use `shasum -a 256` (macOS) or `sha256sum` (Linux) for consistency

## Upstream Status

We've filed an issue with ggml-org requesting they publish checksums:
- Issue: https://github.com/ggml-org/llama.cpp/issues/XXXXX

If ggml-org starts publishing checksums, qwenvert will automatically prefer those over bundled checksums.

## Maintenance

- **Add new release checksums** when ggml-org publishes new releases
- **Remove old checksums** after 6 months (keep last 10 releases)
- **Update this README** if verification process changes
