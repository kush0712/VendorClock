"""
Auth API Routes — Secure Implementation

POST /api/auth/register  — self-service company registration (open signup)
POST /api/auth/login     — authenticate, return JWT (rate-limited: 10/min per IP)
POST /api/auth/logout    — clear client-side session signal
GET  /api/auth/me        — current user info (requires valid JWT)

Security measures:
  - Bcrypt password hashing (via security.py)
  - Password policy enforced server-side (min 8 chars, ≥1 digit)
  - Rate limiting on /login (slowapi): 10 requests/minute per IP
  - All DB queries use SQLAlchemy ORM — no raw SQL → immune to SQL injection
  - JWT signed with HS256 and expiry; user ID in payload (not email) to prevent
    "change email in URL" attacks; all protected routes re-verify token on every request
  - No user enumeration: login always returns the same error for wrong email or password
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Rate limiter keyed on real client IP (works behind proxies too)
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str
    role: UserRole = UserRole.ACCOUNTANT

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("company_name")
    @classmethod
    def company_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Company name cannot be empty.")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user / company account.
    Open self-signup — any company can register.
    """
    # Check for duplicate email — ORM query, no raw SQL
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name.strip(),
        company_name=body.company_name.strip(),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Return the JWT immediately so the user is logged in right after registration
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role.value,
        "full_name": user.full_name,
        "company_name": user.company_name,
    }


@router.post("/login")
@limiter.limit("10/minute")  # Brute-force protection: 10 attempts per IP per minute
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate and return a JWT access token.

    Security: intentionally uses the same error message for wrong email AND wrong
    password to prevent user-enumeration attacks.
    """
    # Constant-time check: always query + verify so timing doesn't leak existence
    user = db.query(User).filter(User.email == body.email).first()

    # Always call verify_password even if user is None (with a dummy hash) to keep
    # timing constant and prevent timing-based user enumeration.
    _DUMMY_HASH = "$2b$12$4BHs0cgyRXQMDBpPMvo9uOX/1yLTE5uVSapJ82EZlTPjCW70k2oXC"
    password_ok = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH)

    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role.value,
        "full_name": user.full_name,
        "company_name": user.company_name,
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout():
    """
    Signal logout. Token invalidation happens client-side (remove from storage).
    For production, implement a token denylist in Redis for hard invalidation.
    """
    return {"message": "Logged out successfully."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user info. The JWT is verified on every call."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "company_name": current_user.company_name,
        "role": current_user.role.value,
    }
