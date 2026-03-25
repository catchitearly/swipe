from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from enum import Enum

from models import (
    Base, User, InfluencerProfile, Brand, Campaign, Coupon, Match, Purchase,
    UserRole, VerificationStatus, CampaignStatus, CouponStatus, PurchaseStatus
)

# ============== CONFIG ==============
SECRET_KEY = "swipematch-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

DATABASE_URL = "sqlite:///./swipematch.db"

# ============== DATABASE ==============
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# ============== SECURITY ==============
from passlib.context import CryptContext
import warnings
warnings.filterwarnings('ignore')

# Use argon2 as bcrypt has issues with Python 3.13
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ============== APP ==============
app = FastAPI(title="SwipeMatch API", description="Influencer Marketplace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== DEPENDENCIES ==============
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Ensure sub is a string
    if 'sub' in to_encode:
        to_encode['sub'] = str(to_encode['sub'])
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


# ============== SCHEMAS ==============
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str  # influencer or brand


class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class InfluencerProfileCreate(BaseModel):
    instagram_handle: Optional[str] = None
    tiktok_handle: Optional[str] = None
    youtube_handle: Optional[str] = None


class InfluencerProfileResponse(BaseModel):
    id: int
    user_id: int
    instagram_handle: Optional[str]
    tiktok_handle: Optional[str]
    youtube_handle: Optional[str]
    follower_count: int
    engagement_rate: float
    verification_status: str
    verified_at: Optional[datetime]
    earnings_balance: float
    pending_payout: float

    class Config:
        from_attributes = True


class BrandCreate(BaseModel):
    company_name: str
    website: Optional[str] = None
    description: Optional[str] = None
    commission_rate: float = 0.30


class BrandResponse(BaseModel):
    id: int
    user_id: int
    company_name: str
    website: Optional[str]
    description: Optional[str]
    commission_rate: float

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_coupons: int = Field(gt=0, description="Number of unique coupon codes")
    uses_per_coupon: int = Field(default=50, gt=0, description="Times each coupon can be used")


class CampaignResponse(BaseModel):
    id: int
    brand_id: int
    name: str
    description: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    total_coupons: int
    uses_per_coupon: int
    distributed_coupons: int
    status: str

    class Config:
        from_attributes = True


class CouponCreate(BaseModel):
    codes: List[str] = Field(description="List of unique coupon codes")


class CouponResponse(BaseModel):
    id: int
    campaign_id: int
    code: str
    uses_remaining: int
    uses_total: int
    assigned_influencer_id: Optional[int]
    status: str

    class Config:
        from_attributes = True


class SwipeResponse(BaseModel):
    campaign_id: int
    name: str
    description: Optional[str]
    brand_name: str
    total_coupons: int
    distributed_coupons: int
    uses_per_coupon: int
    commission_rate: float


class MatchResponse(BaseModel):
    id: int
    campaign_id: int
    campaign_name: str
    coupon_code: str
    uses_remaining: int
    matched_at: datetime

    class Config:
        from_attributes = True


class PurchaseCreate(BaseModel):
    influencer_id: int
    coupon_code: str
    amount: float
    customer_email: Optional[str] = None
    order_id: Optional[str] = None


class PurchaseResponse(BaseModel):
    id: int
    influencer_id: int
    coupon_id: int
    amount: float
    marketplace_commission: float
    influencer_payout: float
    status: str
    purchased_at: datetime

    class Config:
        from_attributes = True


class VerifyRequest(BaseModel):
    platform: str  # instagram, tiktok, youtube
    username: str


# ============== AUTH ENDPOINTS ==============
@app.post("/api/auth/register", response_model=Token)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if email exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = pwd_context.hash(user_data.password)
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        role=UserRole(user_data.role)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create profile based on role
    if user_data.role == "influencer":
        profile = InfluencerProfile(user_id=user.id)
        db.add(profile)
    elif user_data.role == "brand":
        # Brand will be created via separate endpoint
        pass
    
    db.commit()
    
    # Create token
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ============== INFLUENCER ENDPOINTS ==============
@app.post("/api/influencer/profile", response_model=InfluencerProfileResponse)
def create_influencer_profile(
    profile_data: InfluencerProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can create profile")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if profile:
        # Update existing
        if profile_data.instagram_handle:
            profile.instagram_handle = profile_data.instagram_handle
        if profile_data.tiktok_handle:
            profile.tiktok_handle = profile_data.tiktok_handle
        if profile_data.youtube_handle:
            profile.youtube_handle = profile_data.youtube_handle
    else:
        profile = InfluencerProfile(
            user_id=current_user.id,
            instagram_handle=profile_data.instagram_handle,
            tiktok_handle=profile_data.tiktok_handle,
            youtube_handle=profile_data.youtube_handle
        )
        db.add(profile)
    
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/influencer/profile", response_model=InfluencerProfileResponse)
def get_influencer_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can access this")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/api/influencer/verify")
def verify_influencer(
    verify_request: VerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify influencer's social media account"""
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can be verified")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # In production, this would call actual social media APIs
    # For demo, we'll simulate verification
    
    platform = verify_request.platform.lower()
    username = verify_request.username
    
    # Simulated verification logic
    # In production: Call Instagram/TikTok/YouTube API to get follower count
    
    if platform == "instagram":
        profile.instagram_handle = username
        # Simulated: random follower count (in production, call Instagram API)
        import random
        profile.follower_count = random.randint(300, 1000000)
        profile.engagement_rate = round(random.uniform(1.0, 10.0), 2)
    elif platform == "tiktok":
        profile.tiktok_handle = username
        import random
        profile.follower_count = random.randint(300, 1000000)
        profile.engagement_rate = round(random.uniform(1.0, 15.0), 2)
    elif platform == "youtube":
        profile.youtube_handle = username
        import random
        profile.follower_count = random.randint(300, 1000000)
        profile.engagement_rate = round(random.uniform(1.0, 8.0), 2)
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    # Check verification criteria
    if profile.follower_count >= 300:
        profile.verification_status = VerificationStatus.VERIFIED
        profile.verified_at = datetime.utcnow()
        profile.verification_data = {
            "platform": platform,
            "username": username,
            "follower_count": profile.follower_count,
            "engagement_rate": profile.engagement_rate,
            "verified_at": datetime.utcnow().isoformat()
        }
    else:
        profile.verification_status = VerificationStatus.REJECTED
    
    db.commit()
    db.refresh(profile)
    
    return {
        "status": profile.verification_status.value,
        "follower_count": profile.follower_count,
        "engagement_rate": profile.engagement_rate,
        "message": "Verified successfully" if profile.verification_status == VerificationStatus.VERIFIED else "Below minimum 300 followers requirement"
    }


@app.get("/api/influencer/matches", response_model=List[MatchResponse])
def get_influencer_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can access this")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    matches = db.query(Match).filter(
        Match.influencer_id == profile.id,
        Match.status == "active"
    ).all()
    
    result = []
    for match in matches:
        result.append(MatchResponse(
            id=match.id,
            campaign_id=match.campaign_id,
            campaign_name=match.campaign.name,
            coupon_code=match.coupon.code,
            uses_remaining=match.coupon.uses_remaining,
            matched_at=match.matched_at
        ))
    
    return result


@app.get("/api/influencer/earnings")
def get_influencer_earnings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can access this")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Calculate total earnings from purchases
    purchases = db.query(Purchase).filter(
        Purchase.influencer_id == profile.id,
        Purchase.status == PurchaseStatus.CONFIRMED
    ).all()
    
    total_earnings = sum(p.influencer_payout for p in purchases)
    
    return {
        "earnings_balance": profile.earnings_balance,
        "pending_payout": profile.pending_payout,
        "total_earned": total_earnings,
        "purchase_count": len(purchases)
    }


# ============== BRAND ENDPOINTS ==============
@app.post("/api/brand/profile", response_model=BrandResponse)
def create_brand_profile(
    brand_data: BrandCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can create profile")
    
    existing = db.query(Brand).filter(Brand.user_id == current_user.id).first()
    if existing:
        existing.company_name = brand_data.company_name
        existing.website = brand_data.website
        existing.description = brand_data.description
        existing.commission_rate = brand_data.commission_rate
        db.commit()
        db.refresh(existing)
        return existing
    
    brand = Brand(
        user_id=current_user.id,
        company_name=brand_data.company_name,
        website=brand_data.website,
        description=brand_data.description,
        commission_rate=brand_data.commission_rate
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@app.get("/api/brand/profile", response_model=BrandResponse)
def get_brand_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can access this")
    
    brand = db.query(Brand).filter(Brand.user_id == current_user.id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return brand


@app.post("/api/brand/campaign", response_model=CampaignResponse)
def create_campaign(
    campaign_data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can create campaigns")
    
    brand = db.query(Brand).filter(Brand.user_id == current_user.id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    
    campaign = Campaign(
        brand_id=brand.id,
        name=campaign_data.name,
        description=campaign_data.description,
        start_date=campaign_data.start_date,
        end_date=campaign_data.end_date,
        total_coupons=campaign_data.total_coupons,
        uses_per_coupon=campaign_data.uses_per_coupon
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@app.get("/api/brand/campaigns", response_model=List[CampaignResponse])
def get_brand_campaigns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can access this")
    
    brand = db.query(Brand).filter(Brand.user_id == current_user.id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    
    campaigns = db.query(Campaign).filter(Campaign.brand_id == brand.id).all()
    return campaigns


@app.get("/api/brand/campaign/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can access this")
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@app.post("/api/brand/campaign/{campaign_id}/coupons")
def add_coupons(
    campaign_id: int,
    coupon_data: CouponCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add coupon codes to a campaign"""
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can add coupons")
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Verify brand owns this campaign
    brand = db.query(Brand).filter(Brand.user_id == current_user.id).first()
    if campaign.brand_id != brand.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Add coupons
    added_count = 0
    for code in coupon_data.codes:
        # Check if code already exists
        existing = db.query(Coupon).filter(Coupon.code == code).first()
        if existing:
            continue
        
        coupon = Coupon(
            campaign_id=campaign.id,
            code=code,
            uses_remaining=campaign.uses_per_coupon,
            uses_total=campaign.uses_per_coupon,
            status=CouponStatus.AVAILABLE
        )
        db.add(coupon)
        added_count += 1
    
    campaign.total_coupons = added_count
    db.commit()
    
    return {"added": added_count, "message": f"Added {added_count} coupon codes"}


@app.get("/api/brand/campaign/{campaign_id}/stats")
def get_campaign_stats(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get campaign statistics"""
    if current_user.role != UserRole.BRAND:
        raise HTTPException(status_code=403, detail="Only brands can access this")
    
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get coupon stats
    coupons = db.query(Coupon).filter(Coupon.campaign_id == campaign_id).all()
    total_coupons = len(coupons)
    available = len([c for c in coupons if c.status == CouponStatus.AVAILABLE])
    assigned = len([c for c in coupons if c.status == CouponStatus.ASSIGNED])
    exhausted = len([c for c in coupons if c.status == CouponStatus.EXHAUSTED])
    
    # Get purchase stats
    purchases = db.query(Purchase).join(Coupon).filter(
        Coupon.campaign_id == campaign_id,
        Purchase.status == PurchaseStatus.CONFIRMED
    ).all()
    
    total_revenue = sum(p.amount for p in purchases)
    total_commission = sum(p.marketplace_commission for p in purchases)
    
    return {
        "campaign_name": campaign.name,
        "total_coupons": total_coupons,
        "available": available,
        "assigned": assigned,
        "exhausted": exhausted,
        "distributed_coupons": assigned,
        "total_purchases": len(purchases),
        "total_revenue": total_revenue,
        "marketplace_commission": total_commission
    }


# ============== SWIPE ENDPOINTS ==============
@app.get("/api/swipe/next-campaign", response_model=SwipeResponse)
def get_next_campaign(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get next campaign for influencer to swipe"""
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can swipe")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile.verification_status != VerificationStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Please verify your account first (300+ followers required)")
    
    # Get campaigns that have available coupons and aren't already matched
    # Find campaigns with available coupons
    available_coupons = db.query(Coupon).filter(
        Coupon.status == CouponStatus.AVAILABLE,
        Coupon.uses_remaining > 0
    ).all()
    
    if not available_coupons:
        raise HTTPException(status_code=404, detail="No campaigns available")
    
    # Get campaign IDs that influencer already matched with
    matched_campaign_ids = [m.campaign_id for m in db.query(Match).filter(
        Match.influencer_id == profile.id,
        Match.status == "active"
    ).all()]
    
    # Find first campaign not yet matched
    for coupon in available_coupons:
        if coupon.campaign_id not in matched_campaign_ids:
            campaign = db.query(Campaign).filter(Campaign.id == coupon.campaign_id).first()
            if campaign and campaign.status == CampaignStatus.ACTIVE:
                brand = db.query(Brand).filter(Brand.id == campaign.brand_id).first()
                return SwipeResponse(
                    campaign_id=campaign.id,
                    name=campaign.name,
                    description=campaign.description,
                    brand_name=brand.company_name if brand else "Unknown",
                    total_coupons=campaign.total_coupons,
                    distributed_coupons=campaign.distributed_coupons,
                    uses_per_coupon=campaign.uses_per_coupon,
                    commission_rate=brand.commission_rate if brand else 0.30
                )
    
    raise HTTPException(status_code=404, detail="No more campaigns available")


@app.post("/api/swipe/swipe-right")
def swipe_right(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept campaign - assign coupon to influencer"""
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can swipe")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile.verification_status != VerificationStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Please verify your account first")
    
    # Check if already matched
    existing_match = db.query(Match).filter(
        Match.influencer_id == profile.id,
        Match.campaign_id == campaign_id,
        Match.status == "active"
    ).first()
    if existing_match:
        raise HTTPException(status_code=400, detail="Already matched with this campaign")
    
    # Get available coupon
    coupon = db.query(Coupon).filter(
        Coupon.campaign_id == campaign_id,
        Coupon.status == CouponStatus.AVAILABLE,
        Coupon.uses_remaining > 0
    ).first()
    
    if not coupon:
        raise HTTPException(status_code=404, detail="No available coupons for this campaign")
    
    # Assign coupon to influencer
    coupon.assigned_influencer_id = profile.id
    coupon.assigned_at = datetime.utcnow()
    coupon.status = CouponStatus.ASSIGNED
    
    # Create match
    match = Match(
        influencer_id=profile.id,
        campaign_id=campaign_id,
        coupon_id=coupon.id,
        status="active"
    )
    db.add(match)
    
    # Update campaign stats
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    campaign.distributed_coupons += 1
    
    db.commit()
    db.refresh(coupon)
    
    return {
        "message": "Campaign accepted!",
        "coupon_code": coupon.code,
        "uses_remaining": coupon.uses_remaining,
        "promotion_link": f"https://vendor.example.com?ref={coupon.code}"
    }


@app.post("/api/swipe/swipe-left")
def swipe_left(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Decline campaign - just log the swipe"""
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can swipe")
    
    # In production, you might want to track declined campaigns
    # to avoid showing them again
    return {"message": "Campaign declined"}


# ============== PURCHASE ENDPOINTS ==============
@app.post("/api/purchases/track")
def track_purchase(
    purchase_data: PurchaseCreate,
    db: Session = Depends(get_db)
):
    """Track a purchase using a coupon code (called by vendor webhook)"""
    # Find coupon by code
    coupon = db.query(Coupon).filter(Coupon.code == purchase_data.coupon_code).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Invalid coupon code")
    
    if coupon.uses_remaining <= 0:
        raise HTTPException(status_code=400, detail="Coupon exhausted")
    
    if not coupon.assigned_influencer_id:
        raise HTTPException(status_code=400, detail="Coupon not assigned to any influencer")
    
    # Get influencer and brand
    influencer = db.query(InfluencerProfile).filter(InfluencerProfile.id == coupon.assigned_influencer_id).first()
    campaign = db.query(Campaign).filter(Campaign.id == coupon.campaign_id).first()
    brand = db.query(Brand).filter(Brand.id == campaign.brand_id).first()
    
    # Calculate commission
    commission_rate = brand.commission_rate if brand else 0.30
    marketplace_commission = purchase_data.amount * commission_rate
    influencer_payout = purchase_data.amount - marketplace_commission
    
    # Create purchase record
    purchase = Purchase(
        influencer_id=influencer.id,
        coupon_id=coupon.id,
        amount=purchase_data.amount,
        marketplace_commission=marketplace_commission,
        influencer_payout=influencer_payout,
        customer_email=purchase_data.customer_email,
        order_id=purchase_data.order_id,
        status=PurchaseStatus.CONFIRMED
    )
    db.add(purchase)
    
    # Update coupon usage
    coupon.uses_remaining -= 1
    if coupon.uses_remaining <= 0:
        coupon.status = CouponStatus.EXHAUSTED
    
    # Update influencer earnings
    influencer.earnings_balance += influencer_payout
    
    db.commit()
    db.refresh(purchase)
    
    return {
        "message": "Purchase tracked successfully",
        "influencer_payout": influencer_payout,
        "marketplace_commission": marketplace_commission,
        "coupon_uses_remaining": coupon.uses_remaining
    }


@app.get("/api/purchases/history", response_model=List[PurchaseResponse])
def get_purchase_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get purchase history for an influencer"""
    if current_user.role != UserRole.INFLUENCER:
        raise HTTPException(status_code=403, detail="Only influencers can access this")
    
    profile = db.query(InfluencerProfile).filter(InfluencerProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    purchases = db.query(Purchase).filter(Purchase.influencer_id == profile.id).all()
    return purchases


# ============== HEALTH CHECK ==============
@app.get("/")
def root():
    return {"message": "SwipeMatch API is running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}