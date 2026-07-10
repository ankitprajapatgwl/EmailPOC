# EmailPOC → Production-Style App: Migration & Redesign Plan

**Status:** Draft for human review. Once approved, this file is the spec to hand to an AI coding agent to implement, phase by phase.

**Audience:** An AI coding agent (and the developer reviewing its output) working in `/home/gwl/Documents/GWL-Projects/engagelab_email_poc`, a FastAPI + Jinja2 app (NOT Flask, despite the "flask" habit of speech — confirmed via `pyproject.toml`).

---

## 0. Executive Summary — Requirements Mapped

| # | Requirement (as given) | Where addressed below |
|---|---|---|
| 1 | Replace JSON DB completely with PostgreSQL | §2 Database Layer |
| 2 | No hardcoded users; real registration + login | §3 Authentication |
| 3 | Registration must confirm first/last name | §3.2 Registration Wizard — Step 2 |
| 4 | Auto-generate sending address from real email's prefix + `INBOUND_DOMAIN`, check for collision, confirm/re-pick, no duplicates | §3.2 Registration Wizard — Step 3 |
| 5 | All outbound email uses the user's assigned address | §4.1 Outbound Sending |
| 6 | Pick best tracking approach from `email_tracking.md`; Hybrid Architecture is pre-approved if it's the best fit | §4 Tracking Architecture (Hybrid Architecture adopted) |
| 7 | Tracking must work across all 5 providers | §4.4 Per-Provider Gap Closure |
| 8 | Full UI redesign, one consistent light theme app-wide | §5 UI/UX Redesign |
| 9 | Well-defined UI flow | §5.2 Page Inventory & Navigation Flow |

---

## 1. Current State (baseline, for context — do not re-derive, just confirm still true before coding)

- **Stack:** FastAPI + Uvicorn + Jinja2, no frontend build step, no ORM.
- **"Database":** `src/db.py` (`EmailDB`) — a single JSON file (`data/db.json`) read/written in full on every operation. Collections: `conversations`, `users` (just `user_id → [conv_id]`, not a real user table), `user_conversations`, `threads`, `predefined_users`, `predefined_projects`, `unmatched_emails`.
- **Users:** `src/predefined_users.py` — 5 hardcoded people, picked from a `<select>` on the send form. **Zero authentication anywhere.** "Ownership" is just a UUID match in the URL path.
- **Projects/products:** `src/predefined_projects.py` — 10 hardcoded products, also just a `<select>`.
- **Dynamic address today:** `EmailMaster.build_dynamic_email()` in `src/email_platform/email_master.py` builds `{CamelCaseUserName}-{8hexConvId}@{INBOUND_DOMAIN}` **per conversation**, not a permanent per-user address. `parse_dynamic_email()` decodes it back to a `conv_id` on inbound. This is the *only* matching mechanism today — there is no Message-ID/In-Reply-To/References/subject-token logic at all in code.
- **Providers (send + inbound webhook parse):** SendGrid, Mailgun, ElasticEmail, SendCloud (AuroraSendCloud), EngageLab — one active provider at a time via `EMAIL_PROVIDER` env var, selected through `EmailProviderFactory` / `WebhookParserFactory`.
  - Inbound parsing gaps that **must be fixed** for requirement 7: `elasticemail_webhook.py` and `sendcloud_webhook.py` inbound parsing are currently **stubs / not implemented** (outbound-only today).
  - EngageLab and SendCloud only reliably fire their webhook for genuine Reply/Forward (they need thread metadata to pass their own route-matching); a supplier composing a brand-new email to the address is silently dropped today. Documented in `RFQ_EMAIL_FLOW.md` and `setup_docs/engagelab_guide/engagelab_new_thread_issue.md`.
- **UI:** All 5 templates extend `templates/base.html`; all CSS is one large inline `<style>` block in `base.html` (light theme, blue/slate palette, CSS variables already used). No component library, no JS framework, no `static/` assets yet.
- **No `DATABASE_URL`, no password hashing lib, no session/JWT lib, no SQLAlchemy/Alembic** in `pyproject.toml` today — all of this is net-new.

---

## 2. Database Layer — PostgreSQL

### 2.1 Tech choices

