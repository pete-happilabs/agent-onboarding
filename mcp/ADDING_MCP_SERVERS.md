# Adding New MCP Servers

This guide shows how to integrate any MCP server with the DOST bridge.

## Quick Start

1. Create a YAML config in `configs/`
2. Test with: `python3 main.py --config configs/your-server.yaml --interactive`

## Transport Types

### 1. `stdio` - Local MCP Servers (No OAuth)

For npm packages that run locally:

```yaml
# configs/your-server.yaml
mcp:
  transport: stdio
  command: "npx -y @your-org/mcp-server"
  timeout: 30

agent:
  entity_id: "agent.mcp.your-server"
  name: "Your Server"
```

**Examples:**
- `npx -y @modelcontextprotocol/server-filesystem /path`
- `npx -y @modelcontextprotocol/server-fetch`
- `npx -y @modelcontextprotocol/server-memory`
- `npx -y @modelcontextprotocol/server-everything`

### 2. `remote` - Remote MCP Servers (With OAuth)

For hosted MCP servers that require authentication:

```yaml
# configs/your-server.yaml
mcp:
  transport: remote
  url: "https://mcp.example.com/mcp"
  timeout: 60
  auth_timeout: 120  # Time to complete OAuth login

agent:
  entity_id: "agent.mcp.example"
  name: "Example"
```

**Note:** Remote servers need OAuth. Some (like Zomato) only allow whitelisted apps.

### 3. `sse` - Self-Hosted HTTP Servers (No OAuth)

For your own HTTP MCP servers:

```yaml
mcp:
  transport: sse
  url: "http://localhost:3000/mcp"
  timeout: 30

agent:
  entity_id: "agent.mcp.local"
  name: "Local Server"
```

## Finding MCP Servers

### Official Servers (No OAuth)
- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
  - `@modelcontextprotocol/server-filesystem` - File operations
  - `@modelcontextprotocol/server-fetch` - Web fetching
  - `@modelcontextprotocol/server-memory` - Knowledge graph
  - `@modelcontextprotocol/server-git` - Git operations
  - `@modelcontextprotocol/server-everything` - Test server

### Community Servers
- [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)
- [MCP Servers Hub](https://github.com/apappascs/mcp-servers-hub)

### Remote Servers (OAuth Required)
- **Zomato** - `https://mcp-server.zomato.com/mcp` (whitelisted apps only)
- **Linear** - `https://mcp.linear.app/mcp`
- **Sentry** - `https://mcp.sentry.dev/mcp`

## Testing Your Config

```bash
# List available tools
python3 main.py --config configs/your-server.yaml --interactive
# Then type: tools

# Send a test message
python3 main.py --config configs/your-server.yaml --message "Hello"

# Verbose mode for debugging
python3 main.py --config configs/your-server.yaml --interactive --verbose
```

## Troubleshooting

### "command not found: npx"
Install Node.js 16+: https://nodejs.org/

### "MCP server closed connection"
- Check if the npm package name is correct
- Try running the command directly: `npx -y @package/name`

### OAuth errors with remote servers
- Some servers only allow whitelisted apps (Zomato, etc.)
- Clear OAuth tokens: `rm -rf ~/.mcp-auth`
- Increase auth_timeout in config

### Tool call errors
The bridge's `send_message()` uses simple heuristics. For complex tools,
use `call_tool()` directly with proper parameters.

## Config Reference

```yaml
mcp:
  transport: stdio | remote | sse    # Transport type
  command: "npx ..."                 # For stdio
  url: "https://..."                 # For remote/sse
  timeout: 30                        # Request timeout (seconds)

  # Remote-only options:
  oauth_port: 3334                   # OAuth callback port
  auth_timeout: 120                  # OAuth login timeout
  transport_mode: http-first         # http-first | sse-first
  headers:                           # Custom auth headers
    - "Authorization: Bearer xxx"

agent:
  entity_id: "agent.mcp.xxx"         # DOST entity ID
  name: "Display Name"               # Human-readable name
```
