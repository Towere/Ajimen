"""
电商智能客服测试用例
包含单元测试、集成测试和API测试
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 导入被测试模块
from database import ChatDatabase
from knowledge_base import ProductKnowledgeBase
from qianwen_api import QianwenAPI
from chat_service import ChatService
from config import DATABASE_PATH, PRODUCTS_JSON_PATH

# 测试用商品数据
TEST_PRODUCTS = [
    {
        "id": "1",
        "name": "华为Mate 60 Pro",
        "price": 6999.00,
        "description": "华为旗舰智能手机，搭载麒麟9000S芯片",
        "category": "手机",
        "stock": 50,
        "attributes": {
            "color": "黑色",
            "storage": "512GB"
        }
    },
    {
        "id": "2",
        "name": "iPhone 15 Pro",
        "price": 8999.00,
        "description": "苹果最新旗舰手机，A17 Pro芯片",
        "category": "手机",
        "stock": 30,
        "attributes": {
            "color": "钛金属",
            "storage": "256GB"
        }
    },
    {
        "id": "3",
        "name": "小米电视 75英寸",
        "price": 4999.00,
        "description": "4K超高清智能电视，支持MEMC运动补偿",
        "category": "电视",
        "stock": 20,
        "attributes": {
            "resolution": "4K",
            "size": "75英寸"
        }
    }
]

class TestChatDatabase:
    """数据库模块测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        # 使用临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.db = ChatDatabase(self.db_path)

    def teardown_method(self):
        """每个测试方法后执行"""
        # 关闭数据库连接并删除临时文件
        if hasattr(self, 'temp_db'):
            self.temp_db.close()
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)

    def test_init_database(self):
        """测试数据库初始化"""
        # 检查表是否存在
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
        table_exists = cursor.fetchone() is not None

        conn.close()
        assert table_exists, "数据库表应被创建"

    def test_save_conversation(self):
        """测试保存对话记录"""
        # 正常保存
        success = self.db.save_conversation(
            user_id="test_user",
            user_message="你好",
            bot_response="您好，有什么可以帮您？"
        )
        assert success, "对话记录应保存成功"

        # 参数为空
        success = self.db.save_conversation("", "消息", "回复")
        assert not success, "空用户ID应导致保存失败"

        success = self.db.save_conversation("test_user", "", "回复")
        assert not success, "空用户消息应导致保存失败"

        success = self.db.save_conversation("test_user", "消息", "")
        assert not success, "空机器人回复应导致保存失败"

    def test_save_conversation_with_metadata(self):
        """测试保存带元数据的对话记录"""
        metadata = {"intent": "price_inquiry", "api_used": True}
        success = self.db.save_conversation(
            user_id="test_user",
            user_message="这个手机多少钱？",
            bot_response="价格为6999元",
            metadata=metadata
        )
        assert success, "带元数据的对话记录应保存成功"

        # 验证元数据保存
        history = self.db.get_conversation_history("test_user", limit=1)
        assert len(history) == 1
        assert history[0]['metadata'] == metadata

    def test_get_conversation_history(self):
        """测试获取对话历史"""
        # 先保存几条记录
        for i in range(3):
            self.db.save_conversation(
                user_id="test_user",
                user_message=f"消息{i}",
                bot_response=f"回复{i}"
            )

        history = self.db.get_conversation_history("test_user", limit=5)
        assert len(history) == 3, "应获取到3条历史记录"
        assert history[0]['user_message'] == "消息2", "记录应按时间倒序排列"

        # 不存在的用户
        history = self.db.get_conversation_history("non_existent_user")
        assert len(history) == 0, "不存在的用户应返回空列表"

    def test_clear_user_history(self):
        """测试清空用户历史"""
        # 先保存记录
        self.db.save_conversation("test_user", "消息", "回复")

        # 清空历史
        success = self.db.clear_user_history("test_user")
        assert success, "清空历史应成功"

        # 验证已清空
        history = self.db.get_conversation_history("test_user")
        assert len(history) == 0, "用户历史应被清空"

        # 清空不存在的用户
        success = self.db.clear_user_history("non_existent_user")
        assert success, "清空不存在的用户也应返回成功"

    def test_get_all_users(self):
        """测试获取所有用户"""
        # 保存多个用户的记录
        self.db.save_conversation("user1", "消息1", "回复1")
        self.db.save_conversation("user2", "消息2", "回复2")
        self.db.save_conversation("user1", "消息3", "回复3")  # 重复用户

        users = self.db.get_all_users()
        assert len(users) == 2, "应获取到2个唯一用户"
        assert "user1" in users
        assert "user2" in users

