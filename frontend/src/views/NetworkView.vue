<template>
  <div class="network-view">
    <div class="page-header">
      <div class="header-content">
        <h2 class="header-title">线网图</h2>
        <p class="header-subtitle">地铁线路网络可视化</p>
      </div>
      <a-space>
        <a-button type="primary" @click="showAddStationModal">新增站点</a-button>
        <a-button type="primary" @click="showAddLineModal">新增线路</a-button>
        <a-button type="danger" @click="showDeleteModal" :disabled="!selectedNode">删除选中</a-button>
        <a-button type="primary" @click="handleSave" :loading="saving">保存</a-button>
        <a-button type="default" @click="handleReset">重置视图</a-button>
      </a-space>
    </div>

    <div class="stats-section">
      <a-row :gutter="16">
        <a-col :span="8">
          <div class="stat-card">
            <div class="stat-value">{{ stations.length }}</div>
            <div class="stat-label">站点数</div>
          </div>
        </a-col>
        <a-col :span="8">
          <div class="stat-card">
            <div class="stat-value">{{ lines.length }}</div>
            <div class="stat-label">线路数</div>
          </div>
        </a-col>
        <a-col :span="8">
          <div class="stat-card">
            <div class="stat-value">{{ transferCount }}</div>
            <div class="stat-label">换乘站</div>
          </div>
        </a-col>
      </a-row>
    </div>

    <div class="editor-section">
      <a-card class="editor-card" title="编辑面板" :bordered="false">
        <div class="editor-tabs">
          <a-radio-group v-model:value="editMode" button-style="solid">
            <a-radio-button value="view">查看模式</a-radio-button>
            <a-radio-button value="edit">编辑模式</a-radio-button>
          </a-radio-group>
        </div>
        <div class="editor-info" v-if="selectedNode">
          <h4>已选中: {{ selectedNode.name }}</h4>
          <p>X: {{ Math.round(selectedNode.x) }}, Y: {{ Math.round(selectedNode.y) }}</p>
          <a-button type="link" size="small" @click="editSelectedStation">编辑站点信息</a-button>
        </div>
      </a-card>
    </div>

    <div class="network-container">
      <div ref="chartDom" class="network-chart"></div>
    </div>

    <a-modal v-model:open="addStationModalOpen" title="新增站点" @ok="handleAddStation" @cancel="addStationModalOpen = false">
      <a-form :model="newStation">
        <a-form-item label="站点编号">
          <a-input v-model:value="newStation.id" placeholder="如：S11" />
        </a-form-item>
        <a-form-item label="站点名称">
          <a-input v-model:value="newStation.name" placeholder="站点名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="newStation.desc" placeholder="如：3号线起点站" />
        </a-form-item>
        <a-form-item label="X坐标">
          <a-input-number v-model:value="newStation.x" :min="0" :max="800" />
        </a-form-item>
        <a-form-item label="Y坐标">
          <a-input-number v-model:value="newStation.y" :min="0" :max="800" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="addLineModalOpen" title="新增线路" @ok="handleAddLine" @cancel="addLineModalOpen = false">
      <a-form :model="newLine">
        <a-form-item label="线路编号">
          <a-input v-model:value="newLine.id" placeholder="如：L4" />
        </a-form-item>
        <a-form-item label="线路名称">
          <a-input v-model:value="newLine.name" placeholder="线路名称" />
        </a-form-item>
        <a-form-item label="线路颜色">
          <a-color-picker v-model:value="newLine.color" show-text />
        </a-form-item>
        <a-form-item label="站点列表">
          <a-select v-model:value="newLine.stations" mode="multiple" placeholder="选择站点" style="width: 100%">
            <a-select-option v-for="s in stations" :key="s.id" :value="s.id">
              {{ s.id }} - {{ s.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="editStationModalOpen" title="编辑站点" @ok="handleEditStation" @cancel="editStationModalOpen = false">
      <a-form :model="editStation">
        <a-form-item label="站点名称">
          <a-input v-model:value="editStation.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-input v-model:value="editStation.desc" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="deleteModalOpen" title="确认删除" @ok="handleDelete" @cancel="deleteModalOpen = false">
      <p>确定要删除站点 {{ deleteTarget?.name }} 吗？</p>
      <p>相关线路也会受到影响。</p>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { useSubwayStore } from '../stores/subway';
import * as echarts from 'echarts';
import api from '../api';

const store = useSubwayStore();
const chartDom = ref(null);
let chartInstance = null;

const editMode = ref('view');
const selectedNode = ref(null);
const saving = ref(false);

const stations = ref([]);
const lines = ref([]);

const addStationModalOpen = ref(false);
const addLineModalOpen = ref(false);
const editStationModalOpen = ref(false);
const deleteModalOpen = ref(false);

const newStation = ref({ id: '', name: '', desc: '', x: 400, y: 400 });
const newLine = ref({ id: '', name: '', color: '#1890ff', stations: [] });
const editStation = ref({ id: '', name: '', desc: '' });
const deleteTarget = ref(null);

const transferCount = computed(() => {
  let count = 0;
  const stationLines = {};
  lines.value.forEach(line => {
    line.stations.forEach(stationId => {
      if (!stationLines[stationId]) stationLines[stationId] = [];
      stationLines[stationId].push(line.id);
    });
  });
  Object.values(stationLines).forEach(lineList => {
    if (lineList.length > 1) count++;
  });
  return count;
});

const checkIsTransfer = (stationId) => {
  let lineCount = 0;
  lines.value.forEach(line => {
    if (line.stations.includes(stationId)) lineCount++;
  });
  return lineCount > 1;
};

const initChart = () => {
  if (!chartDom.value) return;
  chartInstance = echarts.init(chartDom.value);
  window.addEventListener('resize', handleResize);
  renderChart();
  setupEvents();
};

const renderChart = () => {
  if (!chartInstance) return;

  const nodes = stations.value.map(station => {
    const isTransfer = checkIsTransfer(station.id);
    return {
      id: station.id,
      name: station.name,
      x: station.x,
      y: station.y,
      symbolSize: isTransfer ? 30 : 20,
      value: station.desc || '',
      category: 'default',
      itemStyle: {
        color: isTransfer ? '#faad14' : '#1890ff',
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'right',
        distance: 6,
        color: '#333',
        fontSize: 11,
        formatter: station.id
      }
    };
  });

  const links = [];
  lines.value.forEach(line => {
    const lineStations = line.stations;
    for (let i = 0; i < lineStations.length - 1; i++) {
      if (lineStations[i] && lineStations[i + 1]) {
        links.push({
          source: lineStations[i],
          target: lineStations[i + 1],
          lineStyle: {
            color: line.color || '#1890ff',
            width: 4,
            curveness: 0
          }
        });
      }
    }
  });

  const categories = [{ name: 'default' }];

  const option = {
    backgroundColor: '#f8fafc',
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          const station = stations.value.find(s => s.id === params.name);
          const stationName = station ? station.name : '';
          const desc = station ? station.desc : '';
          return `<div><strong>${params.name} ${stationName}</strong><br/>${desc || ''}</div>`;
        }
        return '';
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: editMode.value === 'view',
        draggable: editMode.value === 'edit',
        nodeScaleRatio: 0,
        label: { show: true, position: 'right', formatter: '{b}' },
        lineStyle: { color: 'source', curveness: 0 },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 6 }
        },
        data: nodes,
        links: links,
        categories: categories
      }
    ]
  };

  chartInstance.setOption(option, true);
};

