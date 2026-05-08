<template>
  <div class="stations-view">
    <div class="page-header">
      <h2>站点管理</h2>
      <a-space>
        <a-select
          v-model:value="selectedLineId"
          placeholder="选择线路"
          style="width: 200px"
          @change="handleLineChange"
        >
          <a-select-option v-for="line in store.lines" :key="line['线路编号']" :value="line['线路编号']">
            {{ line['线路名称'] }}
          </a-select-option>
        </a-select>
        <a-button type="primary" @click="showAddModal = true" :disabled="!selectedLineId">
          <template #icon><PlusOutlined /></template>
          添加站点
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="store.stations"
      :loading="store.stationsLoading"
      row-key="站点编号"
      :pagination="{ pageSize: 10 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link" @click="handleEdit(record)">编辑</a-button>
            <a-popconfirm
              title="确定要删除这个站点吗？"
              @confirm="handleDelete(record['站点编号'])"
            >
              <a-button type="link" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="showAddModal"
      :title="editingStation ? '编辑站点' : '添加站点'"
      @ok="handleSave"
      @cancel="handleCancel"
      :confirm-loading="saving"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item label="站点编号" name="站点编号">
          <a-input v-model:value="formData['站点编号']" placeholder="例如：S1" />
        </a-form-item>
        <a-form-item label="所属线路" name="所属线路编号">
          <a-select v-model:value="formData['所属线路编号']">
            <a-select-option v-for="line in store.lines" :key="line['线路编号']" :value="line['线路编号']">
              {{ line['线路名称'] }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="可换乘线路" name="可换乘线路">
          <a-input v-model:value="formData['可换乘线路']" placeholder="例如：2号线,3号线" />
        </a-form-item>
        <a-form-item label="站点序号" name="站点序号">
          <a-input-number v-model:value="formData['站点序号']" :min="1" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { useSubwayStore } from '../stores/subway'

const store = useSubwayStore()

const selectedLineId = ref(null)
const showAddModal = ref(false)
const editingStation = ref(null)
const saving = ref(false)
const formRef = ref(null)

const formData = reactive({
  '站点编号': '',
  '所属线路编号': '',
  '可换乘线路': '',
  '站点序号': 1
})

const rules = {
  '站点编号': [{ required: true, message: '请输入站点编号' }],
  '所属线路编号': [{ required: true, message: '请选择线路' }]
}

const columns = [
  { title: '站点编号', dataIndex: '站点编号', key: '站点编号' },
  { title: '所属线路', dataIndex: '所属线路编号', key: '所属线路编号' },
  { title: '可换乘线路', dataIndex: '可换乘线路', key: '可换乘线路' },
  { title: '站点序号', dataIndex: '站点序号', key: '站点序号' },
  { title: '操作', key: 'action', width: 200 }
]

onMounted(() => {
  store.fetchLines()
})

const handleLineChange = (lineId) => {
  if (lineId) {
    store.fetchStations(lineId)
  }
}

const handleEdit = (record) => {
  editingStation.value = record
  Object.assign(formData, record)
  showAddModal.value = true
}

const handleDelete = async (stationId) => {
  // 实现删除逻辑
  message.success('删除成功')
}

const handleSave = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    const success = await store.saveStation({ ...formData })
    if (success) {
      message.success(editingStation.value ? '编辑成功' : '添加成功')
      handleCancel()
      if (selectedLineId.value) {
        store.fetchStations(selectedLineId.value)
      }
    }
  } catch (error) {
    console.error('表单验证失败:', error)
  } finally {
    saving.value = false
  }
}

const handleCancel = () => {
  showAddModal.value = false
  editingStation.value = null
  formRef.value?.resetFields()
}
</script>

<style scoped lang="scss">
.stations-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    h2 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }
  }
}
</style>