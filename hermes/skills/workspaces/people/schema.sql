-- People — SQLite schema v1 (engine: pp). stdlib sqlite3 only.
--
-- Canonical person registry: identity, aliases, contacts, languages, nationalities,
-- free tags, person<->person relationships, and a regenerable mirror of Projects team
-- memberships. Consumed by the household budget (counterparties.person_id) and the
-- message-reply skill (sender resolution + comms context), keyed by person_id.
--
-- Principles (mirrors HouseholdBudget):
--   * Stable, state-free ids: review_status carries data state, never the id. Person id is
--     a bare lowercase slug (ar, oy, master) == the person_id consumers reference.
--   * Normalized aliases/handles (NFKC + casefold) for sender/name lookup.
--   * Lookups (countries/languages/contact_channels) are ISO-ish code registries so
--     nationality/residence/language are consistent and joinable.
--   * Mirror tables (person_project_memberships + membership_*) are regenerable from
--     ~/Workspaces/Projects/<project>/teams/members/<person_id>.json (those files are the
--     source of truth); rebuilt by `pp import-projects`.
--   * Versioned (user_version); evolve via migrations/, never a destructive rebuild.
--   * Privacy: sensitive channels (phone/email) are flagged is_sensitive and not populated
--     by default. Never store gov IDs, home addresses, secrets, or full wallet keys.

PRAGMA foreign_keys = ON;

-- ============================ registries / lookups ============================
CREATE TABLE countries (              -- ISO 3166-1 alpha-2 (e.g. JP, MY, ID)
  code  TEXT PRIMARY KEY,
  label TEXT NOT NULL
);

CREATE TABLE languages (              -- ISO 639-1 (e.g. ja, en, id, ms)
  code  TEXT PRIMARY KEY,
  label TEXT NOT NULL
);

CREATE TABLE contact_channels (       -- github, telegram, x, website, signal, matrix, email, phone
  channel      TEXT PRIMARY KEY,
  label        TEXT NOT NULL,
  is_sensitive INTEGER NOT NULL DEFAULT 0 CHECK (is_sensitive IN (0,1))
);