const setupEvents = () => {
  if (!chartInstance) return;

  // 点击选中
  chartInstance.on('click', (params) => {
    if (params.dataType === 'node') {
      selectedNode.value = {
        id: params.data.id,
        name: params.data.name,
        x: params.data.x,
        y: params.data.y
      };
    }
  });

  // 节点拖拽结束，更新本地数据并保存到数据库
  chartInstance.on('mouseup', async () => {
    if (editMode.value === 'edit' && chartInstance) {
      const option = chartInstance.getOption();
      if (option?.series?.[0]?.data) {
        const nodes = option.series[0].data;
        // 收集所有需要保存的站点
        const updates = [];
        nodes.forEach(node => {
          const station = stations.value.find(s => s.id === node.id);
          if (station) {
            station.x = node.x;
            station.y = node.y;
            if (selectedNode.value && selectedNode.value.id === node.id) {
              selectedNode.value.x = node.x;
              selectedNode.value.y = node.y;
            }
            updates.push(station);
          }
        });
        // 批量保存到数据库
        if (updates.length > 0) {
          try {
            await Promise.all(updates.map(station =>
              api.saveNetworkStation({
                station_id: station.id,
                station_name: station.name,
                x: station.x,
                y: station.y,
                description: station.desc || ''
              })
            ));
            message.success('位置已保存');
          } catch (e) {
            console.error('保存位置失败:', e);
          }
        }
      }
    }
  });
};

