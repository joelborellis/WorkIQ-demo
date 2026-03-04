#!/usr/bin/env python3
"""
article_to_images.py — Parse a markdown article and generate contextually relevant
PNG images for headers, sections, and inline placeholders.

Uses the nano-banana model for AI-generated images.
Renders markdown tables locally via table_to_png.py (no API needed for tables).

Part of the article-image-gen skill for Claude Code.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config = {
        "model": "nano-banana",
        "api_key": "",
        "api_base": "https://api.your-provider.com/v1",
        "default_style": "illustrative",
    }
    config_path = Path.home() / ".article-image-gen" / "config.json"
    if config_path.exists():
        try:
            config.update(json.loads(config_path.read_text()))
        except Exception:
            pass
    for env_var, key in [
        ("IMAGE_GEN_MODEL", "model"),
        ("IMAGE_GEN_API_KEY", "api_key"),
        ("IMAGE_GEN_API_BASE", "api_base"),
    ]:
        val = os.environ.get(env_var)
        if val:
            config[key] = val
    return config


# ── Markdown Parser ───────────────────────────────────────────────────────────

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
TABLE_RE = re.compile(r"(\|.+\|\n(?:\|[-:| ]+\|\n)(?:\|.+\|\n?)+)", re.MULTILINE)
IMAGE_PLACEHOLDER_RE = re.compile(r"!\[([^\]]*)\]\(generate(?::([^)]*))?\)", re.MULTILINE)
BOLD_CONCEPT_RE = re.compile(r"\*\*([^*]{4,60})\*\*")


class ImageCandidate:
    def __init__(self, kind: str, context: str, label: str, position: int, raw_text: str = ""):
        self.kind = kind          # "header", "section", "table", "placeholder", "concept"
        self.context = context    # prompt context text
        self.label = label        # short human-readable label
        self.position = position  # char offset in article
        self.raw_text = raw_text  # original text (for tables)
        self.output_path: Optional[str] = None
        self.prompt: Optional[str] = None


def parse_article(markdown_text: str, max_images: int = 6) -> tuple[list[ImageCandidate], str]:
    """
    Parse markdown and return a list of image candidates plus the article title.
    Priority: placeholders > h1 title > h2 sections > tables > bold concepts
    """
    candidates: list[ImageCandidate] = []

    # 1. Explicit placeholders  ![alt](generate) or ![alt](generate:more context)
    for match in IMAGE_PLACEHOLDER_RE.finditer(markdown_text):
        alt = match.group(1)
        extra = match.group(2) or ""
        candidates.append(ImageCandidate(
            kind="placeholder",
            context=f"{alt}. {extra}".strip(),
            label=alt or "placeholder",
            position=match.start(),
            raw_text=match.group(0),
        ))

    # 2. Tables → local render (no API)
    for match in TABLE_RE.finditer(markdown_text):
        # Find surrounding heading for context
        preceding = markdown_text[:match.start()]
        headings = HEADING_RE.findall(preceding)
        table_label = headings[-1][1] if headings else "Data Table"
        candidates.append(ImageCandidate(
            kind="table",
            context=table_label,
            label=f"Table: {table_label}",
            position=match.start(),
            raw_text=match.group(0),
        ))

    # 3. H1 → header image candidate
    h1_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
    article_title = h1_match.group(1).strip() if h1_match else "Article"
    if h1_match:
        candidates.append(ImageCandidate(
            kind="header",
            context=f"Article header for: {article_title}",
            label=f"Header: {article_title}",
            position=0,  # Always first
        ))

    # 4. H2 sections
    for match in re.finditer(r"^##\s+(.+)$", markdown_text, re.MULTILINE):
        heading = match.group(1).strip()
        # Grab a snippet of text after the heading
        section_text = markdown_text[match.end():match.end() + 300]
        section_text = re.sub(r"[#\|*`]", "", section_text)
        candidates.append(ImageCandidate(
            kind="section",
            context=f"Section '{heading}'. {section_text[:200]}",
            label=f"Section: {heading}",
            position=match.start(),
        ))

    # 5. Bold concepts (lower priority, fills remaining slots)
    for match in BOLD_CONCEPT_RE.finditer(markdown_text):
        concept = match.group(1)
        candidates.append(ImageCandidate(
            kind="concept",
            context=f"Conceptual illustration for: {concept}",
            label=f"Concept: {concept}",
            position=match.start(),
        ))

    # Sort by priority, then position
    kind_priority = {"placeholder": 0, "table": 1, "header": 2, "section": 3, "concept": 4}
    candidates.sort(key=lambda c: (kind_priority.get(c.kind, 9), c.position))

    # Deduplicate by rough label similarity and cap
    seen_labels: set[str] = set()
    unique: list[ImageCandidate] = []
    for c in candidates:
        key = c.label[:40].lower()
        if key not in seen_labels:
            seen_labels.add(key)
            unique.append(c)
        if len(unique) >= max_images:
            break

    return unique, article_title


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_prompt(candidate: ImageCandidate, article_title: str, style: str) -> str:
    style_descriptors = {
        "illustrative": "digital illustration, modern flat design, clean vectors",
        "photorealistic": "photorealistic, professional photography, sharp focus",
        "abstract": "abstract digital art, geometric, conceptual",
        "minimal": "minimalist, clean lines, simple shapes, subtle palette",
        "watercolor": "watercolor illustration, soft artistic brushwork",
    }
    style_desc = style_descriptors.get(style, style_descriptors["illustrative"])

    base = (
        f"An image for a learning/informational article titled '{article_title}'. "
        f"Context: {candidate.context}. "
        f"Style: {style_desc}. "
        f"No text in image. Educational, professional, publication-ready. "
        f"Suitable for a blog or documentation site. sRGB, 16:9 composition."
    )
    return base


# ── Image Generation ───────────────────────────────────────────────────────────

def generate_image_api(
    prompt: str,
    model: str,
    api_key: str,
    api_base: str,
    width: int = 800,
    height: int = 450,
) -> bytes:
    """Call the nano-banana image generation API. Adjust payload/response parsing for your provider."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "output_format": "png",
        "response_format": "b64_json",
    }
    endpoint = f"{api_base.rstrip('/')}/images/generate"
    response = requests.post(endpoint, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text[:300]}")

    data = response.json()

    # Pattern A: DALL-E style
    if "data" in data and isinstance(data["data"], list):
        b64 = data["data"][0].get("b64_json")
        if b64:
            return base64.b64decode(b64)
        url = data["data"][0].get("url")
        if url:
            return requests.get(url, timeout=60).content

    # Pattern B: direct base64
    if "image" in data:
        return base64.b64decode(data["image"])

    # Pattern C: output URL
    if "output" in data:
        url = data["output"] if isinstance(data["output"], str) else data["output"][0]
        return requests.get(url, timeout=60).content

    raise RuntimeError(f"Cannot parse API response: {json.dumps(data)[:200]}")


