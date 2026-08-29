import os
from dotenv import load_dotenv

# 1. Load the .env file FIRST before importing database!
load_dotenv()

import bcrypt
from database import ScopedSession, User


def create_emergency_admin(username, pin, full_name, email):
    session = ScopedSession()
    try:
        # Check if the user already exists
        existing_user = session.query(User).filter(User.username == username.lower().strip()).first()

        # Hash the new PIN properly with bcrypt
        hashed_pin = bcrypt.hashpw(pin.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        if existing_user:
            print(f"User '{username}' found. Elevating to 'admin' and resetting PIN.")
            existing_user.role = 'admin'
            existing_user.pin = hashed_pin
        else:
            print(f"Creating brand new emergency admin: '{username}'")
            new_admin = User(
                username=username.lower().strip(),
                email=email.lower().strip(),
                pin=hashed_pin,
                full_name=full_name.strip(),
                role="admin",
                target_lph=400.0,
                shift="Shift 1",
                preferred_theme="Default Dark"
            )
            session.add(new_admin)

        session.commit()
        print("✅ Success! Admin account secured and ready for login.")
    except Exception as e:
        session.rollback()
        print(f"❌ Database Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    print("--- 🛡️ EMERGENCY ADMIN CREATION UTILITY ---")
    u = input("Enter Admin Username: ")
    p = input("Enter Admin PIN: ")
    n = input("Enter Admin Full Name: ")
    e = input("Enter Admin Email: ")
    create_emergency_admin(u, p, n, e)