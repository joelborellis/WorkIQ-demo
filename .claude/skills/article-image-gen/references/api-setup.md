# API Setup Guide — article-image-gen

This skill uses the **nano-banana** image generation model. The scripts are designed
to be provider-agnostic — you configure the API base URL and key, and adjust the
payload/response parsing in `generate_header.py` and `article_to_images.py` to match
your specific provider's API format.

---

## Configuration

### Option A: Config File (recommended)

Create `~/.article-image-gen/config.json`:

```json
{
  "model": "nano-banana",
  "api_key": "YOUR_API_KEY",
  "api_base": "https://api.your-provider.com/v1",
  "default_style": "illustrative"
}
```

### Option B: Environment Variables

```bash
export IMAGE_GEN_MODEL="nano-banana"
export IMAGE_GEN_API_KEY="your-key-here"
export IMAGE_GEN_API_BASE="https://api.your-provider.com/v1"
```

---

## Provider-Specific Notes

### Adapting the Payload

In `generate_header.py` and `article_to_images.py`, look for the `generate_image_api`
function and the `# ── Payload` comment block. Adjust the `payload` dict and response
parsing to match your provider's API spec.

### Common API Patterns

**OpenAI DALL-E style:**
```python
endpoint = f"{api_base}/images/generations"
payload = {
    "model": model,           # e.g., "dall-e-3"
    "prompt": prompt,
    "size": f"{width}x{height}",
    "response_format": "b64_json",
    "n": 1,
}
# Response: data[0]["b64_json"]
```

**Stability AI:**
```python
endpoint = f"{api_base}/generation/{model}/text-to-image"
payload = {
    "text_prompts": [{"text": prompt, "weight": 1.0}],
    "width": width,
    "height": height,
    "steps": 30,
    "samples": 1,
}
# Response: artifacts[0]["base64"]
```

**Replicate:**
```python
endpoint = f"{api_base}/predictions"
payload = {
    "version": model_version_hash,
    "input": {
        "prompt": prompt,
        "width": width,
        "height": height,
    }
}
# Response: poll output URL until complete
```

**Hugging Face Inference API:**
```python
endpoint = f"https://api-inference.huggingface.co/models/{model}"
headers["Accept"] = "image/png"
# Response: raw image bytes
```

---

## Supported Image Dimensions

The scripts default to these sizes — adjust `--width` and `--height` as needed:

| Use Case | Width | Height | Flag |
|----------|-------|--------|------|
| Open Graph / Blog Header | 1200 | 630 | `--width 1200 --height 630` |
| Widescreen Header | 1920 | 1080 | `--width 1920 --height 1080` |
| Inline Article Image (16:9) | 800 | 450 | `--width 800 --height 450` |
| Inline Article Image (4:3) | 800 | 600 | `--width 800 --height 600` |
| Square Thumbnail | 600 | 600 | `--width 600 --height 600` |

---

## Troubleshooting

**"API error 401"** — Check your API key is correct and not expired.

**"API error 422"** — The payload format doesn't match what the provider expects.
Edit the `payload` dict in `generate_image_api()`.

**"Cannot parse API response"** — The response parsing section needs to match your
provider's response format. Print `response.json()` to inspect and update accordingly.

**Table images have garbled characters** — Install a better font:
```bash
sudo apt-get install fonts-liberation  # Linux
brew install font-liberation           # macOS
```
Then set `plt.rcParams["font.family"] = "Liberation Sans"` in `table_to_png.py`.
