// WebSocket-based chat implementation to avoid Ingress buffering

let ws = null;
let currentAssistantMessage = null;
let currentMessageContent = '';
let loadingIndicator = null;
let toolCallArguments = {}; // Store arguments from tool_start events, keyed by tool_call_id

function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        return ws;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use relative path to work with Home Assistant Ingress proxy
    const wsUrl = `${protocol}//${window.location.host}${window.location.pathname}ws/chat`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addSystemMessage('❌ WebSocket connection error');
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
        ws = null;
    };

    return ws;
}

// Override the sendMessage function to use WebSocket
async function sendMessageWebSocket() {
    const message = messageInput.value.trim();
    if (!message) return;

    console.log('Sending message via WebSocket:', message);

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
    currentAssistantMessage = null;
    currentMessageContent = '';
    loadingIndicator = addLoadingIndicator();
    toolCallArguments = {}; // Reset tool arguments for new conversation

    try {
        const ws = connectWebSocket();

        // Wait for connection
        if (ws.readyState !== WebSocket.OPEN) {
            await new Promise((resolve, reject) => {
                ws.onopen = resolve;
                ws.onerror = reject;
                setTimeout(() => reject(new Error('Connection timeout')), 5000);
            });
        }

        // Set up message handler for this request
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        };

        // Send the chat request
        ws.send(JSON.stringify({
            type: 'chat',
            message: message,
            conversation_history: conversationHistory.slice(0, -1)
        }));

    } catch (error) {
        console.error('WebSocket send error:', error);
        removeLoadingIndicator(loadingIndicator);
        addSystemMessage(`❌ Error: ${error.message}`);
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

function handleWebSocketMessage(message) {
    const eventType = message.event;
    const data = message.data;

    console.log('WebSocket event:', eventType);

    try {
        if (eventType === 'token') {
            // Remove loading indicator on first token
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }

            // Accumulate content
            currentMessageContent += data.content;

            // Update or create assistant message element
            if (!currentAssistantMessage) {
                currentAssistantMessage = addAssistantMessageStreaming('');
            }
            updateAssistantMessageStreaming(currentAssistantMessage, currentMessageContent);

        } else if (eventType === 'message_complete') {
            // Add message to conversation history
            conversationHistory.push(data.message);

            // Finalize the assistant message display
            if (currentAssistantMessage) {
                finalizeAssistantMessageStreaming(currentAssistantMessage);
            }
            currentMessageContent = '';
            currentAssistantMessage = null;

        } else if (eventType === 'tool_call') {
            // Finalize current message if any
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

            // Show tool execution indicator summary
            addSystemMessage(`🔧 Calling ${data.tool_calls.length} tool(s): ${data.tool_calls.map(tc => tc.function.name).join(', ')}`);

            // Re-add loading indicator while tools execute and AI processes next response
            if (!loadingIndicator) {
                loadingIndicator = addLoadingIndicator();
            }

        } else if (eventType === 'tool_start') {
            // Store the arguments for later use when we get the tool_result
            if (data.tool_call_id && data.arguments) {
                toolCallArguments[data.tool_call_id] = data.arguments;
                console.log(`Stored arguments for tool_call_id ${data.tool_call_id}:`, data.arguments);
            }

            // Show individual tool execution start
            addSystemMessage(`▶️ Executing: ${data.function}...`);

        } else if (eventType === 'tool_result') {
            console.log('Tool result received:', data.function, 'success:', data.result?.success);

            // Add tool result to history
            conversationHistory.push({
                role: 'tool',
                tool_call_id: data.tool_call_id,
                content: JSON.stringify(data.result)
            });

            // Display tool result visually
            addToolResultMessage(data.function, data.result);

            // Process tool results (especially for propose_config_changes)
            if (data.function === 'propose_config_changes' && data.result.success) {
                console.log('propose_config_changes success, creating approval card');
                console.log('Result:', data.result);

                // Extract changeset info and display approval card
                const changesetData = {
                    changeset_id: data.result.changeset_id,
                    total_files: data.result.total_files,
                    files: data.result.files,
                    reason: data.result.reason
                };

                // Get the arguments from the stored tool_start data
                const args = toolCallArguments[data.tool_call_id];
                console.log('Retrieved arguments from tool_start event:', args);

                if (args && args.changes) {
                    changesetData.file_changes_detail = args.changes;
                    changesetData.original_contents = extractOriginalContents(conversationHistory, args.changes);
                    console.log('Successfully extracted file_changes_detail and original_contents');
                } else {
                    console.error('No arguments found for tool_call_id:', data.tool_call_id);
                    console.log('Available tool call IDs:', Object.keys(toolCallArguments));
                }

                console.log('Final changeset data before addApprovalCard:', changesetData);
                console.log('Has file_changes_detail?', !!changesetData.file_changes_detail);
                console.log('Has original_contents?', !!changesetData.original_contents);

                // Ensure we have the required data for diffs
                if (!changesetData.file_changes_detail) {
                    console.error('ERROR: Missing file_changes_detail in changesetData!');
                    console.log('Attempting to recover from tool result...');

                    // The backend should have sent the changes in the result
                    // but we need them from the tool call arguments for the new_content
                    // Let's try to recover from what we have
                    if (data.result.files && Array.isArray(data.result.files)) {
                        console.warn('Only have file list, not full changes. Approval card will show limited info.');
                    }
                }

                addApprovalCard(changesetData);
            }

        } else if (eventType === 'complete') {
            console.log('Stream complete:', data);

            // Final cleanup
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }
            sendBtn.disabled = false;
            messageInput.focus();

        } else if (eventType === 'error') {
            addSystemMessage(`❌ Error: ${data.error}`);

            // Cleanup
            if (loadingIndicator && loadingIndicator.parentNode) {
                removeLoadingIndicator(loadingIndicator);
                loadingIndicator = null;
            }
            sendBtn.disabled = false;
            messageInput.focus();
        }

    } catch (e) {
        console.error('Error handling WebSocket message:', e);
    }
}

// Export for use in main app
window.sendMessageWebSocket = sendMessageWebSocket;