const handleResize = () => chartInstance?.resize();

const handleReset = () => {
  chartInstance?.dispatchAction({ type: 'restore' });
  message.success('视图已重置');
};

const handleSave = async () => {
  Modal.confirm({
    title: '确认保存',
    content: '确定要保存所有修改吗？这会更新数据库中的线网图数据。',
    onOk: async () => {
      saving.value = true;
      try {
        for (const station of stations.value) {
          await api.saveNetworkStation({
            station_id: station.id,
            station_name: station.name,
            x: station.x,
            y: station.y,
            description: station.desc || ''
          });
        }
        for (const line of lines.value) {
          await api.saveNetworkLine({
            path_id: line.id,
            line_id: line.id,
            line_name: line.name || line.id,
            start_station: line.stations[0] || '',
            end_station: line.stations[line.stations.length - 1] || '',
            station_list: line.stations.join(','),
            line_color: line.color
          });
        }
        message.success('保存成功！所有更改已同步到数据库');
      } catch (error) {
        console.error('保存失败:', error);
        message.error('保存失败，请稍后重试');
      } finally {
        saving.value = false;
      }
    }
  });
};

const showAddStationModal = () => {
  newStation.value = { id: '', name: '', desc: '', x: 400, y: 400 };
  addStationModalOpen.value = true;
};

const handleAddStation = () => {
  if (!newStation.value.id || !newStation.value.name) {
    message.warning('请填写站点编号和名称');
    return;
  }
  stations.value.push({
    id: newStation.value.id,
    name: newStation.value.name,
    desc: newStation.value.desc,
    x: newStation.value.x,
    y: newStation.value.y
  });
  addStationModalOpen.value = false;
  message.success('站点添加成功，请点击保存按钮同步到数据库');
  renderChart();
};

const showAddLineModal = () => {
  newLine.value = { id: '', name: '', color: '#1890ff', stations: [] };
  addLineModalOpen.value = true;
};

const handleAddLine = () => {
  if (!newLine.value.id || !newLine.value.name || newLine.value.stations.length < 2) {
    message.warning('请填写线路信息并至少选择2个站点');
    return;
  }
  lines.value.push({
    id: newLine.value.id,
    name: newLine.value.name,
    color: newLine.value.color,
    stations: newLine.value.stations
  });
  addLineModalOpen.value = false;
  message.success('线路添加成功，请点击保存按钮同步到数据库');
  renderChart();
};

const editSelectedStation = () => {
  if (!selectedNode.value) return;
  const station = stations.value.find(s => s.id === selectedNode.value.id);
  if (station) {
    editStation.value = { id: station.id, name: station.name, desc: station.desc || '' };
    editStationModalOpen.value = true;
  }
};

const handleEditStation = () => {
  const station = stations.value.find(s => s.id === editStation.value.id);
  if (station) {
    station.name = editStation.value.name;
    station.desc = editStation.value.desc;
  }
  editStationModalOpen.value = false;
  message.success('站点更新成功，请点击保存按钮同步到数据库');
  renderChart();
};

const showDeleteModal = () => {
  if (selectedNode.value) {
    deleteTarget.value = selectedNode.value;
    deleteModalOpen.value = true;
  }
};

