"""
vendor_models.py
-----------------
One-time setup (Plan.md ML AUGMENTATION LAYER, Phase A): download the two
frozen pretrained models ml_arbiter.py depends on into a local, read-only,
offline vendored directory restricted to safetensors weights only, and
record a SHA-256 manifest for supply-chain verification.

Run once, from a connected host:
    .venv\\Scripts\\python.exe "Engine 1 and 2/Semantic Engine/vendor_models.py"

After vendoring, ml_arbiter.py loads exclusively from MODELS_DIR with
HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 set — no network access at
inference time.

NOTE: picklescan/modelscan (Plan.md's suggested pre-load scan) do not
support this project's Python version (3.14) as of this writing — both
cap at Python <3.13. Safetensors-only vendoring is the primary mitigation
here: this script only downloads *.safetensors weights, never the
pickle-format pytorch_model.bin/openvino .bin siblings these repos also
publish, which structurally rules out the unsafe-deserialization risk
those two scanners exist to catch. Re-add the scan step once a compatible
release ships.
"""

import hashlib
import os
import stat
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS_DIR = Path(__file__).resolve().parent / "models"

# repo_id -> allowed file patterns. Deliberately excludes *.bin / *.pt /
# *.msgpack (pickle-format or otherwise non-safetensors weights).
MODELS = {
    "intfloat/multilingual-e5-small": [
        "*.safetensors", "*.json", "*.txt", "*.model",
    ],
    "cross-encoder/nli-deberta-v3-small": [
        "*.safetensors", "*.json", "*.txt", "*.model",
    ],
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_read_only(path: Path):
    os.chmod(path, stat.S_IREAD)


def vendor(repo_id: str, allow_patterns):
    local_dir = MODELS_DIR / repo_id.replace("/", "__")
    print(f"Vendoring {repo_id} -> {local_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(local_dir),
        allow_patterns=allow_patterns,
    )

    manifest_lines = []
    for root, _dirs, files in os.walk(local_dir):
        for name in files:
            if name == "MANIFEST.sha256":
                continue
            p = Path(root) / name
            digest = _sha256(p)
            rel = p.relative_to(local_dir).as_posix()
            manifest_lines.append(f"{digest}  {rel}")

    manifest_path = local_dir / "MANIFEST.sha256"
    manifest_path.write_text("\n".join(sorted(manifest_lines)) + "\n", encoding="utf-8")
    print(f"  {len(manifest_lines)} files hashed -> {manifest_path}")

    # Read-only pass happens last so writing the manifest itself doesn't fail.
    for root, _dirs, files in os.walk(local_dir):
        for name in files:
            _make_read_only(Path(root) / name)


def verify(repo_id: str) -> bool:
    """Re-check every vendored file against its recorded hash. Call this
    before first use in a new environment to detect tampering/corruption."""
    local_dir = MODELS_DIR / repo_id.replace("/", "__")
    manifest_path = local_dir / "MANIFEST.sha256"
    if not manifest_path.exists():
        print(f"  NO MANIFEST for {repo_id} - not vendored yet")
        return False
    ok = True
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        p = local_dir / rel
        if not p.exists() or _sha256(p) != digest:
            print(f"  MISMATCH: {rel}")
            ok = False
    return ok


if __name__ == "__main__":
    # Vendoring itself needs the network; ml_arbiter.py is what runs offline.
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    for repo_id, patterns in MODELS.items():
        vendor(repo_id, patterns)
    print("\nVerifying...")
    for repo_id in MODELS:
        status = "OK" if verify(repo_id) else "FAILED"
        print(f"  {repo_id}: {status}")
