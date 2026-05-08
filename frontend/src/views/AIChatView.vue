<template>
  <div class="ai-chat-view">
    <div class="page-header">
      <h2>AI智能问答</h2>
      <a-space>
        <a-button @click="handleClearCache" type="default" danger>
          <template #icon><ReloadOutlined /></template>
          清除缓存
        </a-button>
      </a-space>
    </div>

    <a-card class="chat-card">
      <div class="chat-container" ref="chatContainer">
        <div
          v-for="(msg, index) in store.chatMessages"
          :key="index"
          class="chat-message"
          :class="msg.type"
        >
          <div class="message-avatar">
            <a-avatar :class="msg.type" :icon="msg.type === 'user' ? 'user' : 'robot'" />
          </div>
          <div class="message-content">
            <div class="message-bubble" :class="msg.type">
              {{ msg.content }}
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-container">
        <a-space style="width: 100%">
          <a-input-search
            v-model:value="question"
            placeholder="请输入您的问题..."
            @search="handleSend"
            @pressEnter="handleSend"
            style="flex: 1"
          >
            <template #enterButton>
              <a-button type="primary" :loading="store.chatLoading">发送</a-button>
            </template>
          </a-input-search>
          <a-button @click="clearHistory" title="清除历史记录">
            <template #icon><DeleteOutlined /></template>
          </a-button>
        </a-space>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import api from '../api'
import { useSubwayStore } from '../stores/subway'

const store = useSubwayStore()

const chatContainer = ref(null)
const question = ref('')
const clearingCache = ref(false)

let userId = localStorage.getItem('userId')
if (!userId) {
  userId = 'user_' + Math.random().toString(36).substr(2, 9)
  localStorage.setItem('userId', userId)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const handleSend = async () => {
  if (!question.value.trim()) return
  
  const userQuestion = question.value.trim()
  question.value = ''
  scrollToBottom()
  
  await store.sendMessage(userQuestion, userId)
  scrollToBottom()
}

const clearHistory = () => {
  store.clearChatHistory()
  scrollToBottom()
}

const handleClearCache = async () => {
  clearingCache.value = true
  try {
    const response = await api.clearCache()
    if (response.code === 200) {
      store.clearChatHistory()
      message.success('缓存已清除！现在可以查询最新数据了')
    } else {
      message.error('清除缓存失败')
    }
  } catch (error) {
    console.error('清除缓存失败:', error)
    message.error('清除缓存失败，请稍后再试')
  } finally {
    clearingCache.value = false
  }
}

watch(() => store.chatMessages, () => {
  scrollToBottom()
}, { deep: true })

onMounted(() => {
  store.initChat()
  scrollToBottom()
})
</script>

<style scoped lang="scss">
.ai-chat-view {
  height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;

  .page-header {
    margin-bottom: 24px;
    h2 { margin: 0; font-size: 24px; font-weight: 600; }
  }

  .chat-card {
    flex: 1;
    display: flex;
    flex-direction: column;

    :deep(.ant-card-body) {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 0;
    }
  }

  .chat-container {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    background: #f5f5f5;
  }

  .chat-message {
    display: flex;
    margin-bottom: 16px;
    
    &.user {
      flex-direction: row-reverse;
      
      .message-bubble {
        background: #1890ff;
        color: white;
        border-radius: 18px 18px 4px 18px;
      }
    }

    &.bot {
      .message-bubble {
        background: white;
        color: #333;
        border-radius: 18px 18px 18px 4px;
      }
    }
  }

  .message-content {
    max-width: 70%;
    margin: 0 12px;
  }

  .message-bubble {
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .chat-input-container {
    padding: 16px;
    border-top: 1px solid #f0f0f0;
    background: white;
  }
}
</style>