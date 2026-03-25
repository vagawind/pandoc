# Pandoc WebSocket MCP 服务器

## 概述

本项目为Pandoc添加了WebSocket MCP（Model Context Protocol）服务支持。MCP（Model Context Protocol）是一种用于扩展AI模型能力的协议，允许模型通过WebSocket连接与外部服务交互。

我们提供了两种实现方案：
1. **Haskell 实现** - 基于现有的pandoc-server库，添加WebSocket支持
2. **Python 实现** - 一个简单的概念验证服务器，通过子进程调用pandoc

## 架构设计

### 1. 扩展pandoc-server库
- 在 `pandoc-server/pandoc-server.cabal` 中添加了 `wai-websockets` 和 `websockets` 依赖
- 创建了新的可执行文件 `pandoc-mcp-server`
- 支持JSON-RPC over WebSocket

### 2. MCP 协议支持
- 基于JSON-RPC 2.0
- 支持的方法：
  - `convert` - 文档转换
  - `version` - 获取pandoc版本
  - `list_methods` - 列出可用方法

### 3. Docker 容器化
- 提供了Dockerfile用于容器化部署
- 支持在Docker环境中运行MCP服务

## 文件结构

### 核心文件
- `pandoc-server/pandoc-server.cabal` - 更新后的cabal文件，包含WebSocket依赖
- `pandoc-server/app/Main.hs` - WebSocket MCP服务器实现
- `mcp-server/Dockerfile` - Docker配置
- `mcp-server/requirements.txt` - Python依赖
- `mcp-server/mcp_server.py` - Python WebSocket服务器

### 新增功能
1. **WebSocket 服务器** (`Main.hs`) - 处理MCP协议消息
2. **MCP 消息解析** - JSON-RPC 2.0兼容
3. **错误处理** - 完整的JSON-RPC错误响应

## 实现细节

### Haskell WebSocket 服务器 (`pandoc-server/app/Main.hs`)
- 使用 `wai-websockets` 库处理WebSocket连接
- 实现JSON-RPC 2.0协议解析
- 支持以下MCP方法：
  - `convert` - 调用pandoc库进行文档转换
  - `version` - 返回pandoc版本信息
  - `list_methods` - 返回可用方法列表

### Python WebSocket 服务器 (`mcp-server/mcp_server.py`)
- 使用 `websockets` 库处理WebSocket连接
- 通过子进程调用pandoc命令行工具
- 支持基本的文档转换功能

## 使用方法

### 1. 运行Python WebSocket服务器

#### 安装依赖：
```bash
pip install websockets
```

#### 运行服务器：
```bash
python mcp_server.py
```

### 2. 构建和运行Haskell服务器

#### 构建：
```bash
cd pandoc-server
cabal build pandoc-mcp-server
```

#### 运行：
```bash
cabal run pandoc-mcp-server -- --port 8765 --timeout 30
```

### 3. Docker 运行

#### 构建镜像：
```bash
cd mcp-server
docker build -t pandoc-mcp-server .
```

#### 运行容器：
```bash
docker run -p 8765:8765 pandoc-mcp-server
```

## API 文档

### 请求格式
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "convert",
  "params": {
    "text": "# Hello World\n\nThis is a test.",
    "from": "markdown",
    "to": "html",
    "standalone": false
  }
}
```

### 响应格式
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "success",
    "output": "<h1>Hello World</h1>\n<p>This is a test.</p>"
  }
}
```

### 错误响应
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": null
  }
}
```

## MCP 协议扩展

### 支持的 JSON-RPC 方法：
1. **convert** - 转换文档格式
   - Parameters: text, from, to, standalone, variables
   - Returns: converted document
   
2. **version** - 获取pandoc版本
   - Parameters: none
   - Returns: version string
   
3. **list_methods** - 列出可用方法
   - Parameters: none
   - Returns: list of method names

### 消息格式：
所有消息遵循 JSON-RPC 2.0 规范：
- `jsonrpc`: 必须为 "2.0"
- `id`: 请求ID (整数或字符串)
- `method`: 方法名称
- `params`: 参数对象

## 部署到Docker

### 步骤：
1. 确保Docker已安装并运行
2. 构建镜像：`docker build -t pandoc-mcp-server .`
3. 运行容器：`docker run -p 8765:8765 pandoc-mcp-server`
4. 测试连接：`websocat ws://localhost:8765`

### 环境变量：
- `PORT` - WebSocket服务器端口 (默认: 8765)
- `TIMEOUT` - 请求超时时间 (默认: 30秒)

## 测试

### 使用websocat测试：
```bash
# 安装 websocat (如果未安装)
# 在Windows上，可以通过choco安装：choco install websocat

# 发送转换请求
echo '{"jsonrpc": "2.0", "id": 1, "method": "convert", "params": {"text": "# Test\\n\\nThis is a test.", "from": "markdown", "to": "html"}}' | websocat ws://localhost:8765

# 获取版本
echo '{"jsonrpc": "2.0", "id": 2, "method": "version", "params": {}}' | websocat ws://localhost:8765

# 列出方法
echo '{"jsonrpc": "2.0", "id": 3, "method": "list_methods", "params": {}}' | websocat ws://localhost:8765
```

## 未来改进

1. **完整的MCP协议支持** - 实现所有MCP方法
2. **身份验证** - 添加安全层
3. **性能优化** - 提高转换速度
4. **扩展功能** - 支持更多pandoc选项
5. **监控和日志** - 添加更好的监控支持

## 许可证

本项目基于Pandoc的GPL-2.0-or-later许可证。

## 贡献

欢迎提交问题和拉取请求！
