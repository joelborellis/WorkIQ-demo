# Markdown Table Edge Cases

This reference covers non-standard markdown tables and how to handle them.

---

## Aligned Columns

Markdown supports alignment hints in the separator row:
```
| Left | Center | Right |
|:-----|:------:|------:|
| a    |   b    |     c |
```
The `table_to_png.py` script detects `:` alignment markers and applies left/center/right
text alignment to the corresponding columns automatically.

## Tables with Long Cell Content

If cells contain very long text, the script wraps text within the cell. Use `--font-size 10`
to fit more content, or `--min-width 1400` to expand the canvas.

## Tables Without Headers

Some markdown tables lack a clear header row. If the separator row is missing, the script
treats the first row as the header. If you want to override this, use `--no-header` flag
to render all rows as data rows with auto-generated column letters (A, B, C...).

## Tables with Code in Cells

Backtick code in cells renders as monospace text. The parser strips backtick markers but
preserves the content.

## Multi-Line Cell Content

Standard markdown tables don't support multi-line cells. If you need multi-line content,
use `<br>` as a delimiter — the script converts `<br>` to newlines within cells.

```
| Name | Description |
|------|-------------|
| Foo  | Line one<br>Line two |
```

## Nested Tables

Not supported in standard markdown. Extract them as separate tables and generate
individual PNGs for each.

## Very Wide Tables (10+ columns)

For tables with many columns, use:
- `--font-size 9` to reduce font size
- `--min-width 1600` to expand width
- Or consider splitting into two tables thematically

## Empty Cells

Empty cells `| |` are preserved as blank. The alternating row shading still applies.

## Numeric Columns

The script auto-detects numeric-looking columns and right-aligns them for readability.
Values are not reformatted — they display exactly as written in the markdown.
