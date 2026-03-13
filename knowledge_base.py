"""
商品知识库模块
加载JSON格式的商品数据，提供商品查询功能
包含完整的异常处理和输入验证
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from difflib import SequenceMatcher  # 用于模糊匹配
import jieba  # 中文分词（需先安装：pip install jieba）

from config import PRODUCTS_JSON_PATH

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 中文停用词（无意义词汇，搜索时过滤）
STOPWORDS = {'的', '了', '吗', '呢', '啊', '吧', '哦', '我', '你', '他', '它', '这', '那', '个', '件', '只', '双'}

class ProductKnowledgeBase:
    """商品知识库类"""

    def __init__(self, json_path: str = None):
        """
        初始化商品知识库

        Args:
            json_path: JSON文件路径，默认为config中的PRODUCTS_JSON_PATH

        Raises:
            FileNotFoundError: JSON文件不存在
            json.JSONDecodeError: JSON格式错误
        """
        self.json_path = Path(json_path or PRODUCTS_JSON_PATH)
        self.products: List[Dict[str, Any]] = []
        self._load_products()

    def _load_products(self) -> None:
        """加载商品数据从JSON文件"""
        try:
            if not self.json_path.exists():
                logger.warning(f"商品知识库文件不存在: {self.json_path}")
                self.products = []
                return

            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证JSON结构
            if isinstance(data, list):
                self.products = data
            elif isinstance(data, dict) and 'products' in data:
                self.products = data['products']
            else:
                logger.error(f"商品知识库格式错误，期望列表或包含'products'键的字典")
                self.products = []

            logger.info(f"成功加载 {len(self.products)} 个商品")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            self.products = []
        except Exception as e:
            logger.error(f"加载商品知识库失败: {e}")
            self.products = []

    def _preprocess_text(self, text: str) -> List[str]:
        """
        文本预处理：分词、去停用词、小写转换
        Args:
            text: 原始文本
        Returns:
            处理后的关键词列表
        """
        if not text:
            return []
        
        # 转小写+去除特殊字符
        clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text.lower().strip())
        # 中文分词
        words = jieba.lcut(clean_text)
        # 去停用词+空字符串
        return [word for word in words if word and word not in STOPWORDS and len(word) > 1]

    def _calculate_similarity(self, product: Dict[str, Any], keywords: List[str]) -> float:
        """
        计算商品与关键词的相似度得分（0-1）
        Args:
            product: 商品数据
            keywords: 预处理后的关键词列表
        Returns:
            相似度得分
        """
        if not keywords:
            return 0.0

        # 提取商品文本信息
        product_texts = [
            product.get('name', ''),
            product.get('description', ''),
            product.get('category', ''),
            # 可选：加入商品属性文本（比如颜色、尺码）
            ' '.join(product.get('attributes', {}).values()) if isinstance(product.get('attributes'), dict) else ''
        ]
        product_text = ' '.join(product_texts).lower()
        product_words = self._preprocess_text(product_text)

        # 计算匹配得分
        match_score = 0.0
        total_keywords = len(keywords)

        for keyword in keywords:
            # 1. 精确匹配：关键词在商品词列表中
            if keyword in product_words:
                match_score += 1.0
            else:
                # 2. 模糊匹配：相似度>0.7则加分
                for p_word in product_words:
                    similarity = SequenceMatcher(None, keyword, p_word).ratio()
                    if similarity > 0.7:
                        match_score += similarity * 0.8  # 模糊匹配权重稍低
                        break

        # 归一化得分（0-1）
        return match_score / total_keywords if total_keywords > 0 else 0.0

    def search_products(self, keyword: str, category: str = None,
                       max_price: float = None, min_price: float = None,
                       limit: int = 10) -> List[Dict[str, Any]]:
        """
        优化版：智能搜索商品（支持分词、模糊匹配、权重排序）

        Args:
            keyword: 搜索关键词
            category: 商品分类（可选）
            max_price: 最高价格（可选）
            min_price: 最低价格（可选）
            limit: 返回的最大商品数量

        Returns:
            匹配的商品列表（按相似度降序）
        """
        if not keyword or not keyword.strip():
            logger.warning("搜索关键词不能为空")
            return []

        try:
            # 预处理搜索关键词
            search_keywords = self._preprocess_text(keyword)
            if not search_keywords:
                logger.warning(f"关键词预处理后为空: {keyword}")
                return []

            results = []
            for product in self.products:
                # 验证商品数据结构
                if not self._validate_product(product):
                    continue

                # 1. 分类过滤
                if category:
                    product_category = product.get('category', '').lower()
                    if category.lower() not in product_category:
                        continue

                # 2. 价格过滤
                price = product.get('price', 0)
                if max_price is not None and price > max_price:
                    continue
                if min_price is not None and price < min_price:
                    continue

                # 3. 计算相似度得分
                similarity = self._calculate_similarity(product, search_keywords)
                if similarity > 0:  # 只保留有匹配的商品
                    results.append({
                        'product': product,
                        'similarity': similarity
                    })

            # 按相似度降序排序（相似度越高越靠前）
            results.sort(key=lambda x: x['similarity'], reverse=True)

            # 提取商品数据并限制数量
            limited_results = [item['product'] for item in results[:limit]]
            logger.info(f"搜索 '{keyword}' 找到 {len(limited_results)} 个匹配商品")
            return limited_results

        except Exception as e:
            logger.error(f"商品搜索失败: {e}")
            return []

    def get_product_by_id(self, product_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        根据商品ID获取商品详情

        Args:
            product_id: 商品ID

        Returns:
            商品信息字典，如果未找到返回None
        """
        try:
            product_id_str = str(product_id)
            for product in self.products:
                if self._validate_product(product):
                    pid = product.get('id')
                    if pid and str(pid) == product_id_str:
                        logger.info(f"找到商品ID: {product_id}")
                        return product

            logger.warning(f"未找到商品ID: {product_id}")
            return None

        except Exception as e:
            logger.error(f"根据ID获取商品失败: {e}")
            return None

    def get_categories(self) -> List[str]:
        """
        获取所有商品分类

        Returns:
            分类列表（去重）
        """
        try:
            categories = set()
            for product in self.products:
                if self._validate_product(product):
                    category = product.get('category')
                    if category:
                        categories.add(category)

            category_list = list(categories)
            logger.info(f"获取到 {len(category_list)} 个商品分类")
            return category_list

        except Exception as e:
            logger.error(f"获取商品分类失败: {e}")
            return []

    def _validate_product(self, product: Dict[str, Any]) -> bool:
        """
        验证商品数据结构的有效性

        Args:
            product: 商品数据字典

        Returns:
            有效返回True，否则返回False
        """
        try:
            if not isinstance(product, dict):
                return False

            required_fields = ['id', 'name', 'price']
            for field in required_fields:
                if field not in product:
                    return False

            if not isinstance(product['id'], (str, int)):
                return False
            if not isinstance(product['name'], str):
                return False
            if not isinstance(product['price'], (int, float)) or product['price'] < 0:
                return False

            if 'description' in product and not isinstance(product['description'], str):
                return False
            if 'category' in product and not isinstance(product['category'], str):
                return False
            if 'stock' in product and not isinstance(product['stock'], int):
                return False
            if 'attributes' in product and not isinstance(product['attributes'], dict):
                return False

            return True

        except Exception:
            return False

    def reload(self) -> bool:
        """
        重新加载商品数据

        Returns:
            加载成功返回True，失败返回False
        """
        try:
            old_count = len(self.products)
            self._load_products()
            new_count = len(self.products)

            logger.info(f"商品知识库重新加载，商品数量: {old_count} -> {new_count}")
            return True

        except Exception as e:
            logger.error(f"重新加载商品知识库失败: {e}")
            return False

# 全局知识库实例
knowledge_base = ProductKnowledgeBase()