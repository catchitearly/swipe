# SwipeMatch - Influencer Marketplace App

## Project Overview
- **Project Name**: SwipeMatch
- **Type**: Web Application (Tinder-like Influencer Marketplace)
- **Core Functionality**: A platform connecting brands with influencers through a swipe-based matching system. Brands provide unique coupon codes, influencers swipe to accept campaigns, and purchases are tracked with commission distribution.
- **Target Users**: Brands wanting to promote via influencers, Influencers (300+ followers) seeking monetization opportunities

---

## Functionality Specification

### 1. User Management

#### Influencer Features
- **Registration**: Sign up with email, social media handles (Instagram, TikTok, YouTube)
- **Verification System**: 
  - Connect social media account via API
  - Minimum 300 followers required
  - Bot detection using social media API metrics (engagement rate, follower growth pattern)
  - Manual verification option if API fails
- **Profile**: Display follower count, engagement rate, verified status
- **Dashboard**: View assigned coupons, earnings, promotion links

#### Brand Features
- **Registration**: Sign up with company details
- **Campaign Creation**: Create campaigns with coupon codes
- **Dashboard**: View campaign stats, coupon usage, conversions, payouts

### 2. Campaign Management

#### Brand Campaign Creation
- Campaign name and description
- Upload coupon codes (CSV or manual entry)
  - Each coupon can be used X times (e.g., 50 uses)
  - Example: 100 unique codes × 50 uses each = 5000 total uses
- Campaign budget and dates
- Target demographics (optional)
- Commission rate (default 30% marketplace fee)

#### Coupon Code Format
- Unique code per influencer
- Track: assigned influencer, usage count, usage limit
- Status: available, assigned, exhausted

### 3. Swipe System (Core Feature)

#### Card Display
- Show brand campaign cards to influencers
- Display: Brand name, campaign details, coupon value, commission info
- Swipe right: Accept campaign, get assigned coupon
- Swipe left: Decline, see next campaign

#### Matching Logic
- When influencer swipes right:
  1. Find available coupon code from campaign pool
  2. Assign coupon to influencer
  3. Create "match" record
  4. Show coupon in influencer's dashboard
- Campaign shown until all coupons distributed (100 unique influencers)

### 4. Coupon & Purchase Tracking

#### Coupon Assignment
- Each coupon linked to specific influencer
- Generate unique promotion link per influencer
- Track: code, uses remaining, uses total, conversions

#### Purchase Flow
1. Influencer shares promo link/coupon with followers
2. Customer uses coupon on vendor website
3. Vendor confirms purchase (via webhook or manual)
4. System records: influencer, coupon, purchase amount
5. Calculate commission: 30% marketplace, 70% influencer
6. Update influencer earnings

#### Payment Distribution
- Track all purchases per influencer
- 30% marketplace fee
- 70% to influencer (after verification)
- Payout request system for influencers

### 5. Verification System

#### Social Media API Integration
- Instagram Graph API
- TikTok API
- YouTube Data API

#### Verification Criteria
- Minimum 300 followers
- Account age check
- Engagement rate (likes/comments ratio)
- Follower growth pattern (detect bot spikes)
- Profile completeness

#### Verification States
- `pending`: Submitted for verification
- `verified`: Approved, can participate
- `rejected`: Below requirements
- `needs_review`: Manual review required

### 6. Database Schema

#### Users Table
- id, email, password_hash, role (influencer/brand)
- created_at, updated_at

#### Influencer Profiles Table
- user_id, social_handles (JSON)
- follower_count, engagement_rate
- verification_status, verified_at
- earnings_balance, pending_payout

#### Brands Table
- user_id, company_name, website
- commission_rate

#### Campaigns Table
- brand_id, name, description
- start_date, end_date
- total_coupons, distributed_coupons
- status (active, paused, completed)

#### Coupons Table
- campaign_id, code
- assigned_influencer_id, uses_remaining, uses_total
- status (available, assigned, exhausted)

#### Matches Table
- influencer_id, campaign_id, coupon_id
- matched_at, status

#### Purchases Table
- influencer_id, coupon_id, amount
- marketplace_commission, influencer_payout
- purchased_at, status

---

## Technical Stack

- **Backend**: Python FastAPI
- **Database**: SQLite (for simplicity) with SQLAlchemy
- **Frontend**: HTML/CSS/JavaScript (Vanilla for demo)
- **APIs**: RESTful

---

## UI/UX Specification

### Color Palette
- Primary: #FF6B6B (Coral Red - Tinder-inspired)
- Secondary: #4ECDC4 (Teal)
- Accent: #FFE66D (Yellow)
- Background: #F7F7F7
- Dark: #2C3E50
- Success: #27AE60
- Error: #E74C3C

### Typography
- Headings: Poppins (bold)
- Body: Inter

### Layout
- Mobile-first design
- Card-based swipe interface
- Clean dashboard with stats

---

## API Endpoints

### Authentication
- POST /api/auth/register
- POST /api/auth/login

### Influencer
- POST /api/influencer/profile
- GET /api/influencer/profile
- POST /api/influencer/verify
- GET /api/influencer/matches
- GET /api/influencer/earnings

### Brand
- POST /api/brand/campaign
- GET /api/brand/campaigns
- GET /api/brand/campaign/{id}
- POST /api/brand/campaign/{id}/coupons

### Swipe
- GET /api/swipe/next-campaign
- POST /api/swipe/swipe-right
- POST /api/swipe/swipe-left

### Purchases
- POST /api/purchases/track
- GET /api/purchases/history

---

## Acceptance Criteria

1. ✅ Influencer can register and connect social media
2. ✅ Verification system checks 300+ followers requirement
3. ✅ Brand can create campaign with multiple coupon codes
4. ✅ Influencer sees campaign cards and can swipe
5. ✅ Right swipe assigns coupon to influencer
6. ✅ Coupon is linked to specific influencer in database
7. ✅ Purchase tracking with commission calculation
8. ✅ 30% marketplace fee, 70% to influencer
9. ✅ Dashboard shows earnings and promotion links
10. ✅ Campaign stops showing when all coupons distributed