class TestProductKnowledgeBase:
    """商品知识库测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        # 创建临时JSON文件
        self.temp_json = tempfile.NamedTemporaryFile(suffix=".json", mode='w', delete=False, encoding='utf-8')
        json.dump(TEST_PRODUCTS, self.temp_json, ensure_ascii=False)
        self.temp_json.close()

        self.kb = ProductKnowledgeBase(self.temp_json.name)

    def teardown_method(self):
        """每个测试方法后执行"""
        if hasattr(self, 'temp_json') and os.path.exists(self.temp_json.name):
            os.unlink(self.temp_json.name)

    def test_load_products(self):
        """测试加载商品数据"""
        assert len(self.kb.products) == 3, "应加载3个商品"
        assert self.kb.products[0]['name'] == "华为Mate 60 Pro"

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        kb = ProductKnowledgeBase("non_existent_file.json")
        assert len(kb.products) == 0, "不存在的文件应返回空列表"

    def test_search_products(self):
        """测试商品搜索"""
        # 关键词搜索
        results = self.kb.search_products("华为")
        assert len(results) == 1
        assert results[0]['name'] == "华为Mate 60 Pro"

        # 分类过滤
        results = self.kb.search_products("电视", category="电视")
        assert len(results) == 1
        assert results[0]['name'] == "小米电视 75英寸"

        # 价格过滤
        results = self.kb.search_products("手机", max_price=7000)
        assert len(results) == 1  # 只有华为手机价格<=7000
        assert results[0]['name'] == "华为Mate 60 Pro"

        # 空关键词
        results = self.kb.search_products("")
        assert len(results) == 0

    def test_get_product_by_id(self):
        """测试根据ID获取商品"""
        product = self.kb.get_product_by_id("1")
        assert product is not None
        assert product['name'] == "华为Mate 60 Pro"

        # 不存在的ID
        product = self.kb.get_product_by_id("999")
        assert product is None

        # 字符串ID
        product = self.kb.get_product_by_id(1)  # 整数ID
        assert product is not None

    def test_get_categories(self):
        """测试获取商品分类"""
        categories = self.kb.get_categories()
        assert len(categories) == 2
        assert "手机" in categories
        assert "电视" in categories

    def test_validate_product(self):
        """测试商品验证"""
        valid_product = {
            "id": "100",
            "name": "测试商品",
            "price": 100.0,
            "description": "测试描述",
            "category": "测试分类"
        }
        assert self.kb._validate_product(valid_product)

        # 缺少必需字段
        invalid_product = {"name": "测试商品", "price": 100.0}
        assert not self.kb._validate_product(invalid_product)

        # 价格负数
        invalid_product = {"id": "100", "name": "测试商品", "price": -10}
        assert not self.kb._validate_product(invalid_product)

    def test_reload(self):
        """测试重新加载商品数据"""
        success = self.kb.reload()
        assert success
        assert len(self.kb.products) == 3

class TestQianwenAPI:
    """通义千问API测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.api = QianwenAPI(api_key="test_api_key", api_url="https://test.api.url")

    def test_prepare_headers(self):
        """测试准备请求头"""
        headers = self.api._prepare_headers()
        assert "Content-Type" in headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_api_key"

    def test_prepare_payload(self):
        """测试准备请求数据"""
        payload = self.api._prepare_payload("你好")
        assert "model" in payload
        assert "input" in payload
        assert "parameters" in payload

        messages = payload["input"]["messages"]
        assert len(messages) >= 2  # 系统提示词 + 用户消息
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "你好"

    @patch('requests.post')
    def test_generate_response_success(self, mock_post):
        """测试成功生成回复"""
        # 模拟成功的API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "200",
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": "您好，我是电商客服助手，有什么可以帮您？"
                        }
                    }
                ]
            },
            "usage": {"total_tokens": 50}
        }
        mock_post.return_value = mock_response

        result = self.api.generate_response("你好", retry_count=0)

        assert result["success"]
        assert "您好" in result["content"]
        assert "usage" in result

    @patch('requests.post')
    def test_generate_response_api_error(self, mock_post):
        """测试API返回错误"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "400",
            "message": "参数错误"
        }
        mock_post.return_value = mock_response

        result = self.api.generate_response("你好", retry_count=0)

        assert not result["success"]
        assert "is_fallback" in result
        assert result["is_fallback"]

    @patch('requests.post')
    def test_generate_response_http_error(self, mock_post):
        """测试HTTP错误"""
        mock_post.side_effect = requests.exceptions.ConnectionError("连接失败")

        result = self.api.generate_response("你好", retry_count=0)

        assert not result["success"]
        assert "is_fallback" in result

    def test_generate_response_empty_prompt(self):
        """测试空提示词"""
        result = self.api.generate_response("", retry_count=0)
        assert not result["success"]
        assert "用户输入为空" in result.get("error_reason", "")

    def test_create_fallback_response(self):
        """测试创建降级响应"""
        result = self.api._create_fallback_response("测试错误")
        assert not result["success"]
        assert "is_fallback" in result
        assert result["is_fallback"]

class TestChatService:
    """聊天服务测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        # 创建模拟对象
        self.mock_db = Mock()
        self.mock_kb = Mock()
        self.mock_api = Mock()

        # 创建聊天服务实例并注入模拟对象
        self.chat_service = ChatService()
        self.chat_service.db = self.mock_db
        self.chat_service.knowledge_base = self.mock_kb
        self.chat_service.api_client = self.mock_api

    def test_process_message_success(self):
        """测试成功处理消息"""
        # 模拟依赖组件的行为
        self.mock_kb.products = []  # 空商品列表
        self.mock_db.get_conversation_history.return_value = []
        self.mock_db.save_conversation.return_value = True

        self.mock_api.generate_response.return_value = {
            "success": True,
            "content": "这是AI回复",
            "is_fallback": False
        }

        result = self.chat_service.process_message("test_user", "你好")

        assert result["success"]
        assert result["response"] == "这是AI回复"
        assert result["user_id"] == "test_user"

        # 验证数据库保存被调用
        self.mock_db.save_conversation.assert_called_once()

    def test_process_message_empty_input(self):
        """测试空输入"""
        result = self.chat_service.process_message("", "消息")
        assert not result["success"]

        result = self.chat_service.process_message("test_user", "")
        assert not result["success"]

    def test_analyze_user_intent(self):
        """测试用户意图分析"""
        # 价格查询意图
        intent, info = self.chat_service._analyze_user_intent("这个手机多少钱？")
        assert intent == "price_inquiry"
        assert "keywords" in info

        # 库存查询意图
        intent, info = self.chat_service._analyze_user_intent("有库存吗？")
        assert intent == "stock_inquiry"

        # 商品推荐意图
        intent, info = self.chat_service._analyze_user_intent("推荐手机")
        assert intent == "product_recommendation"

        # 商品详情意图
        intent, info = self.chat_service._analyze_user_intent("商品ID 123")
        assert intent == "product_detail"
        assert info["product_id"] == "123"

    def test_query_product_knowledge(self):
        """测试查询商品知识库"""
        # 模拟知识库返回结果
        mock_products = [
            {"id": "1", "name": "测试商品1", "price": 100},
            {"id": "2", "name": "测试商品2", "price": 200}
        ]
        self.mock_kb.get_product_by_id.return_value = mock_products[0]
        self.mock_kb.search_products.return_value = mock_products

        # 商品详情意图
        intent = "product_detail"
        extracted_info = {"product_id": "1", "keywords": ["手机"]}
        products = self.chat_service._query_product_knowledge(intent, extracted_info, "测试消息")
        assert len(products) == 1
        self.mock_kb.get_product_by_id.assert_called_with("1")

        # 价格查询意图
        intent = "price_inquiry"
        extracted_info = {"keywords": ["手机"], "price_range": {"max": 150}}
        products = self.chat_service._query_product_knowledge(intent, extracted_info, "测试消息")
        self.mock_kb.search_products.assert_called()

    def test_prepare_conversation_history(self):
        """测试准备对话历史"""
        # 模拟数据库返回历史记录
        mock_history = [
            {"user_message": "消息1", "bot_response": "回复1"},
            {"user_message": "消息2", "bot_response": "回复2"}
        ]
        self.mock_db.get_conversation_history.return_value = mock_history

        history = self.chat_service._prepare_conversation_history("test_user")

        assert len(history) == 4  # 2轮对话，每轮2条消息
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "消息1"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "回复1"

# API测试（需要运行中的服务）
class TestAPIIntegration:
    """API集成测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        # 注意：这些测试需要实际运行FastAPI服务
        # 这里只提供测试用例模板
        pass

    def test_health_endpoint(self):
        """测试健康检查端点"""
        # 实际测试时应使用requests库调用本地服务
        # response = requests.get("http://localhost:8000/health")
        # assert response.status_code == 200
        # assert response.json()["success"] == True
        pass

    def test_chat_endpoint(self):
        """测试聊天端点"""
        # 实际测试时应使用requests库调用本地服务
        # data = {"user_id": "test_user", "message": "你好"}
        # response = requests.post("http://localhost:8000/api/chat", params=data)
        # assert response.status_code == 200
        pass

if __name__ == "__main__":
    """直接运行测试"""
    pytest.main([__file__, "-v"])