const handleDelete = async () => {
  if (!deleteTarget.value) return;
  saving.value = true;
  try {
    // 1. 从数据库删除站点
    try {
      await api.deleteNetworkStation(deleteTarget.value.id);
    } catch (e) {
      console.warn('从数据库删除站点失败，但继续本地删除:', e);
    }

    // 2. 更新所有包含该站点的线路
    for (const line of lines.value) {
      if (line.stations.includes(deleteTarget.value.id)) {
        const newStations = line.stations.filter(s => s !== deleteTarget.value.id);
        if (newStations.length >= 2) {
          try {
            await api.saveNetworkLine({
              path_id: line.id,
              line_id: line.id,
              line_name: line.name || line.id,
              start_station: newStations[0] || '',
              end_station: newStations[newStations.length - 1] || '',
              station_list: newStations.join(','),
              line_color: line.color
            });
          } catch (e) {
            console.warn('更新线路失败:', line.id, e);
          }
        }
      }
    }

    // 3. 从本地数据中删除站点
    stations.value = stations.value.filter(s => s.id !== deleteTarget.value.id);
    lines.value = lines.value.map(line => ({
      ...line,
      stations: line.stations.filter(s => s !== deleteTarget.value.id)
    })).filter(line => line.stations.length > 1);

    selectedNode.value = null;
    deleteTarget.value = null;
    deleteModalOpen.value = false;
    message.success('删除成功！');
    renderChart();
  } catch (error) {
    console.error('删除失败:', error);
    message.error('删除失败，请稍后重试');
  } finally {
    saving.value = false;
  }
};

const loadData = async () => {
  try {
    console.log('=== 开始加载数据 ===');
    
    console.log('1. 加载站点数据...');
    const stationsRes = await api.getStations();
    console.log('站点API返回:', stationsRes);
    
    if (stationsRes.code === 200) {
      stations.value = stationsRes.data.map(s => ({
        id: s['站点编号'],
        name: s['站点名称'] || s['站点编号'],
        desc: s['描述'] || '',
        x: s['x坐标'] || 0,
        y: s['y坐标'] || 0
      }));
      console.log('站点数据加载完成:', stations.value);
    }

    console.log('2. 加载线路数据...');
    const linesRes = await api.getNetworkLines();
    console.log('线路API返回:', linesRes);

    if (linesRes.code === 200) {
      lines.value = linesRes.data.map(l => ({
        id: l['线路编号'],
        name: l['线路名称'] || l['线路编号'],
        color: l['线路颜色'],
        stations: l['站点列表']?.split(',') || []
      }));
      console.log('线路数据加载完成:', lines.value);
    }

    console.log('=== 数据加载完成 ===');

  } catch (error) {
    console.error('=== 加载数据失败 ===');
    console.error('Error details:', error);
    console.error('Error message:', error?.message);
    message.error('加载数据失败，请检查后端服务或控制台');
  }
};

watch(editMode, () => {
  if (chartInstance) renderChart();
});

onMounted(async () => {
  await loadData();
  await store.fetchStations();
  await nextTick();
  await new Promise(resolve => setTimeout(resolve, 100));
  initChart();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
});
</script>

<style scoped lang="scss">
.network-view {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-content {
      .header-title {
        margin: 0 0 4px 0;
        font-size: 20px;
        font-weight: 600;
        color: #333;
      }

      .header-subtitle {
        margin: 0;
        font-size: 14px;
        color: #666;
      }
    }
  }

  .stats-section {
    margin-bottom: 20px;

    .stat-card {
      padding: 16px;
      background: #f5f5f5;
      border: 1px solid #e8e8e8;
      border-radius: 4px;
      height: 80px;
      box-sizing: border-box;

      .stat-value {
        font-size: 20px;
        font-weight: 600;
        color: #1890ff;
        margin-bottom: 4px;
        line-height: 1.2;
      }

      .stat-label {
        font-size: 13px;
        color: #666;
      }
    }
  }

  .editor-section {
    margin-bottom: 20px;

    .editor-card {
      :deep(.ant-card-head) {
        border-bottom: 1px solid #e8e8e8;
      }

      :deep(.ant-card-head-title) {
        font-weight: 600;
        font-size: 15px;
        color: #333;
      }

      .editor-tabs {
        margin-bottom: 16px;
      }

      .editor-info {
        h4 {
          margin: 0 0 8px 0;
          font-size: 14px;
          color: #333;
        }
        p {
          margin: 0 0 8px 0;
          font-size: 13px;
          color: #666;
        }
      }
    }
  }

  .network-container {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 4px;
    padding: 16px;

    .network-chart {
      width: 100%;
      height: 600px;
    }
  }
}

@media (max-width: 768px) {
  .network-view {
    padding: 12px;

    .page-header {
      flex-direction: column;
      align-items: flex-start;

      .header-content {
        .header-title {
          font-size: 18px;
        }
      }
    }

    .network-container {
      padding: 12px;

      .network-chart {
        height: 450px;
      }
    }
  }
}
</style>
