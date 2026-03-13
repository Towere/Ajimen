/**
 * 电商智能客服 - 前端聊天逻辑
 */

// API基础URL
const API_BASE_URL = 'http://localhost:8000';
// 当前用户ID
let currentUserId = 'user_001';
// 是否正在等待回复
let isWaitingForResponse = false;

// DOM元素
const elements = {
    userIdInput: document.getElementById('userId'),
    refreshUserBtn: document.getElementById('refreshUser'),
    clearHistoryBtn: document.getElementById('clearHistory'),
    messageInput: document.getElementById('messageInput'),
    sendButton: document.getElementById('sendButton'),
    chatMessages: document.getElementById('chatMessages'),
    productSuggestions: document.getElementById('productSuggestions'),
    productsContainer: document.getElementById('productsContainer'),
    apiStatus: document.getElementById('apiStatus'),
    productCount: document.getElementById('productCount'),
    conversationCount: document.getElementById('conversationCount'),
    typingIndicator: document.getElementById('typingIndicator'),
    serviceStatus: document.getElementById('serviceStatus')
};

// 模板
const templates = {
    userMessage: document.getElementById('userMessageTemplate'),
    botMessage: document.getElementById('botMessageTemplate'),
    productCard: document.getElementById('productCardTemplate')
};

/**
 * 初始化应用
 */
function init() {
    // 加载对话历史
    loadConversationHistory();

    // 检查系统状态
    checkSystemStatus();

    // 设置事件监听器
    setupEventListeners();

    // 设置用户ID
    updateUserId();
}

/**
 * 设置事件监听器
 */
function setupEventListeners() {
    // 发送消息
    elements.sendButton.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 用户ID相关
    elements.userIdInput.addEventListener('change', updateUserId);
    elements.refreshUserBtn.addEventListener('click', generateNewUserId);
    elements.clearHistoryBtn.addEventListener('click', clearConversationHistory);

    // 快速查询按钮
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.getAttribute('data-query');
            elements.messageInput.value = query;
            sendMessage();
        });
    });

    // 监听窗口大小变化，调整滚动
    window.addEventListener('resize', scrollToBottom);
}

/**
 * 更新用户ID
 */
function updateUserId() {
    const newUserId = elements.userIdInput.value.trim();
    if (newUserId && newUserId !== currentUserId) {
        currentUserId = newUserId;
        // 重新加载历史记录
        loadConversationHistory();
        showNotification(`已切换到用户: ${currentUserId}`, 'info');
    }
}

/**
 * 生成新的随机用户ID
 */
function generateNewUserId() {
    const randomNum = Math.floor(Math.random() * 10000);
    const newUserId = `user_${randomNum.toString().padStart(4, '0')}`;
    elements.userIdInput.value = newUserId;
    updateUserId();
}

/**
 * 发送消息
 */
async function sendMessage() {
    const message = elements.messageInput.value.trim();

    // 验证输入
    if (!message) {
        showNotification('请输入消息内容', 'warning');
        return;
    }

    if (isWaitingForResponse) {
        showNotification('请等待当前回复完成', 'warning');
        return;
    }

    // 显示用户消息
    addUserMessage(message);

    // 清空输入框
    elements.messageInput.value = '';

    // 显示"正在输入"指示器
    showTypingIndicator(true);
    isWaitingForResponse = true;

    try {
        // 调用API
        const response = await fetchChatResponse(message);

        // 处理响应
        if (response.success) {
            // 添加AI回复
            addBotMessage(response.data.response, response.data.metadata);

            // 显示商品建议
            if (response.data.product_suggestions && response.data.product_suggestions.length > 0) {
                displayProductSuggestions(response.data.product_suggestions);
            } else {
                clearProductSuggestions();
            }

            // 更新对话计数
            updateConversationCount();
        } else {
            // API错误
            addBotMessage(`抱歉，处理您的请求时出现错误: ${response.error || '未知错误'}`, {
                api_success: false,
                is_fallback: true
            });
            showNotification('API调用失败，已启用降级方案', 'error');
        }
    } catch (error) {
        // 网络错误
        console.error('发送消息失败:', error);
        addBotMessage('网络连接错误，请检查服务是否正常运行。', {
            api_success: false,
            is_fallback: true
        });
        showNotification('网络错误，请检查连接', 'error');
    } finally {
        // 隐藏"正在输入"指示器
        showTypingIndicator(false);
        isWaitingForResponse = false;
    }
}

/**
 * 调用聊天API
 */
async function fetchChatResponse(message) {
    const url = `${API_BASE_URL}/api/chat?user_id=${encodeURIComponent(currentUserId)}&message=${encodeURIComponent(message)}`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Accept': 'application/json'
        }
    });

    if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
    }

    return await response.json();
}

/**
 * 添加用户消息到聊天界面
 */
function addUserMessage(message) {
    const template = templates.userMessage.content.cloneNode(true);
    const messageElement = template.querySelector('.message');
    const messageText = template.querySelector('.message-text');
    const messageTime = template.querySelector('.message-time');

    // 设置消息内容
    messageText.textContent = message;
    messageTime.textContent = getCurrentTime();

    // 添加到聊天区域
    elements.chatMessages.appendChild(messageElement);

    // 滚动到底部
    scrollToBottom();
}

