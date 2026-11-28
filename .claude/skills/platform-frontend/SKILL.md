---
name: platform-frontend
description: Frontend conventions of the nexusHome platform (`platform/`) — React 19 + Vite + Mantine 9 structure, routing and guards, API client and TanStack Query, i18n keys, theme tokens and the visual system, navigation, accessibility and tests. Use when writing or reviewing frontend code.
---

# Frontend Patterns

Paths are relative to `platform/`; run `make` targets from there.

## Stack

React 19 · Vite 8 · React Router 8 · Mantine 9 (+ form, notifications, hooks) · TanStack Query 5 ·
i18next (en, es, gl) · lucide-react · Vitest 5 + Testing Library + MSW 3 · ESLint 9 (jsx-a11y) ·
Prettier. Plain JavaScript (JSX), named exports, one component per file.

## Structure

See the platform-architecture skill for the folders. Rules:

- A route = a page in `pages/` (`pages/admin/` for admin pages), registered in `App.jsx` behind the
  right guard: `AnonymousOnly` (login), `RequireSession` (any signed-in account), `RequireRole min="user"`
  or `"admin"`. Pages most users never open are `lazy()` (they get their own chunk).
- Shared UI goes to `components/` only when a second page uses it. Page-specific helpers stay next to
  the page (`pages/admin/usersApi.js`, `UserDialogs.jsx`).
- Styles: Mantine props and theme first; a CSS module (`Name.module.css`) next to the component for the
  rest; global rules only in `styles/base.css` (and only for Mantine-wide fixes).

## Data and the API

- `api/client.js` `api(path, { method, body })`: JSON, the access token from memory, one shared refresh
  on 401 (then a single retry), `ApiError { status, code, message, details }` on failure. Never call
  `fetch` directly.
- Server state with TanStack Query: one hook per query/mutation (`useUsers`, `useUpdateUser`…), query
  keys starting with the resource (`['users', …]`), mutations invalidate their resource. Errors without
  a local handler show a toast (`notifyError`); dialogs show their own `ErrorAlert`.
- A query whose page shows its own error (a "not found" heading) sets `meta: { handlesErrors: true }`
  (no toast) and stops its `refetchInterval` on error. Live pages refetch every 2 s while visible
  (`devices/devicesApi.js`: the platform polls the boards at that pace).
- Session state only in `AuthContext` (`useAuth()`: `user`, `status`, `loginStart`, `loginVerify`,
  `updateProfile`, `changePassword`, `logout`). No other global store.
- Map API error `code`s to translated messages; unknown codes fall back to a generic message.

## i18n

- Keys by area (`login.*`, `profile.*`, `users.*`, `nav.*`, `common.*`, `errors.*`), the same keys in
  `en.json`, `es.json` and `gl.json` (a test checks parity). English is the reference.
- Copy: sentence case, plain verbs, a button says what happens ("Save changes", "Grant access"), the
  toast echoes it ("Changes saved."). Galician and Spanish written natively, not word for word.
- Language: the account's language after sign-in; before it, the last one used in this browser
  (`localStorage`), else the browser's, else English.

## Accessibility (WCAG 2.2 AA)

Every control has an accessible name (labels, `aria-label` for icon buttons with the target, e.g.
"Edit ana@example.com"); decorative icons `aria-hidden`; visible focus (2 px outline); contrast 4.5:1
text / 3:1 controls in both schemes; 44–48 px touch targets on mobile; errors in `role="alert"` and
focus moved to them when an action fails; dialogs named, focus returned to the trigger; reduced motion
respected. ESLint's jsx-a11y must stay clean.

## Tests

- Vitest + Testing Library: test behaviour through roles and names (`getByRole('button', { name })`),
  never class names or test ids. `renderWithProviders(<AppRoutes />, { route })` renders the real app.
- MSW (`test/server.js`): handlers per test with `server.use(...)`; unhandled requests fail the test.
  Helpers: `withSession(user)`, `makeUser(overrides)`, `apiError(status, code)`.
- Mantine runs with `env="test"` (no transitions); notifications are cleared after each test.
- Coverage thresholds 95 / 90 / 95 / 95 (statements / branches / functions / lines); currently ~100 %.
- The real flows (login with codes, roles, persistence) are covered by the Playwright suite in `e2e/`.

## Visual system (T015)

Minimal and professional, from nudge's palette; made with the `frontend-design` skill. All values live in
`frontend/src/theme.js` (Mantine theme + `cssVariablesResolver`) and `frontend/src/styles/base.css`.

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| Primary (slate) | `#454961` | `#b9bde0` | Actions, links, focus, avatar |
| Text on filled colours | `#ffffff` | `#14161d` | `--app-color-on-filled`; in dark mode `base.css` maps Mantine's `--mantine-color-white` to it inside filled components (user decision: keep nudge's lavender fill) |
| Danger (red) | `#9f1239` | `#f87171` | Errors (`--mantine-color-error`), destructive actions |
| Success (teal) | `#0f766e` | `#2dd4bf` | Confirmations |
| Brand (amber) | `#fcd34d` / text `#78350f` | same | The brand mark only — never actions or page text |
| Page | `#fafafa` | `#14161d` | `--mantine-color-body` |
| Surface | `#ffffff` | `#1d2029` | `--app-color-surface`, inputs |
| Heading | `#0a0a0a` | `#f4f4f6` | h1–h3 |
| Text / dimmed | `#2a2e42` / `#575c75` | `#e6e7ef` / `#9a9fb2` | Body, secondary |
| Divider border | `#e4e4e7` | `#343849` | Separators, header |
| Control border | `#8a8ea1` | `#6f7590` | Inputs (3:1 contrast, WCAG 1.4.11); focused inputs get a 2 px primary outline |

