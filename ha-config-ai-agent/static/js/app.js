// AI Configuration Agent - Main JavaScript

console.log('AI Configuration Agent initializing...');

// Global state
let conversationHistory = [];
let pendingChangeset = null;
let currentChangesetData = null;

// DOM elements
let chatMessages, messageInput, sendBtn, diffModal, diffContent;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing chat interface...');

    // Get DOM elements
    chatMessages = document.getElementById('chatMessages');
    messageInput = document.getElementById('messageInput');
    sendBtn = document.getElementById('sendBtn');
    diffModal = document.getElementById('diffModal');
    diffContent = document.getElementById('diffContent');

    // Set up event listeners
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Check health and config
    checkHealth();
    checkConfig();
});

// Check health endpoint
async function checkHealth() {
    try {
        const response = await fetch('health');
        const data = await response.json();
        console.log('Health check:', data);

        if (!data.agent_system_ready) {
            addSystemMessage('⚠️ AI system not ready. Please configure OPENAI_API_KEY.');
        } else {
            addSystemMessage('✅ AI Configuration Agent ready. How can I help you today?');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        addSystemMessage('❌ Failed to connect to agent system.');
    }
}

// Check config endpoint
async function checkConfig() {
    try {
        const response = await fetch('api/config/info');
        const data = await response.json();
        console.log('Config info:', data);
    } catch (error) {
        console.error('Config check failed:', error);
    }
}

// Send message to agent
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    console.log('Sending message:', message);

    // Add user message to chat
    addUserMessage(message);

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Disable send button and show loading indicator
    sendBtn.disabled = true;
    const loadingIndicator = addLoadingIndicator();

    try {
        const response = await fetch('api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                conversation_history: conversationHistory
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Received response:', data);

        // Remove loading indicator
        removeLoadingIndicator(loadingIndicator);

        // Append new messages to history and process them first
        if (data.messages && Array.isArray(data.messages)) {
            conversationHistory.push(...data.messages);
            processMessages(data.messages);
        }

        // Display the response text if present (this is the final AI response)
        // This comes after processMessages to maintain chronological order
        if (data.response) {
            addAssistantMessage(data.response);
        }

    } catch (error) {
        console.error('Send message error:', error);
        removeLoadingIndicator(loadingIndicator);
        addSystemMessage(`❌ Error: ${error.message}`);
    } finally {
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// Process messages and display them
function processMessages(messages) {
    for (const msg of messages) {
        if (msg.role === 'assistant') {
            if (msg.content) {
                addAssistantMessage(msg.content);
            }

            // Check for propose_config_changes tool call
            if (msg.tool_calls) {
                for (const toolCall of msg.tool_calls) {
                    if (toolCall.function.name === 'propose_config_changes') {
                        // Find the tool response
                        const toolResponse = messages.find(
                            m => m.role === 'tool' && m.tool_call_id === toolCall.id
                        );

                        if (toolResponse) {
                            try {
                                const result = JSON.parse(toolResponse.content);
                                if (result.success && result.changeset_id) {
                                    // Store the full changeset data including file changes
                                    const args = JSON.parse(toolCall.function.arguments);
                                    result.file_changes_detail = args.changes;

                                    // Extract original file contents from conversation history
                                    result.original_contents = extractOriginalContents(conversationHistory, result.file_changes_detail);

                                    addApprovalCard(result);
                                }
                            } catch (e) {
                                console.error('Error parsing tool response:', e);
                            }
                        }
                    }
                }
            }
        }
    }
}

// Extract original file contents from search_config_files tool calls in conversation history
function extractOriginalContents(history, fileChanges) {
    const originalContents = {};

    // Get list of files we need originals for
    const filePathsNeeded = fileChanges.map(fc => fc.file_path);

    // Search through conversation history for search_config_files tool results
    for (const msg of history) {
        if (msg.role === 'assistant' && msg.tool_calls) {
            for (const toolCall of msg.tool_calls) {
                if (toolCall.function.name === 'search_config_files') {
                    // Find the corresponding tool response
                    const toolResponse = history.find(
                        m => m.role === 'tool' && m.tool_call_id === toolCall.id
                    );

                    if (toolResponse) {
                        try {
                            const searchResult = JSON.parse(toolResponse.content);
                            if (searchResult.success && searchResult.files) {
                                // Extract file contents that match our needed files
                                for (const file of searchResult.files) {
                                    if (filePathsNeeded.includes(file.path)) {
                                        originalContents[file.path] = file.content;
                                    }
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing search results:', e);
                        }
                    }
                }
            }
        }
    }

    return originalContents;
}

// Add user message to chat
function addUserMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add assistant message to chat with markdown rendering
function addAssistantMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message';

    // Use marked.js to parse markdown
    if (typeof marked !== 'undefined') {
        messageDiv.innerHTML = marked.parse(content);
    } else {
        messageDiv.textContent = content;
    }

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add system message to chat
function addSystemMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add loading indicator
function addLoadingIndicator() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant-message loading-message';
    loadingDiv.innerHTML = `
        <div class="loading-indicator">
            <div class="loading-dots">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
            </div>
            <span class="loading-text">AI is thinking...</span>
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    scrollToBottom();
    return loadingDiv;
}

// Remove loading indicator
function removeLoadingIndicator(indicator) {
    if (indicator && indicator.parentNode) {
        indicator.parentNode.removeChild(indicator);
    }
}

// Add approval card to chat
function addApprovalCard(changesetData) {
    const cardDiv = document.createElement('div');
    cardDiv.className = 'message approval-card-message';

    let html = '<div class="approval-card-content">';
    html += '<div class="approval-card-header">';
    html += '<span class="approval-icon">📝</span>';
    html += '<div class="approval-text">';
    html += '<strong>Configuration Changes Proposed</strong>';
    html += `<div class="approval-meta">${changesetData.total_files} file(s) • ID: ${changesetData.changeset_id}</div>`;
    html += '</div>';
    html += '</div>';

    if (changesetData.reason) {
        html += `<div class="approval-reason">${escapeHtml(changesetData.reason)}</div>`;
    }

    html += '<div class="approval-card-actions">';
    html += `<button class="btn btn-view" onclick="viewChanges('${changesetData.changeset_id}')">👁️ View Changes</button>`;
    html += '</div>';
    html += '</div>';

    cardDiv.innerHTML = html;
    chatMessages.appendChild(cardDiv);

    // Store changeset data for later retrieval
    cardDiv.dataset.changesetId = changesetData.changeset_id;
    cardDiv.dataset.changesetData = JSON.stringify(changesetData);

    scrollToBottom();
}

// View changes in modal
window.viewChanges = function(changesetId) {
    // Find the approval card with this changeset ID
    const cards = document.querySelectorAll('.approval-card-message');
    let changesetData = null;

    for (const card of cards) {
        if (card.dataset.changesetId === changesetId) {
            changesetData = JSON.parse(card.dataset.changesetData);
            break;
        }
    }

    if (!changesetData) {
        addSystemMessage('❌ Changeset not found');
        return;
    }

    currentChangesetData = changesetData;
    showDiffModal(changesetData);
};

// Show diff modal
function showDiffModal(changesetData) {
    let html = '<div class="diff-header">';
    html += `<p><strong>Changeset ID:</strong> ${changesetData.changeset_id}</p>`;
    html += `<p><strong>Reason:</strong> ${escapeHtml(changesetData.reason)}</p>`;
    html += `<p><strong>Files:</strong> ${changesetData.total_files}</p>`;
    html += '</div>';

    // Show each file change with diff
    if (changesetData.file_changes_detail && changesetData.file_changes_detail.length > 0) {
        html += '<div class="diff-files">';

        for (const change of changesetData.file_changes_detail) {
            const filePath = change.file_path;
            const newContent = change.new_content;
            const originalContent = changesetData.original_contents && changesetData.original_contents[filePath];

            html += '<div class="diff-file">';
            html += `<div class="diff-file-header"><strong>📄 ${escapeHtml(filePath)}</strong></div>`;

            if (originalContent) {
                // Calculate and display diff
                html += '<div class="diff-file-content">';
                html += generateDiffHtml(originalContent, newContent, filePath);
                html += '</div>';
            } else {
                // New file - no original content
                html += '<div class="diff-file-content">';
                html += '<div class="diff-new-file"><em>New file</em></div>';
                html += '<pre><code>' + escapeHtml(newContent) + '</code></pre>';
                html += '</div>';
            }

            html += '</div>';
        }

        html += '</div>';
    } else {
        html += '<div class="diff-files">';
        html += '<p>Files to be modified:</p><ul>';
        for (const file of changesetData.files) {
            html += `<li><code>${escapeHtml(file)}</code></li>`;
        }
        html += '</ul></div>';
    }

    diffContent.innerHTML = html;
    diffModal.style.display = 'flex';
}

// Generate HTML diff view
function generateDiffHtml(oldContent, newContent, fileName) {
    if (typeof Diff === 'undefined') {
        // Fallback if diff library not loaded
        return '<pre><code>' + escapeHtml(newContent) + '</code></pre>';
    }

    // Create unified diff
    const diff = Diff.createPatch(fileName, oldContent, newContent, 'Original', 'Proposed');

    // Convert to HTML
    let html = '<div class="unified-diff">';
    const lines = diff.split('\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Skip header lines (first 4 lines of unified diff format)
        if (i < 4) continue;

        let className = 'diff-line-context';
        let prefix = ' ';

        if (line.startsWith('+')) {
            className = 'diff-line-add';
            prefix = '+';
        } else if (line.startsWith('-')) {
            className = 'diff-line-remove';
            prefix = '-';
        } else if (line.startsWith('@@')) {
            className = 'diff-line-info';
            prefix = '';
        }

        html += `<div class="${className}">`;
        html += `<span class="diff-prefix">${escapeHtml(prefix)}</span>`;
        html += `<span class="diff-text">${escapeHtml(line.substring(1))}</span>`;
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Close diff modal
window.closeDiffModal = function() {
    diffModal.style.display = 'none';
    currentChangesetData = null;
};

// Approve pending changes
window.approvePendingChanges = async function() {
    if (!currentChangesetData) return;

    // Get the approve button and disable it
    const approveBtn = document.querySelector('.modal-actions .btn-approve');
    const rejectBtn = document.querySelector('.modal-actions .btn-reject');

    if (approveBtn) {
        approveBtn.disabled = true;
        approveBtn.textContent = '⏳ Applying...';
    }
    if (rejectBtn) {
        rejectBtn.disabled = true;
    }

    await handleApproval(currentChangesetData.changeset_id, true);
    closeDiffModal();
};

// Reject pending changes
window.rejectPendingChanges = async function() {
    if (!currentChangesetData) return;

    // Get the reject button and disable it
    const approveBtn = document.querySelector('.modal-actions .btn-approve');
    const rejectBtn = document.querySelector('.modal-actions .btn-reject');

    if (rejectBtn) {
        rejectBtn.disabled = true;
        rejectBtn.textContent = '⏳ Rejecting...';
    }
    if (approveBtn) {
        approveBtn.disabled = true;
    }

    await handleApproval(currentChangesetData.changeset_id, false);
    closeDiffModal();
};

// Handle approval/rejection
async function handleApproval(changesetId, approved) {
    try {
        const response = await fetch('api/approve', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                change_id: changesetId,
                approved: approved,
                validate: true
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }

        const data = await response.json();

        // Update the approval card to show the result
        updateApprovalCard(changesetId, approved, data);

        if (approved) {
            if (data.applied) {
                // Show success message with details
                let message = `✅ ${data.message || 'Changes applied successfully!'}`;

                // Add details about which files succeeded/failed
                if (data.applied_files && data.applied_files.length > 0) {
                    message += '\n\n✓ Applied to:';
                    data.applied_files.forEach(file => {
                        message += `\n  • ${file}`;
                    });
                }

                if (data.failed_files && data.failed_files.length > 0) {
                    message += '\n\n✗ Failed:';
                    data.failed_files.forEach(item => {
                        message += `\n  • ${item.file_path}: ${item.error}`;
                    });
                }

                addSystemMessage(message);
            } else {
                addSystemMessage(`⚠️ ${data.message || 'Changes not applied'}`);
            }
        } else {
            addSystemMessage('❌ Changes rejected.');
        }

    } catch (error) {
        console.error('Approval error:', error);
        addSystemMessage(`❌ Error: ${error.message}`);
    }
}

// Update approval card to show result
function updateApprovalCard(changesetId, approved, resultData) {
    // Find the approval card with this changeset ID
    const cards = document.querySelectorAll('.approval-card-message');

    for (const card of cards) {
        if (card.dataset.changesetId === changesetId) {
            const actionsDiv = card.querySelector('.approval-card-actions');

            if (actionsDiv) {
                // Replace the actions with a status message
                if (approved) {
                    if (resultData.applied) {
                        actionsDiv.innerHTML = '<div class="approval-status approval-status-success">✅ Changes Applied</div>';
                    } else {
                        actionsDiv.innerHTML = '<div class="approval-status approval-status-warning">⚠️ Changes Not Applied</div>';
                    }
                } else {
                    actionsDiv.innerHTML = '<div class="approval-status approval-status-rejected">❌ Changes Rejected</div>';
                }
            }

            break;
        }
    }
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
