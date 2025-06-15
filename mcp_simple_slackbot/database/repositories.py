from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .encryption import get_encryption_service
from .models import (
    Conversation,
    MCPServer,
    Message,
    User,
    UserCredential,
    UserServerConfig,
)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.encryption = get_encryption_service()

    async def create_user(
        self,
        slack_user_id: str,
        slack_team_id: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        real_name: Optional[str] = None,
    ) -> User:
        user = User(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            email=email,
            display_name=display_name,
            real_name=real_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_user_by_slack_id(
        self, slack_user_id: str, slack_team_id: str
    ) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(
                and_(
                    User.slack_user_id == slack_user_id,
                    User.slack_team_id == slack_team_id,
                    User.is_active,
                )
            )
            .options(selectinload(User.credentials), selectinload(User.server_configs))
        )
        return result.scalar_one_or_none()

    async def get_or_create_user(
        self, slack_user_id: str, slack_team_id: str, **kwargs
    ) -> User:
        user = await self.get_user_by_slack_id(slack_user_id, slack_team_id)
        if not user:
            user = await self.create_user(slack_user_id, slack_team_id, **kwargs)
        return user


class CredentialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.encryption = get_encryption_service()

    async def store_credential(
        self, user_id: int, credential_type: str, credential_name: str, value: str
    ) -> UserCredential:
        encrypted_value = self.encryption.encrypt(value)

        existing = await self.session.execute(
            select(UserCredential).where(
                and_(
                    UserCredential.user_id == user_id,
                    UserCredential.credential_type == credential_type,
                    UserCredential.credential_name == credential_name,
                )
            )
        )
        credential = existing.scalar_one_or_none()

        if credential:
            credential.encrypted_value = encrypted_value  # type: ignore[assignment]
        else:
            credential = UserCredential(
                user_id=user_id,
                credential_type=credential_type,
                credential_name=credential_name,
                encrypted_value=encrypted_value,
            )
            self.session.add(credential)

        await self.session.flush()
        return credential

    async def get_credential(
        self, user_id: int, credential_type: str, credential_name: str
    ) -> Optional[str]:
        result = await self.session.execute(
            select(UserCredential).where(
                and_(
                    UserCredential.user_id == user_id,
                    UserCredential.credential_type == credential_type,
                    UserCredential.credential_name == credential_name,
                )
            )
        )
        credential = result.scalar_one_or_none()

        if credential:
            return self.encryption.decrypt(credential.encrypted_value)  # type: ignore[arg-type]
        return None

    async def get_user_credentials(self, user_id: int) -> Dict[str, Dict[str, str]]:
        result = await self.session.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        credentials = result.scalars().all()

        decrypted = {}
        for cred in credentials:
            if cred.credential_type not in decrypted:
                decrypted[cred.credential_type] = {}
            decrypted[cred.credential_type][cred.credential_name] = (
                self.encryption.decrypt(cred.encrypted_value)  # type: ignore[arg-type]
            )

        return decrypted


class ServerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        required_credentials: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
    ) -> MCPServer:
        server = MCPServer(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            required_credentials=required_credentials or [],
            description=description,
        )
        self.session.add(server)
        await self.session.flush()
        return server

    async def get_server_by_name(self, name: str) -> Optional[MCPServer]:
        result = await self.session.execute(
            select(MCPServer).where(and_(MCPServer.name == name, MCPServer.is_active))
        )
        return result.scalar_one_or_none()

    async def get_all_servers(self) -> List[MCPServer]:
        result = await self.session.execute(
            select(MCPServer).where(MCPServer.is_active)
        )
        return list(result.scalars().all())

    async def get_user_enabled_servers(self, user_id: int) -> List[MCPServer]:
        result = await self.session.execute(
            select(MCPServer)
            .join(UserServerConfig)
            .where(
                and_(
                    UserServerConfig.user_id == user_id,
                    UserServerConfig.is_enabled,
                    MCPServer.is_active,
                )
            )
        )
        return list(result.scalars().all())


class UserServerConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enable_server_for_user(
        self, user_id: int, server_id: int, custom_env: Optional[Dict[str, str]] = None
    ) -> UserServerConfig:
        existing = await self.session.execute(
            select(UserServerConfig).where(
                and_(
                    UserServerConfig.user_id == user_id,
                    UserServerConfig.server_id == server_id,
                )
            )
        )
        config = existing.scalar_one_or_none()

        if config:
            config.is_enabled = True  # type: ignore[assignment]
            config.custom_env = custom_env or {}  # type: ignore[assignment]
        else:
            config = UserServerConfig(
                user_id=user_id,
                server_id=server_id,
                is_enabled=True,
                custom_env=custom_env or {},
            )
            self.session.add(config)

        await self.session.flush()
        return config

    async def disable_server_for_user(self, user_id: int, server_id: int) -> bool:
        result = await self.session.execute(
            select(UserServerConfig).where(
                and_(
                    UserServerConfig.user_id == user_id,
                    UserServerConfig.server_id == server_id,
                )
            )
        )
        config = result.scalar_one_or_none()

        if config:
            config.is_enabled = False  # type: ignore[assignment]
            await self.session.flush()
            return True
        return False


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_conversation(
        self, user_id: int, slack_channel_id: str, slack_thread_ts: Optional[str] = None
    ) -> Conversation:
        result = await self.session.execute(
            select(Conversation)
            .where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.slack_channel_id == slack_channel_id,
                    Conversation.slack_thread_ts == slack_thread_ts,
                )
            )
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                slack_channel_id=slack_channel_id,
                slack_thread_ts=slack_thread_ts,
            )
            self.session.add(conversation)
            await self.session.flush()

        return conversation

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        slack_ts: Optional[str] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            slack_ts=slack_ts,
        )
        self.session.add(message)

        conversation = await self.session.get(Conversation, conversation_id)
        if conversation:
            conversation.last_message_at = message.created_at

        await self.session.flush()
        return message

    async def get_conversation_messages(
        self, conversation_id: int, limit: int = 10
    ) -> List[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return messages[::-1]
