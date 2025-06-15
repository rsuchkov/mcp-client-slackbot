import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_simple_slackbot.database.repositories import (
    ConversationRepository,
    CredentialRepository,
    ServerRepository,
    UserRepository,
    UserServerConfigRepository,
)


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession, sample_user_data: dict):
        """Test creating a user through repository."""
        repo = UserRepository(db_session)
        
        user = await repo.create_user(**sample_user_data)
        
        assert user.id is not None
        assert user.slack_user_id == sample_user_data["slack_user_id"]
        assert user.slack_team_id == sample_user_data["slack_team_id"]
        assert user.email == sample_user_data["email"]

    @pytest.mark.asyncio
    async def test_get_user_by_slack_id(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving user by Slack ID."""
        repo = UserRepository(db_session)
        
        # Create user first
        created_user = await repo.create_user(**sample_user_data)
        await db_session.commit()
        
        # Retrieve user
        retrieved_user = await repo.get_user_by_slack_id(
            sample_user_data["slack_user_id"], sample_user_data["slack_team_id"]
        )
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.slack_user_id == sample_user_data["slack_user_id"]

    @pytest.mark.asyncio
    async def test_get_user_by_slack_id_not_found(
        self, db_session: AsyncSession
    ):
        """Test retrieving non-existent user returns None."""
        repo = UserRepository(db_session)
        
        user = await repo.get_user_by_slack_id("NONEXISTENT", "TEAM123")
        
        assert user is None

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test get_or_create with existing user."""
        repo = UserRepository(db_session)
        
        # Create user first
        created_user = await repo.create_user(**sample_user_data)
        await db_session.commit()
        
        # Get or create should return existing user
        user = await repo.get_or_create_user(
            sample_user_data["slack_user_id"], sample_user_data["slack_team_id"]
        )
        
        assert user.id == created_user.id

    @pytest.mark.asyncio
    async def test_get_or_create_user_new(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test get_or_create with new user."""
        repo = UserRepository(db_session)
        
        # Get or create should create new user
        user = await repo.get_or_create_user(
            sample_user_data["slack_user_id"],
            sample_user_data["slack_team_id"],
            email=sample_user_data["email"],
        )
        
        assert user.id is not None
        assert user.slack_user_id == sample_user_data["slack_user_id"]
        assert user.email == sample_user_data["email"]


class TestCredentialRepository:
    @pytest.mark.asyncio
    async def test_store_credential(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test storing a credential."""
        user_repo = UserRepository(db_session)
        cred_repo = CredentialRepository(db_session)
        
        # Create user
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        # Store credential
        credential = await cred_repo.store_credential(
            user.id, "api_key", "test_key", "secret_value"
        )
        
        assert credential.id is not None
        assert credential.user_id == user.id
        assert credential.credential_type == "api_key"
        assert credential.credential_name == "test_key"
        # Value should be encrypted
        assert credential.encrypted_value != "secret_value"

    @pytest.mark.asyncio
    async def test_get_credential(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving a credential."""
        user_repo = UserRepository(db_session)
        cred_repo = CredentialRepository(db_session)
        
        # Create user and store credential
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        await cred_repo.store_credential(user.id, "api_key", "test_key", "secret_value")
        await db_session.commit()
        
        # Retrieve credential
        value = await cred_repo.get_credential(user.id, "api_key", "test_key")
        
        assert value == "secret_value"

    @pytest.mark.asyncio
    async def test_get_credential_not_found(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving non-existent credential returns None."""
        user_repo = UserRepository(db_session)
        cred_repo = CredentialRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        value = await cred_repo.get_credential(user.id, "api_key", "nonexistent")
        
        assert value is None

    @pytest.mark.asyncio
    async def test_update_existing_credential(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test updating an existing credential."""
        user_repo = UserRepository(db_session)
        cred_repo = CredentialRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        # Store initial credential
        await cred_repo.store_credential(user.id, "api_key", "test_key", "old_value")
        
        # Update credential
        await cred_repo.store_credential(user.id, "api_key", "test_key", "new_value")
        await db_session.commit()
        
        # Verify updated value
        value = await cred_repo.get_credential(user.id, "api_key", "test_key")
        assert value == "new_value"

    @pytest.mark.asyncio
    async def test_get_user_credentials(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving all user credentials."""
        user_repo = UserRepository(db_session)
        cred_repo = CredentialRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        # Store multiple credentials
        await cred_repo.store_credential(user.id, "api_key", "service1", "key1")
        await cred_repo.store_credential(user.id, "api_key", "service2", "key2")
        await cred_repo.store_credential(user.id, "password", "db_pass", "dbpass")
        await db_session.commit()
        
        credentials = await cred_repo.get_user_credentials(user.id)
        
        assert "api_key" in credentials
        assert "password" in credentials
        assert credentials["api_key"]["service1"] == "key1"
        assert credentials["api_key"]["service2"] == "key2"
        assert credentials["password"]["db_pass"] == "dbpass"


class TestServerRepository:
    @pytest.mark.asyncio
    async def test_create_server(
        self, db_session: AsyncSession, sample_server_config: dict
    ):
        """Test creating a server."""
        repo = ServerRepository(db_session)
        
        server = await repo.create_server(**sample_server_config)
        
        assert server.id is not None
        assert server.name == sample_server_config["name"]
        assert server.command == sample_server_config["command"]

    @pytest.mark.asyncio
    async def test_get_server_by_name(
        self, db_session: AsyncSession, sample_server_config: dict
    ):
        """Test retrieving server by name."""
        repo = ServerRepository(db_session)
        
        # Create server
        created_server = await repo.create_server(**sample_server_config)
        await db_session.commit()
        
        # Retrieve server
        retrieved_server = await repo.get_server_by_name(sample_server_config["name"])
        
        assert retrieved_server is not None
        assert retrieved_server.id == created_server.id

    @pytest.mark.asyncio
    async def test_get_server_by_name_not_found(self, db_session: AsyncSession):
        """Test retrieving non-existent server returns None."""
        repo = ServerRepository(db_session)
        
        server = await repo.get_server_by_name("nonexistent")
        
        assert server is None

    @pytest.mark.asyncio
    async def test_get_all_servers(
        self, db_session: AsyncSession, sample_server_config: dict
    ):
        """Test retrieving all active servers."""
        repo = ServerRepository(db_session)
        
        # Create multiple servers
        config1 = sample_server_config.copy()
        config1["name"] = "server1"
        
        config2 = sample_server_config.copy()
        config2["name"] = "server2"
        
        await repo.create_server(**config1)
        await repo.create_server(**config2)
        await db_session.commit()
        
        servers = await repo.get_all_servers()
        
        assert len(servers) == 2
        server_names = {server.name for server in servers}
        assert "server1" in server_names
        assert "server2" in server_names


class TestUserServerConfigRepository:
    @pytest.mark.asyncio
    async def test_enable_server_for_user(
        self,
        db_session: AsyncSession,
        sample_user_data: dict,
        sample_server_config: dict,
    ):
        """Test enabling a server for a user."""
        user_repo = UserRepository(db_session)
        server_repo = ServerRepository(db_session)
        config_repo = UserServerConfigRepository(db_session)
        
        # Create user and server
        user = await user_repo.create_user(**sample_user_data)
        server = await server_repo.create_server(**sample_server_config)
        await db_session.flush()
        
        # Enable server for user
        config = await config_repo.enable_server_for_user(
            user.id, server.id, {"CUSTOM_VAR": "value"}
        )
        
        assert config.id is not None
        assert config.user_id == user.id
        assert config.server_id == server.id
        assert config.is_enabled is True
        assert config.custom_env == {"CUSTOM_VAR": "value"}

    @pytest.mark.asyncio
    async def test_disable_server_for_user(
        self,
        db_session: AsyncSession,
        sample_user_data: dict,
        sample_server_config: dict,
    ):
        """Test disabling a server for a user."""
        user_repo = UserRepository(db_session)
        server_repo = ServerRepository(db_session)
        config_repo = UserServerConfigRepository(db_session)
        
        # Create user and server
        user = await user_repo.create_user(**sample_user_data)
        server = await server_repo.create_server(**sample_server_config)
        await db_session.flush()
        
        # Enable then disable
        await config_repo.enable_server_for_user(user.id, server.id)
        result = await config_repo.disable_server_for_user(user.id, server.id)
        await db_session.commit()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_disable_nonexistent_server_config(
        self,
        db_session: AsyncSession,
        sample_user_data: dict,
        sample_server_config: dict,
    ):
        """Test disabling non-existent server config returns False."""
        user_repo = UserRepository(db_session)
        server_repo = ServerRepository(db_session)
        config_repo = UserServerConfigRepository(db_session)
        
        # Create user and server but no config
        user = await user_repo.create_user(**sample_user_data)
        server = await server_repo.create_server(**sample_server_config)
        await db_session.flush()
        
        result = await config_repo.disable_server_for_user(user.id, server.id)
        
        assert result is False


class TestConversationRepository:
    @pytest.mark.asyncio
    async def test_get_or_create_conversation_new(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test creating a new conversation."""
        user_repo = UserRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        conversation = await conv_repo.get_or_create_conversation(
            user.id, "C123456789", "1234567890.123456"
        )
        
        assert conversation.id is not None
        assert conversation.user_id == user.id
        assert conversation.slack_channel_id == "C123456789"
        assert conversation.slack_thread_ts == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_existing(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving existing conversation."""
        user_repo = UserRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        # Create conversation
        conv1 = await conv_repo.get_or_create_conversation(user.id, "C123456789")
        await db_session.commit()
        
        # Get same conversation
        conv2 = await conv_repo.get_or_create_conversation(user.id, "C123456789")
        
        assert conv1.id == conv2.id

    @pytest.mark.asyncio
    async def test_add_message(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test adding a message to conversation."""
        user_repo = UserRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        conversation = await conv_repo.get_or_create_conversation(user.id, "C123456789")
        await db_session.flush()
        
        message = await conv_repo.add_message(
            conversation.id, "user", "Hello world!", "1234567890.123456"
        )
        
        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "Hello world!"
        assert message.slack_ts == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_get_conversation_messages(
        self, db_session: AsyncSession, sample_user_data: dict
    ):
        """Test retrieving conversation messages."""
        user_repo = UserRepository(db_session)
        conv_repo = ConversationRepository(db_session)
        
        user = await user_repo.create_user(**sample_user_data)
        await db_session.flush()
        
        conversation = await conv_repo.get_or_create_conversation(user.id, "C123456789")
        await db_session.flush()
        
        # Add multiple messages
        await conv_repo.add_message(conversation.id, "user", "Message 1")
        await conv_repo.add_message(conversation.id, "assistant", "Response 1")
        await conv_repo.add_message(conversation.id, "user", "Message 2")
        await db_session.commit()
        
        messages = await conv_repo.get_conversation_messages(conversation.id, limit=5)
        
        assert len(messages) == 3
        # Messages should be in chronological order
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Response 1"
        assert messages[2].content == "Message 2"