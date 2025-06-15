#!/usr/bin/env python3
"""Initialize the database and run migrations."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from mcp_simple_slackbot.database.session import get_db_manager
from mcp_simple_slackbot.database.encryption import EncryptionService


async def init_database():
    """Initialize the database with tables."""
    print("Initializing database...")
    
    # Check for encryption configuration
    if not os.getenv("ENCRYPTION_KEY") and not os.getenv("MASTER_PASSWORD"):
        print("\nWARNING: No encryption configuration found!")
        print("Please set either ENCRYPTION_KEY or MASTER_PASSWORD environment variable.")
        print("\nTo generate a new encryption key, run:")
        print(f"  export ENCRYPTION_KEY={EncryptionService.generate_key()}")
        print("\nOr set a master password:")
        print("  export MASTER_PASSWORD=your-secure-password")
        return
    
    # Initialize database
    db_manager = get_db_manager()
    
    try:
        # Create all tables
        await db_manager.create_tables()
        print("Database tables created successfully!")
        
        # Test encryption
        encryption = EncryptionService()
        test_string = "test_encryption"
        encrypted = encryption.encrypt(test_string)
        decrypted = encryption.decrypt(encrypted)
        
        if decrypted == test_string:
            print("Encryption service verified successfully!")
        else:
            print("ERROR: Encryption service verification failed!")
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        await db_manager.close()


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(init_database())