- **ORM:** SQLAlchemy 2.0 (async engine) + `asyncpg` driver — fits FastAPI's async routes.
- **Migrations:** Alembic.
- **Local dev:** add `docker-compose.yml` with a single `postgres:16` service; app reads `DATABASE_URL` from `.env`.
- **New dependencies** (add to `pyproject.toml`):
  ```
  sqlalchemy[asyncio]>=2.0
  asyncpg>=0.29
  alembic>=1.13
  passlib[bcrypt]>=1.7   # password hashing
  email-validator>=2.1   # for pydantic EmailStr validation
  ```

### 2.2 Schema (replaces every JSON collection)

```
users
  id                  UUID PK (default gen_random_uuid())
  first_name          VARCHAR NOT NULL
  last_name           VARCHAR NOT NULL
  personal_email      VARCHAR NOT NULL UNIQUE      -- login identifier, real-world email
  password_hash       VARCHAR NOT NULL
  sending_email       VARCHAR UNIQUE               -- NULL until registration finishes; permanent "From" address
  status              VARCHAR NOT NULL DEFAULT 'pending'   -- pending | active
  is_admin            BOOLEAN NOT NULL DEFAULT false        -- grants access to the cross-user admin overview (§5.3)
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()

user_sessions
  id                  UUID PK
  user_id             UUID FK -> users.id, ON DELETE CASCADE
  token_hash          VARCHAR NOT NULL UNIQUE      -- sha256 of the opaque cookie token; never store raw token
  user_agent          VARCHAR NULL
  ip_address          VARCHAR NULL
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  expires_at          TIMESTAMPTZ NOT NULL

products
  id                  UUID PK
  name                VARCHAR NOT NULL
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  -- seeded once from today's PREDEFINED_PROJECTS via an Alembic data migration / seed script,
  -- then src/predefined_projects.py is deleted. No admin UI for these yet (out of scope) — direct
  -- DB seed is enough since the requirement only asks to remove hardcoded USERS, not the product catalog.

conversations
  id                  UUID PK
  user_id             UUID FK -> users.id, ON DELETE CASCADE
  product_id          UUID FK -> products.id, NULL
  product_name        VARCHAR NULL         -- denormalized snapshot at creation time (kept, matches current behavior)
  quantity             VARCHAR NULL
  target_price        VARCHAR NULL
  supplier_name       VARCHAR NOT NULL
  supplier_email      VARCHAR NOT NULL
  subject             VARCHAR NOT NULL
  token               VARCHAR(8) NOT NULL UNIQUE   -- e.g. "93KFD9"; the conversation tracking token
  reply_to_address    VARCHAR NOT NULL             -- reply+{token}@{INBOUND_DOMAIN}
  provider             VARCHAR NOT NULL             -- provider used when this conversation was created
  status               VARCHAR NOT NULL DEFAULT 'open'   -- open | replied | declined
  reply_count          INT NOT NULL DEFAULT 0
  last_reply_at        TIMESTAMPTZ NULL
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()

emails
  id                  UUID PK
  conversation_id     UUID FK -> conversations.id, ON DELETE CASCADE
  direction           VARCHAR NOT NULL       -- 'sent' | 'received'
  from_email          VARCHAR NOT NULL
  to_email            VARCHAR NOT NULL
  subject             VARCHAR NOT NULL
  body_html           TEXT NULL
  body_text           TEXT NULL
  message_id          VARCHAR NOT NULL UNIQUE       -- our generated Message-ID for 'sent'; the inbound Message-ID for 'received'
  in_reply_to         VARCHAR NULL
  references_header   TEXT NULL             -- raw References header, space-separated ids
  reply_type          VARCHAR NULL          -- 'reply' | 'forwarded' | 'new_thread' (display classification, kept from today)
  matched_via         VARCHAR NULL          -- 'reply_to_alias' | 'in_reply_to' | 'references' | 'subject_token' | 'body_token' | 'heuristic' | NULL for sent
  dkim                VARCHAR NULL
  spf                  VARCHAR NULL
  spam_score           NUMERIC NULL
  provider              VARCHAR NOT NULL
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()

attachments
  id                  UUID PK
  email_id            UUID FK -> emails.id, ON DELETE CASCADE
  filename            VARCHAR NOT NULL
  url                  VARCHAR NOT NULL      -- unchanged: /attachments/{name}, still served from disk
  content_type        VARCHAR NULL
  size_bytes           INT NULL

unmatched_emails
  id                  UUID PK
  raw_payload         JSONB NOT NULL
  to_email             VARCHAR NULL
  from_email           VARCHAR NULL
  reason               VARCHAR NOT NULL      -- why matching failed
  candidate_conversation_ids  UUID[] NULL     -- heuristic ranked guesses, for the Needs Review UI
  status                VARCHAR NOT NULL DEFAULT 'needs_review'   -- needs_review | resolved | ignored
  resolved_conversation_id  UUID FK -> conversations.id, NULL
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
```

