from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_simple_slackbot.database.models import (
    Conversation,
    MCPServer,
    Message,
    User,
    UserCredential,
    UserServerConfig,
)


class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession, sample_user_data: dict):
        """Test creating a user."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        assert user.id is not None
        assert user.slack_user_id == sample_user_data["slack_user_id"]
        assert user.slack_team_id == sample_user_data["slack_team_id"]
        assert user.email == sample_user_data["email"]
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)

    @pytest.mark.asyncio
    async def test_user_relationships(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test user model relationships."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        # Test that relationships are properly initialized
        assert user.credentials == []
        assert user.server_configs == []
        assert user.conversations == []


class TestMCPServerModel:
    @pytest.mark.asyncio
    async def test_create_mcp_server(
        self, db_session: AsyncSession, sample_server_config: dict
    ):
        """Test creating an MCP server."""
        server = MCPServer(**sample_server_config)
        db_session.add(server)
        await db_session.flush()
        
        assert server.id is not None
        assert server.name == sample_server_config["name"]
        assert server.command == sample_server_config["command"]
        assert server.args == sample_server_config["args"]
        assert server.env == sample_server_config["env"]
        assert server.is_active is True

    @pytest.mark.asyncio
    async def test_server_relationships(
        self, db_session: AsyncSession, sample_server_config: dict
    ):
        """Test server model relationships."""
        server = MCPServer(**sample_server_config)
        db_session.add(server)
        await db_session.flush()
        
        assert server.user_configs == []


class TestUserCredentialModel:
    @pytest.mark.asyncio
    async def test_create_user_credential(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test creating a user credential."""
        # First create a user
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        # Create credential
        credential = UserCredential(
            user_id=user.id,
            credential_type="api_key",
            credential_name="test_api_key",
            encrypted_value="encrypted_test_value",
        )
        db_session.add(credential)
        await db_session.flush()
        
        assert credential.id is not None
        assert credential.user_id == user.id
        assert credential.credential_type == "api_key"
        assert credential.credential_name == "test_api_key"
        assert credential.encrypted_value == "encrypted_test_value"

    @pytest.mark.asyncio
    async def test_credential_user_relationship(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test credential-user relationship."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        credential = UserCredential(
            user_id=user.id,
            credential_type="api_key",
            credential_name="test_key",
            encrypted_value="encrypted_value",
        )
        db_session.add(credential)
        await db_session.flush()
        
        # Refresh to load relationships
        await db_session.refresh(user)
        await db_session.refresh(credential)
        
        assert credential.user == user
        assert credential in user.credentials


class TestUserServerConfigModel:
    @pytest.mark.asyncio
    async def test_create_user_server_config(
        self,
        db_session: AsyncSession,
        sample_user_data: dict,
        sample_server_config: dict,
    ):
        """Test creating a user server configuration."""
        # Create user and server
        user = User(**sample_user_data)
        server = MCPServer(**sample_server_config)
        db_session.add(user)
        db_session.add(server)
        await db_session.flush()
        
        # Create config
        config = UserServerConfig(
            user_id=user.id,
            server_id=server.id,
            is_enabled=True,
            custom_env={"CUSTOM_VAR": "value"},
        )
        db_session.add(config)
        await db_session.flush()
        
        assert config.id is not None
        assert config.user_id == user.id
        assert config.server_id == server.id
        assert config.is_enabled is True
        assert config.custom_env == {"CUSTOM_VAR": "value"}

    @pytest.mark.asyncio
    async def test_user_server_relationships(
        self,
        db_session: AsyncSession,
        sample_user_data: dict,
        sample_server_config: dict,
    ):
        """Test user-server configuration relationships."""
        user = User(**sample_user_data)
        server = MCPServer(**sample_server_config)
        db_session.add(user)
        db_session.add(server)
        await db_session.flush()
        
        config = UserServerConfig(
            user_id=user.id,
            server_id=server.id,
            is_enabled=True,
        )
        db_session.add(config)
        await db_session.flush()
        
        # Refresh to load relationships
        await db_session.refresh(user)
        await db_session.refresh(server)
        await db_session.refresh(config)
        
        assert config.user == user
        assert config.server == server
        assert config in user.server_configs
        assert config in server.user_configs


class TestConversationModel:
    @pytest.mark.asyncio
    async def test_create_conversation(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test creating a conversation."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        conversation = Conversation(
            user_id=user.id,
            slack_channel_id="C123456789",
            slack_thread_ts="1234567890.123456",
        )
        db_session.add(conversation)
        await db_session.flush()
        
        assert conversation.id is not None
        assert conversation.user_id == user.id
        assert conversation.slack_channel_id == "C123456789"
        assert conversation.slack_thread_ts == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_conversation_user_relationship(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test conversation-user relationship."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        conversation = Conversation(
            user_id=user.id,
            slack_channel_id="C123456789",
        )
        db_session.add(conversation)
        await db_session.flush()
        
        # Refresh to load relationships
        await db_session.refresh(user)
        await db_session.refresh(conversation)
        
        assert conversation.user == user
        assert conversation in user.conversations


class TestMessageModel:
    @pytest.mark.asyncio
    async def test_create_message(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test creating a message."""
        user = User(**sample_user_data)
        db_session.add(user)
        await db_session.flush()
        
        conversation = Conversation(
            user_id=user.id,
            slack_channel_id="C123456789",
        )
        db_session.add(conversation)
        await db_session.flush()
        
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, world!",
            slack_ts="1234567890.123456",
        )
        db_session.add(message)
        await db_session.flush()
        
        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.slack_ts == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_message_conversation_relationship(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test message-conversation relationship."""
        user = User(**sample_user_data)
        conversation = Conversation(
            user_id=user.id,
            slack_channel_id="C123456789",
        )
        db_session.add(user)
        db_session.add(conversation)
        await db_session.flush()
        
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Test message",
        )
        db_session.add(message)
        await db_session.flush()
        
        # Refresh to load relationships
        await db_session.refresh(conversation)
        await db_session.refresh(message)
        
        assert message.conversation == conversation
        assert message in conversation.messages