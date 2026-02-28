// 文件夹列表页面JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initFolderList();
});

let currentView = 'grid';
let currentSort = 'date';
let currentOrder = 'desc';

// 初始化文件夹列表
function initFolderList() {
    initSearchFunction();
    initViewToggle();
    initSortFilters();
    initFolderCards();
    initFolderStatus();
    
    // 恢复用户偏好设置
    loadUserPreferences();
}

// 初始化搜索功能
function initSearchFunction() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    // 使用防抖优化搜索性能
    const debouncedSearch = galleryApp.debounce(performSearch, 300);
    
    searchInput.addEventListener('input', function() {
        debouncedSearch(this.value.trim());
    });
    
    // 支持回车键搜索
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch(this.value.trim());
        }
    });
}

// 执行搜索
function performSearch(query) {
    const folderCards = document.querySelectorAll('.folder-card');
    const emptyState = document.getElementById('emptyState');
    let visibleCount = 0;
    
    folderCards.forEach(card => {
        const folderName = card.dataset.name || '';
        const isVisible = query === '' || folderName.includes(query.toLowerCase());
        
        card.style.display = isVisible ? 'flex' : 'none';
        if (isVisible) visibleCount++;
    });
    
    // 显示/隐藏空状态
    if (emptyState) {
        emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
    }
    
    // 更新计数
    updateFolderCount(visibleCount);
}

// 初始化视图切换
function initViewToggle() {
    const viewButtons = document.querySelectorAll('.view-btn');
    const folderGrid = document.getElementById('folderGrid');
    
    viewButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const view = this.dataset.view;
            switchView(view);
        });
    });
}

// 切换视图模式
function switchView(view) {
    currentView = view;
    const folderGrid = document.getElementById('folderGrid');
    const viewButtons = document.querySelectorAll('.view-btn');
    
    // 更新按钮状态
    viewButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // 更新网格类
    if (folderGrid) {
        folderGrid.classList.toggle('list-view', view === 'list');
    }
    
    // 保存用户偏好
    saveUserPreferences();
}

// 初始化排序筛选器
function initSortFilters() {
    const sortSelect = document.getElementById('sortSelect');
    const orderSelect = document.getElementById('orderSelect');
    
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            currentSort = this.value;
            sortFolders();
            saveUserPreferences();
        });
    }
    
    if (orderSelect) {
        orderSelect.addEventListener('change', function() {
            currentOrder = this.value;
            sortFolders();
            saveUserPreferences();
        });
    }
}

// 排序文件夹
function sortFolders() {
    const folderGrid = document.getElementById('folderGrid');
    if (!folderGrid) return;
    
    const folderCards = Array.from(folderGrid.querySelectorAll('.folder-card'));
    
    folderCards.sort((a, b) => {
        let aValue, bValue;
        
        switch (currentSort) {
            case 'name':
                aValue = a.dataset.name || '';
                bValue = b.dataset.name || '';
                break;
            case 'date':
                aValue = new Date(a.dataset.date || 0);
                bValue = new Date(b.dataset.date || 0);
                break;
            case 'size':
                aValue = parseInt(a.dataset.size || 0);
                bValue = parseInt(b.dataset.size || 0);
                break;
            default:
                return 0;
        }
        
        let result;
        if (typeof aValue === 'string') {
            result = aValue.localeCompare(bValue, 'zh-CN');
        } else {
            result = aValue - bValue;
        }
        
        return currentOrder === 'desc' ? -result : result;
    });
    
    // 重新排列DOM元素
    folderCards.forEach(card => {
        folderGrid.appendChild(card);
    });
}

// 初始化文件夹卡片
function initFolderCards() {
    const folderCards = document.querySelectorAll('.folder-card');
    
    folderCards.forEach(card => {
        // 添加点击效果
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
        
        // 添加键盘支持
        const viewButton = card.querySelector('.btn-primary');
        if (viewButton) {
            card.setAttribute('tabindex', '0');
            card.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    viewButton.click();
                }
            });
        }
    });
}

// 更新文件夹计数
function updateFolderCount(count) {
    const folderCountElement = document.getElementById('folderCount');
    if (folderCountElement) {
        folderCountElement.textContent = count;
    }
}

