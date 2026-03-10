import hmac
import hashlib
import uuid
import sys
import os

# --- DEVELOPER CONFIGURATION ---
# IMPORTANT: This SALT must match the one used in the SecurityManager exactly.
# Keep this script private.
SECRET_SALT = "N3XT-L3V3L-TR4D1NG-5Y5T3M-2026-AL33M-SH4HZAD-S3CR3T"

def generate_key(hwid):
    """
    Generate 16-character license key based on HWID and SALT.
    Formula: Key = HMAC_SHA256(HWID, SECRET_SALT).hexdigest()[:16].upper()
    """
    hwid_bytes = hwid.strip().encode('utf-8')
    salt_bytes = SECRET_SALT.encode('utf-8')
    
    signature = hmac.new(salt_bytes, hwid_bytes, hashlib.sha256).hexdigest()
    key = signature[:16].upper()
    
    # Format the key with hyphens for better readability: XXXX-XXXX-XXXX-XXXX
    formatted_key = "-".join([key[i:i+4] for i in range(0, len(key), 4)])
    return formatted_key

def get_current_hwid():
    """Utility to get the HWID of the current machine (for testing)"""
    # Simple HWID: Node name + UUID
    import platform
    hwid = f"{platform.node()}-{uuid.getnode()}"
    return hwid

if __name__ == "__main__":
    print("="*50)
    print("   NEXT LEVEL - LICENSE KEY GENERATOR (DEV ONLY)")
    print("="*50)
    
    # Check if HWID is provided as argument
    if len(sys.argv) > 1:
        hwid_input = sys.argv[1]
    else:
        print(f"\n[INFO] Your current machine HWID is: {get_current_hwid()}")
        hwid_input = input("\nEnter User's HWID: ").strip()
    
    if not hwid_input:
        print("[ERR] HWID cannot be empty.")
    else:
        generated_key = generate_key(hwid_input)
        print("\n" + "-"*50)
        print(f"  TARGET HWID : {hwid_input}")
        print(f"  GENERATED KEY: {generated_key}")
        print("-"*50)
        print("\n[SUCCESS] Key generated. Send this to the user.")
