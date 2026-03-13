Before writing any code, do the following reconnaissance steps in order:

1. Read ./frontend — understand the full auth flow (MSAL config, token acquisition, how the Bearer token is attached to API requests), the routing setup, all env vars in .env or .env.example, and the vite.config.ts proxy rules.

2. Read ./backend — find the POST /api/v1/copilot_chat route handler and understand: the exact request body shape, the exact response shape (JSON or streaming/SSE), and how auth is verified (Bearer token header, cookie, etc.). Also check CORS settings and any required request headers beyond Authorization.

Once you understand both, scaffold and build a complete React + TypeScript + Vite chat application in ./frontend-v2 with the following requirements:

AUTH
- Replicate the exact same auth flow from ./frontend — same MSAL config pattern, same token acquisition, same Authorization header attachment. Do not invent a new auth approach.
- Include a login page that gates the chat UI. Redirect unauthenticated users to login.
- Create a .env.example in ./frontend-v2 with all required env vars documented, matching what ./frontend needs.

CHAT
- Single multi-turn conversation with message history maintained in React state.
- All messages sent via POST /api/v1/copilot_chat using the exact request shape from the backend.
- If the backend streams (SSE or chunked), implement streaming so tokens render as they arrive.
- Show a typing/loading indicator while waiting for a response.
- Auto-scroll to the latest message.
- Send on Enter (Shift+Enter for newline), plus a send button.

DESIGN
You are an expert frontend designer. Commit to a bold, distinctive aesthetic direction before writing a single line of CSS. Pick a specific tone — refined dark mode, warm editorial, stark brutalist, soft luxury, etc. — and execute it with full intentionality. Avoid all generic AI aesthetics: no purple gradients, no Inter/Roboto, no cookie-cutter chat bubble layouts.

Apply these principles:
- Typography: pair a characterful display font (from Google Fonts) with a refined body font. The font pairing should feel considered and unexpected.
- Color: use CSS custom properties throughout. Dominant background + one sharp accent color. No timid multi-color palettes.
- Motion: staggered page load animation, smooth message entry, subtle hover states. CSS-only where possible.
- Layout: responsive shell — sidebar or header on desktop collapses to a clean mobile layout. The chat input must always be visible and thumb-accessible on mobile.
- Background: add depth via gradient mesh, noise texture, or geometric pattern — not a flat solid color.

RESPONSIVE
- Mobile-first. Test the layout mentally at 375px width.
- Input bar pinned to bottom on mobile.
- Font sizes, spacing, and tap targets must be comfortable on a small screen.

STRUCTURE
Create a clean component breakdown:
- AuthProvider wrapping the app
- LoginPage
- AppShell (responsive layout wrapper)
- ChatWindow (scrollable message list)
- MessageBubble (user vs assistant variants)
- ChatInput (textarea + send)
- TypingIndicator
- api/chat.ts (typed API client for the one route)
- auth/useAuth.ts (token hook)

After scaffolding, run npm install and verify the dev server starts. Fix any TypeScript errors before finishing.