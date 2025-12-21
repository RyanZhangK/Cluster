// 页面切换功能
document.addEventListener('DOMContentLoaded', function() {
    // 获取所有导航链接和内容标签
    const navLinks = document.querySelectorAll('.nav-link');
    const tabContents = document.querySelectorAll('.tab-content');

    // 初始化页面
    initTabs();

    // 绑定导航点击事件
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            // 移除所有活动状态
            navLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(tab => tab.classList.remove('active'));

            // 设置当前活动状态
            this.classList.add('active');
            const tabId = this.dataset.tab + '-tab';
            document.getElementById(tabId).classList.add('active');

            // 加载对应页面数据
            loadTabData(this.dataset.tab);
        });
    });

    // 默认加载状态预览页
    loadTabData('status');
});

// 初始化标签页状态
function initTabs() {
    const activeTab = document.querySelector('.nav-link.active');
    if (activeTab) {
        const tabId = activeTab.dataset.tab + '-tab';
        document.getElementById(tabId).classList.add('active');
    }
}

// 节点状态管理
class NodeManager {
    static createNodeBox(nodeId) {
        const box = document.createElement('div');
        box.className = 'node-box';
        box.id = `node-${nodeId}`;
        box.innerHTML = `
            <h3>${nodeId}</h3>
            <div class="node-status">
                <span class="status-label">在线状态:</span>
                <span class="online-status">加载中...</span>
            </div>
            <div class="node-status">
                <span class="status-label">激活状态:</span>
                <span class="active-status">加载中...</span>
            </div>
            <div class="node-status">
                <span class="status-label">最后更新:</span>
                <span class="last-update">加载中...</span>
            </div>
        `;
        return box;
    }

    static updateNodeBox(box, node) {
        box.querySelector('.online-status').textContent = 
            node.online_status ? '在线' : '离线';
        box.querySelector('.active-status').textContent = 
            node.active_status ? '激活' : '未激活';
        box.querySelector('.last-update').textContent = 
            new Date(node.last_update).toLocaleString();
        box.className = `node-box ${node.online_status ? 'online' : 'offline'}`;
    }
}

// 加载标签页数据
function loadTabData(tabName) {
    const tabContent = document.getElementById(`${tabName}-tab`);
    const loadingIndicator = tabContent.querySelector('.loading-indicator');
    loadingIndicator.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text">正在加载节点状态...</div>
    `;

    if (tabName === 'status') {
        const nodesContainer = document.createElement('div');
        nodesContainer.className = 'nodes-container';
        const nodeBoxes = {};
        
        // 初始化所有节点
        [
            { prefix: 'STA', count: 4 },
            { prefix: 'DET', count: 6 }
        ].forEach(type => {
            for (let i = 1; i <= type.count; i++) {
                const nodeId = `${type.prefix}${i.toString().padStart(2, '0')}`;
                const nodeBox = NodeManager.createNodeBox(nodeId);
                nodesContainer.appendChild(nodeBox);
                nodeBoxes[nodeId] = nodeBox;
            }
        });

        // 替换加载指示器
        loadingIndicator.replaceWith(nodesContainer);

        // 更新节点状态
        function updateNodeStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.data?.nodes) {
                        data.data.nodes.forEach(node => {
                            const box = nodeBoxes[node.node_id];
                            if (box) NodeManager.updateNodeBox(box, node);
                        });
                    }
                })
                .catch(error => {
                    console.error('获取节点状态失败:', error);
                    const errorElement = document.createElement('div');
                    errorElement.className = 'error-message';
                    errorElement.innerHTML = `
                        <div class="error-icon">⚠️</div>
                        <div>加载节点状态失败，请稍后重试</div>
                    `;
                    nodesContainer.replaceWith(errorElement);
                });
        }

        // 立即更新并启动定时刷新
        updateNodeStatus();
        if (window.statusRefreshInterval) {
            clearInterval(window.statusRefreshInterval);
        }
        window.statusRefreshInterval = setInterval(updateNodeStatus, 5000);
    } else {
        // 其他页面处理
        if (window.statusRefreshInterval) {
            clearInterval(window.statusRefreshInterval);
            window.statusRefreshInterval = null;
        }
        setTimeout(() => {
            if (tabName === 'config') {
                // 初始化配置表单
                const configForm = document.createElement('div');
                configForm.className = 'config-form';
                configForm.innerHTML = `
                    <h3>游戏配置</h3>
                    <div class="loading-indicator">加载配置中...</div>
                `;
                loadingIndicator.replaceWith(configForm);
                loadGameConfig(configForm);
            } else {
                loadingIndicator.textContent = `这是${getTabTitle(tabName)}页面内容`;
            }
        }, 500);
    }
}

// 加载游戏配置
function loadGameConfig(container) {
    const loadingIndicator = container.querySelector('.loading-indicator');
    loadingIndicator.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text">正在加载游戏配置...</div>
    `;

    fetch('/api/config')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) {
                throw new Error('无效的响应数据');
            }
            
            if (data.success) {
                if (Array.isArray(data.data) && data.data.length > 0) {
                    const config = data.data[0];
                    container.innerHTML = `
                        <h3>游戏配置</h3>
                        <form id="game-config-form">
                            <div class="config-item">
                                <label for="team-count">队伍数量:</label>
                                <select id="team-count" name="team_count">
                                    <option value="2" ${config.team_count == 2 ? 'selected' : ''}>2队</option>
                                    <option value="3" ${config.team_count == 3 ? 'selected' : ''}>3队</option>
                                    <option value="4" ${config.team_count == 4 ? 'selected' : ''}>4队</option>
                                </select>
                            </div>
                            <div class="config-item">
                                <label for="game-mode">游戏模式:</label>
                                <select id="game-mode" name="game_mode">
                                    <option value="conquer" ${config.game_mode === 'conquer' ? 'selected' : ''}>征服模式</option>
                                    <option value="defense" ${config.game_mode === 'defense' ? 'selected' : ''}>防守模式</option>
                                    <option value="race" ${config.game_mode === 'race' ? 'selected' : ''}>竞速模式</option>
                                </select>
                            </div>
                            <div class="config-item">
                                <label for="game-state">游戏状态:</label>
                                <select id="game-state" name="game_state">
                                    <option value="unstart" ${config.game_state === 'unstart' ? 'selected' : ''}>未开始</option>
                                    <option value="running" ${config.game_state === 'running' ? 'selected' : ''}>进行中</option>
                                    <option value="paused" ${config.game_state === 'paused' ? 'selected' : ''}>已暂停</option>
                                    <option value="finished" ${config.game_state === 'finished' ? 'selected' : ''}>已结束</option>
                                </select>
                            </div>
                            <button type="submit" class="save-btn">保存配置</button>
                        </form>
                    `;

                    // 添加表单提交事件
                    document.getElementById('game-config-form').addEventListener('submit', function(e) {
                        e.preventDefault();
                        if (confirm('确定要更新游戏配置吗？')) {
                            saveGameConfig(this);
                        }
                    });
                } else {
                    throw new Error('配置数据为空');
                }
            } else {
                throw new Error(data.error || '未知错误');
            }
        })
        .catch(error => {
            console.error('获取配置失败:', error);
            container.innerHTML = `
                <div class="error-message">
                    <div class="error-icon">⚠️</div>
                    <div>加载配置失败: ${error.message}</div>
                    <button class="retry-btn" onclick="loadTabData('config')">重试</button>
                </div>
            `;
        });
}

