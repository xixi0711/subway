import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export const api = {
  // 线路管理
  getLines() {
    return apiClient.get('/lines')
  },
  saveLine(line) {
    return apiClient.post('/lines', line)
  },
  deleteLine(lineId) {
    return apiClient.delete(`/lines/${lineId}`)
  },

  // 站点管理
  getStations(lineId = null) {
    if (lineId) {
      return apiClient.get(`/stations?line_id=${lineId}`)
    } else {
      return apiClient.get('/stations')
    }
  },
  saveStation(station) {
    return apiClient.post('/stations', station)
  },
  deleteStation(stationId) {
    return apiClient.delete(`/stations/${stationId}`)
  },

  // 时刻表管理
  getTimetables(lineId) {
    return apiClient.get(`/timetables?line_id=${lineId}`)
  },
  saveTimetable(timetable) {
    return apiClient.post('/timetables', timetable)
  },
  deleteTimetable(trainId, stationCode) {
    return apiClient.delete('/timetables', {
      data: { '列车编号': trainId, '途经站点编号': stationCode }
    })
  },

  // 刷卡记录
  getCardRecords() {
    return apiClient.get('/card-records')
  },
  getCardRecordsByCard(cardId) {
    return apiClient.get(`/card-records/by-card?card_id=${cardId}`)
  },

  // 客流分析
  getPassengerFlowStats() {
    return apiClient.get('/passenger-flow/stats')
  },
  getStationPassengerFlow(stationId) {
    return apiClient.get(`/passenger-flow/station/${stationId}`)
  },
  calculatePassengerFlow() {
    return apiClient.post('/passenger-flow/calculate')
  },

  // AI问答
  aiQuery(question, userId = 'default') {
    return apiClient.post('/ai-query', { question, user_id: userId })
  },
  clearCache() {
    return apiClient.post('/cache/clear')
  },

  // 线网图
  getNetworkStations() {
    return apiClient.get('/network/stations')
  },
  getNetworkLines() {
    return apiClient.get('/network/lines')
  },
  saveNetworkStation(station) {
    return apiClient.post('/network/stations', station)
  },
  saveNetworkLine(line) {
    return apiClient.post('/network/lines', line)
  },
  deleteNetworkStation(stationId) {
    return apiClient.delete(`/network/stations/${stationId}`)
  },
  deleteNetworkLine(lineId) {
    return apiClient.delete(`/network/lines/${lineId}`)
  },

  // RAG知识库
  buildKnowledgeBase() {
    return apiClient.post('/knowledge/build')
  }
}

export default api