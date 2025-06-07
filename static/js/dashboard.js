// Dashboard JavaScript
let connectionChart = null;

// Initialize dashboard
$(document).ready(function() {
    loadStats();
    loadUsers();
    loadConnections();
    loadLogs();
    loadConfig();
    
    // Set up auto-refresh
    setInterval(loadStats, 5000);
    setInterval(loadConnections, 10000);
    
    // Initialize connection chart
    initConnectionChart();
});

// Load statistics
function loadStats() {
    $.get('/api/stats', function(data) {
        $('#stat-users').text(data.total_users);
        $('#stat-connections').text(data.active_connections);
        $('#stat-blocked').text(data.blocked_users);
    });
}

// Load users
function loadUsers() {
    $.get('/api/users', function(users) {
        const tbody = $('#usersTable tbody');
        tbody.empty();
        
        users.forEach(user => {
            const statusBadge = user.is_blocked 
                ? '<span class="badge bg-danger">Blocked</span>'
                : '<span class="badge bg-success">Active</span>';
            
            const blockBtn = user.is_blocked
                ? `<button class="btn btn-sm btn-success" onclick="unblockUser('${user.username}')">Unblock</button>`
                : `<button class="btn btn-sm btn-warning" onclick="blockUser('${user.username}')">Block</button>`;
            
            tbody.append(`
                <tr>
                    <td>${user.username}</td>
                    <td>${user.home_directory}</td>
                    <td>${statusBadge}</td>
                    <td>${new Date(user.created_at).toLocaleString()}</td>
                    <td>
                        ${blockBtn}
                        <button class="btn btn-sm btn-danger" onclick="deleteUser('${user.username}')">Delete</button>
                    </td>
                </tr>
            `);
        });
    });
}

// Add user
function addUser() {
    const data = {
        username: $('#username').val(),
        password: $('#password').val(),
        home_directory: $('#home_directory').val() || `/home/${$('#username').val()}`
    };
    
    $.ajax({
        url: '/api/users',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if (response.success) {
                $('#addUserModal').modal('hide');
                $('#addUserForm')[0].reset();
                loadUsers();
                showAlert('success', response.message);
            } else {
                showAlert('danger', response.message);
            }
        }
    });
}

// Delete user
function deleteUser(username) {
    if (confirm(`Are you sure you want to delete user ${username}?`)) {
        $.ajax({
            url: `/api/users/${username}`,
            method: 'DELETE',
            success: function(response) {
                if (response.success) {
                    loadUsers();
                    showAlert('success', response.message);
                } else {
                    showAlert('danger', response.message);
                }
            }
        });
    }
}

// Block user
function blockUser(username) {
    $.post(`/api/users/${username}/block`, function(response) {
        if (response.success) {
            loadUsers();
            loadStats();
            showAlert('success', response.message);
        } else {
            showAlert('danger', response.message);
        }
    });
}

// Unblock user
function unblockUser(username) {
    $.post(`/api/users/${username}/unblock`, function(response) {
        if (response.success) {
            loadUsers();
            loadStats();
            showAlert('success', response.message);
        } else {
            showAlert('danger', response.message);
        }
    });
}

// Load connections
function loadConnections() {
    $.get('/api/connections', function(connections) {
        const tbody = $('#connectionsTable tbody');
        tbody.empty();
        
        connections.forEach(conn => {
            tbody.append(`
                <tr>
                    <td>${conn.username}</td>
                    <td>${conn.ip_address}</td>
                    <td>${new Date(conn.connected_at).toLocaleString()}</td>
                    <td>${conn.pid}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="killConnection(${conn.pid})">
                            <i class="bi bi-x-circle"></i> Kill
                        </button>
                    </td>
                </tr>
            `);
        });
        
        // Update chart
        updateConnectionChart(connections);
    });
}

// Kill connection
function killConnection(pid) {
    if (confirm('Are you sure you want to terminate this connection?')) {
        $.post(`/api/connections/${pid}/kill`, function(response) {
            if (response.success) {
                loadConnections();
                loadStats();
                showAlert('success', response.message);
            } else {
                showAlert('danger', response.message);
            }
        });
    }
}

