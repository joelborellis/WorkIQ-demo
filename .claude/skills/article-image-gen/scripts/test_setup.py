#!/usr/bin/env python3
"""
test_setup.py — Verify that the article-image-gen skill is properly configured.
Run this first to check dependencies and API connectivity.

Part of the article-image-gen skill for Claude Code.
"""

import importlib
import json
import os
import sys
from pathlib import Path


def check(label: str, ok: bool, detail: str = ""):
    status = "✓" if ok else "✗"
    line = f"  {status}  {label}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    return ok


def main():
    print("\n🔍 article-image-gen — Setup Check\n")
    all_ok = True

    # ── Python version ────────────────────────────────────────────────────────
    py_ok = sys.version_info >= (3, 9)
    all_ok &= check(
        f"Python version",
        py_ok,
        f"{sys.version.split()[0]} {'(ok)' if py_ok else '(need 3.9+)'}",
    )

    # ── Required packages ─────────────────────────────────────────────────────
    print()
    required = ["matplotlib", "requests", "numpy"]
    for pkg in required:
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "?")
            all_ok &= check(f"Package: {pkg}", True, f"v{version}")
        except ImportError:
            all_ok &= check(f"Package: {pkg}", False, f"not installed — run: pip install {pkg}")

    # ── Config file ────────────────────────────────────────────────────────────
    print()
    config_path = Path.home() / ".article-image-gen" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            check("Config file", True, str(config_path))
            check("  model", bool(config.get("model")), config.get("model", "not set"))
            check("  api_key", bool(config.get("api_key")), "set" if config.get("api_key") else "NOT SET")
            check("  api_base", bool(config.get("api_base")), config.get("api_base", "not set"))
        except json.JSONDecodeError:
            all_ok &= check("Config file", False, "invalid JSON")
    else:
        check("Config file", False, f"not found at {config_path}")
        print(f"         Create it with:")
        print(f'         mkdir -p {config_path.parent} && cat > {config_path} << \'EOF\'')
        print(json.dumps({
            "model": "nano-banana",
            "api_key": "YOUR_API_KEY_HERE",
            "api_base": "https://api.your-provider.com/v1",
            "default_style": "illustrative"
        }, indent=2))
        print("EOF")

    # ── Environment variables ─────────────────────────────────────────────────
    print()
    api_key_env = os.environ.get("IMAGE_GEN_API_KEY", "")
    check(
        "Env: IMAGE_GEN_API_KEY",
        bool(api_key_env),
        "set" if api_key_env else "not set (optional if using config.json)",
    )
    check(
        "Env: IMAGE_GEN_MODEL",
        True,  # always optional
        os.environ.get("IMAGE_GEN_MODEL", "not set (will use config or default)"),
    )

    # ── Script files ──────────────────────────────────────────────────────────
    print()
    script_dir = Path(__file__).parent
    scripts = ["table_to_png.py", "generate_header.py", "article_to_images.py"]
    for script in scripts:
        path = script_dir / script
        all_ok &= check(f"Script: {script}", path.exists(), str(path) if path.exists() else "MISSING")

    # ── Quick table render test ────────────────────────────────────────────────
    print()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import tempfile

        sample_headers = ["Feature", "Value", "Notes"]
        sample_rows = [
            ["Speed", "Fast", "< 100ms"],
            ["Accuracy", "High", "99.2%"],
            ["Memory", "Low", "< 50MB"],
        ]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name

        # Inline mini-render
        sys.path.insert(0, str(script_dir))
        from table_to_png import render_table_png
        result = render_table_png(
            sample_headers,
            sample_rows,
            tmp_path,
            title="Test Table",
            theme_name="light",
        )
        size = Path(tmp_path).stat().st_size
        Path(tmp_path).unlink()
        all_ok &= check("Table render test", True, f"Generated {size} byte PNG successfully")
    except Exception as e:
        all_ok &= check("Table render test", False, str(e))

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if all_ok:
        print("✅ All checks passed. Ready to generate article images!\n")
        print("Quick start:")
        print("  # Generate header image:")
        print('  python scripts/generate_header.py --title "My Article Title" --style illustrative')
        print()
        print("  # Convert a markdown table to PNG:")
        print('  python scripts/table_to_png.py --table-file my_table.md --title "My Table"')
        print()
        print("  # Generate images for a full article:")
        print("  python scripts/article_to_images.py --input article.md --max-images 5")
    else:
        print("⚠️  Some checks failed. Fix the issues above and re-run.\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
