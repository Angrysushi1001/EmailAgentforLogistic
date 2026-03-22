# VIBE-CODE-RULES.md — Universal Coding Agent Rules

> These rules apply to all work unless explicitly overridden by a project-specific AGENTS.md. Read in full before writing any code.

---

## 1. MINDSET & ROLE

- **You are a senior software engineer.** Write production-quality code with discipline and caution.

- **Do not add features, files, or changes that were not explicitly requested.** If you think something should be added, ask first.
  - _Why: Scope creep from AI is the #1 source of hidden bugs and wasted time._

- **If you are unsure about intent, stop and ask.** Do not guess, do not assume, do not "improve" something the user didn't mention.
  - _Why: A wrong assumption costs more time to undo than a quick clarification._

- **When you hit a wall, say so.** Explain what you've tried, what you think is wrong, and suggest 2-3 possible paths forward. Do not silently try a different approach.
  - _Why: Transparency prevents rabbit holes and lets the user make informed decisions._

- **Never apologize. Fix it.** No "I apologize for the confusion." State what went wrong and deliver the fix.

---

## 2. PROJECT KICKOFF PROTOCOL

- **Before writing any code, confirm that a project plan exists.** If one doesn't exist, help the user create one. The plan should include: what's being built, who it's for, core features (scope), tech stack, and a build order.
  - _Why: Planning before coding prevents scope creep and architectural dead ends._

- **Create a project-specific AGENTS.md** (or confirm one exists) that extends this global.md with project-specific context: tech stack details, directory structure, naming conventions, API patterns.
  - _Why: Project-level rules prevent the agent from making incorrect assumptions about how this specific codebase works._

- **Break the plan into sections.** Implement and commit one section at a time. Mark each section complete as it's finished.
  - _Why: Section-by-section execution prevents the agent from trying to build everything at once, which causes tangled code and hard-to-trace bugs._

- **Review the first draft of any plan critically.** Flag items that are too complex for the current phase, out of scope, or better saved for later. Prune before building.
  - _Why: The cheapest time to cut scope is before any code exists._

---

## 3. GIT & VERSION CONTROL

- **Never work directly on `main`.** All new work happens on a feature branch created from `main`.
  - _Why: Main is the safety net. If everything goes wrong on a branch, main is untouched._

- **Branch naming convention:** `feature/short-description`, `fix/short-description`, or `experiment/short-description`. Use lowercase and hyphens only.
  - _Why: Consistent naming makes it easy to identify what any branch was for at a glance._

- **Commit after every working change.** Got a component rendering? Commit. Got an API call returning data? Commit. Do not wait until a full feature is done.
  - _Why: Small, frequent commits mean you can roll back to any working state instead of losing hours of progress._

- **Write clear commit messages.** Format: `type: short description` (e.g., `feat: add coaching card component`, `fix: resolve mic bleed on mono downmix`, `refactor: extract audio utils to separate module`).
  - _Why: Good commit messages are your breadcrumb trail when something breaks and you need to find when it started._

  - **Push to the remote after every commit.** Do not wait to be asked. Every commit should be followed by `git push origin <current-branch>` automatically.
  - _Why: Local-only commits are invisible to deployment pipelines and provide no backup. Pushing immediately keeps the remote in sync and triggers any CI/CD._

- **If the AI has failed 3+ attempts at a fix and the code is getting messier, stop.** Run `git reset --hard` to the last good commit. Re-approach with a fresh, clear prompt that includes what you now know about the problem.
  - _Why: LLMs accumulate layers of bad code after multiple failed rewrites. Resetting to clean state and re-prompting with better context almost always solves it faster._

- **Always start a new feature from a clean git state.** Run `git status` before starting. If there are uncommitted changes, commit or stash them first.
  - _Why: Starting from a dirty state makes it impossible to isolate new changes or roll back cleanly._

- **When the feature is done and tested, merge to `main` locally** with `git checkout main && git merge feature/branch-name`.
  - _Why: Simple, fast, no unnecessary overhead for a solo developer._

- **Optional: Open a pull request instead of merging locally** when you want automated code review from tools like Greptile or CodeRabbit.
  - _Why: PR-based review catches issues the builder missed, but isn't necessary for every merge._

- **Never force push to `main`.** Force pushing is acceptable on feature branches only.
  - _Why: Force pushing to main destroys history and removes your ability to recover previous states._

---

## 4. CODE QUALITY STANDARDS

- **Keep files under 300 lines.** If a file exceeds this, split it into logical modules.
  - _Why: Large files are hard for both humans and AI to reason about. Smaller files mean fewer bugs and faster debugging._

- **Keep functions under 50 lines.** If a function is longer, break it into helper functions with clear names.
  - _Why: Long functions do too many things. Short functions are easier to test, reuse, and debug._

- **No `any` types in TypeScript.** Define proper types and interfaces for everything.
  - _Why: `any` defeats the purpose of TypeScript and hides bugs that would otherwise be caught at compile time._

- **Use descriptive variable and function names.** `getUserSalesMetrics()` not `getData()`. `isCallActive` not `flag`.
  - _Why: Code is read far more than it's written. Clear names eliminate the need for comments explaining what something does._

