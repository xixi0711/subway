# 地铁智能问答系统

基于 Vue3 + FastAPI + SQLite 构建的地铁智能问答系统，支持线路管理、站点管理、时刻表查询、客流分析以及AI智能问答功能。

## 📋 功能特性

### 核心功能
- **线路管理** - 管理地铁线路信息（编号、名称、首末班车时间）
- **站点管理** - 管理站点信息（编号、所属线路、换乘线路）
- **时刻表管理** - 管理列车时刻表（到站时间、发车时间）
- **刷卡记录** - 查看乘客刷卡数据
- **客流分析** - 分析各站点客流数据
- **线网图** - 可视化展示地铁线路网络
- **AI智能问答** - 基于大模型的智能问答系统，支持自然语言查询

### AI问答特性
- 意图识别（数据库查询/知识库检索/闲聊）
- RAG知识库增强
- 实时数据库查询
- 支持外部API和本地模型（Ollama）

## 🛠️ 技术栈

### 前端
- Vue 3 + Vite
- Ant Design Vue
- Pinia（状态管理）
- Vue Router
- ECharts（图表可视化）

### 后端
- Python 3.10+
- FastAPI
- SQLite（数据库）
- LangChain（RAG）
- python-dotenv（配置管理）

### AI支持
- 火山引擎API
- Ollama本地模型

## 📁 项目结构

```
subway_trae_project/
├── frontend/                    # 前端项目
│   ├── src/
│   │   ├── api/                # API接口封装
│   │   ├── router/             # 路由配置
│   │   ├── stores/             # Pinia状态管理
│   │   ├── views/              # 页面视图
│   │   ├── assets/             # 静态资源
│   │   ├── App.vue             # 根组件
│   │   └── main.js             # 入口文件
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── backend/                    # 后端项目
│   ├── subway_api.py           # 主API服务
│   ├── subway.db               # SQLite数据库
│   ├── knowledge_base/         # RAG知识库文档
│   ├── vector_store/           # 向量存储
│   └── requirements.txt        # Python依赖
├── .env                        # 环境配置
└── README.md
```

## 🚀 快速开始

### 环境要求
- Node.js 18+
- Python 3.10+
- npm 或 yarn

### 安装步骤

#### 1. 克隆项目
```bash
git clone <repository-url>
cd subway_trae_project
```

#### 2. 安装前端依赖
```bash
cd frontend
npm install
```

#### 3. 安装后端依赖
```bash
cd ..
pip install -r requirements.txt
```

#### 4. 配置环境变量
编辑 `.env` 文件：
```ini
# 火山引擎API配置
ARK_API_KEY=your-api-key
ARK_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
MODEL_NAME=your-model-name

# Ollama配置（可选）
USE_OLLAMA=false
OLLAMA_MODEL=qwen:7b

# 数据库配置
DATABASE_PATH=./subway.db
```

### 启动服务

#### 启动后端服务
```bash
python subway_api.py
```
服务将运行在 http://localhost:5000

#### 启动前端开发服务器
```bash
cd frontend
npm run dev
```
服务将运行在 http://localhost:3000

#### 构建生产版本
```bash
cd frontend
npm run build
```

## 📡 API接口

### 线路管理
- `GET /api/lines` - 获取所有线路
- `POST /api/lines` - 创建/更新线路
- `DELETE /api/lines/{line_id}` - 删除线路

### 站点管理
- `GET /api/stations` - 获取站点列表
- `POST /api/stations` - 创建/更新站点
- `DELETE /api/stations/{station_id}` - 删除站点

### AI问答
- `POST /api/ai-query` - AI智能问答

### 客流分析
- `GET /api/passenger-flow/stats` - 获取客流统计
- `GET /api/passenger-flow/top` - 获取客流最多的站点

## 🧠 AI模型配置

### 使用外部API（默认）
确保 `.env` 中配置正确：
```ini
USE_OLLAMA=false
ARK_API_KEY=your-key
```

### 使用本地模型（Ollama）
1. 安装 Ollama：https://ollama.com/
2. 下载模型：
```bash
ollama pull qwen:7b
```
3. 配置 `.env`：
```ini
USE_OLLAMA=true
OLLAMA_MODEL=qwen:7b
```

## 📊 数据库结构

### 主要表
- **线路信息表** - 线路编号、名称、首末班车时间
- **站点信息表** - 站点编号、所属线路、换乘线路、坐标
- **列车时刻表** - 列车编号、途经站点、到站/发车时间
- **乘客刷卡数据表** - 交易记录、进出站信息
- **客流统计表** - 站点客流统计数据

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

如有问题，请通过Issue联系。