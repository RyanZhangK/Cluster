console.log('开始监听DOMContentLoaded事件');
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded事件触发');
    
    // 检查按钮元素是否存在
    const saveBtn = document.getElementById('save-config');
    const resetBtn = document.getElementById('reset-config');
    console.log('检查按钮元素:', {
        saveConfigBtn: saveBtn ? '存在' : '不存在',
        resetConfigBtn: resetBtn ? '存在' : '不存在'
    });

    // 初始化页面
    initPage();
    
    // 设置页面切换事件
    setupTabSwitching();
    
    // 设置按钮事件
    setupButtonEvents();
    
    // 启动系统状态监控
    startSystemMonitoring();
    
    // 加载初始数据
    loadInitialData();

    console.log('初始化完成');
});

function initPage() {
    // 设置最后更新时间
    document.getElementById('last-update').textContent = new Date().toISOString().split('T')[0];
}

function setupTabSwitching() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            // 移除所有active类
            document.querySelectorAll('.nav-link').forEach(el => {
                el.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(el => {
                el.classList.remove('active');
            });
            
            // 添加active类到当前点击的元素和对应内容
            this.classList.add('active');
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
            
            // 如果是日志页，加载日志文件列表
            if (tabId === 'logs') {
                loadLogFiles();
            }
        });
    });
}

function startSystemMonitoring() {
    // 每5秒更新一次系统状态
    setInterval(updateSystemStats, 5000);
    updateSystemStats();
}

function updateSystemStats() {
    fetch('/api/system_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('network-status').textContent = data.network.status;
            document.getElementById('network-dbm').textContent = `(${data.network.dBm}dBm)`;
            document.getElementById('cpu-usage').textContent = data.cpu_usage;
            document.getElementById('memory-usage').textContent = data.memory_usage;
        })
        .catch(error => {
            console.error('获取系统状态失败:', error);
        });
}

function loadInitialData() {
    // 加载节点状态
    updateNodesStatus();
    
    // 加载游戏配置
    fetch('/api/node_status')
        .then(response => response.json())
        .then(data => {
            const gameMode = document.getElementById('info-game-mode');
            const gameState = document.getElementById('info-game-state');
            const teamCount = document.getElementById('info-team-count');
            
            if (data.length > 0) {
                gameMode.textContent = data[0].game_mode || '未设置';
                gameState.textContent = data[0].game_state || '未知';
                teamCount.textContent = data[0].team_count || '0';
            }
        });
}

function updateNodesStatus() {
    fetch('/api/node_status')
        .then(response => response.json())
        .then(data => {
            const nodesGrid = document.getElementById('nodes-grid');
            nodesGrid.innerHTML = '';
            
            data.forEach(node => {
                const nodeCard = document.createElement('div');
                nodeCard.className = 'node-card';
                nodeCard.innerHTML = `
                    <div class="node-header">
                        <span class="node-id">${node.node_id}</span>
                        <span class="node-status-indicator ${node.online_status ? 'online' : 'offline'}"></span>
                    </div>
                    <div class="node-details">
                        <div class="node-property">
                            <span class="property-label">状态:</span>
                            <span class="property-value">${node.online_status ? '在线' : '离线'}</span>
                        </div>
                        <div class="node-property">
                            <span class="property-label">激活队伍:</span>
                            <span class="property-value">${node.active_status || '无'}</span>
                        </div>
                        <div class="node-property">
                            <span class="property-label">最后更新:</span>
                            <span class="property-value">${node.last_update || '未知'}</span>
                        </div>
                    </div>
                `;
                nodesGrid.appendChild(nodeCard);
            });
        })
        .catch(error => {
            console.error('获取节点状态失败:', error);
            document.getElementById('nodes-grid').innerHTML = 
                '<div class="error-message">加载节点数据失败，请刷新页面重试</div>';
        });
}

function loadLogFiles() {
    fetch('/api/log_files')
        .then(response => response.json())
        .then(files => {
            const logFilesList = document.getElementById('log-files');
            logFilesList.innerHTML = '';
            
            if (files.length === 0) {
                logFilesList.innerHTML = '<li>没有找到日志文件</li>';
                return;
            }
            
            files.forEach(file => {
                const li = document.createElement('li');
                li.textContent = file;
                li.style.cursor = 'pointer';
                li.addEventListener('click', () => loadLogContent(file));
                logFilesList.appendChild(li);
            });
        })
        .catch(error => {
            console.error('获取日志文件列表失败:', error);
            document.getElementById('log-files').innerHTML = 
                '<li>加载日志文件列表失败</li>';
        });
}

function loadLogContent(filename) {
    document.getElementById('current-log-file').textContent = filename;
    document.getElementById('log-content').textContent = '加载中...';
    
    fetch(`/api/log_content?file=${encodeURIComponent(filename)}`)
        .then(response => response.text())
        .then(content => {
            document.getElementById('log-content').textContent = content;
        })
        .catch(error => {
            console.error('获取日志内容失败:', error);
            document.getElementById('log-content').textContent = 
                '加载日志内容失败，请重试';
        });
}

function setupButtonEvents() {
    console.log('初始化游戏配置页交互');
    
    // 启用表单元素
    document.getElementById('config-team-count').disabled = false;
    document.getElementById('config-game-mode').disabled = false;
    document.getElementById('save-config').disabled = false;
    document.getElementById('reset-config').disabled = false;

    // 绑定保存配置按钮事件
    document.getElementById('save-config').addEventListener('click', function() {
        console.log('保存配置按钮被点击');
        const teamCount = document.getElementById('config-team-count').value;
        const gameMode = document.getElementById('config-game-mode').value;
        
        if (confirm('确定要保存当前游戏配置吗？')) {
            fetch('/api/update_config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    team_count: teamCount,
                    game_mode: gameMode,
                    game_state: 'unstart'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('游戏配置保存成功');
                    updateNodesStatus();
                } else {
                    alert('保存失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                console.error('保存游戏配置失败:', error);
                alert('保存游戏配置时发生错误');
            });
        }
    });

    // 绑定重置配置按钮事件
    document.getElementById('reset-config').addEventListener('click', function() {
        if (confirm('确定要重置游戏配置为默认值吗？')) {
            fetch('/api/reset_config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('游戏配置已重置');
                    updateNodesStatus();
                } else {
                    alert('重置失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                console.error('重置游戏配置失败:', error);
                alert('重置游戏配置时发生错误');
            });
        }
    });
}
