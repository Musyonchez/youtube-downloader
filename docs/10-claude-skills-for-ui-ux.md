# 10 — Claude Skills & Claude Design for UI/UX Work

Reference notes, not project-specific — kept portable so this file can be
copied into any project's `docs/` folder as-is. Distilled from three
external sources (credited per section); site chrome, ads, and unrelated
promo content stripped out.

---

## Part 1 — What Claude Skills are (and aren't)

Source: Snyk blog, "Top 8 Claude Skills for UI/UX Engineers" (Stephen Thoemmes)

The Claude ecosystem has several extension mechanisms that are easy to
confuse:

| Mechanism | What it is |
|---|---|
| **CLAUDE.md files** | Persistent project memory, always loaded into every session. On-context, not on-demand. |
| **Custom slash commands** (`.claude/commands/*.md`) | Simple prompt templates triggered by `/command-name`. Effectively merged into Skills — a skill with an `argument-hint` in its frontmatter can be invoked as a slash command; others activate contextually. |
| **MCP servers** | Running processes exposing tools/data via the Model Context Protocol. Require a server process and code. |
| **Claude Connectors** | MCP servers for specific external services (Slack, Figma, Asana) via OAuth. |
| **Claude Apps** | The platforms Claude runs on (claude.ai, Claude Code, mobile, desktop) — not an extension mechanism. |
| **Plugins** | Bundles that package skills, agents, hooks, and MCP servers together for distribution. |
| **Claude Skills** | Directories containing a `SKILL.md` (YAML frontmatter + markdown instructions) plus optional scripts/templates/reference docs. |

### What makes Skills distinct

- **Directories, not single files.** A skill can bundle shell scripts,
  Python helpers, reference docs, and assets alongside its instructions.
- **Progressive disclosure.** At startup, only each skill's `name` +
  `description` (~100 tokens) loads into context. Claude matches the task
  against descriptions to decide activation; only then does the full
  `SKILL.md` load. Supporting files load only when needed during execution.
  This keeps context lean even with dozens of skills installed — and means
  the `description` field is critical: vague descriptions activate
  unreliably, precise ones with explicit trigger phrases activate
  consistently.
- **Can execute code.** Scripts in `scripts/` that Claude runs, or
  `` !`command` `` syntax to inject dynamic output into the prompt.
- **Open standard.** The Agent Skills spec is adopted by Claude Code,
  OpenAI Codex, Cursor, Gemini CLI, and others — skills are portable
  across tools.
- **Can register as slash commands.** Skills with `argument-hint` in
  frontmatter become `/skill-name`; skills without one activate
  contextually when the task matches their description.

### Installing a skill

```
# Project level (shared via version control)
your-project/.claude/skills/skill-name/SKILL.md

# User level (personal, all projects)
~/.claude/skills/skill-name/SKILL.md

# Via plugin marketplace
/plugin marketplace add <org>/<repo>
/plugin menu
```

Precedence when names conflict: enterprise > personal (user-level) > project.

### Security note

