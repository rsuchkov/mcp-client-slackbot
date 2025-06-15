import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from .database.repositories import (
    ConversationRepository,
    CredentialRepository,
    ServerRepository,
    UserRepository,
)
from .database.session import get_db_manager
from .services.mcp_metadata import MCPMetadataParser
from .services.slack_auth import SlackAuthService
from .services.user_server import UserServerManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Configuration:
    """Manages configuration and environment variables for the MCP Slackbot."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.load_env()
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4-turbo")
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost/mcp_slackbot",
        )
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        self.master_password = os.getenv("MASTER_PASSWORD")

    @staticmethod
    def load_env() -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """Load server configuration from JSON file."""
        with open(file_path, "r") as f:
            return json.load(f)

    @property
    def llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on the model."""
        if "gpt" in self.llm_model.lower() and self.openai_api_key:
            return self.openai_api_key
        elif "llama" in self.llm_model.lower() and self.groq_api_key:
            return self.groq_api_key
        elif "claude" in self.llm_model.lower() and self.anthropic_api_key:
            return self.anthropic_api_key

        # Fallback to any available key
        if self.openai_api_key:
            return self.openai_api_key
        elif self.groq_api_key:
            return self.groq_api_key
        elif self.anthropic_api_key:
            return self.anthropic_api_key

        raise ValueError("No API key found for any LLM provider")


class Tool:
    """Represents a tool available from MCP servers."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        server_name: str,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.server_name = server_name

    def format_for_llm(self) -> str:
        """Format tool information for LLM understanding."""
        schema_str = json.dumps(self.input_schema, indent=2)
        return f"""Tool: {self.name}
Server: {self.server_name}
Description: {self.description}
Input Schema:
{schema_str}"""


class LLMClient:
    """Handles communication with various LLM providers."""

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Tool]] = None
    ) -> str:
        """Get response from the configured LLM."""
        llm_model = self.config.llm_model.lower()

        if "gpt" in llm_model:
            return await self._get_openai_response(messages, tools)
        elif "llama" in llm_model:
            return await self._get_groq_response(messages, tools)
        elif "claude" in llm_model:
            return await self._get_anthropic_response(messages, tools)
        else:
            return await self._get_openai_response(messages, tools)

    async def _get_openai_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Tool]] = None
    ) -> str:  # type: ignore[no-untyped-def]
        """Get response from OpenAI API."""
        system_message = self._build_system_message(tools)

        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.config.llm_model,
            "messages": [{"role": "system", "content": system_message}] + messages,
            "temperature": 0.7,
        }

        for attempt in range(3):
            try:
                response = await self.client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == 2:
                    logger.error(f"OpenAI API error after 3 attempts: {e}")
                    raise
                await asyncio.sleep(2**attempt)

    async def _get_groq_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Tool]] = None
    ) -> str:  # type: ignore[no-untyped-def]
        """Get response from Groq API."""
        system_message = self._build_system_message(tools)

        headers = {
            "Authorization": f"Bearer {self.config.groq_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.config.llm_model,
            "messages": [{"role": "system", "content": system_message}] + messages,
            "temperature": 0.7,
        }

        for attempt in range(3):
            try:
                response = await self.client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Groq API error after 3 attempts: {e}")
                    raise
                await asyncio.sleep(2**attempt)

    async def _get_anthropic_response(
        self, messages: List[Dict[str, str]], tools: Optional[List[Tool]] = None
    ) -> str:  # type: ignore[no-untyped-def]
        """Get response from Anthropic API."""
        system_message = self._build_system_message(tools)

        headers = {
            "x-api-key": self.config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        anthropic_messages = []
        for msg in messages:
            anthropic_messages.append(
                {
                    "role": msg["role"] if msg["role"] != "system" else "user",
                    "content": msg["content"],
                }
            )

        data = {
            "model": self.config.llm_model,
            "system": system_message,
            "messages": anthropic_messages,
            "max_tokens": 4096,
        }

        for attempt in range(3):
            try:
                response = await self.client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                return response.json()["content"][0]["text"]
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Anthropic API error after 3 attempts: {e}")
                    raise
                await asyncio.sleep(2**attempt)

    def _build_system_message(self, tools: Optional[List[Tool]] = None) -> str:
        """Build system message with tool information."""
        base_message = """You are a helpful AI assistant integrated with Slack. 
You can execute tools to help users with various tasks.