// 保存游戏配置
function saveGameConfig(form) {
    const formData = {
        team_count: parseInt(form.team_count.value),
        game_mode: form.game_mode.value,
        game_state: form.game_state.value,
        id: 1  // 假设只有一个配置记录
    };

    const saveBtn = form.querySelector('.save-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = '保存中...';

    fetch('/api/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('配置保存成功');
            // 重新加载配置
            loadGameConfig(form.parentElement);
        } else {
            alert(`保存失败: ${data.error || '未知错误'}`);
            saveBtn.disabled = false;
            saveBtn.textContent = '保存配置';
        }
    })
    .catch(error => {
        console.error('保存配置失败:', error);
        alert('保存配置失败，请稍后重试');
        saveBtn.disabled = false;
        saveBtn.textContent = '保存配置';
    });
}

// 获取标签页标题
function getTabTitle(tabName) {
    const titles = {
        'status': '状态预览',
        'config': '系统配置',
        'logs': '系统日志'
    };
    return titles[tabName] || tabName;
}

// 添加CSS样式
const style = document.createElement('style');
style.textContent = `
.nodes-container {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    padding: 20px;
    animation: fadeIn 0.5s ease forwards;
}

.node-box {
    border: 1px solid #444;
    border-radius: 8px;
    padding: 15px;
    background-color: #2d2d2d;
    color: #eee;
    transition: all 0.3s ease;
}

.node-box.online {
    border-left: 4px solid #4CAF50;
    box-shadow: 0 0 10px rgba(76, 175, 80, 0.3);
}

.node-box.offline {
    border-left: 4px solid #F44336;
    opacity: 0.7;
}

.node-box h3 {
    margin-top: 0;
    color: #fff;
}

.node-status {
    margin: 8px 0;
    display: flex;
    justify-content: space-between;
}

.status-label {
    font-weight: bold;
    color: #aaa;
}

.loading-spinner {
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-radius: 50%;
    border-top: 4px solid #3498db;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto 10px;
}

.loading-text {
    color: #777;
    text-align: center;
    font-size: 14px;
}

.error-message {
    padding: 20px;
    color: #e74c3c;
    text-align: center;
    background: rgba(231, 76, 60, 0.1);
    border-radius: 8px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
`;
document.head.appendChild(style);

// API请求函数
async function fetchData(endpoint, data = {}) {
    try {
        const response = await fetch(`/api/${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (error) {
        console.error('API请求失败:', error);
        return { success: false, error: '网络请求失败' };
    }
}