// 保存用户偏好设置
function saveUserPreferences() {
    const preferences = {
        view: currentView,
        sort: currentSort,
        order: currentOrder
    };
    
    try {
        localStorage.setItem('folderListPreferences', JSON.stringify(preferences));
    } catch (error) {
        console.warn('无法保存用户偏好设置:', error);
    }
}

// 加载用户偏好设置
function loadUserPreferences() {
    try {
        const saved = localStorage.getItem('folderListPreferences');
        if (saved) {
            const preferences = JSON.parse(saved);
            
            // 恢复视图模式
            if (preferences.view) {
                switchView(preferences.view);
            }
            
            // 恢复排序设置
            if (preferences.sort) {
                currentSort = preferences.sort;
                const sortSelect = document.getElementById('sortSelect');
                if (sortSelect) {
                    sortSelect.value = currentSort;
                }
            }
            
            if (preferences.order) {
                currentOrder = preferences.order;
                const orderSelect = document.getElementById('orderSelect');
                if (orderSelect) {
                    orderSelect.value = currentOrder;
                }
            }
            
            // 应用排序
            sortFolders();
        }
    } catch (error) {
        console.warn('无法加载用户偏好设置:', error);
    }
}

// 显示加载状态
function showLoading() {
    const loadingState = document.getElementById('loadingState');
    const folderGrid = document.getElementById('folderGrid');
    
    if (loadingState) loadingState.style.display = 'block';
    if (folderGrid) folderGrid.style.display = 'none';
}

// 隐藏加载状态
function hideLoading() {
    const loadingState = document.getElementById('loadingState');
    const folderGrid = document.getElementById('folderGrid');
    
    if (loadingState) loadingState.style.display = 'none';
    if (folderGrid) folderGrid.style.display = 'grid';
}

// 刷新文件夹列表
async function refreshFolderList() {
    showLoading();
    
    try {
        const response = await galleryApp.makeRequest('/api/folders');
        if (response.success) {
            // 重新加载页面或动态更新内容
            window.location.reload();
        }
    } catch (error) {
        galleryApp.showMessage('刷新失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// 导出到全局作用域
window.folderList = {
    refreshFolderList,
    switchView,
    sortFolders
};

// ========== 文件夹状态管理 ==========

// 初始化文件夹状态
async function initFolderStatus() {
    try {
        // 加载所有文件夹状态
        const response = await fetch('/gallery/api/folder-status/all');
        const data = await response.json();
        
        if (data.success && data.data) {
            applyFolderStatus(data.data);
        }
        
        // 绑定状态选择事件
        bindStatusCheckboxEvents();
    } catch (error) {
        console.error('加载文件夹状态失败:', error);
    }
}

// 应用文件夹状态到UI
function applyFolderStatus(statusData) {
    const folderCards = document.querySelectorAll('.folder-card');
    
    folderCards.forEach(card => {
        const folderName = card.dataset.folderName;
        if (folderName && statusData[folderName]) {
            const statusInfo = statusData[folderName];
            const statusCheckboxes = card.querySelectorAll('.status-input');
            
            statusCheckboxes.forEach(checkbox => {
                if (checkbox.value === statusInfo.status) {
                    checkbox.checked = true;
                }
            });
        }
    });
}

// 绑定状态选择框事件
function bindStatusCheckboxEvents() {
    const statusInputs = document.querySelectorAll('.status-input');
    
    statusInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            e.preventDefault();
            
            const folderName = this.dataset.folder;
            const status = this.value;
            const container = this.closest('.status-checkboxes');
            
            if (this.checked) {
                // 取消同组其他复选框的选中状态（单选行为）
                const siblings = container.querySelectorAll('.status-input');
                siblings.forEach(sibling => {
                    if (sibling !== this) {
                        sibling.checked = false;
                    }
                });
                
                // 保存状态
                saveFolderStatus(folderName, status);
            } else {
                // 如果取消选中，则清除状态
                saveFolderStatus(folderName, '');
            }
        });
    });
}

// 保存文件夹状态
async function saveFolderStatus(folderName, status) {
    try {
        const url = `/gallery/api/folder-status/${encodeURIComponent(folderName)}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: status })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            console.error('保存状态失败:', data.message);
            // 恢复原状态
            location.reload();
        }
    } catch (error) {
        console.error('保存状态时发生错误:', error);
    }
}