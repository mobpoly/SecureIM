# SecureIM - 安全即时通讯软件

SecureIM 是一个安全即时通讯桌面应用程序。采用混合加密方案，结合了非对称（RSA）和对称（AES）加密的优点，以确保通信私密和安全。

## 📂 项目结构

```
SecureIM/
├── .gitignore              # Git忽略文件，排除不必要的文件
├── README.md               # 项目介绍文档
├── requirements.txt        # 项目依赖的Python包
├── run_client.py           # 客户端启动脚本
├── run_server.py           # 服务器启动脚本
└── src/
    └── secureim/
        ├── __init__.py
        ├── client/
        │   ├── __init__.py
        │   ├── main.py             # App入口和主控制器
        │   ├── logic.py            # 客户端核心业务逻辑
        │   ├── networking.py       # 封装客户端网络通信
        │   └── ui/
        │       ├── __init__.py
        │       ├── login_window.py # 登录窗口UI
        │       └── main_window.py  # 主聊天窗口UI
        │   └── utils/
        │       ├── __init__.py
        │       ├── crypto.py       # 加密工具模块
        │       └── steganography.py# 隐写术工具模块
        └── server/
            ├── __init__.py
            ├── main.py             # 服务器入口
            ├── connection_handler.py# 处理单个客户端连接
            ├── request_handler.py  # 处理客户端的各种请求
            ├── state.py            # 维护服务器的共享状态（如在线用户）
            └── database.py         # 数据库操作模块

```

## ✨ 主要功能

- **🔒 端到端加密**: 所有消息都使用AES进行加密，确保只有对话者可以阅读内容。
- **🔑 混合加密模型**: 使用RSA安全地交换会话密钥，然后使用AES进行高效的消息加密。
- **🖼️ 隐写术**: 能够将文本消息隐藏在图片中发送，提供额外的安全层。
- **👥 好友系统**: 添加和管理您的联系人。
- **🟢 在线状态**: 查看好友当前是否在线。
- **🖥️ 跨平台**: 基于Python和PyQt6构建，可在Windows、macOS和Linux上运行。
- **🌐 C/S 与 P2P 模式**: 支持通过服务器中继消息或在可能的情况下建立直接的P2P连接。

## 🚀 如何运行

### 1. 环境设置

```bash
git clone <repository_url>
```

安装所需的依赖项：

```bash
pip install -r requirements.txt
```

### 2. 运行服务器

服务器需要先于任何客户端启动。它负责处理用户注册、登录和消息中继。

在项目根目录下运行：

```bash
python run_server.py
```

### 3. 运行客户端

可以启动多个客户端实例来模拟对话。

在项目根目录下运行：

```bash
python run_client.py
```

- **注册**: 在第一个客户端上，使用唯一的用户名和密码创建一个新帐户。
- **登录**: 使用注册的凭据登录。
- **添加好友**: 与朋友（另一个客户端实例）通过用户名添加对方为好友。
- **开始聊天**: 在好友列表中选择一个在线的好友开始安全通信

## 🛠️ 技术栈

- **语言**: Python 3
- **GUI**: PyQt6
- **加密**: `cryptography` 库 (RSA and AES)
- **图像处理**: `Pillow`
- **数据库**: `sqlite3`