When you need to execute a tool, use the following format:
[TOOL: tool_name]
{
  "arg1": "value1",
  "arg2": "value2"
}
[/TOOL]

You can use multiple tools in a single response if needed."""

        if tools:
            tool_descriptions = "\n\n".join([tool.format_for_llm() for tool in tools])
            return f"{base_message}\n\nAvailable tools:\n\n{tool_descriptions}"

        return base_message

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class SlackMCPBot:
    """Main bot class handling Slack integration with multi-user support."""

    def __init__(
        self,
        config: Configuration,
        llm_client: LLMClient,
    ) -> None:
        self.config = config
        self.llm_client = llm_client
        self.user_server_manager = UserServerManager()
        self.db_manager = get_db_manager()

        # Initialize Slack app
        self.app = AsyncApp(token=config.slack_bot_token)
        self.socket_mode_handler = AsyncSocketModeHandler(
            self.app, config.slack_app_token
        )
        self.slack_client = AsyncWebClient(token=config.slack_bot_token)
        self.auth_service = SlackAuthService(self.slack_client)

        # Bot info
        self.bot_id: Optional[str] = None
        self.team_id: Optional[str] = None

        # Setup event handlers
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Setup Slack event handlers."""

        # Handle mentions
        @self.app.event("app_mention")
        async def handle_mention(event: Dict[str, Any], say: Any) -> None:
            await self._handle_mention(event, say)

        # Handle direct messages
        @self.app.message("")
        async def handle_message(message: Dict[str, Any], say: Any) -> None:
            await self._handle_message(message, say)

        # Handle app home opened
        @self.app.event("app_home_opened")
        async def handle_home_opened(
            event: Dict[str, Any], client: AsyncWebClient
        ) -> None:
            await self._handle_home_opened(event, client)

        # Handle interactive actions
        @self.app.action("submit_credential")
        async def handle_credential_submission(ack: Any, body: Dict[str, Any]) -> None:
            await ack()
            await self._handle_credential_submission(body)

        @self.app.action("cancel_credential_flow")
        async def handle_credential_cancel(ack: Any, body: Dict[str, Any]) -> None:
            await ack()
            await self._handle_credential_cancel(body)

    async def initialize(self) -> None:
        """Initialize the bot, database, and load server configurations."""
        # Initialize database
        await self.db_manager.create_tables()

        # Get bot info
        auth_response = await self.slack_client.auth_test()
        self.bot_id = auth_response["user_id"]
        self.team_id = auth_response["team_id"]

        # Load and sync server configurations
        await self._sync_server_configurations()

    async def _sync_server_configurations(self) -> None:
        """Sync server configurations from JSON to database."""
        config_file = "servers_config.json"
        if os.path.exists(config_file):
            config_data = self.config.load_config(config_file)

            async with self.db_manager.session() as session:
                server_repo = ServerRepository(session)

                for server_name, server_config in config_data.get(
                    "mcpServers", {}
                ).items():
                    existing = await server_repo.get_server_by_name(server_name)

                    if not existing:
                        # Parse required credentials
                        required_creds = MCPMetadataParser.parse_server_metadata(
                            server_config
                        )
                        required_creds_data = [
                            {
                                "type": cred.type,
                                "name": cred.name,
                                "description": cred.description,
                                "env_var": cred.env_var,
                                "validation_regex": cred.validation_regex,
                            }
                            for cred in required_creds
                        ]

                        await server_repo.create_server(
                            name=server_name,
                            command=server_config.get("command", ""),
                            args=server_config.get("args", []),
                            env=server_config.get("env", {}),
                            required_credentials=required_creds_data,
                            description=server_config.get("description", ""),
                        )

    async def _get_or_create_user(self, slack_user_id: str) -> Any:
        """Get or create user from Slack ID."""
        async with self.db_manager.session() as session:
            user_repo = UserRepository(session)

            # Try to get user info from Slack
            try:
                user_info = await self.slack_client.users_info(user=slack_user_id)
                profile = user_info.get("user", {}).get("profile", {})

                return await user_repo.get_or_create_user(
                    slack_user_id=slack_user_id,
                    slack_team_id=self.team_id or "",
                    email=profile.get("email"),
                    display_name=profile.get("display_name"),
                    real_name=profile.get("real_name"),
                )
            except SlackApiError:
                # Fallback if we can't get user info
                return await user_repo.get_or_create_user(
                    slack_user_id=slack_user_id, slack_team_id=self.team_id or ""
                )

    async def _handle_mention(self, event: Dict[str, Any], say: Any) -> None:
        """Handle @mentions in channels."""
        user_id = event.get("user")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts", event.get("ts"))
        text = event.get("text", "")

        if not user_id or not channel_id or not thread_ts:
            return

        # Remove bot mention from text
        text = text.replace(f"<@{self.bot_id}>", "").strip()

        await self._process_user_message(user_id, channel_id, thread_ts, text, say)

    async def _handle_message(self, message: Dict[str, Any], say: Any) -> None:
        """Handle direct messages."""
        # Skip bot's own messages
        if message.get("user") == self.bot_id:
            return

        user_id = message.get("user")
        channel_id = message.get("channel")
        thread_ts = message.get("thread_ts", message.get("ts"))
        text = message.get("text", "")

        if not user_id or not channel_id or not thread_ts:
            return

        await self._process_user_message(user_id, channel_id, thread_ts, text, say)

    async def _process_user_message(
        self, user_id: str, channel_id: str, thread_ts: str, text: str, say: Any
    ) -> None:
        """Process a message from a user."""
        # Get or create user
        user = await self._get_or_create_user(user_id)

        # Get user's available tools
        tools = await self._get_user_tools(user)

        # Get conversation history
        async with self.db_manager.session() as session:
            conv_repo = ConversationRepository(session)
            conversation = await conv_repo.get_or_create_conversation(
                user_id=user.id, slack_channel_id=channel_id, slack_thread_ts=thread_ts
            )

            # Add user message
            await conv_repo.add_message(
                conversation_id=conversation.id,  # type: ignore[arg-type]
                role="user",
                content=text,
                slack_ts=thread_ts,
            )

            # Get recent messages
            messages = await conv_repo.get_conversation_messages(
                conversation_id=conversation.id, limit=10  # type: ignore[arg-type]
            )

            # Format messages for LLM
            llm_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

        # Get LLM response
        try:
            thinking_msg = await say(text="🤔 Thinking...", thread_ts=thread_ts)

            # Convert tools to Tool objects
            tool_objects = [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    input_schema=tool["inputSchema"],
                    server_name=tool["server"],
                )
                for tool in tools
            ]

            response = await self.llm_client.get_response(llm_messages, tool_objects)  # type: ignore[no-untyped-call]

            # Process tool calls
            if response:
                response = await self._process_tool_calls(user, response)
            else:
                response = "Sorry, I couldn't generate a response."

            # Update thinking message with response
            await self.slack_client.chat_update(
                channel=channel_id, ts=thinking_msg["ts"], text=response
            )

            # Save assistant response
            async with self.db_manager.session() as session:
                conv_repo = ConversationRepository(session)
                await conv_repo.add_message(
                    conversation_id=conversation.id,  # type: ignore[arg-type]
                    role="assistant",
                    content=response,
                    slack_ts=thinking_msg["ts"],
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await say(
                text=f"❌ Sorry, I encountered an error: {str(e)}", thread_ts=thread_ts
            )

    async def _get_user_tools(self, user: Any) -> List[Dict[str, Any]]:
        """Get available tools for a user."""
        tools = []

        async with self.db_manager.session() as session:
            server_repo = ServerRepository(session)
            cred_repo = CredentialRepository(session)

            # Get user's enabled servers
            servers = await server_repo.get_user_enabled_servers(user.id)  # type: ignore[arg-type]

            for server in servers:
                # Check if user has required credentials
                missing_creds = await self.auth_service.check_missing_credentials(
                    user.slack_user_id,  # type: ignore[arg-type]
                    self.team_id or "",
                    server.name,  # type: ignore[arg-type]
                    {
                        "command": server.command,
                        "args": server.args,
                        "env": server.env,
                        "required_credentials": server.required_credentials,
                    },
                )

                if not missing_creds:
                    # Get user credentials for this server
                    user_creds = await cred_repo.get_user_credentials(user.id)  # type: ignore[arg-type]
                    server_creds = user_creds.get(server.name, {})  # type: ignore[arg-type]

                    # Get or create user server instance
                    user_server = await self.user_server_manager.get_or_create_server(
                        user, server, server_creds
                    )

                    if user_server:
                        server_tools = await user_server.list_tools()
                        for tool in server_tools:
                            tool["server"] = server.name
                        tools.extend(server_tools)

        return tools

    async def _process_tool_calls(self, user: Any, response: str) -> str:
        """Process tool calls in the response."""
        import re

        # Find all tool calls
        tool_pattern = r"\[TOOL:\s*(\w+)\]\s*(.*?)\[/TOOL\]"
        matches = re.finditer(tool_pattern, response, re.DOTALL)

        for match in matches:
            tool_name = match.group(1)
            tool_args_str = match.group(2).strip()

            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                continue

            # Find the server that has this tool
            user_servers = await self.user_server_manager.get_user_servers(user)

            for user_server in user_servers:
                tools = await user_server.list_tools()
                if any(tool["name"] == tool_name for tool in tools):
                    try:
                        result = await user_server.call_tool(tool_name, tool_args)
                        # Replace tool call with result
                        response = response.replace(
                            match.group(0),
                            f"Tool result: {json.dumps(result, indent=2)}",
                        )
                    except Exception as e:
                        response = response.replace(
                            match.group(0), f"Tool error: {str(e)}"
                        )
                    break

        return response

    async def _handle_home_opened(
        self, event: Dict[str, Any], client: AsyncWebClient
    ) -> None:
        """Handle app home opened event."""
        user_id = event["user"]
        user = await self._get_or_create_user(user_id)

        # Get user's tools
        tools = await self._get_user_tools(user)

        # Get all available servers
        async with self.db_manager.session() as session:
            server_repo = ServerRepository(session)
            all_servers = await server_repo.get_all_servers()
            user_servers = await server_repo.get_user_enabled_servers(user.id)  # type: ignore[arg-type]
            user_server_ids = {s.id for s in user_servers}

        # Build home view
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Welcome to MCP Slackbot!* 👋\n\nHello <@{user_id}>!",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Your Active Tools ({len(tools)})*",
                },
            },
        ]

        if tools:
            tool_list = "\n".join(
                [f"• `{tool['name']}` - {tool['description']}" for tool in tools[:10]]
            )
            if len(tools) > 10:
                tool_list += f"\n... and {len(tools) - 10} more"

            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": tool_list}}
            )
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No tools available. Enable some MCP servers below._",
                    },
                }
            )

        blocks.extend(
            [
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Available MCP Servers*"},
                },
            ]
        )

        for server in all_servers:
            is_enabled = server.id in user_server_ids
            status = "✅ Enabled" if is_enabled else "⬜ Disabled"

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{server.name}*\n{server.description}\n{status}",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Enable" if not is_enabled else "Disable",
                        },
                        "action_id": f"toggle_server_{server.id}",
                        "value": server.name,
                        "style": "primary" if not is_enabled else "danger",
                    },
                }
            )

        await client.views_publish(
            user_id=user_id, view={"type": "home", "blocks": blocks}
        )

    async def _handle_credential_submission(self, body: Dict[str, Any]) -> None:
        """Handle credential submission from Slack."""
        # Implementation for handling credential submissions
        pass

    async def _handle_credential_cancel(self, body: Dict[str, Any]) -> None:
        """Handle credential flow cancellation."""
        # Implementation for handling cancellations
        pass

    async def start(self) -> None:
        """Start the bot."""
        await self.initialize()
        logger.info("Starting Slack MCP Bot...")
        await self.socket_mode_handler.start_async()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.user_server_manager.cleanup_all()
        await self.llm_client.close()
        await self.db_manager.close()


async def main() -> None:
    """Main entry point."""
    config = Configuration()

    # Validate configuration
    if not config.slack_bot_token or not config.slack_app_token:
        logger.error(
            "Missing Slack tokens. Please set SLACK_BOT_TOKEN and SLACK_APP_TOKEN"
        )
        sys.exit(1)

    if not config.encryption_key and not config.master_password:
        logger.error(
            "Missing encryption configuration. Please set ENCRYPTION_KEY or "
            "MASTER_PASSWORD"
        )
        sys.exit(1)

    # Create components
    llm_client = LLMClient(config)
    bot = SlackMCPBot(config, llm_client)

    # Handle shutdown
    async def shutdown():
        logger.info("Shutting down...")
        await bot.cleanup()

    # Run bot
    try:
        await bot.start()
    except KeyboardInterrupt:
        await shutdown()
    except Exception as e:
        logger.error(f"Bot error: {e}")
        await shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
