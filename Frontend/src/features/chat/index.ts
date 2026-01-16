/**
 * Chat Feature
 *
 * Exports all chat-related components and utilities.
 */

// Pages
export { default as ChatPage } from './pages/ChatPage'

// Components
export { ConversationList } from './components/ConversationList'
export { ChatThread } from './components/ChatThread'
export { Composer } from './components/Composer'
export { ModelSelector } from './components/ModelSelector'
export { ModelConfigDrawer } from './components/ModelConfigDrawer'
export { ModelProfileSettings } from './components/ModelProfileSettings'

// API Client
export { chatClient } from './api/chatClient'
export type {
  ModelProfile,
  Conversation,
  Message,
  Attachment,
  StreamEvent,
} from './api/chatClient'
