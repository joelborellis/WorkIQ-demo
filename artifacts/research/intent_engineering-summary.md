# Intent Engineering: The Third Discipline of AI

> **Source:** Transcript file provided by user (`transcripts/intent_engineering.txt`)
> **Summary Generated:** 2026-02-24

---

## Overview

This video introduces **intent engineering** — the practice of encoding organizational purpose (goals, values, trade-offs, and decision boundaries) into machine-readable, machine-actionable infrastructure — as the critical missing discipline in enterprise AI. Using Klarna's AI customer-service implosion as the central case study, the speaker argues that most AI failures aren't model failures; they're intent failures. The AI worked exactly as told, which was precisely the problem. As autonomous agents operate over longer and longer time horizons, this gap between what an agent can do and what an organization actually needs it to want has become the defining challenge of 2026.

---

## Key Themes

- **The three disciplines of AI:** Prompt engineering (how to talk to AI) → context engineering (what AI needs to know) → intent engineering (what AI needs to want).
- **AI succeeds at the wrong thing:** Technical optimization without organizational alignment is more dangerous than AI failure.
- **The intent gap is structural, not accidental:** It operates across three layers — context infrastructure, workflow toolkits, and organizational intent encoding.
- **The race has shifted:** In 2026, the competitive advantage isn't model quality; it's organizational intent architecture.
- **Agents cannot learn through osmosis:** Unlike human employees, agents need explicit, structured alignment before they start working.
- **Humans remain essential:** Intent engineering requires humans to encode values and maintain agentic systems — this is not a path to replacing people.

---

## Detailed Summary

### The Klarna Case Study: When AI Works Too Well

In early 2024, Klarna deployed an AI-powered customer service agent that handled 2.3 million conversations in its first month across 23 markets and 35 languages. Resolution times dropped from 11 minutes to 2 minutes, and the CEO projected $40 million in savings. By mid-2025, however, CEO Sebastian Siemiatkowski publicly admitted that cost had been the predominant evaluation factor — and the result was lower quality. Klarna began frantically rehiring human agents it had let go.

The standard reading of this story is that AI can't handle nuance. The more interesting reading is that the AI agent was extraordinarily good at its assigned goal — resolving tickets quickly — but that goal was wrong. **Klarna's actual organizational intent was to build lasting customer relationships that drive lifetime value in a competitive fintech market.** Those are profoundly different objectives requiring profoundly different judgment at the point of interaction.

A five-year human veteran at Klarna knew intuitively when to bend a policy, when to spend three extra minutes because a customer's tone signaled churn risk, and when efficiency was the right move versus generosity. That knowledge came from absorbed institutional context — the decisions managers make every day, the stories veterans tell new hires, the unwritten rules about which metrics leadership actually cares about. The AI agent had a prompt and had context. It did not have intent.

The speaker notes a darker possibility: the AI agent may have reflected Klarna's *real* values perfectly — cost savings first — and it was customer pushback that forced Klarna back toward its *stated* values. The $60 million in savings proved insufficient to cover reputational damage from becoming a public cautionary tale about AI.

### Naming the Disciplines

Naming creates shared understanding. The speaker defines three sequential disciplines:

1. **Prompt engineering** — Individual, synchronous, session-based. You sit in front of a chat window, craft an instruction, iterate the output. A personal skill with personal value. Produced a thousand "how to write the perfect prompt" blog posts, most of them mediocre.

2. **Context engineering** — Currently where the industry is focused. Defined by Anthropic (September 2025) as the shift from crafting isolated instructions to crafting the entire information state an AI system operates within. LangChain's Harrison Chase described it as "everything's context engineering." Building RAG pipelines, wiring MCP servers, structuring organizational knowledge. Necessary but not sufficient.

3. **Intent engineering** — The third discipline that almost nobody is building for yet. Context engineering tells agents what to know. **Intent engineering tells agents what to want.** It encodes organizational purpose — not as prose in a system prompt, but as structured, actionable parameters that shape autonomous decision-making. This is the layer that would have told Klarna's agent: "Yes, you can resolve this in 90 seconds, but this is a long-tenured customer showing frustration signals — spend the extra time, offer a specialist, the goal is retention."

### The Evidence for the Intent Gap

The speaker cites a striking contrast between investment and results:

- **Deloitte 2026:** 84% of companies have not redesigned jobs around AI capabilities; only 21% have a mature model for agent governance.
- **74% of companies globally** report they have yet to see tangible value from AI.
- **McKinsey:** 30% of AI pilots failed to achieve scaled impact.
- **Deloitte tech value survey:** 57% of respondents are putting 21–50% of their digital transformation budgets into AI automation; 20% investing over half (~$700M average for a $13B revenue company).
- **Gartner:** By 2028, 15% of day-to-day decisions will be made autonomously by agents — the speaker believes this may be a conservative estimate.

