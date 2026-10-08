from __future__ import annotations

import uuid

from sqlalchemy import JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
import re

def normalize_country_code(country_input: str) -> str:
    """Robustly parse country string from DB/UI to a 2-letter ISO code."""
    if not country_input:
        return ""
    c = str(country_input).upper().strip()
    
    if "ÉTATS" in c or "ETATS" in c or "UNITED STATES" in c or c == "USA":
        return "US"
    if re.search(r'\bUS\b', c):
        return "US"
        
    if "FRANCE" in c or re.search(r'\bFR\b', c):
        return "FR"
    if "GERMANY" in c or "ALLEMAGNE" in c or re.search(r'\bDE\b', c):
        return "DE"
    if "ITALY" in c or "ITALIE" in c or re.search(r'\bIT\b', c):
        return "IT"
    if "SPAIN" in c or "ESPAGNE" in c or re.search(r'\bES\b', c):
        return "ES"
    if "UNITED KINGDOM" in c or "ROYAUME" in c or re.search(r'\bGB\b|\bUK\b', c):
        return "GB"
        
    m = re.match(r'^([A-Z]{2})', c)
    if m:
        return m.group(1)
        
    return c


class ClientProfile(Base, TimestampMixin):
    __tablename__ = "client_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    activity_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_families: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    product_characteristics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    program_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    naming_conventions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    classification_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    regulatory_scope: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    documents = relationship("Document", back_populates="client_profile")
