import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CredentialRequirement:
    type: str
    name: str
    description: str
    required: bool = True
    env_var: Optional[str] = None
    validation_regex: Optional[str] = None


class MCPMetadataParser:
    KNOWN_CREDENTIAL_PATTERNS = {
        "oauth_token": r".*(OAUTH|ACCESS)_TOKEN$",  # More specific, check first
        "api_key": r".*(_API_KEY|_KEY|_TOKEN)$",
        "username": r".*(USERNAME|USER|LOGIN)$",
        "password": r".*(PASSWORD|PASS|SECRET)$",
        "url": r".*(URL|ENDPOINT|HOST)$",
        "database": r".*(DATABASE|DB)_(NAME|URL|CONNECTION)$",
    }

    @classmethod
    def parse_server_metadata(
        cls, server_config: Dict[str, Any]
    ) -> List[CredentialRequirement]:
        required_credentials = []

        if "required_credentials" in server_config:
            for cred in server_config["required_credentials"]:
                required_credentials.append(
                    CredentialRequirement(
                        type=cred.get("type", "generic"),
                        name=cred["name"],
                        description=cred.get(
                            "description", f"Credential: {cred['name']}"
                        ),
                        required=cred.get("required", True),
                        env_var=cred.get("env_var"),
                        validation_regex=cred.get("validation_regex"),
                    )
                )

        env_vars = server_config.get("env", {})
        for env_var, value in env_vars.items():
            if cls._is_credential_placeholder(value):
                cred_type = cls._detect_credential_type(env_var)
                cred_name = cls._extract_credential_name(env_var)

                if not any(c.env_var == env_var for c in required_credentials):
                    required_credentials.append(
                        CredentialRequirement(
                            type=cred_type,
                            name=cred_name,
                            description=f"Environment variable: {env_var}",
                            env_var=env_var,
                        )
                    )

        return required_credentials

    @staticmethod
    def _is_credential_placeholder(value: str) -> bool:
        if not isinstance(value, str):
            return False

        placeholders = [
            "${",
            "{{",
            "<",
            "[",
            "PLACEHOLDER",
            "YOUR_",
            "INSERT_",
            "CHANGE_ME",
            "REQUIRED",
            "NEEDED",
        ]

        return any(marker in value.upper() for marker in placeholders) or value == ""

    @classmethod
    def _detect_credential_type(cls, env_var: str) -> str:
        env_var_upper = env_var.upper()

        for cred_type, pattern in cls.KNOWN_CREDENTIAL_PATTERNS.items():
            if re.match(pattern, env_var_upper):
                return cred_type

        return "generic"

    @staticmethod
    def _extract_credential_name(env_var: str) -> str:
        words = env_var.split("_")

        prefixes_to_remove = ["MCP", "SERVER", "CLIENT", "API"]
        suffixes_to_remove = ["KEY", "TOKEN", "SECRET", "PASS", "PASSWORD"]

        filtered_words = []
        for word in words:
            if (
                word.upper() not in prefixes_to_remove
                and word.upper() not in suffixes_to_remove
            ):
                filtered_words.append(word)

        if filtered_words:
            return " ".join(filtered_words).title()
        return env_var.replace("_", " ").title()

    @staticmethod
    def build_env_with_credentials(
        server_env: Dict[str, str],
        credentials: Dict[str, str],
        credential_requirements: List[CredentialRequirement],
    ) -> Dict[str, str]:
        env = server_env.copy()

        for req in credential_requirements:
            if req.env_var and req.name in credentials:
                env[req.env_var] = credentials[req.name]

        return env
