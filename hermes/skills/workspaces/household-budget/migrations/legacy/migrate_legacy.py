#!/usr/bin/env python3
"""One-time legacy migration: old budget.db (v1) -> new budget.db (v2).

Reads OLD_DB (read-only), builds a fresh v2 DB from ../schema.sql, and transforms
the data per the agreed mapping:
  * claim_parties  -> counterparties (cp_*) + projects (proj_*)
      - project review_status = confirmed + dir_path when a ~/Workspaces/Projects/<dir>
        matches the name; otherwise needs_review with no dir_path.
      - claim_unknown -> cp_unknown sentinel (no project).
  * reimbursable transactions get project_id + claim.counterparty_id from their claim party.
  * store/item ids: strip the leaked `_pending_` segment -> stable ids (state kept in
    review_status). Collisions get a numeric suffix.
  * transfers / tags start empty (legacy data has no transfers or income).

Usage: migrate_legacy.py OLD_DB NEW_DB
"""
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA = SKILL_DIR / "schema.sql"
PROJECTS_DIR = Path.home() / "Workspaces" / "Projects"


def normalize_text(s):
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", s).strip()


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "unknown"


def strip_pending(eid, prefix):
    token = prefix + "pending_"
    if eid.startswith(token):
        return prefix + eid[len(token):]
    return eid


def build_strip_map(ids, prefix):
    m, used = {}, set()
    for old in sorted(ids):
        new = strip_pending(old, prefix)
        if new in used:
            i = 2
            while f"{new}_{i}" in used:
                i += 1
            new = f"{new}_{i}"
        used.add(new)
        m[old] = new
    return m


def aliases_of(src, etype, eid):
    return [r["alias"] for r in src.execute(
        "SELECT alias FROM entity_aliases WHERE entity_type=? AND entity_id=? ORDER BY is_primary DESC, alias",
        (etype, eid))]


def add_aliases(dst, etype, eid, primary, extra):
    seen, rows = set(), []
    for i, name in enumerate([primary] + list(extra or [])):
        if not name:
            continue
        norm = normalize_text(name)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        rows.append((etype, eid, name, norm, 1 if i == 0 else 0))
    dst.executemany("INSERT OR IGNORE INTO entity_aliases(entity_type, entity_id, alias, alias_norm, is_primary) "
                    "VALUES (?,?,?,?,?)", rows)


