
import os
import sys
from dotenv import load_dotenv

# 1. Load the .env file FIRST before importing database!
load_dotenv()

import bcrypt
from crud import ScopedSession
from models import User


def create_emergency_admin(username, pin, full_name, email=""):
    # This tool only ever creates or elevates to 'admin', so it's held to the
    # same minimum Admin Panel enforces for that role (Finding 9, security
    # posture doc - admin PINs reach the database tools from anywhere on the
    # network, not just a pump on the floor). An emergency reset is not a
    # reason for the resulting account to be weaker than one created the
    # normal way.
    if len((pin or "").strip()) < 6:
        print("❌ Admin accounts need a PIN of at least 6 characters.")
        return 1

    session = ScopedSession()
    try:
        # Check if the user already exists
        existing_user = session.query(User).filter(User.username == username.lower().strip()).first()

        # Hash the new PIN properly with bcrypt
        hashed_pin = bcrypt.hashpw(pin.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Stored as NULL rather than "" when blank - email is UNIQUE, and two
        # accounts both holding "" would collide on that constraint where two
        # NULLs never would.
        email_clean = email.strip().lower() or None

        if existing_user:
            print(f"User '{username}' found. Elevating to 'admin' and resetting PIN.")
            existing_user.role = 'admin'
            existing_user.pin = hashed_pin
        else:
            print(f"Creating brand new emergency admin: '{username}'")
            new_admin = User(
                username=username.lower().strip(),
                email=email_clean,
                pin=hashed_pin,
                full_name=full_name.strip(),
                role="admin",
                target_lph=400.0,
                shift="Shift 1",
                preferred_theme="Formlabs Forge"
            )
            session.add(new_admin)

        session.commit()
        print("✅ Success! Admin account secured and ready for login.")
    except Exception as e:
        session.rollback()
        print(f"❌ Database Error: {e}")
        return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    # Non-interactive form, so a clean install can guarantee a working login
    # without anybody sitting at a keyboard:
    #     python create_admin.py <username> <pin> <full name> [email]
    # Interactive form is unchanged for everyone else who runs this by hand.
    if len(sys.argv) >= 4:
        u, p, n = sys.argv[1], sys.argv[2], sys.argv[3]
        e = sys.argv[4] if len(sys.argv) >= 5 else ""
        sys.exit(create_emergency_admin(u, p, n, e))

    print("--- 🛡️ EMERGENCY ADMIN CREATION UTILITY ---")
    u = input("Enter Admin Username: ")
    p = input("Enter Admin PIN: ")
    n = input("Enter Admin Full Name: ")
    e = input("Enter Admin Email: ")
    sys.exit(create_emergency_admin(u, p, n, e))
