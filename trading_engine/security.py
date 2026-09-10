import os
import json
from pathlib import Path
from loguru import logger

class SecurityManager:
    """Manages system security and authorization"""
    
    def __init__(self):
        self.license_file = Path("config/license.json")
        self.authorized = True  # Auto-authorized - no activation required
        self._check_license()
    
    def _check_license(self):
        """Check if valid license exists"""
        try:
            if self.license_file.exists():
                with open(self.license_file, 'r') as f:
                    data = json.load(f)
                    self.authorized = data.get('authorized', True)
        except:
            self.authorized = True
    
    def is_authorized(self) -> bool:
        """Check if system is authorized"""
        return True  # Always authorized
    
    def prompt_activation(self) -> bool:
        """Prompt user for activation key"""
        return True  # Skip activation prompt
