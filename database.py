"""
SQLite数据库模块
处理对话记录的存储和查询
包含完整的异常处理
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import json

from config import DATABASE_PATH, MAX_HISTORY_PER_USER

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatDatabase:
    """聊天数据库操作类"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认为config中的DATABASE_PATH
        """
        self.db_path = db_path or str(DATABASE_PATH)
        self._init_database()

    def _init_database(self) -> None:
        """初始化数据库表结构"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 创建对话记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT  -- 存储额外信息，如商品ID、API调用状态等
                )
            """)

            # 创建索引以提高查询性能
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON chat_history (user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_history (timestamp)")

            conn.commit()
            conn.close()
            logger.info(f"数据库初始化成功，路径: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            sqlite3.Connection对象

        Raises:
            sqlite3.Error: 数据库连接失败
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 返回字典格式的结果
            return conn
        except sqlite3.Error as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def save_conversation(self, user_id: str, user_message: str, bot_response: str,
                         metadata: Dict[str, Any] = None) -> bool:
        """
        保存对话记录到数据库

        Args:
            user_id: 用户标识
            user_message: 用户消息
            bot_response: 机器人回复
            metadata: 额外元数据

        Returns:
            保存成功返回True，失败返回False
        """
        if not user_id or not user_message or not bot_response:
            logger.warning("保存对话记录失败：参数不能为空")
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 限制每个用户的对话记录数量
            cursor.execute(
                "SELECT COUNT(*) FROM chat_history WHERE user_id = ?",
                (user_id,)
            )
            count = cursor.fetchone()[0]

            if count >= MAX_HISTORY_PER_USER:
                # 删除最旧的记录
                cursor.execute("""
                    DELETE FROM chat_history
                    WHERE id IN (
                        SELECT id FROM chat_history
                        WHERE user_id = ?
                        ORDER BY timestamp ASC
                        LIMIT ?
                    )
                """, (user_id, count - MAX_HISTORY_PER_USER + 1))

            # 插入新记录
            metadata_json = json.dumps(metadata) if metadata else None
            cursor.execute("""
                INSERT INTO chat_history (user_id, user_message, bot_response, metadata)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_message, bot_response, metadata_json))

            conn.commit()
            conn.close()
            logger.info(f"对话记录保存成功，用户: {user_id}")
            return True

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"保存对话记录失败: {e}")
            return False

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户的对话历史

        Args:
            user_id: 用户标识
            limit: 返回的最大记录数

        Returns:
            对话历史列表，按时间倒序排列
        """
        if not user_id:
            logger.warning("获取对话历史失败：user_id不能为空")
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, user_id, user_message, bot_response, timestamp, metadata
                FROM chat_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))

            rows = cursor.fetchall()
            conn.close()

            # 转换为字典列表
            history = []
            for row in rows:
                record = dict(row)
                # 解析metadata JSON
                if record['metadata']:
                    try:
                        record['metadata'] = json.loads(record['metadata'])
                    except json.JSONDecodeError:
                        record['metadata'] = {}
                else:
                    record['metadata'] = {}
                history.append(record)

            logger.info(f"获取到 {len(history)} 条对话历史，用户: {user_id}")
            return history

        except sqlite3.Error as e:
            logger.error(f"获取对话历史失败: {e}")
            return []

    def clear_user_history(self, user_id: str) -> bool:
        """
        清空指定用户的对话历史

        Args:
            user_id: 用户标识

        Returns:
            清空成功返回True，失败返回False
        """
        if not user_id:
            logger.warning("清空对话历史失败：user_id不能为空")
            return False

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()

            logger.info(f"已清空用户对话历史，用户: {user_id}")
            return True

        except sqlite3.Error as e:
            logger.error(f"清空对话历史失败: {e}")
            return False

    def get_all_users(self) -> List[str]:
        """
        获取所有有对话记录的用户ID列表

        Returns:
            用户ID列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT user_id FROM chat_history")
            rows = cursor.fetchall()
            conn.close()

            users = [row[0] for row in rows]
            logger.info(f"获取到 {len(users)} 个用户")
            return users

        except sqlite3.Error as e:
            logger.error(f"获取用户列表失败: {e}")
            return []

# 全局数据库实例
db = ChatDatabase()