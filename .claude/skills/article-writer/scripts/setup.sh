#!/bin/bash
# setup.sh — Install dependencies for the article-writer skill
# Run this once: bash .claude/skills/article-writer/scripts/setup.sh

set -e

echo "🔧 Setting up article-writer skill dependencies..."
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

echo "📦 Installing Python packages..."
pip3 install youtube-transcript-api yt-dlp anthropic --quiet

echo ""
echo "✅ Dependencies installed:"
echo "   - youtube-transcript-api (fetch YouTube transcripts)"
echo "   - yt-dlp (fetch video metadata)"
echo "   - anthropic (AI summary generation)"
echo ""

# Check for Anthropic API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY is not set."
    echo "   AI summaries will be skipped when fetching transcripts."
    echo "   Add to your .env or shell profile:"
    echo "   export ANTHROPIC_API_KEY=your-key-here"
else
    echo "✅ ANTHROPIC_API_KEY is set — AI summaries will be enabled."
fi

echo ""
echo "🗂️  Creating artifacts directory structure..."
mkdir -p artifacts/chats artifacts/research artifacts/drafts
echo "   artifacts/chats/    ← drop AI chat exports here"
echo "   artifacts/research/ ← research notes and YouTube summaries go here"
echo "   artifacts/drafts/   ← article drafts auto-saved here"
echo ""
echo "🎉 Setup complete! You're ready to start writing."
