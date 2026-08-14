/**
 * RouteLink - AI Assistant Module
 * University Final Year Project
 * 
 * Handles all AI-related functionality including:
 * - Travel assistant chat
 * - Business assistant queries
 * - Emergency classification
 * 
 * IMPORTANT: All AI communication goes through server-side endpoints
 * to protect API keys. The frontend never handles API keys directly.
 */

// ==================== CONFIGURATION ====================
const AI_CONFIG = {
    chatEndpoint: '/api/ai/chat',
    classifyEndpoint: '/api/ai/classify-emergency',
    maxMessageLength: 500,
    typingDelay: 300
};

// ==================== CHAT INTERFACE CLASS ====================
/**
 * Manages AI chat interface and communication
 */
class AIChatAssistant {
    /**
     * @param {string} messagesContainerId - ID of chat messages container
     * @param {string} inputId - ID of chat input field
     * @param {string} sendButtonId - ID of send button
     * @param {string} contextType - Type of context ('travel', 'business', 'emergency')
     * @param {Object} contextData - Additional context data to send
     */
    constructor(messagesContainerId, inputId, sendButtonId, contextType = 'general', contextData = {}) {
        this.messagesContainer = document.getElementById(messagesContainerId);
        this.input = document.getElementById(inputId);
        this.sendButton = document.getElementById(sendButtonId);
        this.contextType = contextType;
        this.contextData = contextData;
        this.messageHistory = [];
        
        this.init();
    }
    
    /**
     * Initialize event listeners
     */
    init() {
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        if (this.input) {
            this.input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    }
    
    /**
     * Send message to AI and display response
     */
    async sendMessage() {
        const message = this.input.value.trim();
        
        if (!message) return;
        
        if (message.length > AI_CONFIG.maxMessageLength) {
            this.addMessage('Message too long. Please keep it under 500 characters.', 'error');
            return;
        }
        
        // Add user message to chat
        this.addMessage(message, 'user');
        this.input.value = '';
        
        // Add to history
        this.messageHistory.push({ role: 'user', content: message });
        
        // Show loading indicator
        const loadingId = this.addMessage('Thinking...', 'loading');
        
        try {
            const response = await fetch(AI_CONFIG.chatEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: this.messageHistory.slice(-10), // Last 10 messages for context
                    context_type: this.contextType,
                    context_data: this.contextData
                })
            });
            
            const data = await response.json();
            
            // Remove loading message
            this.removeMessage(loadingId);
            
            if (data.response) {
                this.addMessage(data.response, 'ai');
                this.messageHistory.push({ role: 'assistant', content: data.response });
            } else {
                this.addMessage('Sorry, the AI assistant is currently unavailable.', 'error');
            }
        } catch (error) {
            console.error('AI chat error:', error);
            this.removeMessage(loadingId);
            this.addMessage('Error connecting to AI assistant. Please try again.', 'error');
        }
    }
    
    /**
     * Add message to chat display
     * @param {string} text - Message text
     * @param {string} type - Message type ('user', 'ai', 'error', 'loading')
     * @returns {string} Message element ID
     */
    addMessage(text, type = 'ai') {
        const id = 'msg-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = id;
        messageDiv.className = `chat-message ${type}`;
        messageDiv.textContent = text;
        
        if (this.messagesContainer) {
            this.messagesContainer.appendChild(messageDiv);
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
        
        return id;
    }
    
    /**
     * Remove message from chat
     * @param {string} id - Message element ID
     */
    removeMessage(id) {
        const element = document.getElementById(id);
        if (element) {
            element.remove();
        }
    }
    
    /**
     * Clear chat history
     */
    clear() {
        this.messageHistory = [];
        if (this.messagesContainer) {
            this.messagesContainer.innerHTML = '';
        }
    }
    
    /**
     * Update context data
     * @param {Object} newData - New context data
     */
    updateContext(newData) {
        this.contextData = { ...this.contextData, ...newData };
    }
}

// ==================== EMERGENCY CLASSIFICATION ====================
/**
 * Classifies emergency messages using AI
 * Returns category and priority suggestions
 */
async function classifyEmergency(message) {
    if (!message || message.trim().length === 0) {
        throw new Error('Message is required');
    }
    
    try {
        const response = await fetch(AI_CONFIG.classifyEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        if (!response.ok) {
            throw new Error('Classification failed');
        }
        
        const data = await response.json();
        
        return {
            category: data.category || 'Other',
            priority: data.priority || 'MEDIUM',
            reasoning: data.reasoning || '',
            ai_suggested: data.ai_suggested || false
        };
    } catch (error) {
        console.error('Emergency classification error:', error);
        throw error;
    }
}

// ==================== UTILITY FUNCTIONS ====================
/**
 * Validates AI configuration
 * @returns {boolean} True if AI is available
 */
function isAIAvailable() {
    // This will be determined by server response
    return true;
}

/**
 * Formats AI response with markdown-like syntax
 * @param {string} text - Raw AI response
 * @returns {string} Formatted HTML
 */
function formatAIResponse(text) {
    if (!text) return '';
    
    // Convert basic markdown to HTML
    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
    
    return formatted;
}

// ==================== EXPORTS ====================
window.AIAssistant = {
    AIChatAssistant,
    classifyEmergency,
    isAIAvailable,
    formatAIResponse,
    CONFIG: AI_CONFIG
};