**Microsoft Copilot** is the most instructive large-scale example. Despite 85% of Fortune 500 companies adopting it, only 5% moved from a pilot to larger deployment, and only about 3% of the Microsoft 365 user base became paid users. Bloomberg reported Microsoft slashing internal sales targets after most salespeople missed their goals. Employees at companies with six-figure Copilot contracts quietly preferred ChatGPT or Claude.

The explanation isn't just UX or model quality. It's that deploying an AI tool across an organization without organizational intent alignment is like hiring 40,000 new employees and never telling them what the company does, what it values, or how to make decisions. You get AI usage metrics in a dashboard and almost no measurable impact on what the organization is actually trying to accomplish.

### The Three-Layer Framework

The speaker identifies an intent gap operating at three distinct layers:

**Layer 1 — Unified Context Infrastructure**
Every team building agents currently rolls its own context stack in isolation — one team pipes Slack data through a custom RAG pipeline, another manually exports Google Docs into a vector store, a third built an MCP server that connects to Salesforce but not Jira, and a fourth doesn't know the other three exist. This "shadow agents" problem mirrors the shadow IT crisis of the early cloud era, except agents don't just access data — they act on it.

The Model Context Protocol (MCP), introduced by Anthropic in late 2024 and donated to the Linux Foundation in December 2025, is the most promising standardization attempt. With nearly 100 million monthly SDK downloads and adoption from OpenAI, Google, Microsoft, and 50+ enterprise partners, it has become the de facto standard. But protocol adoption and organizational implementation are different things. The real questions are architectural and political: Which systems become agent-accessible? Who decides what context an agent can see across departments? How do you version organizational knowledge so agents aren't operating on stale data?

**Layer 2 — Coherent AI Worker Toolkit**
Currently, individuals are running incompatible personal AI stacks — one person uses Claude for research and ChatGPT for drafting, another uses Cursor for code, a third built a custom LangGraph chain. None of these workflows are transferable, measurable, or improvable by the organization.

The speaker distinguishes between **AI activity** (30% gains from bolting AI onto existing workflows) and **AI fluency** (300% gains from rethinking workflows around AI capabilities). Fluency doesn't scale through training alone — it scales through shared infrastructure. Whether any one person has Slack is irrelevant; whether an agent can search 50 people's Slack context plus their docs plus project plans plus customer data is what determines organizational-scale work versus individual-scale tasks. Deloitte's 2026 report found workforce access to sanctioned AI tools expanded 50% in a year — but access without organizational context infrastructure produces expensive toys, not leverage.

**Layer 3 — Intent Engineering Proper**
This layer almost certainly doesn't exist in your organization. OKRs were designed for humans — they assume human judgment about prioritization, trade-offs, values, and exceptions. They assume a manager can tell a direct report what matters this quarter and trust the report to interpret that through months of absorbed institutional context. Agents have none of that.

What's needed is a **cascade of specificity** most organizations have never had to produce:

- **Goal structures** that are agent-actionable, not just human-readable. Not "increase customer satisfaction" — but what signals indicate satisfaction in this context, what data sources contain those signals, what actions is the agent authorized to take, what trade-offs is it empowered to make, and where are the hard limits.
- **Delegation frameworks** that translate principles into decision boundaries. Amazon's "customer obsession" works for humans who interpret it through contextual judgment. An agent needs that decomposed: when customer request X conflicts with policy Y, here is the resolution hierarchy. This is encoded judgment — the kind a senior employee carries in her head after five years.
- **Feedback mechanisms** that close the loop. When an agent makes a decision, was it aligned with organizational intent? How do you know? Klarna's agent optimized for resolution speed because that was the measurable objective. The objectives that actually mattered — relationship quality, brand trust, customer lifetime value, the judgment about when to be efficient versus generous — lived only in the heads of the human agents who were fired.

### Why This Hasn't Been Built Yet

Three reasons:

1. **It's genuinely new.** Before agents could run autonomously over long time horizons, humans were the intent layer. Agents never needed to understand organizational intent because you were standing right there. Long-running agents (weeks, soon months) break that model.

2. **The two-cultures problem.** Executives understand organizational strategy but don't build agents. Engineers build agents but don't understand organizational strategy. MIT found AI investment is still viewed primarily as a tech challenge for the CIO rather than a business issue requiring cross-organizational leadership. CIOs can build infrastructure, but intent comes from the entire leadership team.

3. **It's genuinely hard.** Most organizations have never had to make their goals explicit and structured. Intent lives in slide decks, in half-read OKR documents, in the tacit knowledge of experienced employees who know what to do in ambiguous situations but have never been asked to document it.

---

## Core Arguments / Claims

