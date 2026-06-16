-- Projects registry — SQLite schema v1 (engine: pj). stdlib sqlite3 only.
--
-- Central registry for ALL Projects groups: project identity, repos, official links, the
-- team-membership SOURCE OF TRUTH, and flexible tags. The DB is the source of truth; JSON/CSV
-- under .registry/export/ is a regenerable mirror. See ../references/data-model.md (the canon).
--
-- Principles (mirror People / HouseholdBudget):
--   * Stable, state-free ids: review_status carries data state, never the id. A project id is
--     the Projects/<id> directory name (e.g. ExampleProject) == the cross-system join key
--     (People memberships' project_id; the budget reconciles via dir_path / aliases).
--   * Normalized aliases (NFKC + casefold) so the budget's proj_*/aliases reconcile.
--   * Memberships mirror People's mirror tables 1:1, so `pj members` round-trips the exact
--     shape People consumed from teams/members/*.json (now retired — pj is the source).
--   * person_id is NOT a SQL FK (persons live in People's separate DB). Cross-domain checks go
--     through the People CLI (`pp`), read-only — never by opening people.db. See _cross.
--   * Extensible: project_tag_axes + project_tags / membership_tags add free aggregation axes
--     (stage, priority, domain, engagement, …) with no schema change. Report with `pj report`.
--   * Versioned (user_version); evolve via migrations/, never a destructive rebuild.
--   * Sensitivity: member calibration (working_relationship, notes) is semi-private — summarize,
--     never dump raw; the DB lives outside any git tree.

PRAGMA foreign_keys = ON;

-- ============================ core: projects (groups) ============================
-- A "project" == one directory group under ~/Workspaces/Projects/<id>. Spending dimension for
-- the budget; org/team container for repos + memberships.
CREATE TABLE projects (
  id             TEXT PRIMARY KEY,            -- == Projects/<id> dir name (e.g. ExampleProject)
  slug           TEXT NOT NULL,               -- normalized lower-kebab (example-project); URLs/match
  canonical_name TEXT NOT NULL,               -- human ("Career Code Club")
  kind           TEXT NOT NULL DEFAULT 'category'
                   CHECK (kind IN ('org','client','category','personal','external')),
  status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','inactive','archived')),
  dir_path       TEXT,                        -- abs path, or NULL for kind='external' (no dir, e.g. branaid)
  summary        TEXT,
  review_status  TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  last_updated   TEXT,                        -- from source / AGENTS.md
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE TABLE project_aliases (                -- searchable names for budget/handle reconciliation
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  alias      TEXT NOT NULL,
  alias_norm TEXT NOT NULL,                   -- NFKC + casefold + collapse spaces
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  PRIMARY KEY (project_id, alias_norm)
);
CREATE INDEX ix_project_alias_norm ON project_aliases(alias_norm);

CREATE TABLE project_links (                  -- official URLs (from docs/about/official-links.md)
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('landing','x','github','docs','discord','other')),
  url        TEXT NOT NULL,
  label      TEXT,
  PRIMARY KEY (project_id, kind, url)
);

-- ============================ repos (github wiring) ============================
-- One row per repo belonging to a project. Records identity + where the clone/symlink live;
-- `pj link-repo` materializes ghq clone + Projects/<group>/github/<name> symlink.
CREATE TABLE repos (
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,                -- repo name (courses, dashboard, learning-app)
  owner         TEXT,                         -- org/user (example-project, example-org)
  host          TEXT NOT NULL DEFAULT 'github.com',
  url           TEXT,                         -- https://<host>/<owner>/<name>
  ghq_path      TEXT,                         -- ~/ghq/<host>/<owner>/<name> (clone) or NULL
  link_path     TEXT,                         -- Projects/<group>/github/<name> (symlink) or NULL
  has_agents_md INTEGER NOT NULL DEFAULT 0 CHECK (has_agents_md IN (0,1)),
  summary       TEXT,
  status        TEXT NOT NULL DEFAULT 'declared'
                   CHECK (status IN ('declared','linked','missing','archived')),
  review_status TEXT NOT NULL CHECK (review_status IN ('needs_review','confirmed','ignored')),
  PRIMARY KEY (project_id, name)
);
CREATE INDEX ix_repos_project ON repos(project_id);

-- ============================ memberships (SOURCE OF TRUTH) ============================
-- Shape is 1:1 with People's mirror (person_project_memberships + membership_*), so `pj members`
-- reproduces exactly what People consumed from teams/members/*.json. person_id == People persons.id
-- (validated through the People CLI, not a SQL FK — separate DB).
CREATE TABLE memberships (
  project_id           TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  person_id            TEXT NOT NULL,
  status               TEXT,                  -- active|inactive (free; mirrors source)
  working_relationship TEXT,
  can_merge            INTEGER NOT NULL DEFAULT 0 CHECK (can_merge IN (0,1)),
  can_deploy           INTEGER NOT NULL DEFAULT 0 CHECK (can_deploy IN (0,1)),
  last_updated         TEXT,
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id)
);
CREATE INDEX ix_membership_person ON memberships(person_id);

CREATE TABLE membership_roles (
  project_id TEXT NOT NULL, person_id TEXT NOT NULL, role TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, role),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE TABLE membership_responsibilities (
  project_id TEXT NOT NULL, person_id TEXT NOT NULL, responsibility TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, responsibility),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE TABLE membership_areas (
  project_id TEXT NOT NULL, person_id TEXT NOT NULL, area TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, area),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE TABLE membership_permission_scopes (   -- permissions.can_approve[] / can_review[]
  project_id TEXT NOT NULL, person_id TEXT NOT NULL,
  action     TEXT NOT NULL CHECK (action IN ('approve','review')),
  target     TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, action, target),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE TABLE membership_notes (
  project_id TEXT NOT NULL, person_id TEXT NOT NULL, seq INTEGER NOT NULL, text TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, seq),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE TABLE membership_contacts (            -- project_contacts {channel: handle}
  project_id TEXT NOT NULL, person_id TEXT NOT NULL, channel TEXT NOT NULL, handle TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, channel),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);

-- ============================ extensibility: flexible tags ============================
-- New axis = one row in project_tag_axes (mirrors budget tag_axes / People person_tag_axes).
-- The same axis registry serves both project-level and membership-level tags.
CREATE TABLE project_tag_axes (               -- e.g. stage, priority, domain, engagement, comp_model
  axis          TEXT PRIMARY KEY,
  label         TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'confirmed'
                  CHECK (review_status IN ('needs_review','confirmed','ignored'))
);

CREATE TABLE project_tags (                   -- tag a project on a free axis
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  axis       TEXT NOT NULL REFERENCES project_tag_axes(axis),
  value      TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  PRIMARY KEY (project_id, axis, value_norm)
);
CREATE INDEX ix_project_tags_axis ON project_tags(axis, value_norm);

CREATE TABLE membership_tags (                -- tag a person×project on a free axis
  project_id TEXT NOT NULL, person_id TEXT NOT NULL,
  axis       TEXT NOT NULL REFERENCES project_tag_axes(axis),
  value      TEXT NOT NULL, value_norm TEXT NOT NULL,
  PRIMARY KEY (project_id, person_id, axis, value_norm),
  FOREIGN KEY (project_id, person_id) REFERENCES memberships(project_id, person_id) ON DELETE CASCADE
);
CREATE INDEX ix_membership_tags_axis ON membership_tags(axis, value_norm);

-- ============================ audit (git-less change history) ============================
CREATE TABLE project_audit (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  action     TEXT NOT NULL,                   -- upsert-project|set-status|rename|merge|repo|link|member|tag|import|export|…
  tbl        TEXT,
  entity     TEXT,                            -- project_id, "<project_id>/<person_id>", repo name, …
  field      TEXT,
  old_value  TEXT,
  new_value  TEXT,
  note       TEXT
);
CREATE INDEX ix_project_audit_entity ON project_audit(entity);

-- ============================ reporting views ============================
CREATE VIEW v_active_projects AS
  SELECT id, canonical_name, kind, dir_path FROM projects WHERE status = 'active';

CREATE VIEW v_project_member_counts AS
  SELECT p.id, p.canonical_name, COUNT(m.person_id) AS members
  FROM projects p LEFT JOIN memberships m ON m.project_id = p.id
  GROUP BY p.id, p.canonical_name;

PRAGMA user_version = 1;
