"""
配置文件
存储API密钥、数据库路径、知识库文件路径等常量
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库配置
DATABASE_PATH = BASE_DIR / "chat_history.db"  # SQLite数据库文件路径

# 商品知识库JSON文件路径
PRODUCTS_JSON_PATH = BASE_DIR / "products.json"

# 通义千问API配置
# TODO: 请替换为你的阿里云通义千问API密钥
QIANWEN_API_KEY = "sk-7757ceec9c424953b6549d4c5eb14886"
QIANWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
QIANWEN_MODEL = "qwen-turbo"
# API调用超时时间（秒）
API_TIMEOUT = 30

# 降级方案预设话术
FALLBACK_RESPONSES = [
    "抱歉，我现在无法连接到智能客服系统，请稍后再试。",
    "系统暂时繁忙，您可以先查看商品详情或联系人工客服。",
    "网络连接不稳定，建议您刷新页面后重试。"
]

# 最大对话记录保存条数（每个用户）
MAX_HISTORY_PER_USER = 50