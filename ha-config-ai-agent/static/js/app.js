// AI Configuration Agent - Main JavaScript

console.log('AI Configuration Agent initializing...');

// Global state
let conversationHistory = [];
let pendingChangeset = null;
let currentChangesetData = null;
// Track tool_call announcements per assistant iteration to avoid duplicates
let toolCallIterationsShown = new Set();

// DOM elements
let chatMessages, messageInput, sendBtn, diffModal, diffContent, exportBtn, importBtn, importFileInput;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing chat interface...');

    // Get DOM elements
    chatMessages = document.getElementById('chatMessages');
    messageInput = document.getElementById('messageInput');
    sendBtn = document.getElementById('sendBtn');
    diffModal = document.getElementById('diffModal');
    diffContent = document.getElementById('diffContent');
    exportBtn = document.getElementById('exportBtn');
    importBtn = document.getElementById('importBtn');
    importFileInput = document.getElementById('importFileInput');

    // Set up event listeners
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Export/Import listeners
    exportBtn.addEventListener('click', exportConversation);
    importBtn.addEventListener('click', () => importFileInput.click());
    importFileInput.addEventListener('change', importConversation);

    // Check health
    checkHealth();
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


// Send message to agent using SSE
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    console.log('Sending message:', message);

    // Add user message to chat
    addUserMessage(message);

    // Add user message to conversation history
    conversationHistory.push({
        role: 'user',
        content: message
    });

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Disable send button and show loading indicator
    sendBtn.disabled = true;
    let currentAssistantMessage = null;
    let currentMessageContent = '';
    let loadingIndicator = addLoadingIndicator();

    try {
        // Reset per-request tool call dedupe tracker
        toolCallIterationsShown = new Set();
        // Use fetch with streaming instead of EventSource for POST support
        const response = await fetch('api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            },
            body: JSON.stringify({
                message: message,
                conversation_history: conversationHistory.slice(0, -1) // Exclude the message we just added
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        // Parse SSE stream (robust SSE parser)
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // SSE state
        let eventName = null; // defaults to 'message' per spec
        let dataLines = [];

        const dispatchEvent = (name, dataStr) => {
            if (!name) name = 'message';
            if (!dataStr) dataStr = '';

            // Defensive: remove spinner on first delivered event of any type
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }

            try {
                const data = dataStr ? JSON.parse(dataStr) : {};

                if (name === 'token') {
                    // Accumulate content
                    currentMessageContent += data.content || '';

                    // Update or create assistant message element
                    if (!currentAssistantMessage) {
                        currentAssistantMessage = addAssistantMessageStreaming('');
                    }
                    updateAssistantMessageStreaming(currentAssistantMessage, currentMessageContent);

                } else if (name === 'message_complete') {
                    conversationHistory.push(data.message);
                    if (currentAssistantMessage) {
                        finalizeAssistantMessageStreaming(currentAssistantMessage);
                    }
                    currentMessageContent = '';
                    currentAssistantMessage = null;

                } else if (name === 'tool_call') {
                    // Dedupe tool_call announcements per iteration
                    if (typeof data.iteration !== 'undefined') {
                        if (toolCallIterationsShown.has(data.iteration)) {
                            return; // skip duplicate
                        }
                        toolCallIterationsShown.add(data.iteration);
                    }

                    // Finalize current streaming message before tool execution UI
                    if (currentAssistantMessage) {
                        finalizeAssistantMessageStreaming(currentAssistantMessage);
                        currentAssistantMessage = null;
                    }

                    // Add assistant message with tool calls to history
                    conversationHistory.push({
                        role: 'assistant',
                        content: currentMessageContent,
                        tool_calls: data.tool_calls
                    });
                    currentMessageContent = '';

                    // Show tool execution indicator summary with expandable arguments
                    addToolCallMessage(data.tool_calls);

                } else if (name === 'tool_start') {
                    addSystemMessage(`▶️ Executing: ${data.function}...`);

                } else if (name === 'tool_result') {
                    conversationHistory.push({
                        role: 'tool',
                        tool_call_id: data.tool_call_id,
                        content: JSON.stringify(data.result)
                    });
                    addToolResultMessage(data.function, data.result);

                    if (data.function === 'propose_config_changes' && data.result.success) {
                        const changesetData = {
                            changeset_id: data.result.changeset_id,
                            total_files: data.result.total_files,
                            files: data.result.files
                        };
                        const assistantMsg = conversationHistory
                            .slice()
                            .reverse()
                            .find(m => m.role === 'assistant' && m.tool_calls);
                        if (assistantMsg) {
                            const toolCall = assistantMsg.tool_calls.find(tc => tc.id === data.tool_call_id);
                            if (toolCall) {
                                const args = JSON.parse(toolCall.function.arguments);
                                changesetData.file_changes_detail = args.changes;
                                changesetData.original_contents = extractOriginalContents(conversationHistory, args.changes);
                            }
                        }
                        addApprovalCard(changesetData);
                    }

                } else if (name === 'complete') {
                    console.log('Stream complete:', data);

                } else if (name === 'error') {
                    addSystemMessage(`❌ Error: ${data.error}`);
                }
            } catch (e) {
                console.error('Error parsing SSE event:', name, dataStr, e);
            }
        };

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // As soon as any bytes arrive, remove the spinner (defensive)
            if (value && value.byteLength && loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (let raw of lines) {
                // Normalize line endings and trim trailing CR
                const line = raw.endsWith('\r') ? raw.slice(0, -1) : raw;

                if (line === '') {
                    // Blank line indicates dispatch
                    const dataStr = dataLines.length ? dataLines.join('\n') : '';
                    dispatchEvent(eventName, dataStr);
                    // Reset state
                    eventName = null;
                    dataLines = [];
                    continue;
                }

                if (line.startsWith(':')) {
                    // Comment/heartbeat, ignore
                    continue;
                }

                if (line.startsWith('event:')) {
                    eventName = line.substring(6).trim();
                    continue;
                }

                if (line.startsWith('data:')) {
                    dataLines.push(line.substring(5).trimStart());
                    continue;
                }
                // Ignore other fields (id, retry) for now
            }
        }

        // Flush any remaining event if buffer ended without trailing blank line
        if (dataLines.length) {
            const dataStr = dataLines.join('\n');
            dispatchEvent(eventName, dataStr);
        }

        // Final cleanup
        if (loadingIndicator && loadingIndicator.parentNode) {
            removeLoadingIndicator(loadingIndicator);
        }
        sendBtn.disabled = false;
        messageInput.focus();

    } catch (error) {
        console.error('Send message error:', error);
        removeLoadingIndicator(loadingIndicator);
        addSystemMessage(`❌ Error: ${error.message}`);
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

// Add streaming assistant message (creates element)
function addAssistantMessageStreaming(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message streaming';
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

// Update streaming assistant message
function updateAssistantMessageStreaming(messageDiv, content) {
    // For streaming, show plain text first
    messageDiv.textContent = content;
    scrollToBottom();
}

// Finalize streaming assistant message (apply markdown)
function finalizeAssistantMessageStreaming(messageDiv) {
    const content = messageDiv.textContent;
    messageDiv.classList.remove('streaming');

    // Apply markdown rendering
    if (typeof marked !== 'undefined') {
        messageDiv.innerHTML = marked.parse(content);
    }
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

// Add tool call message with expandable arguments
function addToolCallMessage(toolCalls) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message tool-call-message';

    const toolCallId = 'toolcall-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const toolNames = toolCalls.map(tc => tc.function.name).join(', ');

    let html = '<div class="tool-call-content">';
    html += `<div class="tool-call-header">`;
    html += `<span class="tool-call-icon">🔧</span>`;
    html += `<span class="tool-call-summary">Calling ${toolCalls.length} tool(s): ${escapeHtml(toolNames)}</span>`;
    html += `<button class="tool-call-toggle" onclick="toggleToolCall('${toolCallId}')">▼ Arguments</button>`;
    html += `</div>`;
    html += `<div class="tool-call-details" id="${toolCallId}" style="display: none;">`;

    // Show each tool call with its arguments
    for (let i = 0; i < toolCalls.length; i++) {
        const tc = toolCalls[i];
        html += '<div class="tool-call-item">';
        html += `<div class="tool-call-item-header"><strong>${i + 1}. ${escapeHtml(tc.function.name)}</strong></div>`;

        // Parse and format arguments
        let args;
        try {
            args = typeof tc.function.arguments === 'string'
                ? JSON.parse(tc.function.arguments)
                : tc.function.arguments;
            html += `<pre><code>${escapeHtml(JSON.stringify(args, null, 2))}</code></pre>`;
        } catch (e) {
            html += `<pre><code>${escapeHtml(tc.function.arguments)}</code></pre>`;
        }

        html += '</div>';
    }

    html += `</div>`;
    html += '</div>';

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Toggle tool call details
window.toggleToolCall = function(toolCallId) {
    const detailsDiv = document.getElementById(toolCallId);
    const button = detailsDiv.previousElementSibling.querySelector('.tool-call-toggle');

    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        button.textContent = '▲ Arguments';
    } else {
        detailsDiv.style.display = 'none';
        button.textContent = '▼ Arguments';
    }
};

// Add tool result message with expandable details
function addToolResultMessage(functionName, result) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message tool-result-message';

    // Generate summary based on function and result
    let summary = '';
    let icon = '';

    if (result.success === false) {
        icon = '❌';
        summary = `Error in ${functionName}: ${result.error || 'Unknown error'}`;
    } else if (functionName === 'search_config_files') {
        icon = '🔍';
        const fileCount = result.count || result.files?.length || 0;
        summary = `Found ${fileCount} file(s)`;
    } else if (functionName === 'propose_config_changes') {
        icon = '📝';
        summary = `Proposed changes to ${result.total_files || 0} file(s)`;
    } else {
        icon = '✓';
        summary = `${functionName} completed`;
    }

    const resultId = 'result-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

    let html = '<div class="tool-result-content">';
    html += `<div class="tool-result-header">`;
    html += `<span class="tool-result-icon">${icon}</span>`;
    html += `<span class="tool-result-summary">${escapeHtml(summary)}</span>`;
    html += `<button class="tool-result-toggle" onclick="toggleToolResult('${resultId}')">▼ Details</button>`;
    html += `</div>`;
    html += `<div class="tool-result-details" id="${resultId}" style="display: none;">`;
    html += `<pre><code>${escapeHtml(JSON.stringify(result, null, 2))}</code></pre>`;
    html += `</div>`;
    html += '</div>';

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Toggle tool result details
window.toggleToolResult = function(resultId) {
    const detailsDiv = document.getElementById(resultId);
    const button = detailsDiv.previousElementSibling.querySelector('.tool-result-toggle');

    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        button.textContent = '▲ Details';
    } else {
        detailsDiv.style.display = 'none';
        button.textContent = '▼ Details';
    }
};

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
    // Reset buttons to enabled state for new changeset
    const modalFooter = document.querySelector('.modal-footer');
    if (modalFooter) {
        const approveBtn = modalFooter.querySelector('.btn-success');
        const rejectBtn = modalFooter.querySelector('.btn-danger');
        const closeBtn = modalFooter.querySelector('.btn-secondary');

        if (approveBtn) {
            approveBtn.disabled = false;
            approveBtn.textContent = '✓ Approve & Apply';
        }
        if (rejectBtn) {
            rejectBtn.disabled = false;
            rejectBtn.textContent = '✗ Reject';
        }
        if (closeBtn) {
            closeBtn.disabled = false;
        }
    }

    let html = '<div class="diff-header">';
    html += `<p><strong>Changeset ID:</strong> ${changesetData.changeset_id}</p>`;
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

    // Get the buttons from modal-footer
    const modalFooter = document.querySelector('.modal-footer');
    const approveBtn = modalFooter.querySelector('.btn-success');
    const rejectBtn = modalFooter.querySelector('.btn-danger');
    const closeBtn = modalFooter.querySelector('.btn-secondary');
    const modalBody = document.querySelector('.modal-body');

    // Prevent double-clicks by checking if already processing
    if (approveBtn && approveBtn.disabled) return;

    // Add processing indicator
    const processingDiv = document.createElement('div');
    processingDiv.className = 'approval-processing';
    processingDiv.innerHTML = `
        <div class="approval-processing-content">
            <div class="loading-dots">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
            </div>
            <span class="approval-processing-text">Applying changes and validating configuration...</span>
        </div>
    `;
    modalBody.insertBefore(processingDiv, modalBody.firstChild);

    if (approveBtn) {
        approveBtn.disabled = true;
        approveBtn.textContent = '⏳ Applying...';
    }
    if (rejectBtn) {
        rejectBtn.disabled = true;
    }
    if (closeBtn) {
        closeBtn.disabled = true;
    }

    const success = await handleApproval(currentChangesetData.changeset_id, true);

    if (success) {
        // Show success briefly before closing
        processingDiv.innerHTML = `
            <div class="approval-processing-content approval-success">
                <span class="approval-success-icon">✅</span>
                <span class="approval-processing-text">Changes applied successfully!</span>
            </div>
        `;
        await new Promise(resolve => setTimeout(resolve, 1500));
        closeDiffModal();
    } else {
        // Show error and keep modal open
        processingDiv.remove();
        if (approveBtn) {
            approveBtn.disabled = false;
            approveBtn.textContent = '✓ Approve & Apply';
        }
        if (rejectBtn) {
            rejectBtn.disabled = false;
        }
        if (closeBtn) {
            closeBtn.disabled = false;
        }
    }
};

// Reject pending changes
window.rejectPendingChanges = async function() {
    if (!currentChangesetData) return;

    // Get the buttons from modal-footer
    const modalFooter = document.querySelector('.modal-footer');
    const approveBtn = modalFooter.querySelector('.btn-success');
    const rejectBtn = modalFooter.querySelector('.btn-danger');
    const closeBtn = modalFooter.querySelector('.btn-secondary');

    // Prevent double-clicks by checking if already processing
    if (rejectBtn && rejectBtn.disabled) return;

    if (rejectBtn) {
        rejectBtn.disabled = true;
        rejectBtn.textContent = '⏳ Rejecting...';
    }
    if (approveBtn) {
        approveBtn.disabled = true;
    }
    if (closeBtn) {
        closeBtn.disabled = true;
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
            addSystemMessage(`❌ Error: ${error.detail || 'Request failed'}`);
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
                return true;
            } else {
                addSystemMessage(`⚠️ ${data.message || 'Changes not applied'}`);
                return false;
            }
        } else {
            addSystemMessage('❌ Changes rejected.');
            return true;
        }

    } catch (error) {
        console.error('Approval error:', error);
        addSystemMessage(`❌ Error: ${error.message}`);
        return false;
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

// Export conversation to JSON file
function exportConversation() {
    if (conversationHistory.length === 0) {
        addSystemMessage('⚠️ No conversation to export.');
        return;
    }

    const exportData = {
        version: '1.0',
        timestamp: new Date().toISOString(),
        conversationHistory: conversationHistory,
        messageCount: conversationHistory.length
    };

    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `ha-config-agent-conversation-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    addSystemMessage('✅ Conversation exported successfully.');
}

// Import conversation from JSON file
function importConversation(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const importData = JSON.parse(e.target.result);

            // Validate import data structure
            if (!importData.conversationHistory || !Array.isArray(importData.conversationHistory)) {
                throw new Error('Invalid conversation file format.');
            }

            // Clear current conversation
            conversationHistory = [];
            chatMessages.innerHTML = '';

            // Restore conversation history
            conversationHistory = importData.conversationHistory;

            // Rebuild UI from history
            for (const msg of conversationHistory) {
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    if (msg.content) {
                        addAssistantMessage(msg.content);
                    }
                    // Handle tool calls if present
                    if (msg.tool_calls) {
                        addToolCallMessage(msg.tool_calls);
                    }
                } else if (msg.role === 'tool') {
                    // Tool messages are typically not displayed individually in UI
                    // They're shown via tool result messages
                }
            }

            addSystemMessage(`✅ Conversation imported successfully. ${importData.messageCount} messages restored.`);

            // Reset file input
            event.target.value = '';

        } catch (error) {
            console.error('Import error:', error);
            addSystemMessage(`❌ Failed to import conversation: ${error.message}`);
            event.target.value = '';
        }
    };

    reader.onerror = function() {
        addSystemMessage('❌ Failed to read file.');
        event.target.value = '';
    };

    reader.readAsText(file);
}
