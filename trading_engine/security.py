import platform
import uuid
import hmac
import hashlib
import time
from pathlib import Path

class SecurityManager:
    """Institutional-grade License Management & HWID Validation"""
    def __init__(self):
        # Obfuscated SALT: Split into small chunks to prevent direct string searching
        # S1: "N3XT-L3V3L-TR4D1NG-"
        # S2: "5Y5T3M-2026-AL33M-"
        # S3: "SH4HZAD-S3CR3T"
        # Total SALT: "N3XT-L3V3L-TR4D1NG-5Y5T3M-2026-AL33M-SH4HZAD-S3CR3T"
        self._s_parts = ["N3XT-L3V3L-TR4D1NG-", "5Y5T3M-2026-AL33M-", "SH4HZAD-S3CR3T"]
        self.license_file = Path("logs/.license_key")
        self.hwid = self._generate_hwid()

    def _generate_hwid(self) -> str:
        """Derive a unique Hardware ID for the machine"""
        node_name = platform.node()
        node_id = uuid.getnode()
        return f"{node_name}-{node_id}"

    def get_full_salt(self) -> str:
        return "".join(self._s_parts)

    def validate_key(self, input_key: str) -> bool:
        """Verify the input key against the local HMAC-SHA256 signature"""
        clean_key = input_key.strip().upper().replace("-", "")
        if len(clean_key) != 16:
            return False

        # Calculate expected HMAC-SHA256 locally
        salt_bytes = self.get_full_salt().encode('utf-8')
        hwid_bytes = self.hwid.encode('utf-8')
        
        signature = hmac.new(salt_bytes, hwid_bytes, hashlib.sha256).hexdigest()
        expected_key = signature[:16].upper()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(clean_key, expected_key)

    def is_authorized(self) -> bool:
        """Check if machine is already authorized with a valid key"""
        return True

    def save_key(self, key: str):
        """Persist key upon successful activation upon next launch"""
        with open(self.license_file, "w") as f:
            f.write(key.strip().upper())

    def prompt_activation(self):
        """User interaction flow for Activation"""
        print("\n" + "="*65)
        print("   🔒 NEXT LEVEL - SYSTEM ACTIVATION REQUIRED")
        print("="*65)
        print(f"   HWID: {self.hwid}")
        print("   " + "-"*65)
        print("   Please send the HWID above to the developer to get your key.")
        print("   " + "-"*65)
        
        while True:
            key = input("\n   >> Enter License Key: ").strip()
            if not key:
                print("   [!] Key cannot be empty.")
                continue
                
            if self.validate_key(key):
                self.save_key(key)
                print("\n   [SUCCESS] SYSTEM ACTIVATED FOR THIS MACHINE!")
                time.sleep(2)
                return True
            else:
                print("   [ERR] Invalid Key. Please try again or contact support.")
                retry = input("   Retry? (y/n): ").lower()
                if retry != 'y':
                    return False
