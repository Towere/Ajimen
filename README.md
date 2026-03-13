# 电商智能客服MVP版本

基于Python 3.10 + FastAPI + 通义千问API + SQLite + JSON的轻量级电商智能客服系统。

## 架构说明

### 系统架构图
```
用户请求 → FastAPI Web服务 → 聊天服务 → [商品知识库 + 通义千问API]
                                    ↓
                                对话记录 → SQLite数据库
```

### 核心模块
1. **main.py** - FastAPI应用入口，提供REST API接口
2. **chat_service.py** - 核心聊天服务，集成商品知识库和AI API
3. **knowledge_base.py** - JSON商品知识库加载和查询
4. **qianwen_api.py** - 通义千问API调用客户端（含降级方案）
5. **database.py** - SQLite数据库操作，存储对话记录
6. **config.py** - 配置文件（API密钥、路径常量等）
7. **products.json** - 商品知识库数据文件
8. **test_chat_service.py** - 单元测试和集成测试

### 技术特点
- **轻量级**：无需Docker，单文件部署
- **完整异常处理**：API调用失败自动降级，数据库错误优雅处理
- **模块化设计**：各功能模块分离，便于维护和扩展
- **中文友好**：完整中文注释和错误提示

## 环境准备

### 1. Python环境要求
- Python 3.10或更高版本
- pip包管理工具

### 2. 创建虚拟环境（推荐）
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖包
```bash
pip install -r requirements.txt
```

### 4. 配置API密钥
编辑`config.py`文件，替换以下配置：
```python
# 通义千问API配置
QIANWEN_API_KEY = "your-api-key-here"  # ← 替换为你的阿里云API密钥
```

> **注意**：如果没有通义千问API密钥，系统会自动使用降级方案返回预设话术。

## 快速启动

### 1. 启动服务
```bash
python main.py
```

服务将在 `http://localhost:8000` 启动。

### 2. 验证服务状态
```bash
# 健康检查
curl http://localhost:8000/health

# 查看API文档
# 浏览器访问 http://localhost:8000/docs
```

### 3. 测试聊天接口
```bash
# 使用curl测试
curl "http://localhost:8000/api/chat?user_id=test_user_001&message=你好，有什么推荐的手机吗？"

# 预期响应示例
{
  "success": true,
  "data": {
    "response": "您好！根据我们的商品库，我为您推荐以下几款手机...",
    "user_id": "test_user_001",
    "metadata": {...},
    "product_suggestions": [...]
  }
}
```

## 可视化界面

本项目提供三种可视化界面，满足不同使用需求：

### 1. 智能客服聊天界面（推荐）
一个现代化的Web聊天界面，支持：
- 实时对话与智能客服交互
- 商品建议展示
- 对话历史管理
- 用户切换功能
- 系统状态监控

**访问方式**：浏览器打开 `http://localhost:8000/ui`

### 2. API交互式文档（开发者推荐）
基于OpenAPI的交互式文档界面：
- **Swagger UI**：`http://localhost:8000/docs`
  - 交互式API测试
  - 实时请求/响应查看
  - 参数验证和自动生成

- **ReDoc**：`http://localhost:8000/redoc`
  - 更友好的文档阅读体验
  - 清晰的API说明
  - 响应示例展示

### 3. 直接文件访问
前端文件也可直接访问：
- `http://localhost:8000/static/index.html` - 聊天界面
- `http://localhost:8000/static/style.css` - 样式文件
- `http://localhost:8000/static/chat.js` - 前端逻辑

### 界面功能截图
```
┌─────────────────────────────────────────────────────┐
│ 电商智能客服 - 聊天界面                              │
│ 左侧: 快速查询按钮 + 系统状态                        │
│ 中部: 对话区域 (用户消息 + AI回复)                  │
│ 底部: 输入框 + 发送按钮                             │
│ 下部: 商品建议卡片                                  │
└─────────────────────────────────────────────────────┘
```

### 界面特点
- **响应式设计**：适配桌面和移动设备
- **实时反馈**：显示AI思考状态和系统状态
- **商品集成**：对话中自动展示相关商品
- **用户友好**：中文界面，操作简单直观

## API接口文档

### 健康检查
- `GET /` - 服务根目录，显示所有可用端点
- `GET /health` - 健康检查，验证各组件状态

### 对话接口
- `POST /api/chat` - 处理用户消息，返回AI回复
  - 参数：`user_id` (string), `message` (string)
- `GET /api/history/{user_id}` - 获取用户对话历史
  - 参数：`limit` (int, 默认10)
- `DELETE /api/history/{user_id}` - 清空用户对话历史

### 商品接口
- `GET /api/products/search` - 搜索商品
  - 参数：`keyword` (string), `category` (可选), `max_price` (可选), `min_price` (可选), `limit` (默认10)
- `GET /api/products/{product_id}` - 获取商品详情
- `GET /api/products/categories` - 获取所有商品分类

### 系统管理
- `GET /api/system/status` - 获取系统状态信息

## 测试用例

### 1. 运行单元测试
```bash
# 运行所有测试
pytest test_chat_service.py -v

# 运行特定测试类
pytest test_chat_service.py::TestChatDatabase -v

# 生成测试覆盖率报告（需要安装pytest-cov）
pytest test_chat_service.py --cov=. --cov-report=html
```

### 2. 手动测试步骤

