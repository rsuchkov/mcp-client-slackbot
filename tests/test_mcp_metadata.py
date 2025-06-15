
from mcp_simple_slackbot.services.mcp_metadata import (
    CredentialRequirement,
    MCPMetadataParser,
)


class TestMCPMetadataParser:
    def test_parse_explicit_required_credentials(self):
        """Test parsing explicitly defined required credentials."""
        server_config = {
            "required_credentials": [
                {
                    "type": "api_key",
                    "name": "Jira API Key",
                    "description": "API key for Jira access",
                    "env_var": "JIRA_API_KEY",
                    "required": True,
                },
                {
                    "type": "oauth_token",
                    "name": "GitHub Token",
                    "description": "GitHub OAuth token",
                    "env_var": "GITHUB_TOKEN",
                    "required": False,
                },
            ]
        }
        
        requirements = MCPMetadataParser.parse_server_metadata(server_config)
        
        assert len(requirements) == 2
        
        jira_req = next(r for r in requirements if r.name == "Jira API Key")
        assert jira_req.type == "api_key"
        assert jira_req.required is True
        assert jira_req.env_var == "JIRA_API_KEY"
        
        github_req = next(r for r in requirements if r.name == "GitHub Token")
        assert github_req.type == "oauth_token"
        assert github_req.required is False

    def test_parse_env_placeholders(self):
        """Test parsing environment variable placeholders."""
        server_config = {
            "env": {
                "API_KEY": "${API_KEY}",
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "SECRET_TOKEN": "{{SECRET_TOKEN}}",
                "OAUTH_TOKEN": "YOUR_OAUTH_TOKEN_HERE",
                "PASSWORD": "",
                "NORMAL_VAR": "fixed_value",
            }
        }
        
        requirements = MCPMetadataParser.parse_server_metadata(server_config)
        
        # Should detect 4 placeholders (API_KEY, SECRET_TOKEN, OAUTH_TOKEN, PASSWORD)
        assert len(requirements) == 4
        
        env_vars = [req.env_var for req in requirements]
        assert "API_KEY" in env_vars
        assert "SECRET_TOKEN" in env_vars
        assert "OAUTH_TOKEN" in env_vars
        assert "PASSWORD" in env_vars
        assert "DATABASE_URL" not in env_vars  # Fixed value, not placeholder
        assert "NORMAL_VAR" not in env_vars  # Fixed value, not placeholder

    def test_detect_credential_types(self):
        """Test automatic credential type detection."""
        test_cases = [
            ("JIRA_API_KEY", "api_key"),
            # ACCESS_TOKEN matches oauth_token now
            ("GITHUB_ACCESS_TOKEN", "oauth_token"),
            ("GITHUB_OAUTH_TOKEN", "oauth_token"),  # OAUTH_TOKEN matches oauth_token  
            ("SERVICE_API_KEY", "api_key"),  # API_KEY matches api_key
            ("DATABASE_USERNAME", "username"),
            ("DB_PASSWORD", "password"),
            ("SERVICE_URL", "url"),
            ("DATABASE_CONNECTION", "database"),
            ("UNKNOWN_VAR", "generic"),
        ]
        
        for env_var, expected_type in test_cases:
            detected_type = MCPMetadataParser._detect_credential_type(env_var)
            assert detected_type == expected_type, (
                f"Failed for {env_var}: expected {expected_type}, "
                f"got {detected_type}"
            )

    def test_extract_credential_names(self):
        """Test credential name extraction from environment variables."""
        test_cases = [
            ("JIRA_API_KEY", "Jira"),
            # ACCESS is not removed by default
            ("GITHUB_ACCESS_TOKEN", "Github Access"),
            ("MCP_SERVER_SLACK_TOKEN", "Slack"),
            ("API_SOME_SERVICE_KEY", "Some Service"),
            ("DATABASE_PASSWORD", "Database"),
            ("SIMPLE_VAR", "Simple Var"),
        ]
        
        for env_var, expected_name in test_cases:
            extracted_name = MCPMetadataParser._extract_credential_name(env_var)
            assert extracted_name == expected_name, (
                f"Failed for {env_var}: expected {expected_name}, "
                f"got {extracted_name}"
            )

    def test_is_credential_placeholder(self):
        """Test placeholder detection."""
        # Should be detected as placeholders
        placeholders = [
            "${VAR}",
            "{{VAR}}",
            "<VAR>",
            "[VAR]",
            "PLACEHOLDER_VALUE",
            "YOUR_API_KEY",
            "INSERT_TOKEN_HERE",
            "CHANGE_ME",
            "REQUIRED",
            "NEEDED",
            "",
        ]
        
        for placeholder in placeholders:
            assert MCPMetadataParser._is_credential_placeholder(
                placeholder
            ), f"Failed for: {placeholder}"
        
        # Should NOT be detected as placeholders
        fixed_values = [
            "fixed_value",
            "postgresql://localhost/db",
            "true",
            "false",
            "12345",
            "http://example.com",
            "/path/to/file",
        ]
        
        for value in fixed_values:
            assert not MCPMetadataParser._is_credential_placeholder(
                value
            ), f"False positive for: {value}"

    def test_build_env_with_credentials(self):
        """Test building environment with credentials."""
        server_env = {
            "API_KEY": "${API_KEY}",
            "DATABASE_URL": "postgresql://localhost/db",
            "SECRET_TOKEN": "{{SECRET_TOKEN}}",
            "FIXED_VAR": "fixed_value",
        }
        
        credentials = {
            "API Key": "secret_api_key_123",
            "Secret Token": "secret_token_456",
            "Unused Credential": "unused_value",
        }
        
        credential_requirements = [
            CredentialRequirement(
                type="api_key",
                name="API Key",
                description="API Key",
                env_var="API_KEY",
            ),
            CredentialRequirement(
                type="token",
                name="Secret Token",
                description="Secret Token",
                env_var="SECRET_TOKEN",
            ),
        ]
        
        result_env = MCPMetadataParser.build_env_with_credentials(
            server_env, credentials, credential_requirements
        )
        
        expected_env = {
            "API_KEY": "secret_api_key_123",
            "DATABASE_URL": "postgresql://localhost/db",
            "SECRET_TOKEN": "secret_token_456",
            "FIXED_VAR": "fixed_value",
        }
        
        assert result_env == expected_env

    def test_combined_explicit_and_env_parsing(self):
        """Test parsing with both explicit credentials and env placeholders."""
        server_config = {
            "required_credentials": [
                {
                    "type": "api_key",
                    "name": "Primary API Key",
                    "description": "Main API key",
                    "env_var": "PRIMARY_API_KEY",
                }
            ],
            "env": {
                "PRIMARY_API_KEY": "${PRIMARY_API_KEY}",  # Should not duplicate
                "SECONDARY_TOKEN": "{{SECONDARY_TOKEN}}",  # Should be detected
                "FIXED_URL": "https://api.example.com",  # Should be ignored
            },
        }
        
        requirements = MCPMetadataParser.parse_server_metadata(server_config)
        
        # Should have 2 requirements: explicit + detected from env
        assert len(requirements) == 2
        
        names = [req.name for req in requirements]
        assert "Primary API Key" in names  # Explicit
        assert "Secondary" in names  # Extracted from SECONDARY_TOKEN

    def test_empty_server_config(self):
        """Test parsing empty server configuration."""
        requirements = MCPMetadataParser.parse_server_metadata({})
        assert requirements == []

    def test_credential_requirement_defaults(self):
        """Test CredentialRequirement default values."""
        req = CredentialRequirement(
            type="api_key",
            name="Test Key",
            description="Test description",
        )
        
        assert req.required is True  # Default
        assert req.env_var is None  # Default
        assert req.validation_regex is None  # Default

    def test_case_insensitive_placeholder_detection(self):
        """Test that placeholder detection is case insensitive."""
        placeholders = [
            "placeholder_value",
            "PLACEHOLDER_VALUE",
            "PlAcEhOlDeR_VaLuE",
            "your_api_key",
            "YOUR_API_KEY",
            "YoUr_ApI_kEy",
        ]
        
        for placeholder in placeholders:
            assert MCPMetadataParser._is_credential_placeholder(
                placeholder
            ), f"Failed for: {placeholder}"