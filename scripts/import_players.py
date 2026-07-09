#!/usr/bin/env python3
"""
Import players from CSV into tt-auth and tt-members databases.

Usage:
    python scripts/import_players.py <csv_file> [--dry-run] [--password PASSWORD]

Example:
    python scripts/import_players.py ~/Downloads/player-list.csv --dry-run
    python scripts/import_players.py ~/Downloads/player-list.csv --password Tigers2026!
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import json

import psycopg
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AUTH_DSN = "postgresql+psycopg://tt_auth:tt_auth_password@localhost:5432/tt_auth"
MEMBERS_DSN = "postgresql+psycopg://tt_members:tt_members_password@localhost:5432/tt_members"
DEFAULT_PASSWORD = "Tigers2026!"
TEAM_ID = 4          # SENIORS
TEAM_CODE = "SENIORS"
TEAM_NAME = "Seniors"

# Football position prefixes that appear in user_name
POSITION_PREFIXES = {
    "WR", "QB", "RB", "OL", "DL", "LB", "DB", "TE",
    "C", "K", "P", "LS", "DE", "DT", "G", "T", "SS", "FS",
    "OL/DL", "C/DB",
}

# Prefixes that indicate staff (no football position)
STAFF_PREFIXES = {"PT", "TM", "VC", "Media", "X"}

# Role mapping: CSV role → auth member_role
ROLE_MAP = {
    "Spieler": "player",
    "Coach": "coach",
    "Betreuer": "staff",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParsedPerson:
    csv_user_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    address_line1: str
    postal_code: str
    city: str
    position: str           # Football position (WR, QB, …) or ""
    member_role: str        # player / coach / staff
    raw_name: str
    raw_roles: str
    skip: bool = False
    skip_reason: str = ""
    generated_email: bool = False


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_name(raw_name: str) -> tuple[str, str, str]:
    """Return (first_name, last_name, football_position)."""
    raw_name = raw_name.strip()
    parts = raw_name.split()
    if not parts:
        return "", "", ""

    # Check first token for known prefix
    prefix = parts[0].rstrip(",")

    # Multi-word prefixes like "OL/DL" or "C/DB"
    if prefix in POSITION_PREFIXES or prefix in STAFF_PREFIXES:
        rest = parts[1:]
        football_pos = prefix if prefix in POSITION_PREFIXES else ""
        # Also strip nested position in prefix like "OL/DL" → use last part
        if "/" in football_pos:
            football_pos = football_pos.split("/")[-1]
    else:
        rest = parts
        football_pos = ""

    if not rest:
        return raw_name, "", football_pos
    if len(rest) == 1:
        return rest[0], "", football_pos
    return rest[0], " ".join(rest[1:]), football_pos


def parse_address(raw: str) -> tuple[str, str, str]:
    """Parse 'Auweg 71, 3627 Heimberg' → (address_line1, postal_code, city)."""
    raw = raw.strip()
    if not raw:
        return "", "", ""
    # Split on comma
    m = re.match(r"^(.+),\s*(\d{4})\s+(.+)$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return raw, "", ""


def parse_roles(raw_roles: str) -> tuple[str, bool]:
    """Return (member_role, skip). Picks highest-priority role."""
    parts = [r.strip() for r in raw_roles.split(",")]
    # Priority: Coach > player > staff
    for part in parts:
        if part == "Inaktiv":
            return "", True
        if part == "Coach":
            return "coach", False
    for part in parts:
        if part == "Spieler":
            return "player", False
    for part in parts:
        if part == "Betreuer":
            return "staff", False
    return "", True  # unknown role → skip


def make_email(first: str, last: str, csv_user_id: str) -> tuple[str, bool]:
    """Generate a synthetic @example.com email."""
    slug = re.sub(r"[^a-z0-9]", ".", f"{first}.{last}".lower()).strip(".")
    if not slug:
        slug = f"user{csv_user_id}"
    return f"{slug}@example.com", True


def parse_csv(path: Path) -> list[ParsedPerson]:
    people: list[ParsedPerson] = []
    seen_emails: set[str] = set()

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            raw_name = row["user_name"].strip().strip('"')
            raw_roles = row["user_roles"].strip().strip('"')
            raw_email = row["user_email"].strip().strip('"')
            raw_phone = row["user_phone"].strip().strip('"')
            raw_address = row["user_address"].strip().strip('"')
            csv_user_id = row["user_id"].strip().strip('"')

            member_role, skip = parse_roles(raw_roles)
            first, last, position = parse_name(raw_name)

            generated_email = False
            if raw_email:
                email = raw_email.lower()
            else:
                email, generated_email = make_email(first, last, csv_user_id)

            # Deduplicate emails
            base_email = email
            counter = 2
            while email in seen_emails:
                name_part = base_email.split("@")[0]
                domain = base_email.split("@")[1]
                email = f"{name_part}{counter}@{domain}"
                counter += 1
            seen_emails.add(email)

            addr1, plz, city = parse_address(raw_address)

            person = ParsedPerson(
                csv_user_id=csv_user_id,
                first_name=first,
                last_name=last,
                email=email,
                phone=raw_phone,
                address_line1=addr1,
                postal_code=plz,
                city=city,
                position=position,
                member_role=member_role,
                raw_name=raw_name,
                raw_roles=raw_roles,
                skip=skip,
                skip_reason="Inaktiv" if skip else "",
                generated_email=generated_email,
            )
            people.append(person)

    return people


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def psycopg_dsn(url: str) -> str:
    """Convert SQLAlchemy URL to psycopg DSN."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def insert_auth_user(cur, person: ParsedPerson, password_hash: str) -> int:
    cur.execute(
        """
        INSERT INTO users
            (username, password_hash, role, account_status, profile_complete,
             email, first_name, last_name, display_name, is_active, created_at)
        VALUES
            (%s, %s, 'user', 'active', true,
             %s, %s, %s, %s, true, %s)
        ON CONFLICT (username) DO UPDATE
            SET email = EXCLUDED.email,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                display_name = EXCLUDED.display_name
        RETURNING id
        """,
        (
            person.email,
            password_hash,
            person.email,
            person.first_name,
            person.last_name,
            f"{person.first_name} {person.last_name}".strip(),
            datetime.now(timezone.utc),
        ),
    )
    return cur.fetchone()[0]


