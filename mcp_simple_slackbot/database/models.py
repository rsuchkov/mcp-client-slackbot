from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    Text,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    slack_user_id = Column(String(50), unique=True, nullable=False, index=True)
    slack_team_id = Column(String(50), nullable=False, index=True)
    email = Column(String(255))
    display_name = Column(String(255))
    real_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    credentials = relationship("UserCredential", back_populates="user", cascade="all, delete-orphan")
    server_configs = relationship("UserServerConfig", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_slack_ids", "slack_user_id", "slack_team_id"),
    )


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    command = Column(String(255), nullable=False)
    args = Column(JSON, default=list)
    env = Column(JSON, default=dict)
    required_credentials = Column(JSON, default=list)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_configs = relationship("UserServerConfig", back_populates="server", cascade="all, delete-orphan")


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    credential_type = Column(String(50), nullable=False)
    credential_name = Column(String(100), nullable=False)
    encrypted_value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="credentials")

    __table_args__ = (
        UniqueConstraint("user_id", "credential_type", "credential_name", name="uq_user_credential"),
        Index("idx_user_credential", "user_id", "credential_type"),
    )


class UserServerConfig(Base):
    __tablename__ = "user_server_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id = Column(Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    is_enabled = Column(Boolean, default=True)
    custom_env = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="server_configs")
    server = relationship("MCPServer", back_populates="user_configs")

    __table_args__ = (
        UniqueConstraint("user_id", "server_id", name="uq_user_server"),
        Index("idx_user_server", "user_id", "server_id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slack_channel_id = Column(String(50), nullable=False, index=True)
    slack_thread_ts = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    __table_args__ = (
        Index("idx_conversation_lookup", "user_id", "slack_channel_id", "slack_thread_ts"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    slack_ts = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id", "created_at"),
    )