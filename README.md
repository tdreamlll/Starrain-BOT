# Starrain-BOT

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![OneBot](https://img.shields.io/badge/OneBot-v11-green)
![NapCat](https://img.shields.io/badge/NapCat-Compatible-orange)
![License](https://img.shields.io/badge/License-MIT-brightgreen)

## 📖 项目简介

**Starrain-BOT** 是一个基于 [NapCat](https://github.com/NapNeko/NapCatQQ) (OneBot 11) 协议开发的 Python 语聊机器人框架。它旨在提供一个轻量、可扩展的 QQ 机器人解决方案。通过插件化设计，开发者可以轻松地为机器人添加新功能。

本项目采用 Python 异步编程 (`asyncio`, `aiohttp`, `websockets`) 构建，支持 HTTP、正向 WebSocket 和 反向 WebSocket 多种连接方式。

## ✨ 功能特性

本项目采用插件化架构，目前内置以下功能插件：

- **管理插件 (`admin_plugin`)**: 机器人管理、权限控制等。
- **名片插件 (`card_plugin`)**: 群名片管理功能。
- **经济系统 (`currency_plugin`)**: 基础的货币/积分系统。
- **图像生成 (`image_gen_plugin`)**: 基于 AI 或模板的图像生成。
- **文转图 (`text_to_image_plugin`)**: 支持将长文本渲染为图片发送。
- **基础回显 (`echo_plugin`)**: 消息回显测试。

## 🛠️ 环境依赖

在运行本项目之前，请确保您已准备好以下环境：

- **操作系统**: Windows / Linux / macOS
- **Python**: 3.8 或更高版本
- **Protocol端**: [NapCatQQ](https://github.com/NapNeko/NapCatQQ) (或其他 OneBot v11 实现)
- **数据库**: MySQL (部分插件需要)

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Starrain08/Starrain-BOT.git
cd Starrain-BOT
```

### 2. 安装依赖

推荐使用虚拟环境进行部署：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 激活虚拟环境 (Linux/macOS)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置项目

复制配置文件模板并进行修改：

1. 将 `config/config.yaml.example` 复制为 `config/config.yaml`。
2. 编辑 `config/config.yaml`，填入您的 NapCat 地址、Token 以及管理员 QQ 号。

```yaml
# config/config.yaml 示例片段
onebot:
  # 连接类型: ws (正向WS), reverse_ws (反向WS), http
  connection_type: "ws"
  url: "ws://127.0.0.1:3001"
  access_token: "your_token_here"

bot:
  qq: 123456789 # 你的机器人QQ号
  admins:
    - 987654321 # 管理员QQ号
```

### 4. 启动机器人

#### Windows 用户
双击运行 `start.bat` 即可启动。

#### 命令行启动
```bash
python start.py
```

## 📂 目录结构

```
Starrain-BOT/
├── cache/                  # 缓存目录
├── config/                 # 配置文件目录
│   ├── config.yaml         # 配置文件 (需自行创建)
│   └── config.yaml.example # 配置文件模板
├── docs/                   # 文档目录
├── logs/                   # 日志目录
├── plugins/                # 插件目录 (功能模块)
│   ├── admin_plugin.py
│   ├── image_gen_plugin.py
│   └── ...
├── save/                   # 数据持久化目录
├── src/                    # 核心源码
│   ├── core/               # 核心逻辑 (Bot, Adapter, PluginManager)
│   ├── utils/              # 工具库 (DB, Logger, Renderer)
│   └── main.py             # 核心入口
├── main.py                 # 主程序入口
├── start.py                # 启动脚本 (含环境检查等)
├── requirements.txt        # 项目依赖
└── README.md               # 项目说明文档
```

## 🔌 API 支持

本项目完全兼容 OneBot v11 标准，并适配了 NapCat 的扩展 API。

- **基础 API**: 发送消息、群管理、好友管理等。
- **NapCat 扩展**: 支持 NapCat 特有的 API 调用。

更多关于 NapCat 的 API 文档请参考：[NapCat 开发文档](https://napneko.github.io/develop/api)

## 🤝 贡献指南

1. Fork 本项目
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---
**Note**: 本项目仅供学习和技术交流使用，请勿用于非法用途。
