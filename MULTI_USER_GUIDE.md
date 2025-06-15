# Multi-User MCP Slackbot Guide

This guide explains how to set up and use the multi-user features of the MCP Slackbot.

## Overview

The MCP Slackbot now supports multiple users with individual credentials and server configurations. Each user can:

- Enable/disable specific MCP servers
- Store encrypted credentials for servers that require authentication
- Maintain separate conversation histories
- Access only their authorized tools

## Prerequisites

- PostgreSQL database (or compatible)
- Python 3.11+
- Slack app with Socket Mode enabled
- Required environment variables configured

## Environment Setup

### 1. Database Configuration

Set up your database connection:

```bash
export DATABASE_URL="postgresql+asyncpg://username:password@localhost/mcp_slackbot"
```

### 2. Encryption Configuration

Choose one of these methods for credential encryption:

**Option A: Using an encryption key (recommended for production)**
```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set the key
export ENCRYPTION_KEY="your-generated-key-here"
```

**Option B: Using a master password (easier for development)**
```bash
export MASTER_PASSWORD="your-secure-master-password"
export ENCRYPTION_SALT="optional-custom-salt"  # Optional, defaults to 'mcp-slackbot-default-salt'
```

### 3. Slack Configuration

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
```

### 4. LLM Configuration

Configure at least one LLM provider:

```bash
# OpenAI
export OPENAI_API_KEY="sk-your-openai-key"
export LLM_MODEL="gpt-4-turbo"

# Groq
export GROQ_API_KEY="your-groq-key"
export LLM_MODEL="llama-3.1-70b-versatile"

# Anthropic
export ANTHROPIC_API_KEY="your-anthropic-key"
export LLM_MODEL="claude-3-opus-20240229"
```

## Database Initialization

### 1. Install Dependencies

```bash
cd mcp_simple_slackbot
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python init_db.py
```

This will create all necessary tables with the following schema:

- **users**: Stores Slack user information
- **mcp_servers**: Available MCP server configurations
- **user_credentials**: Encrypted user credentials
- **user_server_configs**: User-specific server enablement
- **conversations**: Conversation tracking
- **messages**: Message history

### 3. Run Migrations (if using Alembic)

```bash
cd mcp_simple_slackbot
alembic upgrade head
```

## Server Configuration

### 1. Basic Server Configuration

Edit `servers_config.json` to define available MCP servers:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "./user_data/${user_id}/data.db"],
      "description": "SQLite database for personal data storage"
    },
    "github": {
      "command": "uvx", 
      "args": ["mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub integration",
      "required_credentials": [
        {
          "type": "api_key",
          "name": "github_token",
          "description": "GitHub Personal Access Token",
          "env_var": "GITHUB_TOKEN",
          "validation_regex": "^(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})$"
        }
      ]
    }
  }
}
```

### 2. Credential Requirements

Define required credentials for each server:

```json
"required_credentials": [
  {
    "type": "api_key|oauth_token|username|password|url|database|generic",
    "name": "credential_name",
    "description": "Human-readable description",
    "env_var": "ENVIRONMENT_VARIABLE_NAME",
    "required": true,
    "validation_regex": "optional-validation-pattern"
  }
]
```

## User Workflow

### 1. Initial Setup

When a user first interacts with the bot:

1. The bot automatically creates a user record
2. User can view available servers in the App Home tab
3. User can enable servers that don't require credentials immediately

### 2. Enabling Servers with Credentials

When enabling a server that requires credentials:

1. User clicks "Enable" on a server in App Home
2. Bot sends an ephemeral message requesting credentials
3. User provides credentials through secure forms
4. Credentials are encrypted and stored
5. Server becomes available for the user

### 3. Using Tools

Once servers are enabled:

1. User can mention the bot or send direct messages
2. Bot loads user-specific tools from enabled servers
3. Each user has isolated server instances with their credentials
4. Conversation history is maintained per user

## Security Features

### 1. Credential Encryption

- All credentials are encrypted using Fernet (symmetric encryption)
- Encryption keys are derived from master password using PBKDF2 if needed
- Credentials are never logged or exposed in plain text

### 2. User Isolation

- Each user has separate MCP server instances
- Server processes run with user-specific credentials
- No cross-user data access is possible

### 3. Database Security

- All user credentials are encrypted at rest
- Foreign key constraints ensure data integrity
- Conversations and messages are user-scoped

## Administration

### 1. Adding New Servers

1. Update `servers_config.json` with new server configuration
2. Restart the bot to sync configurations
3. New servers appear in all users' App Home

### 2. Monitoring

Check logs for:
- User authentication events
- Server initialization failures
- Credential validation errors

### 3. Database Maintenance

Regular maintenance tasks:

```sql
-- View active users
SELECT slack_user_id, display_name, created_at 
FROM users 
WHERE is_active = true;

-- Check server usage
SELECT s.name, COUNT(usc.user_id) as user_count
FROM mcp_servers s
LEFT JOIN user_server_configs usc ON s.id = usc.server_id
WHERE usc.is_enabled = true
GROUP BY s.name;

-- Clean old conversations (older than 30 days)
DELETE FROM conversations 
WHERE last_message_at < NOW() - INTERVAL '30 days';
```

## Troubleshooting

### Common Issues

1. **"Missing encryption configuration" error**
   - Ensure ENCRYPTION_KEY or MASTER_PASSWORD is set
   - Check environment variables are loaded

2. **"Database connection failed"**
   - Verify DATABASE_URL is correct
   - Ensure PostgreSQL is running
   - Check network connectivity

3. **"Server initialization failed for user"**
   - Check user has required credentials
   - Verify server command and args are correct
   - Check MCP server is installed (`uvx` availability)

4. **"Credential validation failed"**
   - Ensure credential format matches validation_regex
   - Check for special characters that need escaping

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
export SQL_ECHO=true  # Show SQL queries
```

## Migration from Single-User

If migrating from the single-user version:

1. Backup existing data
2. Run database initialization
3. Manually create server configurations in database
4. Users will need to re-enable servers and provide credentials

## Best Practices

1. **Credential Management**
   - Regularly rotate encryption keys
   - Use strong master passwords
   - Implement credential expiration policies

2. **Server Configuration**
   - Use descriptive server names and descriptions
   - Provide clear credential descriptions
   - Include validation patterns for better UX

3. **Performance**
   - Limit concurrent MCP servers per user
   - Implement server timeout policies
   - Monitor resource usage

4. **Security**
   - Regular security audits
   - Keep dependencies updated
   - Monitor for suspicious activity