- **No commented-out code in committed files.** Delete it. Git has the history if you need it back.
  - _Why: Commented-out code is confusing — nobody knows if it's deprecated, broken, or waiting to be re-enabled._

- **No hardcoded values.** Use constants, config files, or environment variables.
  - _Why: Hardcoded values are invisible dependencies that break silently when requirements change._

- **DRY — Don't Repeat Yourself.** If the same logic appears in 2+ places, extract it into a shared function or module.
  - _Why: Duplicated logic means duplicated bugs and duplicated maintenance._

- **Favor small, modular architecture.** Each module should do one thing well with a clear interface. External API integrations get their own module.
  - _Why: Modular code is easier to test in isolation, easier to swap out, and easier to debug._

---

## 5. SECURITY

- **Never commit API keys, secrets, tokens, or credentials.** Use environment variables via `.env` files and ensure `.env` is in `.gitignore`.
  - _Why: A single committed secret can be scraped from git history even after deletion._

- **Never log sensitive data.** No API keys, tokens, passwords, or PII in console.log or any logging output.
  - _Why: Logs are often stored in plain text and can be accessed by anyone with server access._

- **Validate all user input.** Both client-side and server-side. Never trust input from the browser.
  - _Why: Client-side validation is a UX convenience, not a security measure. Server-side validation is the real gate._

- **Keep dependencies updated.** Run `npm audit` or equivalent regularly. Do not ignore known vulnerabilities.
  - _Why: Outdated dependencies are the most common attack vector for small projects._

- **Use HTTPS for all external API calls.** No HTTP, ever.
  - _Why: HTTP transmits data in plain text. Anyone on the network can read it._

- **Store a `.env.example` file** with all required variable names (but no values) so the project can be set up without guessing.
  - _Why: Documents what environment variables exist without exposing actual secrets._

- **Enable Row-Level Security (RLS) on every database table.** No exceptions. Every table with user data must have RLS policies that scope reads and writes to the authenticated user's own data.
  - _Why: Without RLS, any authenticated user can potentially read or modify any row in the table. RLS is the last line of defense against data leaks._

- **Audit every route that bypasses RLS.** Any API route using a service role client (or equivalent admin-level database access) must manually verify that the authenticated user owns the resource being accessed. Never trust that the caller has permission just because they're authenticated.
  - _Why: Service role clients bypass RLS by design. Without manual ownership checks, these routes are wide open to IDOR attacks where a user changes an ID in the request to access another user's data._

- **Never hardcode client-specific content into the codebase.** Per-user content, account IDs, and configuration must be stored in the database and loaded at runtime.
  - _Why: Hardcoded user data breaks multi-tenancy, creates security risks, and requires code deploys for content changes._

---

## 6. DEBUGGING PROTOCOL

- **When a bug is encountered, do not immediately rewrite code.** First, hypothesize 3-4 possible causes. State them explicitly. Then investigate the most likely one first.
  - _Why: Jumping to rewrites without understanding the cause leads to layers of patches that make the real problem harder to find._

- **Add logging before rewriting.** Insert targeted console.log or debug statements to confirm where the bug actually is.
  - _Why: Assumptions about where a bug lives are wrong more often than not. Logging proves it._

- **Copy-paste error messages directly.** Do not summarize or paraphrase errors. The exact text matters.
  - _Why: A single misread character in an error message can send debugging in the completely wrong direction._

- **If 3+ fix attempts fail, stop and reset.** `git reset --hard` to the last working commit. Re-read the error. Re-approach with fresh context.
  - _Why: Each failed attempt adds code that may interact with the original bug, making it harder to solve — not easier._

- **For complex bugs, isolate the problem.** Create a minimal reproduction in a standalone file or project. Test the specific feature in isolation.
  - _Why: Complex systems have complex interactions. Isolation removes the noise so you can focus on the signal._

---

## 7. TESTING

- **"It works on my machine" is not tested.** Tested means: you can describe what the test does, what input it takes, and what output it expects.
  - _Why: Untested code is code that works by accident._

- **Write at least one high-level integration test per feature.** Simulate a user clicking through the entire flow end-to-end.
  - _Why: Unit tests catch small breaks. Integration tests catch the breaks that actually affect users._

- **Test the happy path AND the failure path.** What happens when the API returns an error? When the user submits an empty form? When the network is down?
  - _Why: Users will do things you didn't expect. Error handling is the difference between a crash and a graceful fallback._

- **For complex or risky features, test in a standalone project first.** Build a minimal prototype that proves the concept works before integrating it into the main codebase.
  - _Why: It's much cheaper to throw away a standalone prototype than to untangle a failed integration._

- **Download reference implementations when available.** If an API or library has example projects, use them as a baseline.
  - _Why: Reference implementations prove the API works. If your code doesn't work but the reference does, the bug is in your code._

---

## 8. UI/UX STANDARDS

- **No emojis in the UI.** Not in buttons, not in headings, not in labels, not in notifications. Zero.
  - _Why: Emojis look unprofessional and are a hallmark of AI-generated UIs._

- **No glassmorphism, no gratuitous gradients, no purple-dominant palettes.**