/**
 * 添加AI回复到聊天界面
 */
function addBotMessage(message, metadata = {}) {
    const template = templates.botMessage.content.cloneNode(true);
    const messageElement = template.querySelector('.message');
    const messageText = template.querySelector('.message-text');
    const messageTime = template.querySelector('.message-time');
    const messageMetadata = template.querySelector('.message-metadata');

    // 设置消息内容
    messageText.innerHTML = formatMessageText(message);
    messageTime.textContent = getCurrentTime();

    // 添加元数据（如果可用）
    if (metadata && Object.keys(metadata).length > 0) {
        let metadataText = '';

        if (metadata.intent) {
            metadataText += `意图: ${metadata.intent} | `;
        }

        if (metadata.product_info_used) {
            metadataText += `参考商品: ${metadata.product_count || 0}个 | `;
        }

        if (metadata.api_success !== undefined) {
            metadataText += `API: ${metadata.api_success ? '成功' : '失败'} | `;
        }

        if (metadata.is_fallback) {
            metadataText += '降级方案';
        }

        if (metadataText) {
            messageMetadata.textContent = metadataText.replace(/\| $/, '');
        }
    }

    // 添加到聊天区域
    elements.chatMessages.appendChild(messageElement);

    // 滚动到底部
    scrollToBottom();
}

/**
 * 格式化消息文本（处理换行和链接）
 */
function formatMessageText(text) {
    // 将换行符转换为<br>
    let formatted = text.replace(/\n/g, '<br>');

    // 高亮显示价格（如：6999元）
    formatted = formatted.replace(/(\d+(?:\.\d+)?)\s*元/g, '<span class="price-highlight">$1元</span>');

    // 高亮显示商品名称（简单的规则）
    const productKeywords = ['华为', 'iPhone', '小米', '联想', '戴尔', '索尼', '苹果', '佳能', '大疆', '九阳'];
    productKeywords.forEach(keyword => {
        const regex = new RegExp(`(${keyword}[^\\s<>{}\\[\\]()]*?)`, 'gi');
        formatted = formatted.replace(regex, '<span class="product-highlight">$1</span>');
    });

    return formatted;
}

/**
 * 加载对话历史
 */
