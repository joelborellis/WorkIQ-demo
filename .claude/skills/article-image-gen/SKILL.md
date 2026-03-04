---
name: article-image-gen
description: >
  Expert image generation skill for learning and informational articles. Use this skill
  whenever the user wants to create images, figures, diagrams, or header artwork for
  articles, blog posts, documentation, or educational content. Always trigger this skill
  when the user mentions: generating images from markdown tables, creating article header
  images, visualizing article content, converting table data to PNG, creating blog visuals,
  or any request to produce PNG images from markdown text. This skill handles three
  distinct superpowers: (1) rendering markdown tables as clean publication-ready PNG images,
  (2) generating compelling header/banner images inspired by article titles, and
  (3) reading full markdown articles and producing contextually relevant inline images.
  Trigger even when the user only mentions "article image", "table image", "header image",
  or pastes a markdown table and asks to visualize it.
---

# Article Image Generation Skill

Expert at generating publication-quality PNG images for learning and informational articles.
Images are generated using the **nano-banana model** via the configured image generation API.

---

## Three Superpowers

### 1. Markdown Table → PNG
Convert any markdown table into a clean, professionally styled PNG image suitable for
publication. Read `scripts/table_to_png.py` for implementation.

**When to use:** User shares a markdown table and wants it as an image, or an article
contains data tables that should be visualized.

**Workflow:**
1. Extract the markdown table from context or user input
2. Run `python scripts/table_to_png.py` with the table content
3. The script outputs a styled PNG with proper headers, alternating rows, and branding

**Key options:**
- `--title "My Table Title"` — adds a title above the table
- `--theme dark|light|blue` — color theme (default: light)
- `--output filename.png` — output file name

---

### 2. Article Title → Header Image
Generate an eye-catching header/banner image by feeding an article title to the
nano-banana image model. This produces wide-format (1200×630 or 1920×1080) imagery
suitable for blog post headers, Open Graph cards, and article thumbnails.

Read `scripts/generate_header.py` for implementation.

**When to use:** User wants a banner/hero image for their article, blog post, or
documentation page.

**Workflow:**
1. Extract or ask for the article title (and optional subtitle/theme keywords)
2. Build a rich prompt using the title and genre context (educational, technical, etc.)
3. Run `python scripts/generate_header.py`
4. Output: a 1200×630 PNG ready for publication

**Key options:**
- `--title "Article Title"` — the article title (required)
- `--style photorealistic|illustrative|abstract|minimal` — visual style
- `--theme "keywords"` — extra context for the model (e.g., "data science, blue palette")
- `--width 1200 --height 630` — dimensions (defaults to Open Graph standard)
- `--output header.png`

---

### 3. Full Markdown Article → Contextual Images
Parse an entire markdown article and generate contextually relevant inline images for
key sections, concepts, or data points. This is the most powerful mode — it reads the
full article structure and produces a set of images that complement the narrative.

Read `scripts/article_to_images.py` for implementation.

**When to use:** User shares a full markdown article and wants images generated for it,
or says "generate images for this article" / "illustrate this piece."

**Workflow:**
1. Read the full markdown file
2. The script identifies image-worthy sections: section headers, callout blocks,
   data mentions, process steps, and explicit `![alt](generate)` placeholders
3. For each candidate, it generates a targeted prompt and calls the image model
4. Outputs a set of numbered PNGs + a manifest JSON mapping image paths to markdown positions
5. Claude then weaves the image references back into the markdown

**Key options:**
- `--input article.md` — path to the markdown file
- `--max-images 8` — cap on images generated (default: 6)
- `--style consistent` — keep a visual style across all images
- `--output-dir images/` — where to save PNGs

---

## Configuration

All scripts read from `~/.article-image-gen/config.json` or the environment:

```json
{
  "model": "nano-banana",
  "api_key": "YOUR_API_KEY",
  "api_base": "https://api.your-provider.com/v1",
  "default_style": "illustrative",
  "default_theme": "light"
}
```

Or set environment variables:
```bash
export IMAGE_GEN_MODEL="nano-banana"
export IMAGE_GEN_API_KEY="your-key"
export IMAGE_GEN_API_BASE="https://api.your-provider.com/v1"
```

See `references/api-setup.md` for provider-specific setup instructions.

---

## Output Standards

All generated images follow these publication standards:
- **Format:** PNG (lossless, wide browser support)
- **Tables:** 1000px wide minimum, 72–144 DPI, clean typography
- **Headers:** 1200×630px (Open Graph standard) or 1920×1080 (widescreen)
- **Inline images:** 800×450px (16:9) or 800×600px (4:3) depending on context
- **Color profiles:** sRGB for web publication

---

## Prompt Engineering Notes

When building prompts for the nano-banana model, follow these patterns for best results:

**Tables:** Do not send tables to the image model — always render them with the
`table_to_png.py` script using matplotlib/pillow (deterministic, professional, fast).

**Header images:** Use this prompt structure:
```
"Header image for an article titled '{title}'. Style: {style}. 
Educational/informational context. Clean composition, wide format (16:9).
Avoid text in image. Color palette: {palette}. High quality, publication ready."
```

**Inline/contextual images:** Use this structure:
```
"Illustration for article section about '{topic}'. Context: {surrounding_text_excerpt}.
Style: {consistent_style}. Informational, clear, no text overlay. PNG format."
```

---

## Quick Reference

| Task | Script | Key Flag |
|------|--------|----------|
| Table → PNG | `table_to_png.py` | `--table`, `--title` |
| Title → Header | `generate_header.py` | `--title`, `--style` |
| Full article | `article_to_images.py` | `--input`, `--max-images` |
| Test setup | `test_setup.py` | — |

---

## Reading Markdown Tables

When extracting markdown tables from user input, look for this pattern:
```
| Col1 | Col2 | Col3 |
|------|------|------|
| val  | val  | val  |
```
Pass the raw table string to `table_to_png.py` via stdin or `--table-file`.

For complex tables with merged cells or footnotes, see `references/table-edge-cases.md`.
