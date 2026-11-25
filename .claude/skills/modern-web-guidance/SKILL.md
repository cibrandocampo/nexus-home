---
name: modern-web-guidance
description: |
  Modern web development best practices (Google Chrome team), read from local guides. MANDATORY: consult FIRST for all HTML/CSS and clientside JS tasks. Do NOT skip — web APIs evolve rapidly and training weights contain obsolete patterns.
  Trigger immediately for: modals/dialogs/popovers, tables, dark mode, anchor positioning, container queries, view transitions, scroll-driven animations, parallax/reveals, forms, validation, autofill, accessibility, custom selects, scrollbars, CWV (LCP, INP, CLS), content-visibility, fetch priority, image optimization, security, passkeys, HTML sanitization, web components, dates/timezones, built-in AI, WebAssembly, standard HTML/CSS/DOM in frameworks, etc.
  DO NOT trigger for: backend (SQL, ORMs, API routes), infra/scripts (CI/CD, Docker, Actions, Python/Go, Git), or tooling/trivial (Vite, tsconfig, ESLint, tests, copy/renames, 3P docs), etc.
---

# Modern Web Guidance

Search and retrieve standardized modern web best practices at the **start** of implementing or updating any web UI, CSS layout/animation, or client-side JS logic (dates/timezones, sanitization, performance, accessibility, UX fixes) before writing ad-hoc solutions or adding dependencies.

## Primary Workflow

> **Project adaptation**: upstream runs `npx -y modern-web-guidance@latest` (a CLI downloaded from npm at
> run time). This project does not run third-party code on the host or fetch it at run time, so the
> same guides are vendored in `guides/` (see `UPSTREAM.md`) and are searched and read directly.

### Step 1. Search Use Cases

Pick a **2–5 word action-oriented English query** for a **single web platform capability or UI pattern**:
- **Keep queries focused and generic**: Describe the user-visible capability (`<verb> + <UI/platform object>`, optionally paired with the target HTML/CSS/JS feature name if known). Omit framework/library names (`React`, `Vue`, `Tailwind`, etc.) and app/domain nouns. Split multi-feature tasks into separate searches.
- **Name implied UI primitives**: translate the domain intent into the implied UI component or platform mechanism (e.g. `confirmation modal dialog` rather than `confirm destructive action`, `date picker input` rather than `pick a date`).

Then search the index and, if needed, the guides themselves (paths relative to this skill's directory):

```sh
grep -iE "dialog|modal" guides/INDEX.md          # titles and first sentences, one line per guide
grep -ril "light dismiss" guides/ | sort          # full-text, when the index is not enough
```

- **Match found**: go to Step 2 with the matching `<category>/<id>`.
- **Weak or empty results**: rephrase **once** with the concrete HTML/CSS/UI component noun or synonym (`dialog`, `modal`, `popover`, `table`, `form`) before reading the whole `guides/INDEX.md` (or use the whole index once for broad UI audits).
- **Topic not covered**: if nothing matches after rephrasing, proceed without reading unrelated guides.

### Step 2. Retrieve Best Practices

Read the full guide file(s) with the file-reading tool: `guides/<category>/<id>.md` — both the specific use-case guides that match the task and any broader discipline guide that applies (`html/…`, `css/…`, `js/…`, `forms/…`, `accessibility/accessibility`, `visual-design/…`, `performance/…`, `security/…`).

### Step 3. Verify Guidance Compliance

When generating or modifying code, cross-check the implementation against the retrieved guide before concluding:
- **Applicable Guidance & Fallbacks**: Ensure the relevant modern patterns and necessary fallback strategies from the guide are correctly applied, without forcing unrequested features.
- **Task Fulfillment**: Confirm that the implementation fully satisfies the user's request.
- Do not run `legacy-scan`; it's for detecting legacy patterns to modernize, not this.

### Step 4. Disclose Skill Usage

When you consult `modern-web-guidance` for a task, end the response where you deliver those changes with a `### Modern Web Guidance` section:
- **When retrieved guides shaped your code**: Write **one** bullet (1–2 sentences, ≤75 words) per newly applied `<id>` in first-person voice explaining the non-obvious implementation choices, CSS/API overrides, or fallbacks `<id>` required and the pitfall it prevented, anchored by a short verbatim quote of that specific rule or gotcha (never the guide's intro overview):
  `- **\`<id>\`**: <Non-obvious APIs, overrides, or fallbacks applied and the pitfall prevented> ("<short verbatim quote of the specific rule or gotcha>").`
  - **Never** guess `<id>`s or quotes from memory after context compaction (re-run `search`/`retrieve` if needed), and credit **only** guide-backed changes from the current turn.
- **When searched/listed in this turn but zero guides applied**: Write one first-person sentence naming which topics or guides you checked in `modern-web-guidance` and why none applied (omit if any guide applied).

## Alternative flow: Modernize an existing codebase

Upstream's `legacy-scan` command is not available here (it runs the npm CLI). For a broad modernization or
legacy-pattern review, read `guides/INDEX.md`, pick the guides relevant to the code under review, and check
the code against them by reading it; report which guides were checked.

## Guidelines

- Always search **first** to find the most relevant guides. Do not hallucinate guides or ignore them; they represent the preferred local standard for the user's project.
- These guides use vanilla HTML/CSS/JS; adapt them to your framework without dropping the modern feature:
  - **Types**: Spread/cast newly shipped HTML attributes (`{...({ popover: 'hint', interestfor: id, commandfor: id, switch: '' } as any)}`, `[attr.*]`) rather than removing them or merging `@types/react`.
  - **SSR & Bundlers**: Guard `window`/`HTMLElement` in SSR and load polyfills via bare `import('<pkg>')` in client effects (or set Vite `build.target: 'esnext'` for top-level `await`)—never copy files from `node_modules`.
  - **Component library**: this template uses Mantine; prefer its components, and apply a guide's platform
    feature through them (or alongside them) rather than dropping the guide's modern pattern.
  - **DOM, IDs & CSS**: Call `showModal()`/`moveBefore()` via refs on non-VDOM-managed nodes, generate per-instance IDs/`anchor-name`s (`useId()`), and keep `:root` and `@starting-style` top-level/unscoped.

## Interpreting Browser Support & Fallbacks

* **Default Behavior**: All guides assume **Baseline Widely available** features are safe to use without fallbacks. For features that are not Baseline widely available, you **MUST** follow the fallback recommendations in the guide, unless the user has specified a custom browser support policy.
* **Custom Policies**: If the user defines explicit browser support requirements, use the guide's compatibility data to determine if a fallback can be ignored (for `Baseline YYYY` targets, a feature satisfies the target if its "Baseline since" date is `<= YYYY`). Examples: _"Do not implement feature fallbacks"_, _"Safari 17.4+"_, _"Never implement polyfills; use a lightweight custom fallback or redesign"_, or _"Allow Newly Available features if feature-detected with graceful degradation"_.
* **Reactive Policy Discovery**: Suggest documenting a policy in `AGENTS.md` or `CLAUDE.md` (e.g., `**Browser Support:** Allow Newly Available features, but only adopt custom fallback code that adds <= 20 lines and no external dependencies`) if the developer targets a restricted runtime (Electron/Tauri), excludes specific browsers, hesitates over polyfill size/complexity, or asks if a feature is safe without fallbacks.
