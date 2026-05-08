<template>
  <div class="card-records-view">
    <div class="page-header">
      <h2>刷卡记录查询</h2>
    </div>

    <a-card>
      <a-space style="margin-bottom: 16px">
        <a-input-search v-model:value="cardId" placeholder="输入卡号" style="width: 200px" @search="handleSearch" />
        <a-button type="primary" @click="handleSearch">查询</a-button>
      </a-space>

      <a-table
        :columns="columns"
        :data-source="store.cardRecords"
        :loading="store.cardRecordsLoading"
        row-key="交易编号"
        :pagination="{ pageSize: 10 }"
      />
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useSubwayStore } from '../stores/subway'

const store = useSubwayStore()
const cardId = ref('')

const columns = [
  { title: '交易编号', dataIndex: '交易编号', key: '交易编号' },
  { title: '卡号', dataIndex: '卡号', key: '卡号' },
  { title: '进站站点', dataIndex: '进站站点', key: '进站站点' },
  { title: '进站时间', dataIndex: '进站时间', key: '进站时间' },
  { title: '出站站点', dataIndex: '出站站点', key: '出站站点' },
  { title: '出站时间', dataIndex: '出站时间', key: '出站时间' },
  { title: '交易金额', dataIndex: '交易金额', key: '交易金额' }
]

const handleSearch = () => {
  if (cardId.value) {
    store.fetchCardRecordsByCard(cardId.value)
  } else {
    store.fetchCardRecords()
  }
}

onMounted(() => {
  store.fetchCardRecords()
})
</script>

<style scoped lang="scss">
.card-records-view {
  .page-header {
    margin-bottom: 24px;
    h2 { margin: 0; font-size: 24px; font-weight: 600; }
  }
}
</style>