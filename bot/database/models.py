from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, Text, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from bot.database.database import Base

class Film(Base):
    __tablename__ = 'films'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # user_created/updated are uuids in DB, we can skip or map as string if not using
    films_article: Mapped[Optional[str]] = mapped_column(String(255))
    films_type: Mapped[Optional[str]] = mapped_column(String(255))
    type_of_film: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    date_created: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    date_updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class ArtRule(Base):
    __tablename__ = 'art_rules'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_created: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    date_created: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    user_updated: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    date_updated: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    glass_article: Mapped[Optional[str]] = mapped_column(String(255))
    glass_type: Mapped[Optional[str]] = mapped_column(String(255))
    type_of_glass: Mapped[Optional[str]] = mapped_column(String(255))
    type_of_processing: Mapped[Optional[str]] = mapped_column(String(255))
    surface: Mapped[Optional[str]] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(Text)
    analog_list: Mapped[Optional[int]] = mapped_column(Integer)


class SizeControl(Base):
    __tablename__ = 'size_control'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_created: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    
    dim1: Mapped[Optional[int]] = mapped_column(BigInteger)
    dim2: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marking: Mapped[Optional[str]] = mapped_column(String(255))
    
    formula_1: Mapped[Optional[str]] = mapped_column(Text)
    formula_2: Mapped[Optional[str]] = mapped_column(Text)
    formula_1_1k: Mapped[Optional[str]] = mapped_column(Text)
    formula_1_2k: Mapped[Optional[str]] = mapped_column(Text)
    formula_2_1k: Mapped[Optional[str]] = mapped_column(Text)
    formula_2_2k: Mapped[Optional[str]] = mapped_column(Text)
    formula_1_3k: Mapped[Optional[str]] = mapped_column(String(255))
    formula_2_3k: Mapped[Optional[str]] = mapped_column(String(255))


class QualFile(Base):
    __tablename__ = 'qual_analize_files'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    
    file_name: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    responce: Mapped[Optional[str]] = mapped_column(Text)
    tg_username: Mapped[Optional[str]] = mapped_column(Text)
    tg_chatid: Mapped[Optional[int]] = mapped_column(BigInteger)
    rules: Mapped[Optional[str]] = mapped_column(Text)
    used_prompt: Mapped[Optional[str]] = mapped_column(Text)
    full_raw: Mapped[Optional[str]] = mapped_column(Text)

    positions: Mapped[List["QualPos"]] = relationship("QualPos", back_populates="file", cascade="all, delete-orphan")


class QualPos(Base):
    __tablename__ = 'qual_analize_pos'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey('public.qual_analize_files.id'))
    date_created: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    position_num: Mapped[Optional[str]] = mapped_column(String(255))
    position_formula: Mapped[Optional[str]] = mapped_column(String(255))
    position_raskl: Mapped[Optional[str]] = mapped_column(String(255))
    
    position_width: Mapped[Optional[int]] = mapped_column(Integer)
    position_hight: Mapped[Optional[int]] = mapped_column(Integer)
    position_width_round: Mapped[Optional[int]] = mapped_column(Integer)
    position_hight_round: Mapped[Optional[int]] = mapped_column(Integer)
    
    position_count: Mapped[Optional[int]] = mapped_column(Integer)
    position_area: Mapped[Optional[float]] = mapped_column(Float)
    position_mass: Mapped[Optional[float]] = mapped_column(Float)
    
    position_formula_slip: Mapped[Optional[str]] = mapped_column(String(255))
    article_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    f1: Mapped[Optional[str]] = mapped_column(String(255))
    f2: Mapped[Optional[str]] = mapped_column(String(255))
    
    cam_count: Mapped[Optional[int]] = mapped_column(Integer) # int2
    
    overall_status: Mapped[Optional[str]] = mapped_column(Text)
    overall_message: Mapped[Optional[str]] = mapped_column(Text)
    
    is_oytside: Mapped[Optional[bool]] = mapped_column(Boolean)

    file: Mapped["QualFile"] = relationship("QualFile", back_populates="positions")
    issues: Mapped[List["QualIssue"]] = relationship("QualIssue", back_populates="pos", cascade="all, delete-orphan")


class QualIssue(Base):
    __tablename__ = 'qual_analize_pos_issues'
    __table_args__ = {'schema': 'public'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pos_id: Mapped[int] = mapped_column(ForeignKey('public.qual_analize_pos.id', ondelete='CASCADE'), nullable=False)
    
    issue_code: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default='error')
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    pos: Mapped["QualPos"] = relationship("QualPos", back_populates="issues")