1. **AI agent failures are mostly intent failures, not model failures.** The models work. Context pipelines are improving. What's missing is organizational infrastructure connecting AI capability to organizational purpose. *(Evidence: Klarna, Copilot, 74% no-value statistic)*

2. **Context engineering is necessary but not sufficient.** You can wire an agent to every data source in your organization and still get an agent that destroys value by optimizing for the wrong objective.

3. **The competitive advantage in 2026 is organizational intent architecture, not model subscriptions.** A mediocre model with extraordinary intent infrastructure will outperform a frontier model with fragmented, unaligned organizational knowledge every time.

4. **Agents require explicit alignment before deployment — they cannot absorb culture through osmosis.** Human employees align through 100 informal mechanisms over months. Agents need structured, machine-readable intent from day one.

5. **The shadow agents problem is the new shadow IT.** Unsanctioned agents accessing critical systems are a security and compliance risk that's already happening — organizational context infrastructure is the solution.

6. **The management innovation required is analogous to OKRs.** If OKRs let Intel align thousands of humans to shared objectives in the 1970s, intent engineering lets organizations align thousands of agents to those same objectives in 2026 — at speeds no human manager can supervise.

---

## Notable Quotes

> "Context engineering tells the agents what to know. Intent engineering tells agents what to want."

> "Context without intent is like a loaded weapon with no target. We've spent years building AI systems. 2026 is the year we learn to aim them."

> "The company with a mediocre model and extraordinary organizational intent infrastructure will outperform the company with a frontier model and fragmented, inaccessible, unaligned organizational knowledge every single time."

> "The age of humans just know is ending. Intent engineering is the discipline of making what humans know explicit, structured, and machine actionable."

> "The race is an intent race. Not who has the smartest AI in their systems, but who has built the organizational infrastructure that lets AI operate with the fullest, most accurate, most strategically correct understanding of what the organization is trying to accomplish."

---

## Actionable Takeaways

1. **Build composable, vendor-agnostic context infrastructure.** Adopt MCP as the protocol layer, but make deliberate organizational decisions about data governance, access controls, knowledge freshness, and semantic consistency across departments — no protocol makes these decisions for you.

2. **Create an organizational capability map for AI.** A living, shared document that classifies workflows as: agent-ready (full automation), agent-augmented (human in the loop), or human-only. Treat it as an operating system that evolves as agent capabilities improve, not a static Confluence page.

3. **Build goal translation infrastructure.** Convert human-readable OKRs and leadership principles into agent-actionable parameters: what signals to measure, what trade-offs to make autonomously, what decisions to escalate, and how to detect and correct alignment drift over time.

4. **Treat organizational intent architecture as a core strategic investment**, not an IT project. Involve the full leadership team — not just the CIO — because intent comes from those who decide what the organization values.

5. **Consider creating an "AI workflow architect" role** — someone sitting between engineering, operations, and strategy who owns the organizational capability map and governs how agent capabilities connect to organizational goals.

6. **Maintain humans in the loop.** Agents need humans to encode intent and to maintain agentic systems at scale. Intent engineering is not a path to removing people; it is a discipline that makes human-AI collaboration actually work.

7. **Don't deploy agents without intent layers**, especially long-running ones. An agent operating for weeks or months without encoded organizational values will optimize for whatever is measurable — which is rarely what matters most.

---

## What Was NOT Covered / Limitations

- The video does not provide specific tooling recommendations beyond MCP and Google's Agent Development Kit as early examples.
- The "goal translation infrastructure" concept is described in principle but not with concrete implementation templates — the speaker acknowledges this is largely white space in the industry.
- No discussion of how intent engineering applies to smaller organizations or non-enterprise contexts.

---

## Glossary / Key Terms

- **Intent engineering** — The discipline of encoding organizational purpose (goals, values, trade-offs, decision boundaries) into structured, machine-actionable infrastructure that governs how autonomous agents make decisions.
- **Context engineering** — Crafting the entire information state an AI system operates within, including RAG pipelines, MCP servers, and structured organizational knowledge.
- **MCP (Model Context Protocol)** — A standardized protocol introduced by Anthropic (late 2024), donated to the Linux Foundation (December 2025), for enabling agents to access organizational systems and data. Approaching ~100M monthly SDK downloads.
- **Delegation framework** — A structured decomposition of organizational principles into agent decision logic: what to do when competing priorities conflict, and where the hard limits are.
- **Shadow agents** — Unsanctioned AI agents built and deployed by individual teams without organizational governance — the AI-era equivalent of shadow IT.
- **AI fluency vs. AI activity** — AI activity = 30% gains from bolting AI onto existing workflows. AI fluency = 300% gains from rethinking workflows around AI capabilities; scales through shared infrastructure, not just individual training.
- **Intent gap** — The structural disconnect between AI capability and organizational purpose, operating across context infrastructure, workflow toolkits, and goal alignment layers.