def main():
    old_db, new_db = sys.argv[1], sys.argv[2]
    new_path = Path(new_db)
    if new_path.exists():
        new_path.unlink()
    src = sqlite3.connect(f"file:{old_db}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(new_db)
    dst.row_factory = sqlite3.Row
    dst.executescript(SCHEMA.read_text(encoding="utf-8"))
    dst.execute("PRAGMA foreign_keys = ON")
    dst.execute("BEGIN")
    dst.execute("PRAGMA defer_foreign_keys = ON")

    # id maps
    store_map = build_strip_map([r["id"] for r in src.execute("SELECT id FROM stores")], "store_")
    item_map = build_strip_map([r["id"] for r in src.execute("SELECT id FROM items")], "item_")

    project_dirs = [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()] if PROJECTS_DIR.exists() else []

    def match_dir(name):
        key = slugify(name).replace("_", "")
        for d in project_dirs:
            if slugify(d).replace("_", "") == key:
                return d
        return None

    # currencies / categories
    for r in src.execute("SELECT * FROM currencies"):
        dst.execute("INSERT INTO currencies(code,label,decimals) VALUES (?,?,?)",
                    (r["code"], r["label"], r["decimals"]))
    for r in src.execute("SELECT * FROM categories"):
        dst.execute("INSERT INTO categories(id,label,parent_id,review_status) VALUES (?,?,?,?)",
                    (r["id"], r["label"], r["parent_id"], r["review_status"]))
        add_aliases(dst, "category", r["id"], r["label"], aliases_of(src, "category", r["id"]))

    # payment accounts
    for r in src.execute("SELECT * FROM payment_accounts"):
        dst.execute("INSERT INTO payment_accounts(id,label,type,default_currency,display_hint,review_status) "
                    "VALUES (?,?,?,?,?,?)",
                    (r["id"], r["label"], r["type"], r["default_currency"], r["display_hint"], r["review_status"]))
        add_aliases(dst, "payment_account", r["id"], r["label"], aliases_of(src, "payment_account", r["id"]))
    for r in src.execute("SELECT * FROM payment_account_currencies"):
        dst.execute("INSERT INTO payment_account_currencies(payment_account_id,currency) VALUES (?,?)",
                    (r["payment_account_id"], r["currency"]))

    # claim_parties -> counterparties (+ projects)
    cp_map, proj_map = {}, {}
    for r in src.execute("SELECT * FROM claim_parties"):
        old = r["id"]
        slug = old[len("claim_"):] if old.startswith("claim_") else slugify(r["canonical_name"])
        if old == "claim_unknown":
            cp = "cp_unknown"
        else:
            cp = "cp_" + slug
        cp_map[old] = cp
        dst.execute("INSERT INTO counterparties(id,canonical_name,type,default_scope,review_status) VALUES (?,?,?,?,?)",
                    (cp, r["canonical_name"], r["type"], r["default_scope"], r["review_status"]))
        add_aliases(dst, "counterparty", cp, r["canonical_name"], aliases_of(src, "claim_party", old))
        if old != "claim_unknown":
            proj = "proj_" + slug
            proj_map[old] = proj
            d = match_dir(r["canonical_name"])
            dir_path = str(PROJECTS_DIR / d) if d else None
            review = "confirmed" if d else "needs_review"
            dst.execute("INSERT INTO projects(id,canonical_name,dir_path,default_counterparty_id,default_scope,"
                        "review_status,last_seen_at) VALUES (?,?,?,?,?,?,?)",
                        (proj, r["canonical_name"], dir_path, cp, r["default_scope"], review, None))
            add_aliases(dst, "project", proj, r["canonical_name"], aliases_of(src, "claim_party", old))

    # stores / items
    for r in src.execute("SELECT * FROM stores"):
        nid = store_map[r["id"]]
        dst.execute("INSERT INTO stores(id,canonical_name,default_category_id,review_status,last_seen_at) "
                    "VALUES (?,?,?,?,?)",
                    (nid, r["canonical_name"], r["default_category_id"], r["review_status"], r["last_seen_at"]))
        add_aliases(dst, "store", nid, r["canonical_name"], aliases_of(src, "store", r["id"]))
    for r in src.execute("SELECT * FROM items"):
        nid = item_map[r["id"]]
        dst.execute("INSERT INTO items(id,canonical_name,default_category_id,review_status,last_seen_at) "
                    "VALUES (?,?,?,?,?)",
                    (nid, r["canonical_name"], r["default_category_id"], r["review_status"], r["last_seen_at"]))
        add_aliases(dst, "item", nid, r["canonical_name"], aliases_of(src, "item", r["id"]))
    for r in src.execute("SELECT * FROM store_payment_options"):
        dst.execute("INSERT INTO store_payment_options(store_id,payment_account_id,currency,is_default) VALUES (?,?,?,?)",
                    (store_map[r["store_id"]], r["payment_account_id"], r["currency"], r["is_default"]))

    # subscriptions
    for r in src.execute("SELECT * FROM subscriptions"):
        cp = cp_map.get(r["claim_party_id"])
        pj = proj_map.get(r["claim_party_id"])
        dst.execute("INSERT INTO subscriptions(id,name,store_id,item_id,budget_scope,project_id,counterparty_id,"
                    "billing_cycle,expected_value,expected_currency,review_status,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["id"], r["name"], store_map.get(r["store_id"]), item_map.get(r["item_id"]),
                     r["budget_scope"], pj, cp, r["billing_cycle"], r["expected_value"], r["expected_currency"],
                     r["review_status"], r["note"]))

    # transactions (+ line_items, claims)
    txn_cols = ("id,date,type,amount_value,amount_currency,reporting_value,reporting_currency,fx_rate,fx_date,"
                "fx_source,store_raw_name,store_id,store_confidence,payment_account_id,payment_raw_text,"
                "payment_confidence,category_id,budget_scope,project_id,status,confidence,source_kind,"
                "source_document_saved,source_raw_text_saved,source_summary,source_organization,source_external_ref,"
                "note,subscription_id,created_at,updated_at")
    for t in src.execute("SELECT * FROM transactions"):
        claim = src.execute("SELECT * FROM claims WHERE txn_id=?", (t["id"],)).fetchone()
        project_id = proj_map.get(claim["claim_party_id"]) if claim else None
        dst.execute(f"INSERT INTO transactions({txn_cols}) VALUES ({','.join('?'*31)})",
                    (t["id"], t["date"], t["type"], t["amount_value"], t["amount_currency"],
                     t["reporting_value"], t["reporting_currency"], t["fx_rate"], t["fx_date"], t["fx_source"],
                     t["store_raw_name"], store_map.get(t["store_id"]), t["store_confidence"],
                     t["payment_account_id"], t["payment_raw_text"], t["payment_confidence"],
                     t["category_id"], t["budget_scope"], project_id, t["status"], t["confidence"],
                     t["source_kind"], t["source_document_saved"], t["source_raw_text_saved"],
                     t["source_summary"], t["source_organization"], None,
                     t["note"], t["subscription_id"], t["created_at"], t["updated_at"]))
        for li in src.execute("SELECT * FROM transaction_line_items WHERE txn_id=? ORDER BY seq", (t["id"],)):
            dst.execute("INSERT INTO transaction_line_items(txn_id,seq,raw_name,item_id,amount_value,amount_currency,"
                        "category_id,confidence) VALUES (?,?,?,?,?,?,?,?)",
                        (li["txn_id"], li["seq"], li["raw_name"], item_map.get(li["item_id"]),
                         li["amount_value"], li["amount_currency"], li["category_id"], li["confidence"]))
        if claim:
            dst.execute("INSERT INTO claims(txn_id,counterparty_id,status,expected_value,expected_currency,"
                        "submitted_at,reimbursed_at,linked_original_txn_id,linked_reimbursement_txn_id,note) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (claim["txn_id"], cp_map[claim["claim_party_id"]], claim["status"], claim["expected_value"],
                         claim["expected_currency"], claim["submitted_at"], claim["reimbursed_at"],
                         claim["linked_original_txn_id"], claim["linked_reimbursement_txn_id"], claim["note"]))

    bad = dst.execute("PRAGMA foreign_key_check").fetchall()
    if bad:
        dst.execute("ROLLBACK")
        raise SystemExit(f"foreign_key_check failed: {[tuple(b) for b in bad]}")
    dst.execute("COMMIT")

    def c(con, t):
        return con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print("migrated -> ", new_db)
    print(f"  transactions {c(src,'transactions')} -> {c(dst,'transactions')}")
    print(f"  line_items   {c(src,'transaction_line_items')} -> {c(dst,'transaction_line_items')}")
    print(f"  claims       {c(src,'claims')} -> {c(dst,'claims')}")
    print(f"  stores       {c(src,'stores')} -> {c(dst,'stores')}")
    print(f"  items        {c(src,'items')} -> {c(dst,'items')}")
    print(f"  counterparties (from claim_parties {c(src,'claim_parties')}) -> {c(dst,'counterparties')}")
    print(f"  projects     -> {c(dst,'projects')}")
    print(f"  subscriptions {c(src,'subscriptions')} -> {c(dst,'subscriptions')}")
    src.close()
    dst.close()


if __name__ == "__main__":
    main()
