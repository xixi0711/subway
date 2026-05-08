<template>
  <a-layout class="layout">
    <a-layout-sider 
      v-model:collapsed="collapsed" 
      class="sider" 
      width="240"
      theme="dark"
      :trigger="null"
      collapsible
      breakpoint="lg"
      collapsedWidth="64"
    >
      <div class="logo">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#1890ff"/>
            <path d="M2 17L12 22L22 17" stroke="#1890ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="#1890ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="logo-text" v-if="!collapsed">地铁智能问答</div>
      </div>
      <a-menu
        v-model:selectedKeys="current"
        theme="dark"
        mode="inline"
        :items="menuItems"
        @click="handleMenuClick"
        class="sidebar-menu"
      />
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="header">
        <a-button
          type="text"
          class="trigger"
          @click="collapsed = !collapsed"
        >
          <MenuFoldOutlined v-if="!collapsed" class="trigger-icon" />
          <MenuUnfoldOutlined v-else class="trigger-icon" />
        </a-button>
        <h1 class="page-title" v-if="collapsed">地铁智能问答系统</h1>
      </a-layout-header>
      <a-layout-content class="content">
        <div class="page-container">
          <router-view />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { ref, watch, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { 
  LineChartOutlined, 
  EnvironmentOutlined, 
  ClockCircleOutlined, 
  CreditCardOutlined, 
  BarChartOutlined, 
  RobotOutlined, 
  LinkOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()

const current = ref(['lines'])
const collapsed = ref(false)

const menuItems = [
  { 
    key: 'lines', 
    label: '线路管理', 
    icon: () => h(LineChartOutlined)
  },
  { 
    key: 'stations', 
    label: '站点管理', 
    icon: () => h(EnvironmentOutlined)
  },
  { 
    key: 'timetables', 
    label: '时刻表', 
    icon: () => h(ClockCircleOutlined)
  },
  { 
    key: 'card-records', 
    label: '刷卡记录', 
    icon: () => h(CreditCardOutlined)
  },
  { 
    key: 'passenger-flow', 
    label: '客流分析', 
    icon: () => h(BarChartOutlined)
  },
  { 
    key: 'ai-chat', 
    label: 'AI问答', 
    icon: () => h(RobotOutlined)
  },
  { 
    key: 'network', 
    label: '线网图', 
    icon: () => h(LinkOutlined)
  }
]

const handleMenuClick = ({ key }) => {
  router.push(`/${key}`)
}

watch(() => route.path, (path) => {
  const key = path.replace('/', '')
  if (key) {
    current.value = [key]
  }
}, { immediate: true })
</script>

<style scoped lang="scss">
.layout {
  min-height: 100vh;
}

.sider {
  background: #001529;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  z-index: 10;

  .logo {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 0 20px;
    height: 64px;
    background: #002140;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);

    .logo-icon {
      width: 28px;
      height: 28px;
      flex-shrink: 0;
      
      svg {
        width: 100%;
        height: 100%;
      }
    }

    .logo-text {
      margin-left: 12px;
      font-size: 15px;
      font-weight: 600;
      color: white;
      white-space: nowrap;
    }
  }

  :deep(.sidebar-menu) {
    margin-top: 8px;
    border: none;
    background: transparent;

    .ant-menu-item {
      margin: 2px 8px;
      height: 44px;
      line-height: 44px;
      border-radius: 6px;
      transition: all 0.2s ease;
      font-weight: 400;
      color: rgba(255, 255, 255, 0.85);

      &::after {
        display: none;
      }

      &:hover {
        background: rgba(255, 255, 255, 0.08) !important;
        color: white;
      }

      &.ant-menu-item-selected {
        background: #1890ff !important;
        color: white;

        &:hover {
          background: #40a9ff !important;
        }
      }

      .anticon {
        font-size: 16px;
      }
    }
  }
}

.header {
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  height: 64px;
  z-index: 9;

  .trigger {
    width: 36px;
    height: 36px;
    border-radius: 4px;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 16px;

    &:hover {
      background: #f0f2f5;
      color: #1890ff;
    }

    .trigger-icon {
      font-size: 18px;
    }
  }

  .page-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #262626;
  }
}

.content {
  background: #f0f2f5;
  padding: 24px;
  min-height: calc(100vh - 64px);
}

.page-container {
  background: white;
  border-radius: 8px;
  padding: 24px;
  min-height: calc(100vh - 112px);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03), 0 2px 4px rgba(0, 0, 0, 0.03);
}

@media (max-width: 768px) {
  .content {
    padding: 16px;
  }

  .page-container {
    padding: 16px;
    border-radius: 6px;

    .page-title {
      font-size: 16px;
    }
  }

  .header {
    padding: 0 16px;

    .trigger {
      margin-right: 12px;
    }
  }
}
</style>