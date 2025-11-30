# backend/database/models.py
"""
=====================================================
🧠 models.py
-----------------------------------------------------
Defines ORM models for users, interview sessions,
and multimodal feedback reports.
=====================================================
"""

from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .db_connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("InterviewSession", back_populates="user")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    domain = Column(String(50))
    question_id = Column(String(50))
    nlp_score = Column(Float)
    tone_score = Column(Float)
    emotion_score = Column(Float)
    posture_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    feedback = relationship("FeedbackReport", back_populates="session", uselist=False)


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    feedback_text = Column(Text)
    overall_score = Column(Float)
    qualitative_feedback = Column(String(50))
    generated_at = Column(DateTime, default=datetime.utcnow)
    raw_data = Column(JSON)  # Stores the original module outputs

    session = relationship("InterviewSession", back_populates="feedback")