The Agent Skills ecosystem is new and growing fast — supply-chain risk is
real. Cited research (Snyk's "ToxicSkills" study) found prompt injection in
36% of skills tested and 1,467 malicious payloads across the ecosystem
sampled, plus 13% of tested skills with critical security flaws, some
actively attempting credential exfiltration. Before installing any skill:

1. **Read the `SKILL.md` and any bundled scripts** — they're markdown and
   shell scripts, not compiled binaries; every line is inspectable.
2. **Check the source** — established orgs (Anthropic, Vercel) carry lower
   risk than random community repos.
3. **Review the `allowed-tools` frontmatter** — a skill requesting `Bash`
   access warrants more scrutiny than one using only `Read`/`Grep`.
4. **Scan scripts with a code scanner** if available (the source article
   plugs Snyk Code here, but the principle generalizes to any SAST tool).

Treat a third-party skill like any third-party code you'd run in your
environment — trust, then verify.

---

## Part 2 — Top 8 Claude Skills for UI/UX (catalog, as of the source article)

| # | Skill | Stars | Focus | Source repo |
|---|---|---|---|---|
| 1 | Anthropic Frontend Design | 65,847 | Distinctive, production-grade UI aesthetics | `anthropics/skills` |
| 2 | Vercel Web Design Guidelines | 19,487 | Web interface audit (100+ rules: accessibility, UX) | `vercel-labs/agent-skills` |
| 3 | Vercel React Best Practices | 19,487 | React/Next.js performance (57 rules, 8 categories) | `vercel-labs/agent-skills` |
| 4 | Vercel Composition Patterns | 19,487 | React component architecture/design patterns | `vercel-labs/agent-skills` |
| 5 | UI/UX Pro Max | 29,636 | Design intelligence: 50 styles, 97 palettes, 9 stacks | `nextlevelbuilder/ui-ux-pro-max-skill` |
| 6 | Bencium UX Designer | 72 | Comprehensive UX: accessibility, responsive, motion specs | `bencium/bencium-claude-code-design-skill` |
| 7 | AccessLint | 8 | WCAG 2.1 auditing, contrast checking, refactoring | `accesslint/claude-marketplace` |
| 8 | Vercel React Native Skills | 19,487 | Mobile UI performance, animations, navigation | `vercel-labs/agent-skills` |

### 1. Anthropic Frontend Design

`anthropics/skills` (path `skills/frontend-design/`), also in
`anthropics/claude-code` plugins. Anthropic's own answer to "AI slop" —
generic purple-gradient-on-white output, overused fonts (explicitly bans
Inter, Roboto, Arial, system fonts, and even Space Grotesk as "overused by
AI"). Before writing code it has Claude reason through purpose, tone,
constraints, and differentiation. Covers five areas:

- **Typography** — distinctive, characterful fonts; unexpected pairings.
- **Color/theme** — commit to a cohesive palette via CSS variables; dominant
  colors + sharp accents over timid even distribution.
- **Motion** — prioritize one well-orchestrated high-impact moment (e.g. a
  staggered page-load reveal) over scattered micro-interactions.
- **Spatial composition** — asymmetry, overlap, diagonal flow,
  grid-breaking elements, generous negative space.
- **Backgrounds/detail** — gradient meshes, noise textures, geometric
  patterns, layered transparency, dramatic shadows, custom cursors.

Opinionated toward bold/distinctive work — best for landing pages,
marketing sites, portfolios; pair with a more structured skill (#2 or #6)
if consistency matters more than creative flair (e.g. internal tools).

Install: `git clone anthropics/skills`, copy `skills/frontend-design` into
`~/.claude/skills/`, or via the `anthropics/claude-code` plugin menu.

### 2. Vercel Web Design Guidelines

`vercel-labs/agent-skills` (path `skills/web-design-guidelines/`). A
quality gate, not a creative tool — reviews existing UI code against the
Web Interface Guidelines (100+ rules: ARIA, focus states, labeled inputs,
touch target sizes, reduced-motion support, semantic HTML, keyboard nav,
heading hierarchy). Workflow: fetches the latest guidelines from source
(stays current), reads specified files, checks every rule, outputs
`file:line` findings. Registers as `/web-design-guidelines <glob>`.

### 3. Vercel React Best Practices

`vercel-labs/agent-skills` (path `skills/react-best-practices/`). 57
performance rules across 8 categories, prioritized by real-world impact:

| Priority | Category | Impact | Rules |
|---|---|---|---|
| 1 | Eliminating waterfalls | Critical | 5 |
| 2 | Bundle size optimization | Critical | 5 |
| 3 | Server-side performance | High | 7 |
| 4 | Client-side data fetching | Medium-high | 4 |
| 5 | Re-render optimization | Medium | 12 |
| 6 | Rendering performance | Medium | 9 |
| 7 | JavaScript performance | Low-medium | 12 |
| 8 | Advanced patterns | Low | 3 |

The ordering itself is the lesson: waterfalls and bundle size dwarf
`useMemo`-level micro-optimization in real impact. Each rule ships
incorrect/correct code pairs with rationale.

### 4. Vercel Composition Patterns

`vercel-labs/agent-skills` (path `skills/composition-patterns/`). Targets
boolean-prop-proliferation (`isCompact`, `showHeader`, `isRounded`...) by
teaching composition patterns that scale:

- Avoid boolean props for behavior — use composition instead (the
  foundational rule).
- Compound components with shared context (à la Radix `<Select>`,
  `<Select.Trigger>`, `<Select.Content>`).
- Decouple state implementation behind a provider; components consume a
  clean `{state, actions, meta}` interface.
- Explicit variant components (`<Alert.Destructive>`) over boolean modes
  (`<Alert isDestructive>`).
- Children-based composition over `renderX` props.
- React 19+: skip `forwardRef`, use `use()` over `useContext()`.

### 5. UI/UX Pro Max

`nextlevelbuilder/ui-ux-pro-max-skill`. The most comprehensive *design
intelligence* skill — ships a searchable database (via a bundled Python
CLI, `scripts/search.py`) of 50+ UI styles, 97 color palettes, 57 font
pairings, 99 UX guidelines, 25 chart types, across 9 tech stacks
(html-tailwind, react, nextjs, vue, svelte, swiftui, react-native, flutter,
shadcn, jetpack-compose). Four-step workflow: analyze requirements →
generate a design system (`--design-system`, searches 5 domains in
parallel and applies reasoning rules) → supplement with domain-specific
searches → pull stack-specific implementation guidelines. Supports a
persistent `MASTER.md` + per-page override pattern for multi-page projects.

Rule priority: accessibility and touch/interaction rank **critical**
(4.5:1 min contrast, visible focus rings, alt text, ARIA labels, keyboard
nav, proper form labels) — ranked above aesthetics.

### 6. Bencium UX Designer

`bencium/bencium-claude-code-design-skill`. The most thorough single-skill
UX *fundamentals* reference (~28,000 chars) — design thinking, visual
standards, interaction design, accessibility, in one package. Two variants:
`bencium-innovative-ux-designer` (bold/creative) and
`bencium-controlled-ux-designer` (consistency-first). Both ship reference
docs: `ACCESSIBILITY.md`, `RESPONSIVE-DESIGN.md`, `MOTION-SPEC.md`,
`DESIGN-SYSTEM-TEMPLATE.md`. Core philosophy: simplicity through
reduction, material honesty, functional layering via typography/contrast/
spacing, obsessive per-pixel intentionality, coherent design language,
"invisibility of technology." Interaction design emphasizes direct
manipulation (drag-drop over up/down buttons), feedback within 100ms,
forgiveness patterns (prevent + recover), progressive disclosure.

### 7. AccessLint

`accesslint/claude-marketplace`. Dedicated accessibility toolkit — 4
skills (`contrast-checker`, `refactor`, `use-of-color`, `link-purpose`), 1
review agent (`accesslint:reviewer`, multi-step WCAG 2.1 A/AA audit with
severity-ranked findings), and a bundled MCP server (`@accesslint/mcp`)
exposing `calculate_contrast_ratio`, `analyze_color_pair`, and
`suggest_accessible_color` as tools other skills/agents can call. Low star
count (8) but focused, high-quality scope. Covers WCAG's four principles:
perceivable (alt text, semantic structure, contrast), operable (keyboard
nav, focus management/visibility), understandable (clear labels, error ID,
consistent behavior), robust (ARIA correctness).

### 8. Vercel React Native Skills

`vercel-labs/agent-skills` (path `skills/react-native-skills/`).
Mobile-specific performance/interaction patterns:

| Priority | Category | Impact | Rules |
|---|---|---|---|
| 1 | List performance | Critical | 8 |
| 2 | Animation | High | 3 |
| 3 | Navigation | High | 1 |
| 4 | UI patterns | High | 10 |
| 5 | State management | Medium | 5 |
| 6 | Rendering | Medium | 2 |
| 7 | Monorepo | Medium | 2 |
| 8 | Configuration | Low | 3 |

List performance ranked critical (most common mobile bottleneck): FlashList
over FlatList, memoized items, stable callback refs, no inline style
objects, extracted render functions, optimized list images, item-type
heterogeneity. UI-pattern highlights: `expo-image` over RN's `Image`,
`Pressable` over `TouchableOpacity`, safe-area handling, native context
menus/modals, `onLayout` over `measure()`. Animation: only animate
`transform`/`opacity` (GPU-accelerated), `useDerivedValue` for computed
animation, `Gesture.Tap` over `Pressable` for gesture-driven interaction.

### Recommended combination (per the source article)

The four categories aren't mutually exclusive — combine across them:

- **Creative direction:** Frontend Design (#1) or Bencium (#6)
- **Design intelligence:** UI/UX Pro Max (#5)
- **Quality/compliance:** Web Design Guidelines (#2) or AccessLint (#7)
- **Engineering patterns:** React Best Practices (#3), Composition
  Patterns (#4), React Native Skills (#8)

E.g.: Frontend Design for aesthetic quality + Web Design Guidelines for
accessibility compliance + React Best Practices for performance — they
complement rather than conflict.

### Where to find more

No single official marketplace site as of the source article. In
claude.ai: Customize → Skills → Browse skills (Anthropic + partner skills
from Notion, Figma, Atlassian; can also upload your own). Anthropic's
examples: `github.com/anthropics/skills`. Community catalogs:
`travisvn/awesome-claude-skills`, `VoltAgent/awesome-agent-skills`.

---

## Part 3 — Prescriptive vs. principle-based skill design

Source: dev.to, "I figured out how to get consistently good UI from Claude
Code" (Oyindamola Akinleye)

Core finding: **the more prescriptive a UI-generation skill/prompt is, the
worse the output tends to be.** Claude pattern-matches against training
data — a vague instruction like "a modern dashboard" triggers whatever
safe, generic pattern is most statistically likely, rather than genuine
reasoning about the problem.

The author tried heavy prescriptiveness first (exact alpha values for
borders, specific design-token patterns) and got output that was
technically fine but visually homogeneous across very different
instructions — no diversity in creativity or information architecture.

Analyzing Anthropic's `frontend-design` skill (Part 2, #1) revealed why it
works: it's **principle-based and evocative**, not a checklist of exact
values. That framing forces Claude to genuinely explore the task's design
space before producing visual output, rather than filling in a template.
Switching their own skill to the same pattern — detailing design
principles but stating them evocatively rather than as rigid rules —
produced markedly more thoughtful initial output.

**Takeaway for writing a custom design skill:** state *principles and
intent* ("commit to a dominant color with sharp accents, resist timid even
distribution") rather than *exact values* ("use `rgba(0,0,0,0.12)` for all
borders"). The latter is easier to write but caps the model at
"technically compliant, creatively flat." A skill built for *systematic
consistency* across a functional app (dashboards, internal tools) and one
built for *distinctive one-off aesthetics* (landing pages) are legitimately
different goals — but even the consistency-oriented one benefits from
principle-based framing over rigid value tables, per this finding.

---

## Part 4 — Claude Design walkthrough (product, not Claude Code)

Source: a course-site blog post, "How to Use Claude Design for UX/UI"
(dated within the source's own site as 22 April, year unstated in the
excerpt available). **Note: the source material was cut off mid-article by
a length limit before reaching several announced sections (UX logic and
planning, high-fidelity prototyping with animation, and Claude Code
handoff) — those are listed below as topics covered by the full article,
not summarized, since the input didn't include their content.**

Claude Design (a separate product from Claude Code / Skills, in Research
Preview Beta at time of writing) requires a paid plan and has its own
independent, separately-capped daily usage limit from the main Claude
account.

### Design system as the foundation

Everything in Claude Design centers on a **Design System**:

- Can be generated from scratch — feed it a brand/style guide, or even
  just visual inspiration screenshots, and it proposes one.
- Can start from an existing system — link a GitHub repo of components, or
  upload a local asset folder.
- Plays with Figma — can ingest a `.fig` export of a style guide,
  components, or brand guide.
- Can also start from an existing open-source design system.

**Cost tip from the source:** generating a system from raw assets can burn
significant tokens/credits; consider drafting the base system in a
cheaper/faster tool first if starting from nothing, and switch to a
lighter model for simple tweaks to conserve usage.

### Review workflow

Generation takes several minutes and shows a live progress list of files
read/created. The output is a **draft** design system presented for
line-item review, not a finished product:

- Color palette — presented with an explicit accessibility check
  (foreground/surface pairs); the source's own draft initially failed
  contrast and required an explicit "make these accessible" follow-up
  before passing.
- Typography — full type scale, including a fallback/substitute font
  choice if requested font files weren't uploaded.
- Spacing scale, buttons, wordmark — reviewed individually.
- Motion — takes a natural-language description of desired *feel* (not
  exact easing curves/durations) and produces animation specs from it.

Each element is approved or sent back for revision individually before
moving on — the workflow is iterative and human-gated per design-system
component, not one-shot generation.

### Starting a project (wireframes)

Once a design system exists, it can be applied to a new project. Per the
source, Claude Design proactively asks clarifying UX questions before
producing wireframes for a given flow (e.g. onboarding) — rather than
generating directly from a one-line prompt — to make sure it understands
the underlying UX intent first.

### Topics the full source article covers but this excerpt doesn't reach

(Titled sections announced at the top of the source post; not summarized
here since their content wasn't in the available excerpt — consult the
original for these.)

- UX logic and planning
- Making a high-fidelity app prototype (with animations)
- Handing off the design to Claude Code for implementation
