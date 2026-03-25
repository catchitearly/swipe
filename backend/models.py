from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    INFLUENCER = "influencer"
    BRAND = "brand"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class CampaignStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CouponStatus(str, enum.Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    EXHAUSTED = "exhausted"


class PurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    influencer_profile = relationship("InfluencerProfile", back_populates="user", uselist=False)
    brand = relationship("Brand", back_populates="user", uselist=False)


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    user = relationship("User", back_populates="influencer_profile")
    
    # Social media handles
    instagram_handle = Column(String, nullable=True)
    tiktok_handle = Column(String, nullable=True)
    youtube_handle = Column(String, nullable=True)
    
    # Verification data
    follower_count = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    verified_at = Column(DateTime, nullable=True)
    verification_data = Column(JSON, nullable=True)  # Store API response data
    
    # Earnings
    earnings_balance = Column(Float, default=0.0)
    pending_payout = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    matches = relationship("Match", back_populates="influencer")
    purchases = relationship("Purchase", back_populates="influencer")


class Brand(Base):
    __tablename__ = "brands"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    user = relationship("User", back_populates="brand")
    
    company_name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    commission_rate = Column(Float, default=0.30)  # 30% default
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    campaigns = relationship("Campaign", back_populates="brand")


class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    brand = relationship("Brand", back_populates="campaigns")
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    total_coupons = Column(Integer, default=0)
    uses_per_coupon = Column(Integer, default=50)
    distributed_coupons = Column(Integer, default=0)
    
    status = Column(Enum(CampaignStatus), default=CampaignStatus.ACTIVE)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    coupons = relationship("Coupon", back_populates="campaign")
    matches = relationship("Match", back_populates="campaign")


class Coupon(Base):
    __tablename__ = "coupons"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    campaign = relationship("Campaign", back_populates="coupons")
    
    code = Column(String, unique=True, nullable=False, index=True)
    uses_remaining = Column(Integer, default=0)
    uses_total = Column(Integer, default=50)
    
    assigned_influencer_id = Column(Integer, ForeignKey("influencer_profiles.id"), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    status = Column(Enum(CouponStatus), default=CouponStatus.AVAILABLE)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    assigned_influencer = relationship("InfluencerProfile", foreign_keys=[assigned_influencer_id])
    matches = relationship("Match", back_populates="coupon")
    purchases = relationship("Purchase", back_populates="coupon")


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    influencer_id = Column(Integer, ForeignKey("influencer_profiles.id"))
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    coupon_id = Column(Integer, ForeignKey("coupons.id"))
    
    status = Column(String, default="active")  # active, unmatched
    
    matched_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    influencer = relationship("InfluencerProfile", back_populates="matches")
    campaign = relationship("Campaign", back_populates="matches")
    coupon = relationship("Coupon", back_populates="matches")


class Purchase(Base):
    __tablename__ = "purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    influencer_id = Column(Integer, ForeignKey("influencer_profiles.id"))
    coupon_id = Column(Integer, ForeignKey("coupons.id"))
    
    amount = Column(Float, nullable=False)
    marketplace_commission = Column(Float, nullable=False)
    influencer_payout = Column(Float, nullable=False)
    
    customer_email = Column(String, nullable=True)
    order_id = Column(String, nullable=True)
    
    status = Column(Enum(PurchaseStatus), default=PurchaseStatus.PENDING)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    influencer = relationship("InfluencerProfile", back_populates="purchases")
    coupon = relationship("Coupon", back_populates="purchases")