Notes:
- `emails_sent[]` / `emails_received[]` (embedded arrays in today's JSON) become the normalized `emails` table with `direction`.
- `users → [conv_id]` (today's crude index) is replaced by a real FK (`conversations.user_id`).
- `user_conversations` and `threads` (today's denormalized lookup tables) are dropped entirely — they were only needed because JSON has no joins; plain SQL joins/queries replace them.
- Every field that exists today in `data/db.json` is preserved somewhere above; nothing is silently dropped.

### 2.3 Data migration decision

**Assumption (flag for review):** existing `data/db.json` data is **not migrated** — since every conversation there belongs to a hardcoded predefined user that will cease to exist, and the whole point of this change is that real accounts must be created going forward. Recommended: archive `data/db.json` (e.g. rename to `data/db.json.bak` or move under `data/legacy/`) and start the Postgres schema empty. If the user actually wants historical data preserved under a real account, that needs a one-off manual script and a decision about *which* new registered user each hardcoded user's data should be reassigned to — call this out explicitly before building anything for it.

### 2.4 Files to add / remove

- **Add:** `src/db/` package — `session.py` (async engine/sessionmaker), `models.py` (SQLAlchemy models above), `repository.py` or split per-entity repositories (`users_repo.py`, `conversations_repo.py`, `emails_repo.py`, `unmatched_repo.py`) exposing the same kind of method surface `ConversationService` already expects (`get_conversation`, `insert_conversation`, `add_sent_email`, `add_received_email`, `update_conversation`, `delete_conversation`, `get_user_conversations`, `get_stats`, etc.) so `src/services/conversation_service.py` needs mostly call-site edits (sync→async `await`), not a rewrite.
- **Add:** `alembic/` (init via `alembic init`), first migration = full schema above, second migration/seed script = insert `products` rows from the current `PREDEFINED_PROJECTS` list.
- **Add:** `docker-compose.yml` (Postgres service for local dev).
- **Remove:** `src/db.py` (JSON store), `src/predefined_users.py`, `data/db.json` (archive, don't hard-delete — see §2.3).
- **Keep, trim:** `src/predefined_projects.py` — only used one time as the seed source for the `products` table migration, then it can be deleted too.

---

## 3. Authentication

### 3.1 Session mechanism

- **Server-side sessions**, not JWT — easier to revoke (logout, "log out everywhere"), and this app doesn't need to be stateless across services.
- Opaque random session token (32 bytes, `secrets.token_urlsafe`), stored in an **httpOnly, Secure, SameSite=Lax** cookie named `session_id`. Only the **sha256 hash** of the token is stored in `user_sessions.token_hash` (so a DB leak alone doesn't hand out valid sessions).
- Sliding expiry: `expires_at = now + SESSION_TTL_DAYS` (new env var, default 7), refreshed on each request (bump `last_seen_at`, optionally extend `expires_at` if less than half the TTL remains).
- Passwords hashed with `passlib`'s bcrypt (cost factor 12). Never log or store plaintext passwords.
- FastAPI dependency `get_current_user(request) -> User | None` reads the cookie, hashes it, looks up `user_sessions`, loads the user; a second dependency `require_login(request)` raises a redirect-to-`/login` (for HTML routes) if `get_current_user` is `None`.
- `/webhooks/inbound` stays fully public/unauthenticated (providers call it) — do not put it behind login.
- Basic brute-force mitigation on `/login`: simple in-memory or DB-based rate limit (e.g. 5 failed attempts per email per 15 minutes) — lightweight, not a full WAF; call out as a recommended addition, not a blocker.

### 3.2 Registration wizard (3 steps, matches requirements 2–4 exactly)

**Step 1 — Create Account** (`GET/POST /register`)
Fields: `first_name`, `last_name`, `personal_email` (their real, existing email — used for login), `password`, `confirm_password`.
On submit: validate (passwords match, `personal_email` not already registered, min password length), hash the password, **insert a `users` row with `status='pending'`, `sending_email=NULL`**, issue a short-lived signed cookie/token referencing this pending user id, redirect to Step 2.

**Step 2 — Confirm Name** (`GET/POST /register/confirm-name`)
Shows "Please confirm your name: **{first_name} {last_name}**" read back from the pending row, with an "Edit" link (back to Step 1, prefilled) and a "Confirm" button. This directly satisfies requirement 3 — the user must actively confirm the name before continuing, not just type it once. `POST` just advances the wizard state (or straight to Step 3 — no separate DB write needed here beyond a state flag).

**Step 3 — Assign Sending Email** (`GET/POST /register/assign-email`)
- Compute `candidate = local_part(personal_email) + INBOUND_DOMAIN` (e.g. `ankit.prajapat` + `@mail.jobsetu.online` → `ankit.prajapat@mail.jobsetu.online`).
- Query `users.sending_email` for a collision.
  - **No collision:** show the candidate address with copy: *"Your outgoing emails will always be sent from this address: `{candidate}`"* + a **Confirm & Finish** button. On confirm: `UPDATE users SET sending_email = candidate, status = 'active' WHERE id = pending_id`. Wrap in a try/except for a unique-constraint violation (race with a concurrent registration using the same prefix) — on conflict, re-render this same step with an error and ask for an alternate email instead of crashing.
  - **Collision:** show *"This address is already in use. Please provide a different email address so we can generate an alternative."* + an input for an **alternate email** (does not have to be their login email — just used to derive a different local-part). Recompute `candidate` from the alternate's prefix, re-check, loop until free, then same confirm step as above.
- On success: create the session (cookie), redirect to `/tracking` (the dashboard/home).
- **No duplicates, ever:** enforced both at the DB level (`UNIQUE` constraint on `sending_email` and `personal_email`) and at the application level (pre-check before showing the candidate) — satisfies requirement 4's "duplicate email save nahi karna" explicitly.

### 3.3 Login / Logout

- `GET/POST /login` — `personal_email` + `password`; on success create a session row + cookie, redirect to `/tracking`; on failure, generic "invalid email or password" (don't reveal which field was wrong).
- `POST /logout` — delete the current `user_sessions` row, clear the cookie, redirect to `/login`.
- All existing routes (`/`, `/send`, `/tracking*`) become login-required; `/login`, `/register*`, `/webhooks/inbound` stay public.

### 3.4 Files to add

`src/auth/` — `security.py` (password hashing helpers), `sessions.py` (create/validate/revoke session), `dependencies.py` (`get_current_user`, `require_login`), plus new routes (either a new `src/auth/routes.py` router mounted in `src/app.py`, or added to `src/route.py` — recommend a separate router for clarity). New templates: `templates/login.html`, `templates/register_step1.html`, `templates/register_step2.html`, `templates/register_step3.html` (or a single `register.html` with a step param — either is fine, keep consistent with the design system in §5).

---

## 4. Tracking Architecture — Adopting the Hybrid Architecture

`email_tracking.md`'s **"Recommended Hybrid Architecture"** is adopted as-is, adapted to this app's permanent-per-user-address model (§3.2) instead of a fully dynamic per-supplier address:

```
From:        {user.sending_email}                          (permanent, one per user — §3.2 Step 3)
Reply-To:    reply+{conversation.token}@{INBOUND_DOMAIN}    (unique per conversation)
Subject:     {original subject} [Q-{conversation.token}]
Message-ID:  <{token}@{INBOUND_DOMAIN}>                     (root); <{token}-{n}@...> for later sends in the same thread
Headers:     X-App-Conversation-Token: {token}
```

### 4.1 Outbound sending (`src/services/conversation_service.py`, `src/email_platform/*`)

- `EmailMaster.build_dynamic_email()` (per-conversation address) is **removed**. The "From" address is simply `current_user.sending_email` — always, per requirement 5.
- Add `EmailMaster.generate_conversation_token()` — short, unambiguous, unique code (recommend 6 chars, uppercase alphanumeric minus `0/O/1/I`, `secrets.choice`; re-roll on unique-constraint collision).
- Add `EmailMaster.build_reply_to(token) -> f"reply+{token}@{settings.inbound_domain}"`.
- Add `EmailMaster.build_subject_with_token(base_subject, token) -> f"{base_subject} [Q-{token}]"`.
- Add `EmailMaster.build_message_id(token, seq=0) -> f"<{token}@{domain}>"` if `seq==0` else `f"<{token}-{seq}@{domain}>"`.
- Every provider's `send_email(...)` call site must now pass: `from_email=user.sending_email`, `reply_to=reply_to_address`, custom header `X-App-Conversation-Token`, and an explicit `Message-ID`. Check each of the 5 provider modules (`sendgrid_provider.py`, `mailgun_provider.py`, `elasticemail_provider.py`, `sendcloud_provider.py`, `engagelab_provider.py`) supports setting a custom `Message-ID` and arbitrary custom headers on send — all 5 SDKs/HTTP APIs support custom headers; confirm Message-ID override support per-provider while implementing (some providers may override/ignore a client-supplied Message-ID — if a given provider silently replaces it, store *their* returned Message-ID instead of ours, since the matching engine below keys off whatever value ends up in the actual sent message).
- Every follow-up email sent within an existing conversation must set `In-Reply-To` / `References` to the previous message(s)' Message-IDs (stored in the `emails` table) — this makes our own outgoing thread internally consistent too, not just the first message.

### 4.2 Inbound matching engine — priority chain

New module `src/services/matching.py`, called from `ConversationService.handle_inbound()` (replacing today's single `parse_dynamic_email`-only lookup). Try each step in order, stop at first hit, record which one matched in `emails.matched_via`:

1. **Reply-To alias** — if `to_email` matches `reply+{token}@{domain}`, look up `conversations.token == token` directly. (Primary path — works whenever the supplier's client honors `Reply-To`, which is the overwhelming majority of real-world replies.)
2. **In-Reply-To header** — look up `emails.message_id == in_reply_to` → get its `conversation_id`.
3. **References header** — split on whitespace, look up each id against `emails.message_id`, take the first hit.
4. **Subject token** — regex `\[Q-([A-Z0-9]{6})\]` against the subject (survives most Reply/Forward subject mangling, including `Re:`/`Fwd:` prefixes and many clients that drop Reply-To but keep subject).
5. **Hidden body token** — regex for an HTML comment `<!-- CONV:{token} -->` appended to the outgoing body (add this to `EmailMaster.build_rfq_html`) — last-resort textual survival if headers and subject are both stripped by some relay.
6. **Heuristic fallback** (only when 1–5 all fail and `to_email` is exactly some user's `sending_email` — i.e., a genuinely new, untagged thread aimed at the permanent address): candidate = conversations belonging to that user, where `supplier_email == from_email`, `created_at` within a configurable window (default 30 days), ordered by recency. If exactly one candidate → auto-bind. If multiple or none → fall through to step 7.
7. **Needs Review** — insert into `unmatched_emails` with `reason` set to whichever step got furthest, and `candidate_conversation_ids` populated from step 6's ranking (even if it didn't auto-bind) so the review UI can show suggestions instead of a blank slate.

This is intentionally a deterministic, explainable heuristic chain (no ML/embeddings) — matches the doc's own recommendation to leave true "AI similarity matching" (its Option 6) as a documented future enhancement rather than building it now; the explicit `matched_via`/`candidate_conversation_ids` fields make it trivial to bolt on later without a schema change.

### 4.3 Needs Review UI

New page `/needs-review` (see §5.2) listing `unmatched_emails` where `status='needs_review'`, each showing the raw from/to/subject/snippet plus any ranked candidates from step 6, with actions: **Bind to conversation** (pick one from candidates or search all of the current user's conversations) → runs the same append-email logic as an automatic match, sets `matched_via='manual'`, flips `unmatched_emails.status='resolved'`; or **Ignore** (`status='ignored'`, e.g. spam/irrelevant).

### 4.4 Per-provider gap closure (required for requirement 7 — "must work with all providers")

| Provider | Gap found in current code | Required fix |
|---|---|---|
| SendGrid | Inbound parser (`sendgrid_webhook.py`) only reads basic multipart fields; ignores the raw `headers` field Inbound Parse already sends. | Parse the `headers` field to extract `Message-Id`, `In-Reply-To`, `References` and populate `InboundEmail` with them. |
| Mailgun | Need to confirm `In-Reply-To`/`References`/`Message-Id` are being read from the POST payload (Mailgun exposes these as top-level fields). | Extend `mailgun_webhook.py` to pull these fields into `InboundEmail`; already has real signature verification, keep that. |
| ElasticEmail | Inbound parsing is a **stub today** (`elasticemail_webhook.py` raises not-implemented). | Implement full inbound parsing per ElasticEmail's inbound webhook payload docs (PRO plan feature) — required, this provider cannot support requirement 7 otherwise. |
| SendCloud (AuroraSendCloud) | Inbound parsing is a **stub today** (`sendcloud_webhook.py`). Also documented: attachments on replies aren't relayed by SendCloud at all. | Implement inbound parsing against SendCloud/AuroraSendCloud's inbound webhook docs. Attachment relay limitation is a provider-side constraint — document as a known limitation, not fixable in our code. |
| EngageLab | Dashboard-level "watermark" issue: EngageLab's Inbound Route only fires for genuine Reply/Forward by default; a fresh email to the permanent `sending_email` (no Reply-To honored) can fail their route match *before it ever reaches our webhook*. | Two-part fix: (a) code: our new `reply+{token}@{domain}` scheme already routes almost all real replies correctly since Reply-To is honored by most clients; (b) **manual dashboard change required** (not code): update the EngageLab Inbound Route Dashboard's matching expression to key off recipient-prefix only (not strict thread matching), exactly as recommended in `setup_docs/engagelab_guide/engagelab_new_thread_issue.md` — call this out as an operational task, not something an AI coding agent can do from the repo. |

Net effect: after these fixes, steps 1–5 of the matching chain in §4.2 work uniformly across all 5 providers for genuine replies; the previously-documented "new thread not tracked" gap for EngageLab/SendCloud is substantially narrowed (their own route-level filtering is bypassed once Reply-To is honored) but can't be claimed as 100% solved purely in our codebase — the EngageLab dashboard change and SendCloud's own route config are external, provider-console tasks that should be tracked alongside the code work.

---

## 5. UI/UX Redesign

### 5.1 Design system

- **Theme:** single light theme app-wide (per requirement 8) — refine, don't discard, the existing palette in `templates/base.html` (`--primary: #2563EB`, slate neutrals, white cards) since it's already a coherent light theme; the problem today is that it's a single giant inline `<style>` block with no reusable component classes for the *new* pages (login/register/needs-review) that don't exist yet, and no image cropping. Fix: pull tokens + components into real static assets so every page — old and new — draws from one source.
- **New structure:**
  - `static/css/tokens.css` — CSS variables (colors, spacing, radius, shadows, font stack).
  - `static/css/base.css` — resets, typography, layout shell (sidebar + topbar + content).
  - `static/css/components.css` — buttons, form inputs (incl. validation states), cards, badges, tables, modal/dialog, toast, step-indicator (for the registration wizard), avatar.
  - `static/css/pages/*.css` only if a page genuinely needs page-specific rules beyond components.
  - `static/js/app.js` — shared vanilla JS (confirm-dialog modal replacing raw `confirm()`, toast helper, disable-button-on-submit for the send form).
  - `templates/base.html` keeps `{% block content %}` but now just links the CSS/JS files; the sidebar/topbar markup moves into a `templates/_layout/` partial included by `base.html` so logged-out pages (login/register) can use a stripped-down variant (centered card, no sidebar) without duplicating the shell.
- **New shared chrome for authenticated pages:** topbar with app name + logged-in user's name/avatar + dropdown (Profile, Logout); left sidebar nav items: **Send Email**, **Tracking**, **Needs Review**.
- **Components to (re)build:** primary/secondary/danger/ghost buttons, styled modal for destructive confirmations (replacing today's `confirm()` on delete buttons), toast/flash messages for success/error (registration errors, "address already taken", send success), a step-progress indicator for the 3-step registration wizard, form field components with inline validation error text.

### 5.2 Page inventory & navigation flow

```
Not logged in:
  /login              → email + password → success: session cookie → redirect /tracking
  /register           → Step 1: account details (name, personal_email, password)
  /register/confirm-name → Step 2: confirm first/last name (Edit / Confirm)
  /register/assign-email → Step 3: candidate sending address → Confirm & Finish, or
                             alternate-email retry loop if taken
                           → success: session cookie → redirect /tracking

Logged in (all require session; unauthenticated request → redirect /login):
  /                 → redirect to /tracking (dashboard/home)
  /send             → Send RFQ / compose form (today's index.html, minus the user <select> —
                      sender is always the logged-in user; show read-only
                      "Sending from: {sending_email}"; keep supplier + product fields)
  /tracking         → PERSONAL dashboard: stat cards (my open/replied/declined conversations)
                      + list/table of MY conversations (see §5.3 scope note)
  /tracking/{conversation_id}  → thread detail (same content as today's conversation_detail.html:
                      thread of sent/received emails, attachments, DKIM/SPF/spam metadata),
                      ownership-checked against the logged-in user
  /needs-review     → list of unmatched inbound emails relevant to this user, each with
                      suggested candidate conversations + Bind / Ignore actions
  /profile          → name, personal_email (read-only), sending_email (read-only),
                      change-password form, Logout button
  POST /logout      → clear session → redirect /login

Admin only (current_user.is_admin == true; else 404/redirect):
  /admin/tracking             → all-users grid (today's tracking.html content), per-user stats
  /admin/tracking/{user_id}   → that user's full conversation list (read-only for the admin,
                                 same table view as personal /tracking)

Always public (provider callbacks, unaffected by auth):
  POST/GET /webhooks/inbound
```

### 5.3 Scope: personal dashboard for everyone, plus a lightweight admin overview

**Decision (confirmed):** `/tracking` becomes each user's **personal** dashboard — stat cards + list scoped to `conversations.user_id == current_user.id`. This matches a normal per-user app and is what every registered user sees by default.

In addition, a small role system is introduced: `users.is_admin` (default `false`). Users with `is_admin = true` also get an **`/admin/tracking`** page that reproduces today's all-users grid (per-user stat cards: conversations/replied/open, clickable through to that user's conversations) — i.e. the current cross-user overview is preserved, just moved behind a role check instead of being the default view for everyone. Nothing in this pass builds a UI to *grant* admin — set `is_admin = true` directly in the DB (e.g. via a one-off SQL statement or a small seed step) for whichever accounts should have it; a self-service admin-management UI is out of scope for this pass.

- `/tracking` — always personal, for every logged-in user (admins included — an admin also has their own conversations).
- `/admin/tracking` — only reachable if `current_user.is_admin`; otherwise 404/redirect. Lists all users with aggregate stats (same shape as today's `tracking.html` grid) and drills into `/admin/tracking/{user_id}` for that user's full conversation list (reuses the same detail/table view logic as personal `/tracking`, just parameterized by a target user id instead of "me").
- Nav: the sidebar shows an extra "Admin Overview" link only when `current_user.is_admin` is true.

### 5.4 Templates to add/replace

- **Add:** `login.html`, `register_step1.html`, `register_step2.html`, `register_step3.html`, `needs_review.html`, `profile.html`, `admin_tracking.html` (reuses the current all-users grid markup, gated by `is_admin`).
- **Replace (redesigned, same purpose):** `index.html` (send form), `tracking.html` (now personal dashboard instead of all-users grid — the old all-users grid content moves to `admin_tracking.html` instead of being replaced outright), `user_conversations.html` (reused as the admin per-user drill-down at `/admin/tracking/{user_id}`, and folded into personal `/tracking` for the non-admin case), `conversation_detail.html`.
- **Rework:** `base.html` → becomes the shared shell, delegating to the new `templates/_layout/` partials described in §5.1.

---

## 6. Environment / configuration changes

Add to `.env.example` / `src/config.py` `Settings`:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/emailpoc

SESSION_COOKIE_SECURE=true          # false only for local http dev
SESSION_TTL_DAYS=7

# Existing INBOUND_DOMAIN is reused for BOTH the per-user sending address
# and the per-conversation Reply-To alias — no new domain var needed.
INBOUND_DOMAIN=mail.jobsetu.online
```

Remove from config/usage: `FROM_EMAIL` (no longer used — sending address is always the logged-in user's `sending_email` now; keep the var only if it's still wanted as a fallback for system/transactional emails unrelated to RFQs, otherwise delete it to avoid confusion).

---

## 7. Implementation phases (ordered — hand to the AI agent phase by phase, verify each before moving on)

1. **Infra:** add Postgres deps to `pyproject.toml`, `docker-compose.yml`, `alembic` init, `DATABASE_URL` wiring in `src/config.py`.
2. **Schema:** write SQLAlchemy models (§2.2) + first Alembic migration; seed `products` from `PREDEFINED_PROJECTS`; archive `data/db.json`.
3. **Repository layer:** implement the async repositories replacing `src/db.py`'s method surface; delete `src/db.py`, `src/predefined_users.py`; update `src/app.py` DI wiring (async session per request) and `src/services/conversation_service.py` call sites (`await` everywhere).
4. **Auth:** `src/auth/` (hashing, sessions, dependencies), login/register routes + templates (Step 1 only, `sending_email` left NULL), protect existing routes with `require_login`.
5. **Address assignment:** Step 2 (confirm name) + Step 3 (assign/collision-retry `sending_email`) routes + templates; finish registration → session → redirect `/tracking`.
6. **Outbound rework:** `EmailMaster` new helpers (§4.1: token, reply-to, subject token, message-id), update all 5 provider `send_email` call sites and `ConversationService.send_rfq` to use `user.sending_email`, custom headers, explicit Message-ID/In-Reply-To/References.
7. **Inbound rework:** `src/services/matching.py` priority chain (§4.2), rewire `ConversationService.handle_inbound`; implement the ElasticEmail + SendCloud inbound parser stubs; extend SendGrid/Mailgun parsers to surface Message-ID/In-Reply-To/References (§4.4).
8. **Needs Review UI + route** (§4.3).
9. **Admin overview:** `/admin/tracking` + `/admin/tracking/{user_id}` gated on `users.is_admin` (§5.3); manually flip `is_admin = true` on at least one seed account for testing.
10. **UI redesign:** design tokens/components/layout partials (§5.1), rebuild every template (§5.4), wire the new nav/flow (§5.2) including the conditional "Admin Overview" sidebar link.
11. **Cleanup + docs:** update `README.md`, `.env.example`, delete now-unused files (`src/predefined_projects.py` after seeding, old JSON db docs), sanity-pass over `RFQ_EMAIL_FLOW.md`/`email_tracking.md` references so they reflect the new architecture instead of the old dynamic-per-conversation-address one.

---

## 8. Decisions confirmed with the user

1. **No historical data migration** from `data/db.json` — fresh start (§2.3). `data/db.json` is archived, not deleted.
2. **Personal dashboard + lightweight admin overview**: `/tracking` is personal to every user; a new `is_admin` flag (set directly in the DB, no self-service UI yet) unlocks `/admin/tracking` reproducing today's all-users grid (§5.3).
3. **Alternate email during Step 3 collision** is used only to derive a new sending-address candidate — it does **not** replace the account's login `personal_email` (§3.2).

## 9. Remaining open items (confirm before/while implementing)

1. **Sessions over JWT** for auth (§3.1) — confirm no requirement for stateless/multi-service auth that would push toward JWT instead.
2. **EngageLab dashboard reconfiguration** (§4.4) is a manual operational step outside the codebase — confirm someone will actually do this in the EngageLab console, otherwise the "new thread" gap for that provider remains even after the code changes.
