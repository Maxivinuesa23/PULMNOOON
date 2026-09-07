from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Examen(Base):
    __tablename__ = "examenes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre_paciente: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    imagen_url: Mapped[str] = mapped_column(Text, nullable=False)
