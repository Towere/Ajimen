"""
FastAPI主应用
电商智能客服的REST API接口
包含完整的API文档、异常处理和输入验证
"""

import logging
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from chat_service import chat_service
from knowledge_base import knowledge_base
from database import db
from qianwen_api import qianwen_client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="电商智能客服API",
    description="基于通义千问API和商品知识库的智能客服系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件（允许所有来源，仅用于开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加静态文件服务（用于提供Web界面）
app.mount("/static", StaticFiles(directory="."), name="static")

# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "服务器内部错误",
            "detail": str(exc)[:100]
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

# 健康检查端点
@app.get("/", tags=["健康检查"])
async def root():
    """根端点，返回服务状态"""
    return {
        "service": "电商智能客服API",
        "status": "运行正常",
        "version": "1.0.0",
        "endpoints": {
            "健康检查": "/health",
            "对话接口": "/api/chat",
            "对话历史": "/api/history/{user_id}",
            "商品搜索": "/api/products/search",
            "商品详情": "/api/products/{product_id}",
            "商品分类": "/api/products/categories",
            "系统状态": "/api/system/status"
        }
    }

@app.get("/ui", tags=["Web界面"], response_class=HTMLResponse)
async def chat_ui():
    """聊天Web界面"""
    try:
        # 检查index.html文件是否存在
        if os.path.exists("index.html"):
            with open("index.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            # 如果index.html不存在，返回一个简单的界面
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>电商智能客服</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .container { max-width: 800px; margin: 0 auto; }
                    .card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; }
                    a { color: #007bff; text-decoration: none; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>电商智能客服系统</h1>
                    <div class="card">
                        <h2>可用界面</h2>
                        <p><a href="/docs">API文档 (Swagger UI)</a> - 交互式API测试界面</p>
                        <p><a href="/redoc">API文档 (ReDoc)</a> - 更友好的API文档界面</p>
                        <p><a href="/static/index.html">聊天界面</a> - 与智能客服对话</p>
                    </div>
                    <div class="card">
                        <h2>API端点</h2>
                        <ul>
                            <li><code>/api/chat</code> - 对话接口</li>
                            <li><code>/api/history/{user_id}</code> - 对话历史</li>
                            <li><code>/api/products/search</code> - 商品搜索</li>
                            <li><code>/api/products/{product_id}</code> - 商品详情</li>
                            <li><code>/health</code> - 健康检查</li>
                        </ul>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"加载UI界面失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加载界面失败: {str(e)[:50]}"
        )