#### 测试场景1：基础聊天功能
```bash
# 1. 启动服务
python main.py

# 2. 新用户首次对话
curl "http://localhost:8000/api/chat?user_id=user_001&message=你好"

# 3. 询问商品价格
curl "http://localhost:8000/api/chat?user_id=user_001&message=华为手机多少钱？"

# 4. 查看对话历史
curl "http://localhost:8000/api/history/user_001"
```

#### 测试场景2：商品搜索功能
```bash
# 1. 搜索手机类商品
curl "http://localhost:8000/api/products/search?keyword=手机"

# 2. 按价格筛选
curl "http://localhost:8000/api/products/search?keyword=电视&max_price=6000"

# 3. 获取商品详情
curl "http://localhost:8000/api/products/P001"
```

#### 测试场景3：API降级方案
```bash
# 当API密钥未配置或网络故障时，系统应自动降级
# 编辑config.py，将API密钥设置为空或无效值
# 然后测试聊天接口，应返回预设话术而非API错误
curl "http://localhost:8000/api/chat?user_id=user_001&message=你好"
```

### 3. 预期输出
- 所有测试用例应通过（绿色√）
- API接口应返回正确的HTTP状态码（200/400/404/500等）
- 错误情况应有清晰的错误信息
- 降级方案应在API失败时自动启用

## 问题排查

### 常见问题及解决方案

#### 1. 服务启动失败
**问题**：`ModuleNotFoundError: No module named 'fastapi'`
**解决**：确保已安装所有依赖包
```bash
pip install -r requirements.txt
```

#### 2. API调用失败
**问题**：通义千问API返回401错误
**解决**：
1. 检查`config.py`中的`QIANWEN_API_KEY`是否已替换
2. 确认阿里云账户余额充足
3. 验证API服务是否已开通

**问题**：网络连接超时
**解决**：
- 系统会自动启用降级方案，返回预设话术
- 检查网络连接，或增加`config.py`中的`API_TIMEOUT`值

#### 3. 数据库错误
**问题**：`sqlite3.OperationalError: unable to open database file`
**解决**：
- 检查文件权限：确保应用有写入当前目录的权限
- 检查文件路径：`config.py`中的`DATABASE_PATH`应为相对路径

#### 4. 商品知识库加载失败
**问题**：`JSONDecodeError`或商品搜索返回空结果
**解决**：
1. 检查`products.json`文件格式是否正确
2. 验证JSON文件编码为UTF-8
3. 确认文件路径正确：`config.py`中的`PRODUCTS_JSON_PATH`

#### 5. 测试失败
**问题**：pytest测试用例失败
**解决**：
1. 检查测试数据：`test_chat_service.py`中的测试数据可能需要更新
2. 检查模拟对象：确保模拟对象的返回值符合预期
3. 运行单个测试定位问题：`pytest test_chat_service.py::TestClassName::test_method_name -v`

### 日志查看
系统使用Python标准logging模块，日志级别为INFO。如需更详细日志：
1. 修改`config.py`或其他模块中的`logging.basicConfig(level=logging.INFO)`为`logging.DEBUG`
2. 查看控制台输出的日志信息

### 性能优化建议
1. **数据库优化**：对话记录较多时可添加更多索引
2. **缓存策略**：频繁查询的商品信息可加入内存缓存
3. **连接池**：高并发场景可使用数据库连接池
4. **异步处理**：将API调用改为异步，提高吞吐量

## 扩展开发

### 1. 添加新的商品字段
编辑`products.json`文件，在商品对象中添加新字段，然后在`knowledge_base.py`的`_validate_product`方法中添加验证逻辑。

### 2. 扩展用户意图识别
修改`chat_service.py`中的`_analyze_user_intent`方法，添加新的意图识别逻辑。

### 3. 集成其他AI服务
创建新的API客户端类（参考`qianwen_api.py`），然后在`chat_service.py`中切换或组合使用。

### 4. 添加用户认证
可扩展`main.py`，添加JWT认证中间件，保护API端点。

## 部署说明

### 生产环境部署
1. 禁用热重载：修改`main.py`中`uvicorn.run`的`reload=False`
2. 设置CORS白名单：修改`main.py`中的`allow_origins`为具体域名
3. 使用进程管理器：如`gunicorn` + `uvicorn` worker
4. 配置反向代理：Nginx/Apache转发请求到FastAPI应用

### 环境变量配置
建议将敏感信息（如API密钥）移至环境变量：
```python
import os
QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY", "default-key")
```

## 文件结构
```
.
├── README.md                    # 本文档
├── requirements.txt             # 依赖包列表
├── config.py                    # 配置文件
├── main.py                      # FastAPI主应用
├── chat_service.py              # 核心聊天服务
├── knowledge_base.py            # 商品知识库模块
├── qianwen_api.py               # 通义千问API客户端
├── database.py                  # SQLite数据库模块
├── test_chat_service.py         # 测试用例
├── products.json                # 商品知识库数据
├── index.html                   # 聊天界面HTML文件
├── style.css                    # 聊天界面样式文件
├── chat.js                      # 聊天界面JavaScript逻辑
├── chat_history.db              # SQLite数据库文件（运行时生成）
└── .gitignore                   # Git忽略文件
```

## 许可证
本项目仅供学习和演示使用。实际商用需考虑数据安全、性能优化和合规性要求。

## 技术支持
如遇到问题，请检查：
1. 本文档的"问题排查"部分
2. Python和依赖包的版本兼容性
3. 网络连接和防火墙设置
4. 文件权限和路径配置