// Load logs
function loadLogs() {
    $.get('/api/logs', function(logs) {
        const tbody = $('#logsTable tbody');
        tbody.empty();
        
        logs.forEach(log => {
            const statusClass = log.status === 'OK' ? 'text-success' : 'text-danger';
            tbody.append(`
                <tr class="log-entry">
                    <td>${new Date(log.timestamp).toLocaleString()}</td>
                    <td>${log.username}</td>
                    <td>${log.action}</td>
                    <td>${log.ip_address}</td>
                    <td class="${statusClass}">${log.status}</td>
                </tr>
            `);
        });
    });
}

// Refresh logs
function refreshLogs() {
    loadLogs();
    showAlert('info', 'Logs refreshed');
}

// Load configuration
function loadConfig() {
    $.get('/api/config', function(config) {
        const configList = $('#configList');
        configList.empty();
        
        Object.keys(config).forEach(key => {
            const item = config[key];
            const inputType = item.type === 'bool' ? 'checkbox' : 'text';
            const checked = item.type === 'bool' && (item.value === 'YES' || item.value === 'true') ? 'checked' : '';
            const value = item.type === 'bool' ? '' : item.value;
            
            configList.append(`
                <div class="config-item">
                    <div class="row align-items-center">
                        <div class="col-md-3">
                            <strong>${key}</strong>
                            <br><small class="text-muted">${item.description}</small>
                        </div>
                        <div class="col-md-6">
                            ${item.type === 'bool' ? 
                                `<div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="config_${key}" ${checked} 
                                           onchange="updateConfig('${key}', this.checked ? 'YES' : 'NO')">
                                    <label class="form-check-label" for="config_${key}">
                                        ${item.value}
                                    </label>
                                </div>` :
                                `<input type="text" class="form-control" id="config_${key}" value="${value}" 
                                        onblur="updateConfig('${key}', this.value)">`
                            }
                        </div>
                        <div class="col-md-3">
                            <span class="badge bg-secondary">${item.type}</span>
                        </div>
                    </div>
                </div>
            `);
        });
    });
}

// Update configuration
function updateConfig(key, value) {
    $.ajax({
        url: '/api/config',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({key: key, value: value}),
        success: function(response) {
            if (response.success) {
                showAlert('success', response.message);
            } else {
                showAlert('danger', response.message);
                loadConfig(); // Reload to reset values
            }
        }
    });
}

// Initialize connection chart
function initConnectionChart() {
    const ctx = document.getElementById('connectionChart').getContext('2d');
    connectionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Active Connections',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Update connection chart
function updateConnectionChart(connections) {
    if (!connectionChart) return;
    
    const now = new Date();
    const timeLabel = now.toLocaleTimeString();
    
    // Keep only last 20 data points
    if (connectionChart.data.labels.length >= 20) {
        connectionChart.data.labels.shift();
        connectionChart.data.datasets[0].data.shift();
    }
    
    connectionChart.data.labels.push(timeLabel);
    connectionChart.data.datasets[0].data.push(connections.length);
    connectionChart.update();
}

// Show alert
function showAlert(type, message) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Remove existing alerts
    $('.alert').remove();
    
    // Add new alert at the top
    $('body').prepend(alertHtml);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        $('.alert').fadeOut();
    }, 5000);
}

// Tab change handlers
$('#mainTabs button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
    const target = $(e.target).attr('data-bs-target');
    
    switch(target) {
        case '#users':
            loadUsers();
            break;
        case '#connections':
            loadConnections();
            break;
        case '#logs':
            loadLogs();
            break;
        case '#config':
            loadConfig();
            break;
    }
});

// Auto-refresh for active tab
setInterval(() => {
    const activeTab = $('.nav-link.active').attr('data-bs-target');
    
    switch(activeTab) {
        case '#connections':
            loadConnections();
            break;
        case '#logs':
            if (Math.random() < 0.1) { // 10% chance to refresh logs
                loadLogs();
            }
            break;
    }
}, 5000);