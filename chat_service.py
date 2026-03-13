"""
核心聊天服务模块
集成商品知识库和通义千问API，处理用户消息并生成智能回复
包含完整的业务流程和异常处理
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
import json

from database import db
from knowledge_base import knowledge_base
from qianwen_api import qianwen_client

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务核心类"""

    def __init__(self):
        """初始化聊天服务"""
        self.knowledge_base = knowledge_base
        self.api_client = qianwen_client
        self.db = db

    def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        处理用户消息，生成回复

        Args:
            user_id: 用户标识
            message: 用户消息

        Returns:
            包含回复和元数据的字典
        """
        # 输入验证
        if not user_id or not user_id.strip():
            logger.warning("用户ID不能为空")
            return self._create_error_response("用户ID不能为空")

        if not message or not message.strip():
            logger.warning("用户消息不能为空")
            return self._create_error_response("用户消息不能为空")

        # 清理用户输入
        user_id = user_id.strip()
        message = message.strip()

        try:
            logger.info(f"处理用户消息，用户: {user_id}, 消息: {message[:50]}...")

            # 1. 提取用户意图和关键信息
            intent, extracted_info = self._analyze_user_intent(message)

            # 2. 根据意图查询商品知识库
            product_info = self._query_product_knowledge(intent, extracted_info, message)

            # 3. 获取对话历史
            history = self._prepare_conversation_history(user_id)

            # 4. 构建AI提示词（包含商品信息）
            enhanced_prompt = self._enhance_prompt_with_products(message, product_info)

            # 5. 调用AI API生成回复
            ai_response = self.api_client.generate_response(
                prompt=enhanced_prompt,
                history=history
            )

            # 6. 提取AI回复内容
            if ai_response.get("success"):
                response_content = ai_response["content"]
                metadata = {
                    "intent": intent,
                    "product_info_used": bool(product_info),
                    "product_count": len(product_info) if product_info else 0,
                    "api_success": True,
                    "is_fallback": ai_response.get("is_fallback", False)
                }
            else:
                # API调用失败，使用降级回复
                response_content = ai_response["content"]
                metadata = {
                    "intent": intent,
                    "product_info_used": bool(product_info),
                    "product_count": len(product_info) if product_info else 0,
                    "api_success": False,
                    "is_fallback": True,
                    "error_reason": ai_response.get("error_reason", "unknown")
                }

            # 7. 保存对话记录
            save_success = self.db.save_conversation(
                user_id=user_id,
                user_message=message,
                bot_response=response_content,
                metadata=metadata
            )

            if not save_success:
                logger.warning("对话记录保存失败，但已生成回复")

            # 8. 构建最终响应
            response_data = {
                "success": True,
                "response": response_content,
                "user_id": user_id,
                "metadata": metadata,
                "product_suggestions": product_info[:3] if product_info else []  # 最多返回3个商品建议
            }

            logger.info(f"消息处理完成，用户: {user_id}, 回复长度: {len(response_content)}")
            return response_data

        except Exception as e:
            logger.error(f"处理用户消息时发生异常: {e}")
            return self._create_error_response(f"系统错误: {str(e)[:100]}")

    def _analyze_user_intent(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """
        分析用户意图和提取关键信息

        Args:
            message: 用户消息

        Returns:
            (意图类型, 提取的信息字典)
        """
        message_lower = message.lower()

        # 初始化提取信息
        extracted_info = {
            "keywords": [],
            "categories": [],
            "price_range": {},  # 改为空字典，避免None导致的.get()错误
            "product_id": None
        }

        # 提取关键词（简单的分词）
        words = re.findall(r'\b\w+\b', message_lower)
        extracted_info["keywords"] = [word for word in words if len(word) > 1]

        # 检查价格相关词汇
        price_patterns = [
            r'(\d+)\s*元', r'(\d+)\s*块钱', r'价格.*?(\d+)', r'多少钱', r'价格多少',
            r'低于\s*(\d+)', r'高于\s*(\d+)', r'(\d+)\s*以下', r'(\d+)\s*以上'
        ]
        for pattern in price_patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                for match in matches:
                    if match.isdigit():
                        price = float(match)
                        if "低于" in message_lower or "以下" in message_lower:
                            extracted_info["price_range"] = {"max": price}
                        elif "高于" in message_lower or "以上" in message_lower:
                            extracted_info["price_range"] = {"min": price}
                        else:
                            # 简单价格查询
                            pass

        # 检查商品ID
        id_patterns = [r'商品\s*[#]?\s*(\d+)', r'id\s*[:]?\s*(\d+)', r'编号\s*[:]?\s*(\d+)']
        for pattern in id_patterns:
            match = re.search(pattern, message_lower)
            if match:
                extracted_info["product_id"] = match.group(1)
                break

        # 判断意图类型
        intent = "general_query"  # 默认意图：一般查询

        if any(word in message_lower for word in ["价格", "多少钱", "价", "cost", "price"]):
            intent = "price_inquiry"
        elif any(word in message_lower for word in ["库存", "有货", "没货", "stock", "availability"]):
            intent = "stock_inquiry"
        elif any(word in message_lower for word in ["推荐", "有什么", "看看", "商品", "product"]):
            intent = "product_recommendation"
        elif any(word in message_lower for word in ["物流", "发货", "快递", "delivery", "shipping"]):
            intent = "delivery_inquiry"
        elif any(word in message_lower for word in ["售后", "退货", "换货", "退款", "warranty"]):
            intent = "after_sales"
        elif extracted_info["product_id"]:
            intent = "product_detail"

        logger.debug(f"用户意图分析: {intent}, 提取信息: {extracted_info}")
        return intent, extracted_info

    def _query_product_knowledge(self, intent: str, extracted_info: Dict[str, Any],
                                original_message: str) -> List[Dict[str, Any]]:
        """
        根据意图查询商品知识库

        Args:
            intent: 用户意图
            extracted_info: 提取的信息
            original_message: 原始用户消息

        Returns:
            相关商品列表
        """
        if not self.knowledge_base.products:
            logger.warning("商品知识库为空")
            return []

        try:
            product_results = []

            # 根据意图采用不同的查询策略
            if intent == "product_detail" and extracted_info.get("product_id"):
                # 按ID查询具体商品
                product = self.knowledge_base.get_product_by_id(
                    extracted_info["product_id"]
                )
                if product:
                    product_results.append(product)

            elif intent in ["price_inquiry", "stock_inquiry", "product_recommendation"]:
                # 基于关键词的搜索
                keywords = extracted_info.get("keywords") or []
                if keywords:
                    # 使用最长的关键词进行搜索
                    main_keyword = max(keywords, key=len) if keywords else ""
                    if main_keyword:
                        # 处理可能为None的price_range
                        price_range = extracted_info.get("price_range") or {}
                        product_results = self.knowledge_base.search_products(
                            keyword=main_keyword,
                            max_price=price_range.get("max"),
                            min_price=price_range.get("min"),
                            limit=5
                        )

            elif intent == "general_query":
                # 通用查询，尝试所有关键词
                keywords = extracted_info.get("keywords") or []
                for keyword in keywords:
                    if len(keyword) > 2:  # 忽略太短的词
                        results = self.knowledge_base.search_products(
                            keyword=keyword,
                            limit=3
                        )
                        product_results.extend(results)
                        if product_results:
                            break

            # 去重（基于商品ID）
            unique_products = []
            seen_ids = set()
            for product in product_results:
                # 防御性编程：跳过None值
                if product is None:
                    continue
                pid = product.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    unique_products.append(product)

            logger.info(f"商品知识库查询结果: {len(unique_products)} 个商品")
            return unique_products

        except Exception as e:
            logger.error(f"查询商品知识库失败: {e}")
            return []

    def _prepare_conversation_history(self, user_id: str) -> List[Dict[str, str]]:
        """
        准备对话历史，用于AI上下文

        Args:
            user_id: 用户标识

        Returns:
            格式化的对话历史列表
        """
        try:
            history_records = self.db.get_conversation_history(user_id, limit=5)

            # 转换为API所需的格式
            formatted_history = []
            for record in reversed(history_records):  # 按时间正序排列
                formatted_history.append({
                    "role": "user",
                    "content": record["user_message"]
                })
                formatted_history.append({
                    "role": "assistant",
                    "content": record["bot_response"]
                })

            logger.debug(f"准备对话历史: {len(formatted_history)//2} 轮对话")
            return formatted_history

        except Exception as e:
            logger.error(f"准备对话历史失败: {e}")
            return []

    def _enhance_prompt_with_products(self, original_prompt: str,
                                     product_info: List[Dict[str, Any]]) -> str:
        """
        用商品信息增强用户提示词

        Args:
            original_prompt: 原始用户提示词
            product_info: 相关商品信息

        Returns:
            增强后的提示词
        """
        if not product_info:
            return original_prompt

        try:
            # 构建商品信息文本
            product_texts = []
            for i, product in enumerate(product_info[:3], 1):  # 最多3个商品
                # 防御性编程：跳过None值
                if product is None:
                    continue
                product_text = f"商品{i}:\n"
                product_text += f"- 名称: {product.get('name', '未知')}\n"
                product_text += f"- 价格: {product.get('price', 0)}元\n"

                if product.get('description'):
                    desc = product['description']
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    product_text += f"- 描述: {desc}\n"

                if product.get('category'):
                    product_text += f"- 分类: {product.get('category')}\n"

                if product.get('stock') is not None:
                    product_text += f"- 库存: {product.get('stock')}件\n"

                product_texts.append(product_text)

            enhanced_prompt = f"""{original_prompt}

根据以下商品信息回答用户问题（如果相关）：

{chr(10).join(product_texts)}

请基于以上信息提供准确、有帮助的回答。如果商品信息不足以回答问题，请如实告知。"""
            logger.debug(f"提示词增强完成，添加了 {len(product_info)} 个商品信息")
            return enhanced_prompt

        except Exception as e:
            logger.error(f"增强提示词失败: {e}")
            return original_prompt

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        创建错误响应

        Args:
            error_message: 错误信息

        Returns:
            错误响应字典
        """
        return {
            "success": False,
            "response": f"抱歉，处理您的请求时出现错误: {error_message}",
            "error": error_message,
            "metadata": {
                "api_success": False,
                "is_fallback": True
            }
        }

    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户的对话历史

        Args:
            user_id: 用户标识
            limit: 最大记录数

        Returns:
            对话历史列表
        """
        return self.db.get_conversation_history(user_id, limit)

    def clear_user_history(self, user_id: str) -> bool:
        """
        清空用户的对话历史

        Args:
            user_id: 用户标识

        Returns:
            清空成功返回True，失败返回False
        """
        return self.db.clear_user_history(user_id)

# 全局聊天服务实例
chat_service = ChatService()