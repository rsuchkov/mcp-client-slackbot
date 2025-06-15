"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slack_user_id", sa.String(length=50), nullable=False),
        sa.Column("slack_team_id", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("real_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_slack_ids", "users", ["slack_user_id", "slack_team_id"], unique=False
    )
    op.create_index(
        op.f("ix_users_slack_team_id"), "users", ["slack_team_id"], unique=False
    )
    op.create_index(
        op.f("ix_users_slack_user_id"), "users", ["slack_user_id"], unique=True
    )

    # Create mcp_servers table
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("command", sa.String(length=255), nullable=False),
        sa.Column("args", sa.JSON(), nullable=True),
        sa.Column("env", sa.JSON(), nullable=True),
        sa.Column("required_credentials", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create user_credentials table
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_type", sa.String(length=50), nullable=False),
        sa.Column("credential_name", sa.String(length=100), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "credential_type", "credential_name", name="uq_user_credential"
        ),
    )
    op.create_index(
        "idx_user_credential",
        "user_credentials",
        ["user_id", "credential_type"],
        unique=False,
    )

    # Create user_server_configs table
    op.create_table(
        "user_server_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("custom_env", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "server_id", name="uq_user_server"),
    )
    op.create_index(
        "idx_user_server", "user_server_configs", ["user_id", "server_id"], unique=False
    )

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slack_channel_id", sa.String(length=50), nullable=False),
        sa.Column("slack_thread_ts", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_conversation_lookup",
        "conversations",
        ["user_id", "slack_channel_id", "slack_thread_ts"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_slack_channel_id"),
        "conversations",
        ["slack_channel_id"],
        unique=False,
    )

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("slack_ts", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_message_conversation",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_message_conversation", table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_conversations_slack_channel_id"), table_name="conversations")
    op.drop_index("idx_conversation_lookup", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("idx_user_server", table_name="user_server_configs")
    op.drop_table("user_server_configs")
    op.drop_index("idx_user_credential", table_name="user_credentials")
    op.drop_table("user_credentials")
    op.drop_table("mcp_servers")
    op.drop_index(op.f("ix_users_slack_user_id"), table_name="users")
    op.drop_index(op.f("ix_users_slack_team_id"), table_name="users")
    op.drop_index("idx_user_slack_ids", table_name="users")
    op.drop_table("users")
