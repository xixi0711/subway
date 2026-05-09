<template>
  <div class="timetables-view">
    <div class="page-header">
      <h2>时刻表管理</h2>
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
          添加时刻表
        </a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="store.timetables"
      :loading="store.timetablesLoading"
      row-key="列车编号"
      :pagination="{ pageSize: 10 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button type="link">编辑</a-button>
            <a-popconfirm title="确定要删除吗？" @confirm="handleDelete(record)">
              <a-button type="link" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="showAddModal" title="添加时刻表" @ok="handleSave" @cancel="handleCancel">
      <a-form ref="formRef" :model="formData" layout="vertical">
        <a-form-item label="列车编号" name="列车编号">
          <a-input v-model:value="formData['列车编号']" />
        </a-form-item>
        <a-form-item label="运行方向" name="运行方向">
          <a-select v-model:value="formData['运行方向']">
            <a-select-option value="上行">上行</a-select-option>
            <a-select-option value="下行">下行</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="途经站点编号" name="途经站点编号">
          <a-input v-model:value="formData['途经站点编号']" placeholder="例如：S1" />
        </a-form-item>
        <a-form-item label="到站时间" name="到站时间">
          <a-time-picker v-model:value="formData['到站时间']" format="HH:mm" />
        </a-form-item>
        <a-form-item label="发车时间" name="发车时间">
          <a-time-picker v-model:value="formData['发车时间']" format="HH:mm" />
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
const formRef = ref(null)

const formData = reactive({
  '列车编号': '',
  '所属线路编号': '',
  '运行方向': '上行',
  '途经站点编号': '',
  '到站时间': null,
  '发车时间': null
})

const columns = [
  { title: '列车编号', dataIndex: '列车编号', key: '列车编号' },
  { title: '线路', dataIndex: '所属线路编号', key: '所属线路编号' },
  { title: '运行方向', dataIndex: '运行方向', key: '运行方向' },
  { title: '到站时间', dataIndex: '到站时间', key: '到站时间' },
  { title: '发车时间', dataIndex: '发车时间', key: '发车时间' },
  { title: '操作', key: 'action', width: 200 }
]

onMounted(() => {
  store.fetchLines()
})

const handleLineChange = (lineId) => {
  if (lineId) {
    store.fetchTimetables(lineId)
    formData['所属线路编号'] = lineId
  }
}

const handleDelete = (record) => {
  message.success('删除成功')
}

const handleSave = async () => {
  message.success('添加成功')
  handleCancel()
}

const handleCancel = () => {
  showAddModal.value = false
  formRef.value?.resetFields()
}
</script>

<style scoped lang="scss">
.timetables-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    h2 { margin: 0; font-size: 24px; font-weight: 600; }
  }
}
</style>