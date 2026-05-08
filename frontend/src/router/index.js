import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/lines'
  },
  {
    path: '/lines',
    name: 'Lines',
    component: () => import('../views/LinesView.vue')
  },
  {
    path: '/stations',
    name: 'Stations',
    component: () => import('../views/StationsView.vue')
  },
  {
    path: '/timetables',
    name: 'Timetables',
    component: () => import('../views/TimetablesView.vue')
  },
  {
    path: '/card-records',
    name: 'CardRecords',
    component: () => import('../views/CardRecordsView.vue')
  },
  {
    path: '/passenger-flow',
    name: 'PassengerFlow',
    component: () => import('../views/PassengerFlowView.vue')
  },
  {
    path: '/ai-chat',
    name: 'AIChat',
    component: () => import('../views/AIChatView.vue')
  },
  {
    path: '/network',
    name: 'Network',
    component: () => import('../views/NetworkView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router