@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查端点"""
    try:
        # 检查数据库连接
        db_ok = len(db.get_all_users()) >= 0  # 简单查询，不关心结果

        # 检查商品知识库
        kb_ok = len(knowledge_base.products) >= 0

        # 检查API连接（可选，因为需要网络）
        api_ok = True  # 默认True，避免健康检查依赖外部API
        # api_ok = qianwen_client.test_connection()  # 取消注释以启用API检查

        overall_status = db_ok and kb_ok and api_ok

        return {
            "success": True,
            "status": "healthy" if overall_status else "degraded",
            "components": {
                "database": "healthy" if db_ok else "unhealthy",
                "knowledge_base": "healthy" if kb_ok else "unhealthy",
                "qianwen_api": "healthy" if api_ok else "unhealthy"
            }
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e)[:100]
            }
        )

# 对话相关端点
@app.post("/api/chat", tags=["对话"])
async def chat(
    user_id: str = Query(..., description="用户标识，用于区分不同用户"),
    message: str = Query(..., description="用户消息内容", min_length=1, max_length=1000)
):
    """
    处理用户消息并返回智能回复

    - **user_id**: 用户唯一标识（如：user_123）
    - **message**: 用户发送的消息内容

    返回包含AI回复和相关元数据的JSON响应
    """
    # 输入验证已在Query参数中完成，这里做额外检查
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户ID不能为空"
        )

    if not message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="消息内容不能为空"
        )

    try:
        logger.info(f"收到聊天请求，用户: {user_id}, 消息: {message[:50]}...")

        # 调用聊天服务处理消息
        result = chat_service.process_message(user_id, message)

        if result.get("success"):
            return {
                "success": True,
                "data": {
                    "response": result["response"],
                    "user_id": result["user_id"],
                    "metadata": result.get("metadata", {}),
                    "product_suggestions": result.get("product_suggestions", [])
                }
            }
        else:
            # 聊天服务返回错误
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "聊天服务处理失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天接口处理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)[:50]}"
        )

@app.get("/api/history/{user_id}", tags=["对话"])
async def get_chat_history(
    user_id: str,
    limit: int = Query(10, ge=1, le=100, description="返回的最大记录数")
):
    """
    获取指定用户的对话历史

    - **user_id**: 用户标识
    - **limit**: 返回的记录数量限制（1-100）
    """
    try:
        if not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户ID不能为空"
            )

        history = chat_service.get_user_history(user_id, limit)

        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "history": history,
                "count": len(history)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史记录失败: {str(e)[:50]}"
        )

@app.delete("/api/history/{user_id}", tags=["对话"])
async def clear_chat_history(user_id: str):
    """
    清空指定用户的对话历史

    - **user_id**: 用户标识
    """
    try:
        if not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户ID不能为空"
            )

        success = chat_service.clear_user_history(user_id)

        if success:
            return {
                "success": True,
                "message": f"用户 {user_id} 的对话历史已清空"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="清空对话历史失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清空对话历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空历史记录失败: {str(e)[:50]}"
        )

# 商品相关端点
@app.get("/api/products/search", tags=["商品"])
async def search_products(
    keyword: str = Query(..., description="搜索关键词", min_length=1),
    category: str = Query(None, description="商品分类过滤"),
    max_price: float = Query(None, ge=0, description="最高价格"),
    min_price: float = Query(None, ge=0, description="最低价格"),
    limit: int = Query(10, ge=1, le=50, description="返回的最大商品数量")
):
    """
    搜索商品

    - **keyword**: 搜索关键词
    - **category**: 商品分类（可选）
    - **max_price**: 最高价格（可选）
    - **min_price**: 最低价格（可选）
    - **limit**: 返回的商品数量限制（1-50）
    """
    try:
        if not keyword.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="搜索关键词不能为空"
            )

        products = knowledge_base.search_products(
            keyword=keyword,
            category=category,
            max_price=max_price,
            min_price=min_price,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "keyword": keyword,
                "category": category,
                "price_range": {
                    "min": min_price,
                    "max": max_price
                },
                "products": products,
                "count": len(products)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"商品搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"商品搜索失败: {str(e)[:50]}"
        )

@app.get("/api/products/{product_id}", tags=["商品"])
async def get_product_detail(product_id: str):
    """
    根据商品ID获取商品详情

    - **product_id**: 商品ID
    """
    try:
        if not product_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商品ID不能为空"
            )

        product = knowledge_base.get_product_by_id(product_id)

        if product:
            return {
                "success": True,
                "data": product
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到商品ID: {product_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取商品详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取商品详情失败: {str(e)[:50]}"
        )

@app.get("/api/products/categories", tags=["商品"])
async def get_product_categories():
    """获取所有商品分类"""
    try:
        categories = knowledge_base.get_categories()

        return {
            "success": True,
            "data": {
                "categories": categories,
                "count": len(categories)
            }
        }

    except Exception as e:
        logger.error(f"获取商品分类失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取商品分类失败: {str(e)[:50]}"
        )

# 系统管理端点
@app.get("/api/system/status", tags=["系统管理"])
async def system_status():
    """获取系统状态信息"""
    try:
        # 数据库状态
        db_users = db.get_all_users()
        db_conversations = sum(len(db.get_conversation_history(user)) for user in db_users)

        # 知识库状态
        kb_products = len(knowledge_base.products)
        kb_categories = len(knowledge_base.get_categories())

        # API状态
        api_status = "未测试"
        # 可选：实际测试API连接
        # api_status = "正常" if qianwen_client.test_connection() else "异常"

        return {
            "success": True,
            "data": {
                "database": {
                    "path": "chat_history.db",
                    "user_count": len(db_users),
                    "conversation_count": db_conversations,
                    "status": "正常"
                },
                "knowledge_base": {
                    "path": "products.json",
                    "product_count": kb_products,
                    "category_count": kb_categories,
                    "status": "正常" if kb_products > 0 else "空"
                },
                "qianwen_api": {
                    "status": api_status,
                    "configured": qianwen_client.api_key != "your-api-key-here"
                }
            }
        }

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)[:50]}"
        )

if __name__ == "__main__":
    """主程序入口"""
    logger.info("启动电商智能客服API服务...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发环境启用热重载
        log_level="info"
    )