#!/usr/bin/env python3
"""
generate_header.py — Generate a publication-quality header/banner image for an article.

Uses the nano-banana image generation model via the configured API.
Outputs a 1200x630 PNG (Open Graph standard) or configurable dimensions.

Part of the article-image-gen skill for Claude Code.
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load configuration from file or environment variables."""
    config = {
        "model": "nano-banana",
        "api_key": "",
        "api_base": "https://api.your-provider.com/v1",
        "default_style": "illustrative",
    }

    # Config file
    config_path = Path.home() / ".article-image-gen" / "config.json"
    if config_path.exists():
        try:
            file_config = json.loads(config_path.read_text())
            config.update(file_config)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse config file at {config_path}", file=sys.stderr)

    # Environment overrides
    env_map = {
        "IMAGE_GEN_MODEL": "model",
        "IMAGE_GEN_API_KEY": "api_key",
        "IMAGE_GEN_API_BASE": "api_base",
    }
    for env_var, key in env_map.items():
        val = os.environ.get(env_var)
        if val:
            config[key] = val

    return config


# ── Prompt Builder ─────────────────────────────────────────────────────────────

STYLE_DESCRIPTORS = {
    "photorealistic": (
        "photorealistic, high-quality photograph, professional photography, "
        "sharp focus, natural lighting, editorial style"
    ),
    "illustrative": (
        "digital illustration, clean vector style, modern flat design, "
        "professional infographic aesthetic, smooth gradients"
    ),
    "abstract": (
        "abstract art, geometric shapes, flowing forms, conceptual design, "
        "dynamic composition, bold colors"
    ),
    "minimal": (
        "minimalist design, clean lines, lots of white space, simple shapes, "
        "subtle color palette, elegant typography-friendly background"
    ),
    "watercolor": (
        "watercolor illustration, soft washes, artistic brushwork, "
        "warm and inviting, hand-painted feel"
    ),
}


def build_header_prompt(
    title: str,
    style: str = "illustrative",
    theme_keywords: str = "",
    audience: str = "general",
) -> str:
    style_desc = STYLE_DESCRIPTORS.get(style, STYLE_DESCRIPTORS["illustrative"])
    theme_part = f" Visual theme keywords: {theme_keywords}." if theme_keywords else ""
    audience_part = f" Target audience: {audience}." if audience != "general" else ""

    return (
        f"Header banner image for an educational article titled: '{title}'. "
        f"Wide format 16:9 banner composition. {style_desc}."
        f"{theme_part}{audience_part} "
        f"The image should visually represent the article's topic in an engaging and "
        f"professional way. No text or typography in the image. "
        f"High quality, publication-ready, suitable for a blog or documentation site. "
        f"sRGB color space. Clean, uncluttered composition with visual breathing room "
        f"for potential title overlay."
    )


# ── API Client ────────────────────────────────────────────────────────────────

def generate_image_api(
    prompt: str,
    model: str,
    api_key: str,
    api_base: str,
    width: int = 1200,
    height: int = 630,
    num_inference_steps: int = 30,
) -> bytes:
    """
    Call the image generation API (nano-banana model).
    Adjust this function's payload structure to match your provider's API spec.

    Common provider patterns:
      - Replicate: POST /predictions with model ID and version
      - Stability AI: POST /v1/generation/{engine}/text-to-image
      - OpenAI DALL-E: POST /v1/images/generations
      - Hugging Face Inference API: POST /models/{model}
      - Custom / nano-banana native API: POST /v1/images/generate

    The default payload below follows a generic REST pattern.
    Edit the `payload` dict and response parsing to match your provider.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # ── Payload — adjust to match your API provider ──────────────────────────
    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "output_format": "png",
        "response_format": "b64_json",  # or "url"
    }
    # ─────────────────────────────────────────────────────────────────────────

    endpoint = f"{api_base.rstrip('/')}/images/generate"
    response = requests.post(endpoint, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(
            f"API error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()

    # ── Response parsing — adjust to match your API provider ─────────────────
    # Pattern A: base64 JSON response (DALL-E style)
    if "data" in data and isinstance(data["data"], list):
        b64 = data["data"][0].get("b64_json")
        if b64:
            return base64.b64decode(b64)
        url = data["data"][0].get("url")
        if url:
            img_response = requests.get(url, timeout=60)
            return img_response.content

    # Pattern B: direct base64
    if "image" in data:
        b64 = data["image"]
        if isinstance(b64, str):
            return base64.b64decode(b64)

    # Pattern C: output URL
    if "output" in data:
        output = data["output"]
        if isinstance(output, list):
            url = output[0]
        else:
            url = output
        img_response = requests.get(url, timeout=60)
        return img_response.content
    # ─────────────────────────────────────────────────────────────────────────

    raise RuntimeError(f"Could not parse image from API response: {json.dumps(data)[:300]}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a header image for an article using the nano-banana model."
    )
    parser.add_argument("--title", required=True, help="Article title (used as prompt inspiration)")
    parser.add_argument(
        "--style",
        choices=list(STYLE_DESCRIPTORS.keys()),
        default="illustrative",
        help="Visual style of the generated image",
    )
    parser.add_argument(
        "--theme",
        default="",
        help='Extra theme/context keywords (e.g., "machine learning, neural networks, blue palette")',
    )
    parser.add_argument("--audience", default="general", help="Target audience for tone calibration")
    parser.add_argument("--width", type=int, default=1200, help="Image width in pixels")
    parser.add_argument("--height", type=int, default=630, help="Image height in pixels")
    parser.add_argument("--steps", type=int, default=30, help="Inference steps (quality vs speed)")
    parser.add_argument("--output", "-o", default="header.png", help="Output PNG path")
    parser.add_argument("--print-prompt", action="store_true", help="Print the generated prompt and exit")
    args = parser.parse_args()

    config = load_config()

    # Build prompt
    prompt = build_header_prompt(
        title=args.title,
        style=args.style,
        theme_keywords=args.theme,
        audience=args.audience,
    )

    if args.print_prompt:
        print("=== Generated Prompt ===")
        print(prompt)
        return

    # Validate config
    if not config["api_key"]:
        print(
            "ERROR: No API key configured.\n"
            "Set IMAGE_GEN_API_KEY env var or add 'api_key' to ~/.article-image-gen/config.json",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"🎨 Generating header image for: '{args.title}'", file=sys.stderr)
    print(f"   Model: {config['model']}", file=sys.stderr)
    print(f"   Style: {args.style} | {args.width}×{args.height}px", file=sys.stderr)

    start = time.time()
    image_bytes = generate_image_api(
        prompt=prompt,
        model=config["model"],
        api_key=config["api_key"],
        api_base=config["api_base"],
        width=args.width,
        height=args.height,
        num_inference_steps=args.steps,
    )
    elapsed = time.time() - start

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_bytes)

    print(f"✓ Header image saved: {output_path} ({len(image_bytes) / 1024:.1f} KB, {elapsed:.1f}s)", file=sys.stderr)
    result = {
        "success": True,
        "output": str(output_path),
        "size_bytes": len(image_bytes),
        "width": args.width,
        "height": args.height,
        "model": config["model"],
        "style": args.style,
        "prompt": prompt,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
