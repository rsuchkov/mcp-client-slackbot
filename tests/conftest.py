import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_simple_slackbot.database.encryption import EncryptionService
from mcp_simple_slackbot.database.session import DatabaseManager


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    db_url = f"sqlite+aiosqlite:///{db_path}"
    yield db_url
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest_asyncio.fixture
async def db_manager(temp_db: str) -> AsyncGenerator[DatabaseManager, None]:
    """Create a database manager with a temporary database."""
    manager = DatabaseManager(temp_db)
    await manager.create_tables()
    yield manager
    await manager.close()


@pytest_asyncio.fixture
async def db_session(db_manager: DatabaseManager) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async with db_manager.session() as session:
        yield session


@pytest.fixture
def encryption_service() -> EncryptionService:
    """Create an encryption service with a test key."""
    test_key = EncryptionService.generate_key()
    return EncryptionService(test_key)


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user data for testing."""
    return {
        "slack_user_id": "U123456789",
        "slack_team_id": "T123456789",
        "email": "test@example.com",
        "display_name": "Test User",
        "real_name": "Test User Real",
    }


@pytest.fixture
def sample_server_config() -> dict:
    """Sample MCP server configuration for testing."""
    return {
        "name": "test-server",
        "command": "python",
        "args": ["-m", "test_server"],
        "env": {
            "API_KEY": "${API_KEY}",
            "DATABASE_URL": "sqlite:///test.db",
        },
        "required_credentials": [
            {
                "type": "api_key",
                "name": "API Key",
                "description": "Required API key for the service",
                "env_var": "API_KEY",
            }
        ],
    }