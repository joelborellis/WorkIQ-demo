#!/usr/bin/env python3
"""
fetch_transcript.py — Fetch a YouTube video transcript and summarize it into a markdown file.

Usage:
    python3 fetch_transcript.py "https://youtube.com/watch?v=..." --output artifacts/research/
    python3 fetch_transcript.py "https://youtube.com/watch?v=..." --output artifacts/research/ --no-summary
    python3 fetch_transcript.py "https://youtube.com/watch?v=..." --title "My Custom Title"

Requirements:
    pip install youtube-transcript-api yt-dlp

The script will:
1. Extract the video ID from the URL
2. Fetch the transcript (auto-generated or manual captions)
3. Fetch video metadata (title, channel, date)
4. Write a markdown file to the output directory with:
   - Video metadata
   - Cleaned transcript
   - Optional AI summary (if ANTHROPIC_API_KEY is set)
"""

import argparse
import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|youtu\.be/|/embed/|/v/|/e/|watch\?v=|&v=)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:60]  # cap length


def fetch_metadata(video_id: str) -> dict:
    """Fetch video metadata using yt-dlp."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "title": data.get("title", "Unknown Title"),
                "channel": data.get("uploader", "Unknown Channel"),
                "upload_date": data.get("upload_date", ""),
                "duration": data.get("duration_string", ""),
                "description": (data.get("description", "") or "")[:500],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
    except Exception as e:
        print(f"[warn] Could not fetch metadata via yt-dlp: {e}", file=sys.stderr)

    return {
        "title": f"YouTube Video ({video_id})",
        "channel": "Unknown",
        "upload_date": "",
        "duration": "",
        "description": "",
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def fetch_transcript(video_id: str) -> list[dict]:
    """Fetch transcript using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except ImportError:
        print("[error] youtube-transcript-api not installed.", file=sys.stderr)
        print("  Run: pip install youtube-transcript-api", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Try getting any available transcript
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Try auto-generated first, then manual
            for t in transcript_list:
                try:
                    return t.fetch()
                except Exception:
                    continue
        except Exception:
            pass
        print(f"[error] Could not fetch transcript: {e}", file=sys.stderr)
        sys.exit(1)


def clean_transcript_text(transcript: list[dict]) -> str:
    """Convert transcript entries to clean paragraphs."""
    texts = []
    current_chunk = []
    current_time = 0

    for entry in transcript:
        text = entry["text"].strip()
        # Remove common auto-caption artifacts
        text = re.sub(r"\[.*?\]", "", text).strip()  # [Music], [Applause] etc.
        if not text:
            continue

        start = entry.get("start", 0)

        # Start a new paragraph every ~2 minutes of content
        if start - current_time > 120 and current_chunk:
            texts.append(" ".join(current_chunk))
            current_chunk = []
            current_time = start

        current_chunk.append(text)

    if current_chunk:
        texts.append(" ".join(current_chunk))

    return "\n\n".join(texts)


def summarize_with_claude(title: str, transcript_text: str) -> str:
    """Generate a structured summary using the Anthropic API if key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are helping a tech writer extract research notes from a YouTube video transcript.

Video title: {title}

Transcript:
{transcript_text[:8000]}

Please produce a structured research summary with these sections:

## Key Points
(3-7 bullet points of the most important ideas)

## Core Concepts Explained
(Brief definitions or explanations of any technical concepts introduced)

## Interesting Quotes / Statements
(2-4 direct quotes or paraphrased statements worth referencing)

## Potential Article Angles
(2-3 ideas for how this content could be used in an article)

## Gaps / Questions Raised
(Things the video didn't explain or questions it raised)

Be concise and focus on what's useful for writing a tech article."""

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    except ImportError:
        print("[warn] anthropic package not installed — skipping AI summary.", file=sys.stderr)
        print("  Run: pip install anthropic", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[warn] Could not generate AI summary: {e}", file=sys.stderr)
        return ""


def format_duration(upload_date: str) -> str:
    """Format YYYYMMDD date string."""
    if len(upload_date) == 8:
        try:
            d = datetime.strptime(upload_date, "%Y%m%d")
            return d.strftime("%B %d, %Y")
        except Exception:
            pass
    return upload_date


def build_markdown(metadata: dict, transcript_text: str, summary: str) -> str:
    """Build the final markdown file content."""
    date_fetched = datetime.now().strftime("%Y-%m-%d")
    upload_date = format_duration(metadata.get("upload_date", ""))

    lines = [
        f"# {metadata['title']}",
        "",
        f"> **Source:** YouTube — [{metadata['channel']}]({metadata['url']})  ",
        f"> **Published:** {upload_date}  " if upload_date else "",
        f"> **Duration:** {metadata['duration']}  " if metadata.get("duration") else "",
        f"> **Fetched:** {date_fetched}",
        "",
    ]

    if metadata.get("description"):
        lines += [
            "## Video Description",
            "",
            metadata["description"],
            "",
        ]

    if summary:
        lines += [
            "## Research Summary (AI-Generated)",
            "",
            summary,
            "",
            "---",
            "",
        ]

    lines += [
        "## Full Transcript",
        "",
        transcript_text,
    ]

    return "\n".join(line for line in lines if line is not None)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a YouTube transcript and save it as a research markdown file."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output",
        default="artifacts/research",
        help="Output directory (default: artifacts/research)",
    )
    parser.add_argument("--title", help="Override the video title for the filename")
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip AI summary generation (transcript only)",
    )

    args = parser.parse_args()

    # Validate output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Extracting video ID from: {args.url}")
    video_id = extract_video_id(args.url)
    print(f"      Video ID: {video_id}")

    print("[2/4] Fetching video metadata...")
    metadata = fetch_metadata(video_id)
    print(f"      Title: {metadata['title']}")
    print(f"      Channel: {metadata['channel']}")

    print("[3/4] Fetching transcript...")
    transcript = fetch_transcript(video_id)
    transcript_text = clean_transcript_text(transcript)
    word_count = len(transcript_text.split())
    print(f"      Fetched {len(transcript)} segments (~{word_count} words)")

    summary = ""
    if not args.no_summary:
        print("[4/4] Generating research summary with Claude...")
        summary = summarize_with_claude(metadata["title"], transcript_text)
        if summary:
            print("      Summary generated.")
        else:
            print("      Skipped (no API key or anthropic package not installed).")
    else:
        print("[4/4] Skipping AI summary (--no-summary flag set)")

    # Build filename
    title_for_slug = args.title or metadata["title"]
    slug = slugify(title_for_slug)
    filename = f"yt-{slug}.md"
    output_path = output_dir / filename

    # Write file
    content = build_markdown(metadata, transcript_text, summary)
    output_path.write_text(content, encoding="utf-8")

    print(f"\n✅ Saved to: {output_path}")
    print(f"   Words: {word_count:,}")
    if summary:
        print("   Includes: AI research summary")


if __name__ == "__main__":
    main()
