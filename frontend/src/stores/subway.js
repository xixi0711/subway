import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useSubwayStore = defineStore('subway', () => {
  // AI聊天相关
  const chatMessages = ref([])
  const chatLoading = ref(false)
  const pendingRequests = ref(new Map())
  
  // 线路数据
  const lines = ref([])
  const linesLoading = ref(false)

  // 站点数据
  const stations = ref([])
  const stationsLoading = ref(false)

  // 时刻表数据
  const timetables = ref([])
  const timetablesLoading = ref(false)

  // 刷卡记录
  const cardRecords = ref([])
  const cardRecordsLoading = ref(false)

  // 客流数据
  const passengerFlowStats = ref(null)
  const stationFlowData = ref([])
  const allStationsFlowData = ref([])
  const passengerFlowLoading = ref(false)

  // 线网数据
  const networkStations = ref([])
  const networkLines = ref([])
  const networkLoading = ref(false)

  // 获取线路列表
  async function fetchLines() {
    linesLoading.value = true
    try {
      const response = await api.getLines()
      if (response.code === 200) {
        lines.value = response.data
      }
    } catch (error) {
      console.error('获取线路列表失败:', error)
    } finally {
      linesLoading.value = false
    }
  }

  // 保存线路
  async function saveLine(line) {
    try {
      const response = await api.saveLine(line)
      if (response.code === 200) {
        await fetchLines()
        return true
      }
    } catch (error) {
      console.error('保存线路失败:', error)
    }
    return false
  }

  // 删除线路
  async function deleteLine(lineId) {
    try {
      const response = await api.deleteLine(lineId)
      if (response.code === 200) {
        await fetchLines()
        return true
      }
    } catch (error) {
      console.error('删除线路失败:', error)
    }
    return false
  }

  // 获取站点列表
  async function fetchStations(lineId = null) {
    stationsLoading.value = true
    try {
      const response = await api.getStations(lineId)
      if (response.code === 200) {
        stations.value = response.data
      }
    } catch (error) {
      console.error('获取站点列表失败:', error)
    } finally {
      stationsLoading.value = false
    }
  }

  // 保存站点
  async function saveStation(station) {
    try {
      const response = await api.saveStation(station)
      if (response.code === 200) {
        return true
      }
    } catch (error) {
      console.error('保存站点失败:', error)
    }
    return false
  }

  // 获取时刻表
  async function fetchTimetables(lineId) {
    timetablesLoading.value = true
    try {
      const response = await api.getTimetables(lineId)
      if (response.code === 200) {
        timetables.value = response.data
      }
    } catch (error) {
      console.error('获取时刻表失败:', error)
    } finally {
      timetablesLoading.value = false
    }
  }

  // 获取刷卡记录
  async function fetchCardRecords() {
    cardRecordsLoading.value = true
    try {
      const response = await api.getCardRecords()
      if (response.code === 200) {
        cardRecords.value = response.data
      }
    } catch (error) {
      console.error('获取刷卡记录失败:', error)
    } finally {
      cardRecordsLoading.value = false
    }
  }

  // 按卡号查询刷卡记录
  async function fetchCardRecordsByCard(cardId) {
    cardRecordsLoading.value = true
    try {
      const response = await api.getCardRecordsByCard(cardId)
      if (response.code === 200) {
        cardRecords.value = response.data
      }
    } catch (error) {
      console.error('查询刷卡记录失败:', error)
    } finally {
      cardRecordsLoading.value = false
    }
  }

  // 获取客流统计
  async function fetchPassengerFlowStats() {
    passengerFlowLoading.value = true
    try {
      const response = await api.getPassengerFlowStats()
      if (response.code === 200) {
        passengerFlowStats.value = response.data
      }
    } catch (error) {
      console.error('获取客流统计失败:', error)
    } finally {
      passengerFlowLoading.value = false
    }
  }

  // 获取站点客流数据
  async function fetchStationPassengerFlow(stationId) {
    try {
      const response = await api.getStationPassengerFlow(stationId)
      if (response.code === 200) {
        stationFlowData.value = response.data
      }
    } catch (error) {
      console.error('获取站点客流数据失败:', error)
    }
  }

  // 计算客流数据
  async function calculatePassengerFlow() {
    try {
      const response = await api.calculatePassengerFlow()
      if (response.code === 200) {
        await fetchPassengerFlowStats()
        return true
      }
    } catch (error) {
      console.error('计算客流数据失败:', error)
    }
    return false
  }

  // 获取所有站点客流数据（用于图表）
  async function fetchAllStationsFlowData() {
    passengerFlowLoading.value = true
    try {
      const result = []
      // 遍历所有站点，获取每个站点的客流数据
      for (const station of stations.value) {
        const response = await api.getStationPassengerFlow(station['站点编号'])
        if (response.code === 200) {
          const stationData = response.data
          // 计算每个站点的总客流
          if (stationData && stationData.length > 0) {
            const totalInbound = stationData.reduce((sum, d) => sum + (d['进站人数'] || 0), 0)
            const totalOutbound = stationData.reduce((sum, d) => sum + (d['出站人数'] || 0), 0)
            result.push({
              key: station['站点编号'],
              stationId: station['站点编号'],
              stationName: station['站点名称'] || station['站点编号'],
              total: totalInbound + totalOutbound,
              inbound: totalInbound,
              outbound: totalOutbound
            })
          }
        }
      }
      // 按总客流排序
      result.sort((a, b) => b.total - a.total)
      allStationsFlowData.value = result
    } catch (error) {
      console.error('获取所有站点客流数据失败:', error)
      allStationsFlowData.value = []
    } finally {
      passengerFlowLoading.value = false
    }
  }

  // 获取线网数据
  async function fetchNetworkData() {
    networkLoading.value = true
    try {
      const [stationsRes, linesRes] = await Promise.all([
        api.getNetworkStations(),
        api.getNetworkLines()
      ])
      if (stationsRes.code === 200) {
        networkStations.value = stationsRes.data
      }
      if (linesRes.code === 200) {
        networkLines.value = linesRes.data
      }
    } catch (error) {
      console.error('获取线网数据失败:', error)
    } finally {
      networkLoading.value = false
    }
  }

  // AI聊天相关方法
  const STORAGE_KEY = 'chat_history'
  const USE_STREAM = true // 使用流式响应
  
  function loadChatHistory() {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed
        }
      } catch (e) {
        console.error('加载聊天历史失败:', e)
      }
    }
    return [
      { type: 'bot', content: '您好！我是地铁智能助手，有什么可以帮您的吗？' }
    ]
  }
  
  function saveChatHistory() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(chatMessages.value))
    } catch (e) {
      console.error('保存聊天历史失败:', e)
    }
  }
  
  async function sendMessage(question, userId, modelType = null) {
    if (!question.trim()) return
    
    chatMessages.value.push({ type: 'user', content: question.trim() })
    saveChatHistory()
    
    const requestId = Date.now().toString()
    chatLoading.value = true
    pendingRequests.value.set(requestId, true)
    
    // 添加空的 bot 消息用于流式显示
    let botMessageIndex = chatMessages.value.length
    chatMessages.value.push({ type: 'bot', content: '', streaming: true })
    saveChatHistory()
    
    let streamComplete = false
    let hasError = false
    
    const onChunk = (data) => {
      if (!pendingRequests.value.has(requestId)) return
      
      if (data.content) {
        chatMessages.value[botMessageIndex].content += data.content
        saveChatHistory()
      }
      
      if (data.intent) {
        console.log(`[AI] Intent: ${data.intent}`)
      }
      
      if (data.done) {
        streamComplete = true
      }
    }
    
    const onComplete = () => {
      if (pendingRequests.value.has(requestId)) {
        chatMessages.value[botMessageIndex].streaming = false
        saveChatHistory()
        pendingRequests.value.delete(requestId)
        if (pendingRequests.value.size === 0) {
          chatLoading.value = false
        }
      }
    }
    
    const onError = (error) => {
      if (pendingRequests.value.has(requestId)) {
        console.error('流式AI查询失败:', error)
        chatMessages.value[botMessageIndex].content = '抱歉，系统出现错误，请稍后再试。'
        chatMessages.value[botMessageIndex].streaming = false
        saveChatHistory()
        pendingRequests.value.delete(requestId)
        if (pendingRequests.value.size === 0) {
          chatLoading.value = false
        }
      }
    }
    
    try {
      if (USE_STREAM) {
        api.aiQueryStream(question.trim(), userId, modelType, onChunk, onComplete, onError)
      } else {
        // 回退到非流式
        const response = await api.aiQuery(question.trim(), userId, modelType)
        if (pendingRequests.value.has(requestId)) {
          if (response.code === 200) {
            const data = response.data
            chatMessages.value[botMessageIndex].content = data.answer
            chatMessages.value[botMessageIndex].streaming = false
            console.log(`[AI] Intent: ${data.intent}`)
          } else {
            chatMessages.value[botMessageIndex].content = '抱歉，我暂时无法回答这个问题，请稍后再试。'
            chatMessages.value[botMessageIndex].streaming = false
          }
          saveChatHistory()
          pendingRequests.value.delete(requestId)
          if (pendingRequests.value.size === 0) {
            chatLoading.value = false
          }
        }
      }
    } catch (error) {
      onError(error)
    }
  }
  
  function clearChatHistory() {
    chatMessages.value = [{ type: 'bot', content: '您好！我是地铁智能助手，有什么可以帮您的吗？' }]
    saveChatHistory()
  }
  
  function initChat() {
    chatMessages.value = loadChatHistory()
  }

  return {
    // 状态
    chatMessages,
    chatLoading,
    lines,
    linesLoading,
    stations,
    stationsLoading,
    timetables,
    timetablesLoading,
    cardRecords,
    cardRecordsLoading,
    passengerFlowStats,
    stationFlowData,
    allStationsFlowData,
    passengerFlowLoading,
    networkStations,
    networkLines,
    networkLoading,
    // 方法
    sendMessage,
    clearChatHistory,
    initChat,
    fetchLines,
    saveLine,
    deleteLine,
    fetchStations,
    saveStation,
    fetchTimetables,
    fetchCardRecords,
    fetchCardRecordsByCard,
    fetchPassengerFlowStats,
    fetchStationPassengerFlow,
    calculatePassengerFlow,
    fetchAllStationsFlowData,
    fetchNetworkData
  }
})