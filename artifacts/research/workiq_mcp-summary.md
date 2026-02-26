# Microsoft Work IQ: A Plain-English Search Tool for Your Entire Work Life

> **Source:** Transcript file provided by user (`transcripts/workiq_mcp.txt`)
> **Summary Generated:** 2026-02-25

---

## Overview

This video is a beginner-friendly product explainer for Microsoft's new **Work IQ** tool — an AI-powered search assistant that connects to a user's personal Microsoft 365 data (emails, files, calendars, Teams chats) and lets them find information using plain English questions. The pitch is simple: instead of hunting across a dozen apps for a buried file or forgotten conversation, you just ask. The video covers what Work IQ is, how it works at a high level, what it can do, and the key setup steps required to get started.

> **Note:** This video covers Work IQ as a user-facing product. For the strategic investment thesis behind Work IQ as a moat-building capability, see `microsoft_moat-summary.md`.

---

## Key Themes

- **The scattered data problem** — Modern work is spread across emails, documents, calendars, and chats; finding specific information when you need it wastes significant time and momentum.
- **Context over search** — Work IQ isn't just a file finder; it retrieves the meaning and context buried inside your data, not just the files themselves.
- **Natural language as the interface** — No need for exact file names, folder paths, or query syntax; you ask the way you'd talk to a knowledgeable colleague.
- **Privacy by design** — Work IQ only searches your personal Microsoft 365 data, not your organization's entire data pool.
- **Early-stage, evolving product** — Currently in public preview; expected to gain capabilities over time.

---

## Detailed Summary

### The Problem: The Digital Haystack

Work today is fragmented across dozens of applications — email, documents, calendars, chat, shared drives. Finding one specific piece of information (a manager's comment in an old email thread, a slide deck from three months ago, who's responsible for a given project) often requires an inefficient search across multiple tools. The speaker uses the relatable experience of a frantic morning search for a single file as the emotional hook — it's a problem that derails focus and kills momentum.

### What Work IQ Is

Work IQ is an AI tool that securely connects to a user's personal Microsoft 365 data and lets them query it in plain English. The key shift is from *search* (finding files by name or keyword) to *context retrieval* (finding the meaning, decisions, and details embedded within those files and conversations). The example given: asking "What did my manager say about the project deadline?" and getting a direct answer pulled from a specific buried email — not just a link to the email itself.

### How It Works

The process is intentionally simple:

1. **Ask** — Type a question in plain English (no special syntax or commands required).
2. **Search** — Work IQ securely scans your personal Microsoft 365 universe only.
3. **Answer** — It returns the relevant information with context, not just a list of files.

The speaker emphasizes privacy: the search is limited to your own data, not organization-wide.

### What It Can Do

Work IQ can handle a broad range of everyday workplace queries:

- Find specific emails from a particular colleague.
- Check your calendar for upcoming meetings or deadlines.
- Locate recent PowerPoint presentations you've been working on.
- Summarize a chaotic Teams channel thread.
- Identify who is working on a specific project.

The unifying capability is connecting dots *across* the entire Microsoft 365 workspace rather than searching within any single app.

### How to Get Started

Two important requirements before use:

1. **Tenant administrator consent** — An IT admin must grant Work IQ permission to access the organization's data before any individual user can use it. This is the critical blocker for most people and requires IT department involvement.
2. **Developer/technical setup** — For technical users, Work IQ installs as a plugin for the **GitHub Copilot command line tool** with a few simple commands.

Once authorized, Work IQ runs on **Windows, Linux, and macOS**.

The speaker notes Work IQ is currently in **public preview**, meaning it is actively being developed and users should expect the feature set to expand.

---

## Core Arguments / Claims

1. **Work IQ solves a universal workplace productivity problem.** Information fragmentation across apps is a daily pain point for knowledge workers; a natural language search layer across all of it directly addresses lost time and focus.

2. **The real value is context, not file retrieval.** Finding what someone *said* about a deadline is more useful than finding the *file* where they said it — Work IQ targets the former.

3. **Natural language removes the barrier to effective search.** Most enterprise search tools require users to know where to look or what to type; Work IQ removes both requirements.

4. **Privacy is a first-class design constraint.** Limiting search to personal data (not org-wide) makes the tool more trustworthy and easier to get approved through IT governance.

---

## Notable Quotes

> "This isn't just about finding files anymore. It's about finding context."

> "If you could ask your entire history of work anything, what would be the very first thing you'd ask?"

---

## Actionable Takeaways

1. **Contact your IT department first.** Work IQ requires tenant administrator consent before any individual can use it — this is the necessary first step for most users.

2. **If you're a developer or technical user**, set it up as a GitHub Copilot CLI plugin once IT consent is granted; the speaker describes the install as quick and straightforward.

3. **Think in questions, not file names.** The most effective use of Work IQ is asking natural questions ("What was decided about X?", "Who owns Y project?") rather than trying to remember where something was saved.

4. **Set expectations appropriately** — Work IQ is in public preview and will improve; current limitations should be weighed against the tool's future trajectory.

---

## Glossary / Key Terms

- **Work IQ** — Microsoft's AI-powered natural language search tool for personal Microsoft 365 data (email, documents, calendars, Teams); currently in public preview.
- **Public preview** — A product release stage where the tool is available but still actively being developed; features and stability are expected to improve before general availability.
- **Tenant administrator** — The IT administrator responsible for an organization's Microsoft 365 environment; must grant consent for Work IQ to access organizational data.
- **GitHub Copilot CLI** — The GitHub Copilot command-line interface tool, used here as the installation host for Work IQ's developer plugin.
- **Context retrieval** — Fetching the meaning, decisions, or details embedded within documents and conversations, as opposed to simply locating and returning a file.
