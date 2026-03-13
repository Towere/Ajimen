"""
通义千问API模块
调用阿里云通义千问API，实现智能对话功能
包含完整的异常处理和降级方案
"""
import json
import logging
import random
import time
from typing import Dict, Any, Optional, List

import requests

from config import QIANWEN_API_KEY, QIANWEN_API_URL, QIANWEN_MODEL, API_TIMEOUT, FALLBACK_RESPONSES

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QianwenAPI:
    """通义千问API客户端（修复版）"""

    def __init__(self, api_key: str = None, api_url: str = None):
        """
        初始化API客户端

        Args:
            api_key: 通义千问API密钥，默认为config中的QIANWEN_API_KEY
            api_url: API端点URL，默认为config中的QIANWEN_API_URL

        Raises:
            ValueError: API密钥未配置
        """
        # 优先使用传入值，兜底用配置文件（修复原代码未使用传入值的问题）
        self.api_key = api_key or QIANWEN_API_KEY
        self.api_url = api_url or QIANWEN_API_URL
        self.model = QIANWEN_MODEL  # 改用配置文件的模型，不再硬编码
        self.timeout = API_TIMEOUT

        # 强化密钥校验（抛异常而非仅警告）
        if not self.api_key or self.api_key.strip() == "" or self.api_key == "your-api-key-here":
            raise ValueError("API密钥未配置！请替换config.py中的QIANWEN_API_KEY为有效密钥")
        logger.info("通义千问API客户端初始化成功")

    def _prepare_headers(self) -> Dict[str, str]:
        """
        准备请求头（移除冗余字段，简化配置）

        Returns:
            包含认证信息的请求头字典
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"  # 移除X-DashScope-SSE，默认禁用即可
        }

    def _prepare_payload(self, prompt: str, history: List[Dict[str, str]] = None,
                        temperature: float = 0.8, max_tokens: int = 1000) -> Dict[str, Any]:
        """
        准备请求数据（修复模型硬编码、简化参数）

        Args:
            prompt: 用户输入的提示词
            history: 对话历史，格式为[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数

        Returns:
            请求数据字典
        """
        messages = []

        # 精简系统提示词（避免过长导致token浪费）
        system_prompt = """你是专业的电商客服助手，回答用户关于商品、价格、库存、物流、售后的问题，友好且专业。
不知道答案时建议查看商品详情或联系人工客服，不编造信息。"""
        messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        if history and isinstance(history, list):
            # 过滤无效历史记录
            valid_history = [h for h in history if isinstance(h, dict) and "role" in h and "content" in h]
            messages.extend(valid_history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": prompt.strip()})

        # 修复：使用配置文件的模型，简化参数（只保留核心参数）
        return {
            "model": self.model,  # 不再硬编码qwen-max，使用config中的qwen-turbo
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "message"  # 强制返回message格式，避免解析错误
            }
        }

    def generate_response(self, prompt: str, history: List[Dict[str, str]] = None,
                         temperature: float = 0.8, max_tokens: int = 1000,
                         retry_count: int = 2) -> Dict[str, Any]:
        """
        生成AI回复（修复响应解析、重试逻辑、日志）

        Args:
            prompt: 用户输入的提示词
            history: 对话历史
            temperature: 温度参数
            max_tokens: 最大生成token数
            retry_count: 重试次数（默认2次，总尝试3次，匹配日志）

        Returns:
            包含响应状态和内容的字典
        """
        # 输入验证
        if not prompt or not prompt.strip():
            logger.warning("生成回复失败：prompt不能为空")
            return self._create_fallback_response("用户输入为空")

        # 准备请求数据
        payload = self._prepare_payload(prompt, history, temperature, max_tokens)
        headers = self._prepare_headers()

        # 重试机制（retry_count=2 → 总尝试3次，匹配日志）
        for attempt in range(retry_count + 1):
            try:
                logger.info(f"调用通义千问API，第{attempt + 1}次尝试，prompt长度: {len(prompt.strip())}")

                # 发送请求
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )

                # 检查HTTP状态码
                response.raise_for_status()  # 自动抛出4xx/5xx错误
                result = response.json()

                # 修复：千问API成功时无code字段，直接判断output是否存在
                if "output" in result:
                    output = result["output"]
                    choices = output.get("choices", [])
                    if choices and "message" in choices[0]:
                        content = choices[0]["message"]["content"].strip()
                        if content:
                            logger.info(f"API调用成功，生成回复长度: {len(content)}")
                            return {
                                "success": True,
                                "content": content,
                                "usage": result.get("usage", {}),
                                "model": result.get("model", self.model)
                            }
                    logger.error("API响应无有效回复内容")
                else:
                    # 解析API错误信息（千问API错误时返回code/message）
                    error_code = result.get("code", "unknown")
                    error_msg = result.get("message", "未知API错误")
                    logger.error(f"API返回错误: {error_code} - {error_msg}")

            except requests.exceptions.HTTPError as e:
                # 处理HTTP错误（401/429/500等）
                status_code = response.status_code if 'response' in locals() else 0
                if status_code == 401:
                    logger.error("API认证失败，请检查API密钥是否有效")
                    return self._create_fallback_response("API密钥无效/过期")
                elif status_code == 429:
                    logger.warning(f"API调用频率限制（{status_code}），等待后重试")
                    if attempt < retry_count:
                        time.sleep(2 ** attempt)  # 指数退避（1s→2s→4s）
                        continue
                elif status_code == 403:
                    logger.error("API权限不足（qwen-max需要申请，建议改用qwen-turbo）")
                    return self._create_fallback_response("模型权限不足")
                else:
                    logger.error(f"HTTP错误: {status_code}, 响应: {response.text[:200]}")

            except requests.exceptions.Timeout:
                logger.warning(f"API调用超时（{self.timeout}s），第{attempt + 1}次尝试")
                if attempt < retry_count:
                    time.sleep(1)
                    continue

            except requests.exceptions.ConnectionError:
                logger.warning(f"网络连接错误，第{attempt + 1}次尝试")
                if attempt < retry_count:
                    time.sleep(2)
                    continue

            except json.JSONDecodeError:
                logger.error("API响应不是有效的JSON格式")
                if attempt < retry_count:
                    time.sleep(1)
                    continue

            except Exception as e:
                logger.error(f"API调用异常: {str(e)[:100]}")
                if attempt < retry_count:
                    time.sleep(1)
                    continue

            # 单次尝试失败，继续重试（最后一次失败则退出）
            if attempt == retry_count:
                logger.error(f"API调用第{attempt + 1}次尝试失败，无更多重试次数")

        # 所有重试都失败
        return self._create_fallback_response("API调用失败，请稍后再试")

    def _create_fallback_response(self, error_reason: str = "") -> Dict[str, Any]:
        """
        创建降级响应（保持原有逻辑）

        Args:
            error_reason: 错误原因

        Returns:
            降级响应字典
        """
        fallback_text = random.choice(FALLBACK_RESPONSES) if FALLBACK_RESPONSES else "抱歉，暂时无法为你解答，请稍后再试。"
        if error_reason:
            fallback_text += f"（原因: {error_reason}）"

        logger.info(f"使用降级方案，回复: {fallback_text[:50]}...")

        return {
            "success": False,
            "content": fallback_text,
            "error_reason": error_reason,
            "is_fallback": True
        }

    def test_connection(self) -> bool:
        """
        测试API连接是否正常（修复测试逻辑）

        Returns:
            连接成功返回True，失败返回False
        """
        try:
            # 发送极简测试请求
            test_prompt = "你好"
            result = self.generate_response(test_prompt, retry_count=0)  # 不重试，快速测试

            if result.get("success"):
                logger.info("API连接测试成功")
                return True
            else:
                logger.warning(f"API连接测试失败: {result.get('error_reason', '未知错误')}")
                return False

        except Exception as e:
            logger.error(f"API连接测试异常: {str(e)[:100]}")
            return False

# 全局API客户端实例
try:
    qianwen_client = QianwenAPI()
except ValueError as e:
    logger.error(f"全局API客户端初始化失败: {e}")
    qianwen_client = None