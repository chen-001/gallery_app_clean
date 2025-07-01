// 登录页面JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initLoginForm();
});

// 初始化登录表单
function initLoginForm() {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // 自动聚焦到用户名输入框
    if (usernameInput) {
        usernameInput.focus();
    }
    
    // 监听回车键
    document.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && loginForm) {
            e.preventDefault();
            loginForm.dispatchEvent(new Event('submit'));
        }
    });
}

// 处理登录表单提交
async function handleLogin(e) {
    e.preventDefault();
    
    const btn = document.getElementById('loginBtn');
    const messageDiv = document.getElementById('message');
    const username = document.getElementById('username').value.trim();
    const nextUrl = document.querySelector('input[name="next"]').value;
    
    if (!username) {
        showLoginMessage('请输入用户名', 'error');
        return;
    }
    
    // 显示加载状态
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 验证中...';
    
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('next', nextUrl);
        
        const response = await fetch('/gallery/login', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showLoginMessage('登录成功，正在跳转...', 'success');
            
            // 延迟跳转，让用户看到成功消息
            setTimeout(() => {
                if (result.redirect_url) {
                    window.location.href = result.redirect_url;
                } else {
                    window.location.href = nextUrl || '/gallery';
                }
            }, 1000);
        } else {
            showLoginMessage(result.message || '登录失败，请检查用户名', 'error');
            
            // 重置表单
            document.getElementById('username').value = '';
            document.getElementById('username').focus();
        }
    } catch (error) {
        console.error('登录请求失败:', error);
        showLoginMessage('网络错误，请稍后重试', 'error');
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> 登录';
    }
}

// 显示登录消息
function showLoginMessage(message, type) {
    const messageDiv = document.getElementById('message');
    if (!messageDiv) return;
    
    messageDiv.className = `message ${type}-message`;
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    
    // 自动隐藏消息（除了成功消息）
    if (type !== 'success') {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

// 清除登出状态
async function clearLogoutStatus() {
    const btn = document.querySelector('.enable-auto-login-btn');
    if (!btn) return;
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/gallery/clear_logout_status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 隐藏手动登出信息
            const logoutInfo = document.querySelector('.manual-logout-info');
            if (logoutInfo) {
                logoutInfo.style.display = 'none';
            }
            
            showLoginMessage('登出状态已清除', 'success');
        } else {
            showLoginMessage('操作失败，请刷新页面重试', 'error');
        }
    } catch (error) {
        console.error('清除登出状态失败:', error);
        showLoginMessage('网络错误，请稍后重试', 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// 导出到全局作用域
window.clearLogoutStatus = clearLogoutStatus;