async function loadConversationHistory() {
    try {
        const url = `${API_BASE_URL}/api/history/${encodeURIComponent(currentUserId)}?limit=20`;
        const response = await fetch(url);

        if (!response.ok) {
            // 可能是新用户，没有历史记录
            return;
        }

        const data = await response.json();

        if (data.success && data.data.history && data.data.history.length > 0) {
            // 清空当前消息（除了欢迎消息）
            const welcomeMessage = document.querySelector('.message.welcome');
            elements.chatMessages.innerHTML = '';
            if (welcomeMessage) {
                elements.chatMessages.appendChild(welcomeMessage);
            }

            // 按时间正序添加历史消息
            const sortedHistory = [...data.data.history].reverse();

            for (const record of sortedHistory) {
                // 添加用户消息
                addUserMessage(record.user_message);

                // 添加AI回复
                addBotMessage(record.bot_response, record.metadata || {});
            }

            // 更新计数
            updateConversationCount();
        }
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

/**
 * 清空对话历史
 */
async function clearConversationHistory() {
    if (!confirm(`确定要清空用户 ${currentUserId} 的对话历史吗？`)) {
        return;
    }

    try {
        const url = `${API_BASE_URL}/api/history/${encodeURIComponent(currentUserId)}`;
        const response = await fetch(url, { method: 'DELETE' });

        if (response.ok) {
            // 清空聊天界面（保留欢迎消息）
            const welcomeMessage = document.querySelector('.message.welcome');
            elements.chatMessages.innerHTML = '';
            if (welcomeMessage) {
                elements.chatMessages.appendChild(welcomeMessage);
            }

            // 清空商品建议
            clearProductSuggestions();

            // 更新计数
            updateConversationCount();

            showNotification('对话历史已清空', 'success');
        }
    } catch (error) {
        console.error('清空历史记录失败:', error);
        showNotification('清空历史记录失败', 'error');
    }
}

/**
 * 显示商品建议
 */
function displayProductSuggestions(products) {
    // 清空当前商品
    clearProductSuggestions();

    if (!products || products.length === 0) {
        elements.productsContainer.innerHTML = '<div class="empty-products">暂无商品建议</div>';
        return;
    }

    // 添加商品卡片
    products.forEach(product => {
        const template = templates.productCard.content.cloneNode(true);
        const card = template.querySelector('.product-card');
        const name = template.querySelector('.product-name');
        const price = template.querySelector('.product-price');
        const description = template.querySelector('.product-description');
        const category = template.querySelector('.product-category');
        const stock = template.querySelector('.product-stock');
        const queryBtn = template.querySelector('[data-action="query"]');

        // 设置商品信息
        name.textContent = product.name || '未知商品';
        price.textContent = `¥${(product.price || 0).toFixed(2)}`;
        description.textContent = product.description || '暂无描述';
        category.textContent = product.category || '未分类';
        stock.textContent = `库存: ${product.stock || 0}件`;

        // 设置查询按钮
        if (queryBtn) {
            queryBtn.addEventListener('click', () => {
                elements.messageInput.value = `${product.name}多少钱？`;
                elements.messageInput.focus();
            });
        }

        // 添加到容器
        elements.productsContainer.appendChild(card);
    });

    // 显示商品建议区域
    elements.productSuggestions.style.display = 'block';
}

/**
 * 清空商品建议
 */
function clearProductSuggestions() {
    elements.productsContainer.innerHTML = '<div class="empty-products">暂无商品建议，开始对话后这里会显示相关商品</div>';
}

/**
 * 检查系统状态
 */
async function checkSystemStatus() {
    try {
        // 检查健康状态
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();

            // 更新API状态
            if (healthData.success) {
                const apiStatus = healthData.components?.qianwen_api?.status || 'unknown';
                updateApiStatus(apiStatus);

                // 更新服务状态
                elements.serviceStatus.textContent = '运行正常';
                elements.serviceStatus.style.color = '#10b981';
            }
        }

        // 获取系统状态
        const statusResponse = await fetch(`${API_BASE_URL}/api/system/status`);
        if (statusResponse.ok) {
            const statusData = await statusResponse.json();

            if (statusData.success) {
                // 更新商品数量
                const kb = statusData.data.knowledge_base;
                if (kb) {
                    elements.productCount.textContent = kb.product_count || '0';
                }

                // 更新对话记录数量
                const db = statusData.data.database;
                if (db) {
                    elements.conversationCount.textContent = db.conversation_count || '0';
                }
            }
        }
    } catch (error) {
        console.error('检查系统状态失败:', error);
        updateApiStatus('error');
        elements.serviceStatus.textContent = '连接失败';
        elements.serviceStatus.style.color = '#ef4444';
        showNotification('无法连接到服务器', 'error');
    }
}

/**
 * 更新API状态显示
 */
function updateApiStatus(status) {
    const statusElement = elements.apiStatus;
    const icon = statusElement.querySelector('i') || document.createElement('i');

    // 移除所有状态类
    statusElement.classList.remove('status-unknown', 'status-good', 'status-warning', 'status-error');

    switch (status.toLowerCase()) {
        case 'healthy':
            statusElement.textContent = '正常';
            statusElement.classList.add('status-good');
            icon.className = 'fas fa-check-circle';
            break;
        case 'unhealthy':
            statusElement.textContent = '异常';
            statusElement.classList.add('status-error');
            icon.className = 'fas fa-times-circle';
            break;
        case 'degraded':
            statusElement.textContent = '降级';
            statusElement.classList.add('status-warning');
            icon.className = 'fas fa-exclamation-triangle';
            break;
        default:
            statusElement.textContent = '未知';
            statusElement.classList.add('status-unknown');
            icon.className = 'fas fa-question-circle';
    }

    // 更新图标
    if (!statusElement.contains(icon)) {
        statusElement.prepend(icon);
        statusElement.insertAdjacentText('afterbegin', ' ');
    } else {
        icon.className = icon.className.split(' ')[0] + ' ' + icon.className.split(' ')[1];
    }
}

/**
 * 更新对话计数
 */
async function updateConversationCount() {
    try {
        const url = `${API_BASE_URL}/api/history/${encodeURIComponent(currentUserId)}?limit=1`;
        const response = await fetch(url);

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                elements.conversationCount.textContent = data.data.count || '0';
            }
        }
    } catch (error) {
        // 忽略错误
    }
}

/**
 * 显示/隐藏"正在输入"指示器
 */
function showTypingIndicator(show) {
    elements.typingIndicator.style.display = show ? 'block' : 'none';
}

/**
 * 显示通知
 */
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // 添加到页面
    document.body.appendChild(notification);

    // 添加样式（如果不存在）
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 1000;
                animation: slideIn 0.3s ease-out;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                max-width: 300px;
            }
            .notification-info {
                background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            }
            .notification-success {
                background: linear-gradient(135deg, #10b981, #059669);
            }
            .notification-warning {
                background: linear-gradient(135deg, #f59e0b, #d97706);
            }
            .notification-error {
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // 自动消失
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out forwards';

        // 添加消失动画
        if (!document.querySelector('#notification-slide-out')) {
            const slideOutStyle = document.createElement('style');
            slideOutStyle.id = 'notification-slide-out';
            slideOutStyle.textContent = `
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(slideOutStyle);
        }

        // 移除元素
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

/**
 * 获取当前时间字符串
 */
function getCurrentTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
}

/**
 * 滚动到底部
 */
function scrollToBottom() {
    setTimeout(() => {
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }, 100);
}

// 添加CSS样式
const additionalStyles = document.createElement('style');
additionalStyles.textContent = `
    .price-highlight {
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        color: #92400e;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }

    .product-highlight {
        background: linear-gradient(135deg, #dbeafe, #93c5fd);
        color: #1e40af;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }
`;
document.head.appendChild(additionalStyles);

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);