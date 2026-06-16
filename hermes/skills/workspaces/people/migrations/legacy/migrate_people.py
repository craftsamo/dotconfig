#!/usr/bin/env python3
"""One-time legacy migration: People per-person JSON (schema_version 1) -> people.db (v1).

Reads the old flat registry (SRC_DIR/<id>.json), builds a fresh people.db from
../../schema.sql, seeds base lookups + the person_unknown sentinel, and transforms each
record per the agreed mapping:
  * id / display_name kept as-is (id stays the bare slug consumers reference).
  * kind = 'self' for the `master` record, else 'individual'.
  * review_status = 'confirmed' (existing records are curated).
  * nationality / residence (demonym or country name) -> ISO 3166-1 alpha-2 via NAME2COUNTRY.
  * languages (English/Indonesian/Malay/Japanese) -> ISO 639-1 via NAME2LANG.
  * preferred_language = the sole language when unambiguous; multi-language -> NULL (never guessed).
  * contacts.{github,telegram} (non-null) -> person_contacts; telegram is primary when present.
  * display_name + aliases[] -> person_aliases (display_name primary).
  * notes[] -> person_notes. timezone/preferred_contact_channel start NULL (not in source).
Unmapped country/language values are left NULL and reported (review later) rather than guessed.

Usage: migrate_people.py SRC_DIR NEW_DB
"""
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / "schema.sql"
SENTINEL = "person_unknown"

SEED_COUNTRIES = {"JP": "Japan", "MY": "Malaysia", "ID": "Indonesia"}
SEED_LANGUAGES = {"ja": "Japanese", "en": "English", "id": "Indonesian", "ms": "Malay"}
SEED_CHANNELS = [
    ("github", "GitHub", 0), ("telegram", "Telegram", 0), ("x", "X / Twitter", 0),
    ("website", "Website", 0), ("signal", "Signal", 0), ("matrix", "Matrix", 0),
    ("discord", "Discord", 0), ("linkedin", "LinkedIn", 0),
    ("email", "Email", 1), ("phone", "Phone", 1),
]
SEED_AXES = {
    "comms": "Communication preferences", "how_we_met": "How we met",
    "team": "Team", "interests": "Interests", "availability": "Availability",
}