def insert_team_membership(cur, user_id: int, member_role: str) -> None:
    cur.execute(
        """
        INSERT INTO team_memberships (user_id, team_id, member_role, is_active)
        VALUES (%s, %s, %s, true)
        ON CONFLICT (user_id, team_id, member_role) DO NOTHING
        """,
        (user_id, TEAM_ID, member_role),
    )


def insert_members_user(cur, auth_user_id: int, person: ParsedPerson) -> int:
    cur.execute(
        """
        INSERT INTO "user"
            (auth_user_id, username, first_name, last_name, display_name,
             email, platform_role, service_role, profile_complete,
             claims_json, created_at, updated_at)
        VALUES
            (%s, %s, %s, %s, %s,
             %s, 'user', 'user', true,
             %s::jsonb, %s, %s)
        ON CONFLICT (auth_user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                display_name = EXCLUDED.display_name,
                email = EXCLUDED.email
        RETURNING id
        """,
        (
            auth_user_id,
            person.email,
            person.first_name,
            person.last_name,
            f"{person.first_name} {person.last_name}".strip(),
            person.email,
            json.dumps({
                "sub": str(auth_user_id),
                "username": person.email,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "display_name": f"{person.first_name} {person.last_name}".strip(),
                "email": person.email,
                "profile_complete": True,
                "memberships": [{"team_id": TEAM_ID, "team_code": TEAM_CODE,
                                  "team_name": TEAM_NAME, "member_role": person.member_role}],
            }),
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        ),
    )
    return cur.fetchone()[0]


def insert_member_profile(cur, members_user_id: int, person: ParsedPerson) -> None:
    cur.execute(
        """
        INSERT INTO member_profile
            (user_id, first_name, last_name, email, phone,
             address_line1, postal_code, city, position,
             license_photo_status)
        VALUES
            (%s, %s, %s, %s, %s,
             %s, %s, %s, %s, 'none')
        ON CONFLICT (user_id) DO UPDATE
            SET first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                address_line1 = EXCLUDED.address_line1,
                postal_code = EXCLUDED.postal_code,
                city = EXCLUDED.city,
                position = EXCLUDED.position
        """,
        (
            members_user_id,
            person.first_name,
            person.last_name,
            person.email if not person.generated_email else None,
            person.phone or None,
            person.address_line1 or None,
            person.postal_code or None,
            person.city or None,
            person.position or None,
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import players from CSV into local stack.")
    parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Default password (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--auth-dsn", default=AUTH_DSN)
    parser.add_argument("--members-dsn", default=MEMBERS_DSN)
    args = parser.parse_args(argv)

    people = parse_csv(args.csv_file)

    to_import = [p for p in people if not p.skip]
    skipped = [p for p in people if p.skip]

    print(f"\n{'='*60}")
    print(f"  CSV: {args.csv_file.name}")
    print(f"  Total rows: {len(people)}")
    print(f"  To import:  {len(to_import)}")
    print(f"  Skipped:    {len(skipped)} ({', '.join(p.raw_name for p in skipped)})")
    print(f"  Password:   {args.password}")
    print(f"  Dry-run:    {args.dry_run}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print(f"{'CSV-ID':<12} {'Email':<40} {'Name':<30} {'Rolle':<8} {'Pos':<6} {'Gen.Mail'}")
        print("-" * 105)
        for p in to_import:
            gen = "✓" if p.generated_email else ""
            print(f"{p.csv_user_id:<12} {p.email:<40} {p.first_name+' '+p.last_name:<30} {p.member_role:<8} {p.position:<6} {gen}")
        return 0

    password_hash = generate_password_hash(args.password)

    with (
        psycopg.connect(psycopg_dsn(args.auth_dsn)) as auth_conn,
        psycopg.connect(psycopg_dsn(args.members_dsn)) as members_conn,
    ):
        with auth_conn.cursor() as auth_cur, members_conn.cursor() as members_cur:
            ok = 0
            for person in to_import:
                try:
                    auth_user_id = insert_auth_user(auth_cur, person, password_hash)
                    insert_team_membership(auth_cur, auth_user_id, person.member_role)
                    members_user_id = insert_members_user(members_cur, auth_user_id, person)
                    insert_member_profile(members_cur, members_user_id, person)
                    print(f"  ✓ [{person.member_role:<6}] {person.first_name} {person.last_name} <{person.email}>")
                    ok += 1
                except Exception as e:
                    print(f"  ✗ {person.raw_name}: {e}", file=sys.stderr)
                    auth_conn.rollback()
                    members_conn.rollback()
                    continue

        auth_conn.commit()
        members_conn.commit()

    print(f"\n→ {ok}/{len(to_import)} Personen importiert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