def render_table_locally(candidate: ImageCandidate, output_path: str, title: str = "") -> bool:
    """Render a markdown table to PNG using table_to_png.py"""
    script_dir = Path(__file__).parent
    table_script = script_dir / "table_to_png.py"
    if not table_script.exists():
        return False

    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            str(table_script),
            "--table", candidate.raw_text,
            "--title", title or candidate.context,
            "--output", output_path,
            "--theme", "light",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parse a markdown article and generate contextual PNG images."
    )
    parser.add_argument("--input", "-i", required=True, help="Path to the markdown article file")
    parser.add_argument("--output-dir", "-d", default="images", help="Directory for output PNGs")
    parser.add_argument("--max-images", type=int, default=6, help="Maximum number of images to generate")
    parser.add_argument(
        "--style",
        default="illustrative",
        choices=["illustrative", "photorealistic", "abstract", "minimal", "watercolor"],
    )
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=450)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print candidates without generating images",
    )
    parser.add_argument(
        "--manifest",
        default="image_manifest.json",
        help="Path for output manifest JSON",
    )
    args = parser.parse_args()

    config = load_config()

    # Read article
    article_path = Path(args.input)
    if not article_path.exists():
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    markdown_text = article_path.read_text(encoding="utf-8")
    print(f"📄 Parsing article: {article_path.name} ({len(markdown_text):,} chars)", file=sys.stderr)

    candidates, article_title = parse_article(markdown_text, max_images=args.max_images)
    print(f"🔍 Found {len(candidates)} image candidates for '{article_title}'", file=sys.stderr)

    if args.dry_run:
        print("\n=== Image Candidates (dry run) ===")
        for i, c in enumerate(candidates, 1):
            print(f"\n[{i}] Kind: {c.kind}")
            print(f"    Label: {c.label}")
            print(f"    Position: char {c.position}")
            if c.kind != "table":
                prompt = build_prompt(c, article_title, args.style)
                print(f"    Prompt: {prompt[:120]}...")
            else:
                print(f"    → Will render table locally (no API)")
        return

    if not config["api_key"] and any(c.kind != "table" for c in candidates):
        print(
            "ERROR: IMAGE_GEN_API_KEY not set. Table images will still be generated locally.\n"
            "Set IMAGE_GEN_API_KEY or add api_key to ~/.article-image-gen/config.json",
            file=sys.stderr,
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "article": str(article_path),
        "article_title": article_title,
        "style": args.style,
        "model": config["model"],
        "images": [],
    }

    for i, candidate in enumerate(candidates, 1):
        slug = re.sub(r"[^\w]+", "_", candidate.label[:40]).strip("_").lower()
        filename = f"{i:02d}_{slug}.png"
        output_path = str(output_dir / filename)

        print(f"\n[{i}/{len(candidates)}] {candidate.label}", file=sys.stderr)

        try:
            if candidate.kind == "table":
                # Render locally — no API call needed
                print(f"  📊 Rendering table locally...", file=sys.stderr)
                success = render_table_locally(candidate, output_path, title=candidate.context)
                if not success:
                    print(f"  ⚠️  Table render failed, skipping.", file=sys.stderr)
                    continue
                prompt_used = "local render (matplotlib)"
            else:
                prompt = build_prompt(candidate, article_title, args.style)
                candidate.prompt = prompt
                print(f"  🎨 Generating via nano-banana ({args.width}×{args.height})...", file=sys.stderr)

                if not config["api_key"]:
                    print(f"  ⚠️  Skipping (no API key).", file=sys.stderr)
                    continue

                image_bytes = generate_image_api(
                    prompt=prompt,
                    model=config["model"],
                    api_key=config["api_key"],
                    api_base=config["api_base"],
                    width=args.width,
                    height=args.height,
                )
                Path(output_path).write_bytes(image_bytes)
                prompt_used = prompt
                print(f"  ✓ Saved ({len(image_bytes)/1024:.1f} KB)", file=sys.stderr)

            manifest["images"].append({
                "index": i,
                "kind": candidate.kind,
                "label": candidate.label,
                "position": candidate.position,
                "output": output_path,
                "prompt": prompt_used if candidate.kind != "table" else "local render",
                "suggested_markdown": f'![{candidate.label}]({output_path})',
            })
            candidate.output_path = output_path

        except Exception as e:
            print(f"  ❌ Error: {e}", file=sys.stderr)
            continue

        # Be polite to the API
        if i < len(candidates) and candidate.kind != "table":
            time.sleep(1)

    # Save manifest
    manifest_path = Path(args.manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n✓ Manifest saved: {manifest_path}", file=sys.stderr)

    # Print suggested markdown insertions
    print("\n=== Suggested Markdown Image Insertions ===")
    for img in manifest["images"]:
        print(f"\n# {img['label']} (position ~{img['position']})")
        print(img["suggested_markdown"])

    print("\n" + json.dumps(manifest))


if __name__ == "__main__":
    main()