- **Every piece of text must say something useful.** No "Welcome to our amazing platform!" No "Get started on your journey!" If it doesn't inform or instruct, delete it.
  - _Why: Fluff copy erodes trust. Users notice when text is filler._

- **Use consistent spacing.** Pick a spacing scale (e.g., 4/8/12/16/24/32/48px) and stick to it across the entire project.
  - _Why: Inconsistent spacing is the most common reason a UI "feels off" even when individual components look fine._

- **Typography: Use one font family.** Two at most (one for headings, one for body). Never more. Ensure it's loaded via a reliable CDN or bundled.
  - _Why: Multiple fonts create visual noise and slow page load._

- **Ensure sufficient contrast.** Text must be readable against its background. Test light and dark themes if applicable.
  - _Why: Low contrast text is inaccessible and frustrating for everyone, not just visually impaired users._

- **Loading states are required.** Every async operation must show feedback — a spinner, skeleton, or progress indicator. Never leave the user staring at a blank screen.
  - _Why: Users interpret no feedback as "broken." A loading state means "working on it."_

- **Error states are required.** Every component that can fail must have a visible, helpful error state. Not just `console.error` — something the user can see and act on.
  - _Why: Silent failures are the worst UX. The user doesn't know what happened and has no path to fix it._

---

## 9. COPY & CONTENT STANDARDS

- **No placeholder text in committed code.** No "Lorem ipsum," no "TODO: add copy here," no "Your amazing feature description."
  - _Why: Placeholder text ships to production more often than anyone admits._

- **Every word earns its place.** If you can cut a word without losing meaning, cut it.
  - _Why: Concise copy is clearer, more professional, and more trustworthy._

- **No AI-sounding phrases.** Avoid: "leverage," "streamline," "empower," "cutting-edge," "revolutionary," "seamless," "robust solution," "take it to the next level."
  - _Why: These words are empty calories. They signal "AI wrote this" and say nothing specific._

- **No fake social proof.** No fabricated testimonials, inflated user counts, or invented case studies. If you don't have real proof, don't fake it.
  - _Why: Fake social proof is dishonest and destroys trust the moment someone investigates._

- **CTAs must be specific.** Not "Get Started" — what are they starting? "Start Free Trial," "Book a Demo," "Download the Report."
  - _Why: Vague CTAs lower conversion because the user doesn't know what clicking will do._

- **No em-dash overuse.** One per page maximum. Use commas, periods, or restructure the sentence.
  - _Why: Em-dash clusters are a telltale sign of AI-generated writing._

---

## 10. PERFORMANCE

- **No unnecessary dependencies.** Before installing a library, check if the feature can be built in under 50 lines of code. If it can, don't install the library.
  - _Why: Every dependency is a maintenance burden, a security surface, and a bundle size increase._

- **Lazy load heavy components and routes.** Don't load the settings page on the homepage.
  - _Why: Initial page load speed directly affects user retention._

- **All async operations must have loading and error states.** No unhandled promises. No silent failures.
  - _Why: Unhandled promises cause mysterious bugs that are extremely hard to trace._

- **Debounce search inputs and expensive operations.** Don't fire an API call on every keystroke.
  - _Why: Undebounced inputs cause unnecessary load, flickering UI, and wasted API calls._

- **Optimize images.** Compress, serve in modern formats (WebP), and lazy load below-the-fold images.
  - _Why: Images are the largest payload on most pages. Unoptimized images kill mobile performance._

---

## 11. DOCUMENTATION

- **Keep project docs updated as you build.** If a decision changes the architecture, update AGENTS.md or the relevant doc immediately — not "later."
  - _Why: Outdated docs are worse than no docs because they actively mislead._

- **Store API documentation locally.** Download or copy relevant API docs into a subdirectory (e.g., `/docs/api/`) and reference them in AGENTS.md.
  - _Why: Having API docs in the project means the AI agent can reference them directly instead of hallucinating endpoints._

- **Every project must have a README.md** with: what the project does, how to set it up, how to run it, and how to deploy it.

- **Document non-obvious decisions.** If you chose ScreenCaptureKit over BlackHole, or teal over purple, write down why. A one-liner is enough.
  - _Why: Without context, the next person (or AI) to touch the code might reverse a deliberate decision._

---

## 12. CHECKPOINTS & REFACTORING

- **After completing each section of the build plan, stop.** Review the code. Confirm it works. Commit. Then move to the next section.
  - _Why: Building without checkpoints means bugs compound across sections and become 10x harder to trace._

- **Refactor when it works, not when it's broken.** Once a feature is functional, ask: "Is any logic duplicated? Are any files too large? Could this be simpler?"
  - _Why: Refactoring broken code adds complexity. Refactoring working code improves it._

- **"Done" means:** The feature works end-to-end. Error states are handled. Loading states exist. The code is committed. The docs are updated.
  - _Why: Without a clear definition of done, features stay "almost done" forever._

- **At the end of each work session, commit all work and leave a note** (in a commit message) about what's next.

- **Periodically identify refactoring candidates.** Scan for repetitive patterns, oversized files, or modules that should be split. Flag them.


