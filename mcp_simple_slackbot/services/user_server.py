import asyncio
import json
from typing import Dict, List, Optional, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ..database.models import User, MCPServer
from ..database.repositories import CredentialRepository
from ..database.session import get_session
from .mcp_metadata import MCPMetadataParser


class UserMCPServer:
    def __init__(self, user: User, server_config: MCPServer, credentials: Dict[str, str]):
        self.user = user
        self.server_config = server_config
        self.credentials = credentials
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
    
    @property
    def server_id(self) -> str:
        return f"{self.user.slack_user_id}_{self.server_config.name}"
    
    async def initialize(self) -> bool:
        try:
            self.exit_stack = AsyncExitStack()
            
            env = MCPMetadataParser.build_env_with_credentials(
                self.server_config.env,
                self.credentials,
                self.server_config.required_credentials
            )
            
            server_params = StdioServerParameters(
                command=self.server_config.command,
                args=self.server_config.args,
                env=env
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, writer = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, writer)
            )
            
            await self.session.initialize()
            
            self._tools_cache = None
            
            return True
        except Exception as e:
            print(f"Failed to initialize server {self.server_config.name} for user {self.user.slack_user_id}: {e}")
            await self.cleanup()
            return False
    
    async def cleanup(self):
        self._tools_cache = None
        if self.exit_stack:
            await self.exit_stack.aclose()
            self.exit_stack = None
            self.session = None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self.session:
            return []
        
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            response = await asyncio.wait_for(
                self.session.list_tools(),
                timeout=5.0
            )
            self._tools_cache = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema.model_dump() if tool.inputSchema else {}
                }
                for tool in response.tools
            ]
            return self._tools_cache
        except Exception as e:
            print(f"Error listing tools for {self.server_config.name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.session:
            raise Exception(f"Server {self.server_config.name} not initialized")
        
        try:
            response = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments=arguments),
                timeout=30.0
            )
            return response
        except Exception as e:
            print(f"Error calling tool {tool_name} on {self.server_config.name}: {e}")
            raise


class UserServerManager:
    def __init__(self):
        self.user_servers: Dict[str, UserMCPServer] = {}
    
    async def get_or_create_server(
        self,
        user: User,
        server_config: MCPServer,
        credentials: Dict[str, str]
    ) -> Optional[UserMCPServer]:
        server_id = f"{user.slack_user_id}_{server_config.name}"
        
        if server_id in self.user_servers:
            return self.user_servers[server_id]
        
        user_server = UserMCPServer(user, server_config, credentials)
        if await user_server.initialize():
            self.user_servers[server_id] = user_server
            return user_server
        
        return None
    
    async def get_user_servers(self, user: User) -> List[UserMCPServer]:
        return [
            server for server_id, server in self.user_servers.items()
            if server_id.startswith(f"{user.slack_user_id}_")
        ]
    
    async def cleanup_user_servers(self, user: User):
        user_prefix = f"{user.slack_user_id}_"
        servers_to_remove = [
            server_id for server_id in self.user_servers.keys()
            if server_id.startswith(user_prefix)
        ]
        
        for server_id in servers_to_remove:
            server = self.user_servers.pop(server_id)
            await server.cleanup()
    
    async def cleanup_all(self):
        for server in self.user_servers.values():
            await server.cleanup()
        self.user_servers.clear()
    
    async def get_user_tools(self, user: User) -> List[Dict[str, Any]]:
        all_tools = []
        
        async with get_session() as session:
            cred_repo = CredentialRepository(session)
            
            for server in await self.get_user_servers(user):
                tools = await server.list_tools()
                for tool in tools:
                    tool["server"] = server.server_config.name
                    all_tools.append(tool)
        
        return all_tools