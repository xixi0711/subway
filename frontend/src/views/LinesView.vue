<template>
  <div class="lines-view">
    <div class="page-header">
      <div class="header-content">
        <h2 class="header-title">线路管理</h2>
        <p class="header-subtitle">管理地铁线路信息</p>
      </div>
      <a-button 
        type="primary" 
        @click="showAddModal = true"
      >
        添加线路
      </a-button>
    </div>

    <div class="table-container">
      <a-table
        :columns="columns"
        :data-source="store.lines"
        :loading="store.linesLoading"
        row-key="线路编号"
        :pagination="{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }"
        :bordered="false"
        :scroll="{ x: 800 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space size="middle">
              <a-button 
                type="link" 
                @click="handleEdit(record)"
              >
                <template #icon><EditOutlined /></template>
                编辑
              </a-button>
              <a-popconfirm
                title="确定要删除这条线路吗？"
                @confirm="handleDelete(record['线路编号'])"
                ok-text="确定"
                cancel-text="取消"
              >
                <a-button 
                  type="link" 
                  danger
                >
                  <template #icon><DeleteOutlined /></template>
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="showAddModal"
      :title="editingLine ? '编辑线路' : '添加线路'"
      @ok="handleSave"
      @cancel="handleCancel"
      :confirm-loading="saving"
      :width="500"
      :mask-closable="false"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        layout="vertical"
      >
        <a-form-item label="线路编号" name="线路编号">
          <a-input 
            v-model:value="formData['线路编号']" 
            placeholder="例如：L1" 
          />
        </a-form-item>
        <a-form-item label="线路名称" name="线路名称">
          <a-input 
            v-model:value="formData['线路名称']" 
            placeholder="例如：一号线" 
          />
        </a-form-item>
        <a-form-item label="首班车时间" name="首班车时间">
          <a-time-picker 
            v-model:value="formData['首班车时间']" 
            format="HH:mm" 
          />
        </a-form-item>
        <a-form-item label="末班车时间" name="末班车时间">
          <a-time-picker 
            v-model:value="formData['末班车时间']" 
            format="HH:mm" 
          />
        </a-form-item>
        <a-form-item label="起点站点" name="起点站点">
          <a-input 
            v-model:value="formData['起点站点']" 
            placeholder="例如：S1" 
          />
        </a-form-item>
        <a-form-item label="终点站点" name="终点站点">
          <a-input 
            v-model:value="formData['终点站点']" 
            placeholder="例如：S10" 
          />
        </a-form-item>
        <a-form-item label="站点列表" name="站点列表">
          <a-input 
            v-model:value="formData['站点列表']" 
            placeholder="逗号分隔，例如：S1,S2,S3" 
          />
        </a-form-item>
        <a-form-item label="线路颜色" name="线路颜色">
          <a-input 
            v-model:value="formData['线路颜色']" 
            placeholder="例如：#1890ff" 
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { useSubwayStore } from '../stores/subway'
import dayjs from 'dayjs'

const store = useSubwayStore()

const showAddModal = ref(false)
const editingLine = ref(null)
const saving = ref(false)
const formRef = ref(null)

const formData = reactive({
  '线路编号': '',
  '线路名称': '',
  '首班车时间': null,
  '末班车时间': null,
  '起点站点': '',
  '终点站点': '',
  '站点列表': '',
  '线路颜色': '#1890ff'
})

const rules = {
  '线路编号': [{ required: true, message: '请输入线路编号' }],
  '线路名称': [{ required: true, message: '请输入线路名称' }]
}

const columns = [
  { 
    title: '线路编号', 
    dataIndex: '线路编号', 
    key: '线路编号',
    width: 120,
    sorter: (a, b) => a['线路编号'].localeCompare(b['线路编号'])
  },
  { 
    title: '线路名称', 
    dataIndex: '线路名称', 
    key: '线路名称',
    width: 150,
    sorter: (a, b) => a['线路名称'].localeCompare(b['线路名称'])
  },
  { 
    title: '首班车时间', 
    dataIndex: '首班车时间', 
    key: '首班车时间',
    width: 120
  },
  { 
    title: '末班车时间', 
    dataIndex: '末班车时间', 
    key: '末班车时间',
    width: 120
  },
  { 
    title: '操作', 
    key: 'action', 
    width: 180,
    fixed: 'right'
  }
]

onMounted(() => {
  store.fetchLines()
})

const handleEdit = (record) => {
  editingLine.value = record
  formData['线路编号'] = record['线路编号']
  formData['线路名称'] = record['线路名称']
  formData['起点站点'] = record['起点站点'] || ''
  formData['终点站点'] = record['终点站点'] || ''
  formData['站点列表'] = record['站点列表'] || ''
  formData['线路颜色'] = record['线路颜色'] || '#1890ff'
  
  // 处理时间字段，从字符串转换为dayjs对象
  if (record['首班车时间']) {
    formData['首班车时间'] = dayjs(record['首班车时间'], 'HH:mm')
  } else {
    formData['首班车时间'] = null
  }
  
  if (record['末班车时间']) {
    formData['末班车时间'] = dayjs(record['末班车时间'], 'HH:mm')
  } else {
    formData['末班车时间'] = null
  }
  
  showAddModal.value = true
}

const handleDelete = async (lineId) => {
  const success = await store.deleteLine(lineId)
  if (success) {
    message.success('删除成功')
  } else {
    message.error('删除失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    
    // 转换时间格式为字符串
    const saveData = { ...formData }
    if (saveData['首班车时间']) {
      saveData['首班车时间'] = saveData['首班车时间'].format('HH:mm')
    } else {
      saveData['首班车时间'] = null
    }
    if (saveData['末班车时间']) {
      saveData['末班车时间'] = saveData['末班车时间'].format('HH:mm')
    } else {
      saveData['末班车时间'] = null
    }
    
    const success = await store.saveLine(saveData)
    if (success) {
      message.success(editingLine.value ? '编辑成功' : '添加成功')
      handleCancel()
    } else {
      message.error('操作失败')
    }
  } catch (error) {
    console.error('表单验证失败:', error)
  } finally {
    saving.value = false
  }
}

const handleCancel = () => {
  showAddModal.value = false
  editingLine.value = null
  formRef.value?.resetFields()
  Object.assign(formData, {
    '线路编号': '',
    '线路名称': '',
    '首班车时间': null,
    '末班车时间': null,
    '起点站点': '',
    '终点站点': '',
    '站点列表': '',
    '线路颜色': '#1890ff'
  })
}
</script>

<style scoped lang="scss">
.lines-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;

    .header-content {
      .header-title {
        margin: 0 0 6px 0;
        font-size: 20px;
        font-weight: 600;
        color: #262626;
      }

      .header-subtitle {
        margin: 0;
        font-size: 14px;
        color: #8c8c8c;
      }
    }
  }

  .table-container {
    background: white;
    border: 1px solid #f0f0f0;
    border-radius: 4px;
    padding: 16px;

    :deep(.ant-table-header) {
      th {
        font-weight: 600;
        color: #262626;
        background: #fafafa !important;
      }
    }
  }
}
</style>