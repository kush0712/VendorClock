import sys
from app.core.database import SessionLocal
from app.models.user import User, UserRole

def promote_to_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Error: No user found with email '{email}'")
            sys.exit(1)
        
        user.role = UserRole.ADMIN
        db.commit()
        print(f"Success: User {email} has been promoted to ADMIN.")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python promote_admin.py <user_email>")
        sys.exit(1)
    
    promote_to_admin(sys.argv[1])
