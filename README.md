# MCP Simple Slackbot

A simple Slack bot that uses the Model Context Protocol (MCP) to enhance its capabilities with external tools.

## Features

![2025-03-08-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/0e2b6e1c-80f2-48c3-8ca4-1c41f3678478)

- **AI-Powered Assistant**: Responds to messages in channels and DMs using LLM capabilities
- **MCP Integration**: Full access to MCP tools like SQLite database and web fetching
- **Multi-LLM Support**: Works with OpenAI, Groq, and Anthropic models
- **Multi-User Support**: 🆕 Individual user credentials, server configurations, and conversation histories
- **Encrypted Credentials**: 🆕 Secure storage of user API tokens and passwords
- **Per-User MCP Servers**: 🆕 Each user runs isolated MCP server instances with their credentials
- **App Home Tab**: Shows available tools and user-specific server configurations

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Choose "From an app manifest" and select your workspace
3. Copy the contents of `mcp_simple_slackbot/manifest.yaml` into the manifest editor
4. Create the app and install it to your workspace
5. Under the "Basic Information" section, scroll down to "App-Level Tokens"
6. Click "Generate Token and Scopes" and:
   - Enter a name like "mcp-assistant"
   - Add the `connections:write` scope
   - Click "Generate"
7. Take note of both your:
   - Bot Token (`xoxb-...`) found in "OAuth & Permissions"
   - App Token (`xapp-...`) that you just generated

### 2. Install Dependencies

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install project dependencies
pip install -r mcp_simple_slackbot/requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `mcp_simple_slackbot` directory (see `.env.example` for a template):

```
# Slack API credentials
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token

# Database configuration (for multi-user support)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/mcp_slackbot

# Credential encryption (choose one method)
ENCRYPTION_KEY=your-generated-fernet-key
# OR
MASTER_PASSWORD=your-secure-master-password

# LLM API credentials
OPENAI_API_KEY=sk-your-openai-key
# or use GROQ_API_KEY or ANTHROPIC_API_KEY

# LLM configuration
LLM_MODEL=gpt-4-turbo
```

## Running the Bot

### Initialize Database (First Time Setup)

```bash
# Navigate to the module directory
cd mcp_simple_slackbot

# Initialize database and test encryption
python init_db.py
```

### Start the Bot

```bash
# Run the bot directly
python main.py
```

The bot will:
1. Initialize database tables and user management
2. Sync MCP server configurations from `servers_config.json`
3. Start the Slack app in Socket Mode
4. Listen for mentions and direct messages

## Multi-User Setup

For detailed information about setting up and using multi-user features, see [MULTI_USER_GUIDE.md](MULTI_USER_GUIDE.md).

Quick overview:
- Each user can enable/disable MCP servers individually
- User credentials are encrypted and stored securely
- Each user gets isolated MCP server instances
- Conversation histories are maintained per user

## Usage

- **Direct Messages**: Send a direct message to the bot
- **Channel Mentions**: Mention the bot in a channel with `@MCP Assistant`
- **App Home**: Visit the bot's App Home tab to see available tools

## Architecture

The bot is designed with a multi-user architecture:

### Core Components
1. **SlackMCPBot**: Core class managing Slack events and user-specific message processing
2. **LLMClient**: Handles communication with LLM APIs (OpenAI, Groq, Anthropic)
3. **UserServerManager**: Manages per-user MCP server instances with isolated credentials
4. **EncryptionService**: Handles secure encryption/decryption of user credentials
5. **Database Layer**: SQLAlchemy models for users, credentials, servers, and conversations

### User Flow
When a message is received, the bot:
1. Identifies or creates the user in the database
2. Loads user-specific enabled servers and credentials
3. Instantiates MCP servers with user's encrypted credentials
4. Sends the message to the LLM with user's available tools
5. Executes any tool calls within the user's isolated server context
6. Stores the conversation in the user's history
7. Delivers the response to the user

### Security Features
- **Credential Encryption**: All user credentials encrypted with Fernet
- **User Isolation**: Each user has separate MCP server processes
- **Database Security**: Foreign key constraints and user-scoped queries
- **No Cross-User Access**: Users can only access their own tools and data

## Credits

This project is based on the [MCP Simple Chatbot example](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/clients/simple-chatbot).

## License

MIT License
