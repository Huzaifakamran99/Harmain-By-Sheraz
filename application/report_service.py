from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from domain.models import PilgrimStatus, Gender
from domain.rules import calculate_remaining
from infrastructure.repositories import PilgrimRepository, PaymentRepository, PartyRepository
from infrastructure.db import get_connection


class ReportService:
    def __init__(self):
        self.pilgrims = PilgrimRepository()
        self.payments = PaymentRepository()
        self.parties = PartyRepository()

    def dashboard_summary(self) -> dict:
        conn = get_connection()
        active = conn.execute("SELECT COUNT(*) c FROM pilgrims WHERE status='Active'").fetchone()["c"]
        free_male = conn.execute("SELECT COUNT(*) c FROM pilgrims WHERE status='FreeMale'").fetchone()["c"]
        free_female = conn.execute("SELECT COUNT(*) c FROM pilgrims WHERE status='FreeFemale'").fetchone()["c"]
        visited = free_male + free_female
        total_charge = conn.execute(
            "SELECT COALESCE(SUM(charge),0) t FROM pilgrims WHERE status != 'Archived'"
        ).fetchone()["t"]
        total_received = conn.execute("SELECT COALESCE(SUM(amount),0) t FROM payments").fetchone()["t"]
        upcoming = self.count_upcoming()
        return {
            "total_active": active,
            "free_male": free_male,
            "free_female": free_female,
            "total_visited": visited,
            "total_charge": round(total_charge, 2),
            "total_received": round(total_received, 2),
            "total_remaining": calculate_remaining(total_charge, total_received),
            "upcoming_permits": upcoming,
        }

    def count_upcoming(self) -> int:
        from domain.rules import is_within_reminder_window
        active = self.pilgrims.list_upcoming_active()
        return sum(1 for p in active if is_within_reminder_window(p.permit_date, p.permit_time))

    def party_wise_totals(self) -> list[dict]:
        parties = self.parties.list_active()
        result = []
        for party in parties:
            pilgrims = self.pilgrims.list_by_party(party.id)
            charge = round(sum(p.charge for p in pilgrims), 2)
            received = round(self.payments.totals_for_party(party.id), 2)
            result.append({
                "party": party.name,
                "people": len(pilgrims),
                "charge": charge,
                "received": received,
                "remaining": calculate_remaining(charge, received),
            })
        return result

    def visited_report(self, date_from: Optional[date] = None, date_to: Optional[date] = None,
                        gender: Optional[Gender] = None) -> list:
        conn = get_connection()
        sql = "SELECT * FROM pilgrims WHERE status IN ('FreeMale','FreeFemale')"
        params: list = []
        if date_from:
            sql += " AND date(moved_to_free_at) >= ?"
            params.append(date_from.isoformat())
        if date_to:
            sql += " AND date(moved_to_free_at) <= ?"
            params.append(date_to.isoformat())
        if gender:
            sql += " AND gender = ?"
            params.append(gender.value)
        sql += " ORDER BY moved_to_free_at DESC"
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]
