---
target: frontend/src/pages/ObjectStorage/Credentials.vue
total_score: 26
p0_count: 0
p1_count: 3
timestamp: 2026-09-01T02-21-45Z
slug: frontend-src-pages-objectstorage-credentials-vue
---
#### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2/4 | Failed data requests collapse into the same empty state as a successful zero-data result. |
| 2 | Match System / Real World | 3/4 | Bucket and credential concepts are clear, but “shared scope” needs more direct operator language. |
| 3 | User Control and Freedom | 3/4 | Refresh, clear-secret, and confirmation controls are present; load failures lack an in-context retry path. |
| 4 | Consistency and Standards | 3/4 | Shared buttons, panels, labels, and sidebar patterns are consistent, but page metadata props are not rendered. |
| 5 | Error Prevention | 3/4 | Credential rotation requires explicit confirmation and retrieval is gated by an approved application. |
| 6 | Recognition Rather Than Recall | 3/4 | Status and scope are visible, but empty states do not explain the next step or whether the request failed. |
| 7 | Flexibility and Efficiency | 2/4 | The credentials layout waits for the `xl` breakpoint, so it becomes a long single column at the 1159px viewport shown. |
| 8 | Aesthetic and Minimalist Design | 3/4 | Calm and restrained overall, though persistent info alerts and repeated bordered panels add visual weight. |
| 9 | Error Recovery | 2/4 | The credentials page only exposes load failure through a toast, which disappears and offers no direct retry context. |
| 10 | Help and Documentation | 2/4 | Supporting copy is authored but globally hidden, and the empty states provide little operational guidance. |
| **Total** | | **26/40** | **Good foundation; status communication and information hierarchy need attention.** |

#### Anti-Patterns Verdict

**LLM assessment:** The interface does not look obviously AI-generated. The restrained navy/slate action hierarchy, familiar sidebar, and standard form controls fit an operations console. The main risk is a mild “glass dashboard” bias: translucent surfaces, shadows, and repeated bordered panels compete with the task, especially on the credentials page.

**Deterministic scan:** The Impeccable detector returned no findings for the four employee object-storage pages. This is a clean automated result, but it does not detect the runtime state ambiguity or the missing `PageFrame` output.

#### Overall Impression

The module is visually calm and structurally understandable. The single biggest opportunity is to make data state trustworthy: operators must be able to tell “no credentials/buckets exist” from “the API could not be read,” without bringing back a large noisy alert.

#### What's Working

- The left sidebar is now the single navigation source, which removes duplicated navigation and gives the content area more room.
- The credentials flow separates inventory, one-time delivery, and rotation into clear task areas; explicit confirmation before rotation is appropriate for a high-risk action.
- The visual vocabulary is coherent: dark primary actions, light secondary actions, status badges, and compact list rows all fit the existing HyperOps console.

#### Priority Issues

- **[P1] Failed loads look like successful empty states**
  - **Why it matters:** `loadSafeData()` clears all data and only calls `showError()` on failure. After the toast disappears, the page looks identical to an account with no credentials, applications, or rotation candidate. The same pattern exists in `Buckets.vue` and `Applications.vue`.
  - **Fix:** Keep the large alert removed, but add a compact retryable state inside the affected section: “暂时无法读取” + “重试”, distinct from “尚未创建”. Prefer section-local state so one failed endpoint does not blank unrelated content.
  - **Suggested command:** `$impeccable harden`

- **[P1] PageFrame silently drops page context**
  - **Why it matters:** Object-storage pages pass `eyebrow` and `subtitle`, but `PageFrame.vue` only renders the title and action slot. The global stylesheet also hides `.page-eyebrow`, `.page-subtitle`, and `.section-copy`, so users lose the explanation of what each section means and why an action is available.
  - **Fix:** Render `eyebrow` and `subtitle` in `PageFrame` when provided, then stop globally hiding supporting copy. If compact density is needed, shorten specific copy or add a page-level compact variant rather than suppressing all helper text.
  - **Suggested command:** `$impeccable clarify`

- **[P1] Credentials page is too vertically long at common desktop widths**
  - **Why it matters:** The two-column layout activates only at `xl` (1280px). At the shown 1159px viewport, the summary, delivery, and rotation panels stack, pushing the high-risk rotation action far below the primary credential workflow.
  - **Fix:** Use a container-aware breakpoint or move the rotation panel into a compact secondary column at `lg` when the content area can support it. On narrower screens, keep stacking but preserve a short sticky/anchored section navigation or clear progression.
  - **Suggested command:** `$impeccable layout`

- **[P2] Small muted labels are too faint for an operations console**
  - **Why it matters:** `.admin-filter-label` is 10px uppercase in `text-slate-400`; metadata also leans on `text-slate-400/500`. These labels are low contrast and easy to miss when scanning or when the browser is zoomed.
  - **Fix:** Use at least 11–12px, a darker neutral such as slate-600 for field labels, and reserve uppercase tracking for short metadata only. Verify contrast against the actual surface.
  - **Suggested command:** `$impeccable typeset`

- **[P2] One-time secrets are immediately exposed as plain text**
  - **Why it matters:** The access key and secret access key are rendered directly into readonly inputs. That is functional, but a screen share or shoulder-surfing incident exposes the secret before the operator chooses to reveal it.
  - **Fix:** Mask the secret by default with an explicit reveal control; keep copy available and announce copy/reveal state to assistive technology. Clear the material on navigation/unmount as already done.
  - **Suggested command:** `$impeccable harden`

#### Persona Red Flags

**Alex (Power User):** After a failed credentials request, the toast disappears and the empty inventory gives no direct retry target. Alex must infer that the top Refresh button reloads all three endpoints. At 1159px, rotation is also pushed below delivery, slowing a routine rotation check.

**Jordan (First-Timer):** The page title is visible, but the page subtitle and section helper text are not. “共享作用域” and “申请记录” require domain knowledge, while an empty credential list does not explain how to create an eligible application or what “delivery ready” means.

**Sam (Security-Conscious Operator):** The one-time secret appears in clear text immediately after retrieval, with no reveal/mask choice. The clear action exists, but the safer default should be masked presentation.

#### Minor Observations

- `PageFrame.vue` declares an `eyebrow` prop but does not consume it; this is a component contract defect, not just a styling preference.
- `EmptyState.vue` declares a `description` prop but does not render it, limiting the ability to teach the next step without adding ad-hoc markup.
- Small buttons are around 32px high; check mobile touch targets and consider 40–44px hit areas while preserving compact visual styling.
- The persistent informational alert on credentials duplicates the scope facts shown again in the summary `<dl>`; one concise presentation would be enough.

#### Questions to Consider

- Can “no data” and “could not load” become two explicit states everywhere, while keeping the page visually quiet?
- Should rotation be treated as an advanced action that is visually separated, or should it be easier to reach for frequent operators?
- Which supporting copy is essential enough to remain visible at a glance, and which can move into an expandable help affordance?
