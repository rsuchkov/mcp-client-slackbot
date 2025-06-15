import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from ..database.repositories import (
    CredentialRepository,
    ServerRepository,
    UserRepository,
)
from ..database.session import get_db_manager
from .mcp_metadata import CredentialRequirement, MCPMetadataParser


class SlackAuthService:
    def __init__(self, slack_client: AsyncWebClient):
        self.slack_client = slack_client
        self.pending_auth_flows: Dict[str, Dict[str, Any]] = {}
        self.auth_flow_timeout = timedelta(minutes=10)

    def _cleanup_expired_flows(self):
        current_time = datetime.utcnow()
        expired_flows = [
            flow_id
            for flow_id, flow_data in self.pending_auth_flows.items()
            if current_time - flow_data["created_at"] > self.auth_flow_timeout
        ]
        for flow_id in expired_flows:
            del self.pending_auth_flows[flow_id]

    async def request_credentials(
        self,
        user_slack_id: str,
        channel_id: str,
        server_name: str,
        missing_credentials: List[CredentialRequirement],
    ) -> str:
        self._cleanup_expired_flows()

        flow_id = f"{user_slack_id}_{server_name}_{int(datetime.utcnow().timestamp())}"

        self.pending_auth_flows[flow_id] = {
            "user_slack_id": user_slack_id,
            "server_name": server_name,
            "credentials": missing_credentials,
            "collected": {},
            "created_at": datetime.utcnow(),
            "current_index": 0,
        }

        blocks = self._build_credential_request_blocks(
            server_name, missing_credentials[0], 0, len(missing_credentials)
        )

        try:
            await self.slack_client.chat_postEphemeral(
                channel=channel_id,
                user=user_slack_id,
                text=f"Please provide credentials for {server_name}",
                blocks=blocks,
            )
            return flow_id
        except SlackApiError as e:
            print(f"Error sending credential request: {e}")
            del self.pending_auth_flows[flow_id]
            raise

    def _build_credential_request_blocks(
        self,
        server_name: str,
        credential: CredentialRequirement,
        current_index: int,
        total_count: int,
    ) -> List[Dict[str, Any]]:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🔐 *Credential Setup for {server_name}*\n\n"
                        f"Step {current_index + 1} of {total_count}"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{credential.name}*\n{credential.description}",
                },
            },
            {
                "type": "input",
                "block_id": f"credential_input_{current_index}",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "credential_value",
                    "placeholder": {
                        "type": "plain_text",
                        "text": f"Enter {credential.name}",
                    },
                    "multiline": False,
                },
                "label": {"type": "plain_text", "text": credential.name},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Submit"},
                        "style": "primary",
                        "action_id": "submit_credential",
                        "value": json.dumps(
                            {
                                "flow_id": f"pending_{current_index}",
                                "credential_index": current_index,
                            }
                        ),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "style": "danger",
                        "action_id": "cancel_credential_flow",
                    },
                ],
            },
        ]

        if credential.validation_regex:
            blocks.insert(
                3,
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"ℹ️ Format: `{credential.validation_regex}`",
                        }
                    ],
                },
            )

        return blocks

    async def handle_credential_submission(
        self,
        flow_id: str,
        message_ts: str,
        credential_index: int,
        value: str,
        response_url: str,
    ) -> bool:
        if flow_id not in self.pending_auth_flows:
            return False

        flow_data = self.pending_auth_flows[flow_id]
        credential = flow_data["credentials"][credential_index]

        flow_data["collected"][credential.name] = value
        flow_data["current_index"] = credential_index + 1

        if flow_data["current_index"] < len(flow_data["credentials"]):
            next_credential = flow_data["credentials"][flow_data["current_index"]]
            blocks = self._build_credential_request_blocks(
                flow_data["server_name"],
                next_credential,
                flow_data["current_index"],
                len(flow_data["credentials"]),
            )

            try:
                await self.slack_client.chat_update(
                    channel=response_url,
                    ts=message_ts,
                    text=f"Please provide credentials for {flow_data['server_name']}",
                    blocks=blocks,
                )
            except SlackApiError as e:
                print(f"Error updating credential request: {e}")
                return False
        else:
            await self._save_collected_credentials(flow_data)

            try:
                await self.slack_client.chat_update(
                    channel=response_url,
                    ts=message_ts,
                    text="✅ Credentials saved successfully!",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    f"✅ *Credentials for {flow_data['server_name']} "
                                    "saved successfully!*\n\n"
                                    "You can now use this MCP server."
                                ),
                            },
                        }
                    ],
                )
            except SlackApiError as e:
                print(f"Error sending success message: {e}")

            del self.pending_auth_flows[flow_id]

        return True

    async def _save_collected_credentials(self, flow_data: Dict[str, Any]):
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            cred_repo = CredentialRepository(session)
            server_repo = ServerRepository(session)

            # Get team info
            auth_response = await self.slack_client.auth_test()
            team_id = auth_response["team_id"]

            user = await user_repo.get_user_by_slack_id(
                flow_data["user_slack_id"], team_id or ""
            )

            if not user:
                user_info = await self.slack_client.users_info(
                    user=flow_data["user_slack_id"]
                )
                profile = user_info.get("user", {}).get("profile", {})
                user = await user_repo.create_user(
                    slack_user_id=flow_data["user_slack_id"],
                    slack_team_id=team_id or "",
                    email=profile.get("email"),
                    display_name=profile.get("display_name"),
                    real_name=profile.get("real_name"),
                )

            server = await server_repo.get_server_by_name(flow_data["server_name"])
            if server:
                for cred_name, cred_value in flow_data["collected"].items():
                    await cred_repo.store_credential(
                        user_id=user.id,  # type: ignore[arg-type]
                        credential_type=flow_data["server_name"],
                        credential_name=cred_name,
                        value=cred_value,
                    )

    async def check_missing_credentials(
        self,
        user_slack_id: str,
        team_id: str,
        server_name: str,
        server_config: Dict[str, Any],
    ) -> List[CredentialRequirement]:
        required_credentials = MCPMetadataParser.parse_server_metadata(server_config)

        if not required_credentials:
            return []

        db_manager = get_db_manager()
        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            cred_repo = CredentialRepository(session)

            user = await user_repo.get_user_by_slack_id(user_slack_id, team_id)
            if not user:
                return required_credentials

            user_credentials = await cred_repo.get_user_credentials(user.id)  # type: ignore[arg-type]
            server_credentials = user_credentials.get(server_name, {})

            missing = []
            for req in required_credentials:
                if req.required and req.name not in server_credentials:
                    missing.append(req)

            return missing