CREATE TABLE person_tag_axes (        -- comms, how_we_met, team, interests, availability, …
  axis          TEXT PRIMARY KEY,
  label         TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'confirmed' CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

-- ============================ core: persons ============================
CREATE TABLE persons (
  id                        TEXT PRIMARY KEY,         -- bare slug; == person_id used by consumers
  display_name              TEXT NOT NULL,
  kind                      TEXT NOT NULL DEFAULT 'individual' CHECK (kind IN ('self','individual')),
  status                    TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  review_status             TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  residence_country         TEXT REFERENCES countries(code),
  preferred_language        TEXT REFERENCES languages(code),
  preferred_contact_channel TEXT REFERENCES contact_channels(channel),
  timezone                  TEXT,                     -- IANA tz (e.g. Asia/Tokyo)
  last_updated              TEXT,
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL
);

CREATE TABLE person_aliases (
  person_id  TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  alias      TEXT NOT NULL,
  alias_norm TEXT NOT NULL,                           -- NFKC + casefold + collapse spaces
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (person_id, alias_norm)
);
CREATE INDEX ix_person_alias_norm ON person_aliases(alias_norm);

CREATE TABLE person_contacts (
  person_id   TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  channel     TEXT NOT NULL REFERENCES contact_channels(channel),
  handle      TEXT NOT NULL,
  handle_norm TEXT NOT NULL,                          -- normalized for sender resolution
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (person_id, channel, handle_norm)
);
CREATE INDEX ix_person_contact_handle ON person_contacts(channel, handle_norm);

CREATE TABLE person_languages (
  person_id   TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  language    TEXT NOT NULL REFERENCES languages(code),
  proficiency TEXT CHECK (proficiency IN ('native','fluent','conversational','basic')),
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (person_id, language)
);

CREATE TABLE person_nationalities (
  person_id  TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  country    TEXT NOT NULL REFERENCES countries(code),
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (person_id, country)
);

CREATE TABLE person_notes (
  person_id  TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  seq        INTEGER NOT NULL,
  text       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (person_id, seq)
);

CREATE TABLE person_tags (            -- flexible axes (mirrors HouseholdBudget tags)
  person_id  TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  axis       TEXT NOT NULL REFERENCES person_tag_axes(axis),
  value      TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  PRIMARY KEY (person_id, axis, value_norm)
);
CREATE INDEX ix_person_tags_axis ON person_tags(axis, value_norm);

CREATE TABLE person_relationships (   -- directed person -> person edge
  from_person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  to_person_id   TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  type           TEXT NOT NULL,        -- colleague, supervisor, reports_to, friend, family, …
  note           TEXT,
  PRIMARY KEY (from_person_id, to_person_id, type),
  CHECK (from_person_id <> to_person_id)
);
CREATE INDEX ix_person_rel_to ON person_relationships(to_person_id);

CREATE TABLE person_audit (           -- change history (Personal is git-less)
  seq       INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id TEXT,                      -- no FK: audit survives delete/rename/merge
  ts        TEXT NOT NULL,
  action    TEXT NOT NULL,             -- create|update|set-status|alias|contact|lang|nat|note|tag|rel|rename|merge|import-projects
  tbl       TEXT,
  field     TEXT,
  old_value TEXT,
  new_value TEXT,
  note      TEXT
);
CREATE INDEX ix_person_audit_person ON person_audit(person_id);

-- ============================ mirror: project memberships ============================
-- Regenerable from ~/Workspaces/Projects/<project>/teams/members/<person_id>.json
-- (those files are the source of truth). Rebuilt by `pp import-projects`.
CREATE TABLE person_project_memberships (
  person_id            TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
  project_id           TEXT NOT NULL,        -- Projects dir slug (e.g. ExampleProject)
  status               TEXT,
  working_relationship TEXT,
  can_merge            INTEGER NOT NULL DEFAULT 0 CHECK (can_merge IN (0,1)),
  can_deploy           INTEGER NOT NULL DEFAULT 0 CHECK (can_deploy IN (0,1)),
  source_path          TEXT,
  last_synced_at       TEXT,
  PRIMARY KEY (person_id, project_id)
);
CREATE INDEX ix_membership_project ON person_project_memberships(project_id);

CREATE TABLE membership_roles (
  person_id  TEXT NOT NULL,
  project_id TEXT NOT NULL,
  role       TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, role),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

CREATE TABLE membership_responsibilities (
  person_id      TEXT NOT NULL,
  project_id     TEXT NOT NULL,
  responsibility TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, responsibility),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

CREATE TABLE membership_areas (
  person_id  TEXT NOT NULL,
  project_id TEXT NOT NULL,
  area       TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, area),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

CREATE TABLE membership_permission_scopes (
  person_id  TEXT NOT NULL,
  project_id TEXT NOT NULL,
  action     TEXT NOT NULL CHECK (action IN ('approve','review')),
  target     TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, action, target),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

CREATE TABLE membership_notes (
  person_id  TEXT NOT NULL,
  project_id TEXT NOT NULL,
  seq        INTEGER NOT NULL,
  text       TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, seq),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

CREATE TABLE membership_contacts (    -- per-project contact overrides (project_contacts)
  person_id  TEXT NOT NULL,
  project_id TEXT NOT NULL,
  channel    TEXT NOT NULL,
  handle     TEXT NOT NULL,
  PRIMARY KEY (person_id, project_id, channel),
  FOREIGN KEY (person_id, project_id) REFERENCES person_project_memberships(person_id, project_id) ON DELETE CASCADE
);

-- ============================ reporting views ============================
CREATE VIEW v_active_persons AS
  SELECT id, display_name, kind, residence_country, preferred_language, timezone
  FROM persons WHERE status = 'active';

CREATE VIEW v_person_membership_counts AS
  SELECT p.id, p.display_name, COUNT(m.project_id) AS projects
  FROM persons p LEFT JOIN person_project_memberships m ON m.person_id = p.id
  GROUP BY p.id, p.display_name;

PRAGMA user_version = 1;