- **Type**: the system font stack; h1 1.75 rem, h2 1.375 rem, h3 1.125 rem, weight 650; sentence case;
  no all-caps labels.
- **Links**: standalone links are underlined (`Anchor` default); the brand link opts out.
- **Shape**: radius 6 px (controls), 8 px (surfaces), avatars round. Borders separate surfaces; shadows only on floating
  layers (menus, notifications).
- **Layout**: screens before the app use `AuthLayout` (same 1080 px container and 56 px top row as the shell,
  so the brand does not move; a 360 px column, no card: left-aligned with the brand on wide screens,
  centred on phones up to 48 em). The app uses `AppLayout` (56 px top bar with a bottom border, content in a
  1080 px container, left-aligned). Pages start with an h1.
- **Motion**: none decorative; Mantine transitions only on things the user opened, plus the bottom
  navigation's 200 ms tab change; reduced motion respected. Never call Mantine's `setColorScheme` unless the
  scheme really changes: every call switches off all CSS transitions on the page for a moment.
- **Progressive disclosure**: pages show content read-only; rare actions open on demand and close when
  done. A pencil or an icon button opens the form in a dialog (`Modal`, named close button, Cancel and
  Save on the right, `data-autofocus` on the first field; the form mounts inside the dialog so each
  opening starts fresh, and Mantine returns the focus to the trigger). The profile shows who is signed in
  (round picture placeholder; name with its pencil; email and account type; a key icon on the right,
  "Change password", only for password accounts) over its preferences. Preferences save at once and share one look: name over a full-width, large control, all the
  same height (`SegmentedControl` for short choices such as language and colour scheme, a searchable
  `Select` for long lists such as the time zone). Lists keep the frequent action visible (search; "Grant access" on a waiting account) and fold the
  rest: secondary filters in a "Filters (n)" popover, row actions in one "⋯" menu (destructive last, in
  red, after a divider). Tables fit a phone without scrolling sideways: combine cells (name over email),
  show states as badges, narrow columns on small screens.
- **Scroll**: `scrollbar-gutter: stable` on the root, so short and long pages do not shift sideways.
- **Copy**: plain, active, sentence case; errors say what happened and what to do.
- Contrast of every token pair is checked (all ≥ 4.5:1 text, ≥ 3:1 controls), with a script over `theme.js` and `base.css` (the template's T015 did it for the current palette).
- Dark-mode fills: `base.css` maps Mantine's `--mantine-color-white` to the on-filled colour on elements that
  carry a fill, matched by state (`[data-variant='filled']`, default-variant Button/ActionIcon/Badge/ThemeIcon,
  selected options, active pagination/tabs/nav links, checkbox/radio/progress/indicator/stepper fills, checked
  switch). A new filled component must be checked in dark mode (render it in both schemes in the dev stack
  and look) and added there if it shows white on lavender — on the element
  whose CSS reads the variable, not a child.
- Palette colours are `slate`, `red`, `teal` (and `gray`). Mantine's other colours (yellow, blue…) are not tuned
  for this palette and are not used. Do not use the `white` variant (primary text on white fails in dark mode).
- `Avatar.Group` draws a page-coloured ring between overlapping avatars on purpose (a separator, not a
  boundary): contrast checks do not apply to it.
- Shade rule: every Mantine colour shows shade 7 in light and shade 3 in dark (`primaryShade`); new colours
  must put their light-mode token at 7 and their dark-mode token at 3.
- Known limit: an explicit scheme that differs from the OS one can flash on first paint (the CSP forbids the
  inline script that would prevent it).
- New screens: follow this table and layout; critique with screenshots of the dev stack in both schemes and
  at mobile width before calling the work done.

## Navigation and app shell (T009)
- Icons: `lucide-react` only (same set as nudge); decorative icons get `aria-hidden`, icon-only controls an
  `aria-label`.
- `BottomNav` is the app's only navigation: fixed to the bottom on every screen size, `--nav-h` (64 px) plus
  `env(safe-area-inset-bottom)`. The current tab is a slate pill with icon and label; the others show the icon
  only, with the label kept in the DOM as the accessible name. The pill is one element (`ul::before`, anchored
  to the current tab with CSS anchor positioning); on a tab change `useSlidingPill` slides it from the old tab
  to the new one in 200 ms, in step with the labels folding and unfolding (without anchor support the current
  tab paints its own pill and nothing slides). Tabs are declared in `TABS` with the minimum
  role (`none`/`user`/`admin`); the bar is not rendered with fewer than two tabs or while the on-screen
  keyboard is open (`useKeyboardOpen`, ignoring pinch zoom).
- Space under the bar: the shell's content reserves `--nav-h` + safe area + 2 rem at the bottom, and
  `:root:has([data-bottom-nav])` sets `scroll-padding-bottom` so focused fields are never hidden under it.
  Do not override the content's bottom padding (`py` on the container would).
- The app's top bar holds the brand and, on the right, log out (plus whatever actions each app adds). Language
  and colour scheme are set in `/profile` once signed in; the language and colour-scheme menus appear only on
  the screens before the app (`AuthLayout`: login, welcome). Name and password live on `/profile`.
- Dialogs: name the close button (`closeButtonProps={{ 'aria-label': t('common.close') }}`); a dialog mounted
  on open must give focus back to its trigger on close (or a stable fallback); a failed action moves focus to
  its error alert.
- Badges are sentence case (`tt: 'none'` in the theme); `SegmentedControl` uses a filled indicator.