NAME2COUNTRY = {
    "japanese": "JP", "japan": "JP",
    "indonesia": "ID", "indonesian": "ID",
    "malaysia": "MY", "malaysian": "MY",
}
NAME2LANG = {
    "english": "en", "indonesian": "id", "malay": "ms", "japanese": "ja",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_text(s):
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", s).strip()


def normalize_handle(s):
    n = normalize_text(s)
    n = re.sub(r"^(https?://)?(t\.me/|x\.com/|twitter\.com/|github\.com/)", "", n)
    return n.lstrip("@").strip("/")


def seed_base(con):
    for code, label in SEED_COUNTRIES.items():
        con.execute("INSERT OR IGNORE INTO countries(code, label) VALUES (?,?)", (code, label))
    for code, label in SEED_LANGUAGES.items():
        con.execute("INSERT OR IGNORE INTO languages(code, label) VALUES (?,?)", (code, label))
    for ch, label, sens in SEED_CHANNELS:
        con.execute("INSERT OR IGNORE INTO contact_channels(channel, label, is_sensitive) VALUES (?,?,?)", (ch, label, sens))
    for ax, label in SEED_AXES.items():
        con.execute("INSERT OR IGNORE INTO person_tag_axes(axis, label, review_status) VALUES (?,?, 'confirmed')", (ax, label))
    now = now_iso()
    con.execute("INSERT OR IGNORE INTO persons(id, display_name, kind, status, review_status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)", (SENTINEL, "Unknown person", "individual", "active", "confirmed", now, now))


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: migrate_people.py SRC_DIR NEW_DB")
    src_dir, new_db = Path(sys.argv[1]), Path(sys.argv[2])
    if new_db.exists():
        new_db.unlink()
    new_db.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in src_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"no *.json in {src_dir}")

    dst = sqlite3.connect(str(new_db))
    dst.row_factory = sqlite3.Row
    dst.executescript(SCHEMA.read_text(encoding="utf-8"))
    dst.execute("PRAGMA foreign_keys = ON")
    dst.execute("BEGIN")
    dst.execute("PRAGMA defer_foreign_keys = ON")
    seed_base(dst)

    warnings = []
    now = now_iso()
    n_persons = n_alias = n_contact = n_lang = n_nat = n_note = 0

    for f in files:
        r = json.loads(f.read_text(encoding="utf-8"))
        pid = r["id"]
        kind = "self" if pid == "master" else "individual"
        residence = r.get("residence")
        residence_code = None
        if residence:
            residence_code = NAME2COUNTRY.get(normalize_text(residence))
            if residence_code:
                dst.execute("INSERT OR IGNORE INTO countries(code, label) VALUES (?,?)", (residence_code, residence))
            else:
                warnings.append(f"{pid}: residence {residence!r} unmapped -> NULL")
        langs = r.get("languages") or []
        lang_codes = []
        for lname in langs:
            code = NAME2LANG.get(normalize_text(lname))
            if code:
                dst.execute("INSERT OR IGNORE INTO languages(code, label) VALUES (?,?)", (code, lname))
                lang_codes.append(code)
            else:
                warnings.append(f"{pid}: language {lname!r} unmapped -> skipped")
        preferred_language = lang_codes[0] if len(lang_codes) == 1 else None

        dst.execute(
            "INSERT INTO persons(id, display_name, kind, status, review_status, residence_country, "
            "preferred_language, preferred_contact_channel, timezone, last_updated, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, r["display_name"], kind, r.get("status", "active"), "confirmed", residence_code,
             preferred_language, None, None, r.get("last_updated"), now, now))
        n_persons += 1

        # aliases: display_name primary + extras
        seen = set()
        for i, name in enumerate([r["display_name"]] + (r.get("aliases") or [])):
            norm = normalize_text(name)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            dst.execute("INSERT OR IGNORE INTO person_aliases(person_id, alias, alias_norm, is_primary) VALUES (?,?,?,?)",
                        (pid, name, norm, 1 if i == 0 else 0))
            n_alias += 1

        # nationality -> primary nationality
        nat = r.get("nationality")
        if nat:
            code = NAME2COUNTRY.get(normalize_text(nat))
            if code:
                dst.execute("INSERT OR IGNORE INTO countries(code, label) VALUES (?,?)", (code, nat))
                dst.execute("INSERT OR IGNORE INTO person_nationalities(person_id, country, is_primary) VALUES (?,?,1)", (pid, code))
                n_nat += 1
            else:
                warnings.append(f"{pid}: nationality {nat!r} unmapped -> skipped")

        # languages
        for idx, code in enumerate(lang_codes):
            is_primary = 1 if len(lang_codes) == 1 else 0
            dst.execute("INSERT OR IGNORE INTO person_languages(person_id, language, proficiency, is_primary) VALUES (?,?,?,?)",
                        (pid, code, None, is_primary))
            n_lang += 1

        # contacts: telegram primary if present, else github
        contacts = r.get("contacts") or {}
        tg = contacts.get("telegram")
        gh = contacts.get("github")
        for channel, handle in (("telegram", tg), ("github", gh)):
            if handle:
                is_primary = 1 if (channel == "telegram") or (channel == "github" and not tg) else 0
                dst.execute("INSERT OR IGNORE INTO person_contacts(person_id, channel, handle, handle_norm, is_primary) VALUES (?,?,?,?,?)",
                            (pid, channel, handle, normalize_handle(handle), is_primary))
                n_contact += 1

        # notes
        for i, note in enumerate(r.get("notes") or [], start=1):
            dst.execute("INSERT INTO person_notes(person_id, seq, text, created_at) VALUES (?,?,?,?)", (pid, i, note, now))
            n_note += 1

    bad = dst.execute("PRAGMA foreign_key_check").fetchall()
    if bad:
        dst.execute("ROLLBACK")
        raise SystemExit(f"foreign_key_check failed: {[tuple(b) for b in bad]}")
    dst.execute("COMMIT")

    print(f"migrated {len(files)} JSON record(s) -> {new_db}")
    print(f"  persons        {n_persons} (+1 sentinel = {dst.execute('SELECT COUNT(*) FROM persons').fetchone()[0]})")
    print(f"  aliases        {n_alias}")
    print(f"  contacts       {n_contact}")
    print(f"  languages      {n_lang}")
    print(f"  nationalities  {n_nat}")
    print(f"  notes          {n_note}")
    if warnings:
        print("warnings:")
        for w in warnings:
            print(f"  - {w}")
    dst.close()


if __name__ == "__main__":
    main()
