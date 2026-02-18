<template>
  <v-container fluid>
    <v-row class="mb-4">
      <v-col v-for="stat in stats" :key="stat.label" cols="12" sm="6" md="3">
        <v-card>
          <v-card-text class="text-center">
            <div class="text-h4" :style="{ color: stat.color }">{{ stat.value }}</div>
            <div class="text-caption mt-1">{{ stat.label }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card>
      <v-card-title>🔥 Горячие сделки</v-card-title>
      <v-data-table
        :headers="headers"
        :items="deals"
        :sort-by="[{ key: 'deal_score', order: 'desc' }]"
        @click:row="openDetail"
        hover
      >
        <template #item.deal_score="{ item }">
          <v-chip :color="getScoreColor(item.deal_score)" dark small>
            {{ item.deal_score }}
          </v-chip>
        </template>
        <template #item.price_deviation="{ item }">
          <span class="text-red font-weight-bold">-{{ item.price_deviation }}%</span>
        </template>
        <template #item.start_price="{ item }">
          {{ formatPrice(item.start_price) }} ₽
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="dialog" max-width="800">
      <v-card v-if="selectedDeal">
        <v-card-title>{{ selectedDeal.district }}</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="6">
              <div class="text-caption">Цена</div>
              <div class="text-h5">{{ formatPrice(selectedDeal.start_price) }} ₽</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption">Deal Score</div>
              <div class="text-h5">{{ selectedDeal.deal_score }}/100</div>
            </v-col>
          </v-row>
          <v-row class="mt-4">
            <v-col cols="12">
              <div class="text-caption mb-2">Investment Score</div>
              <v-progress-linear
                :model-value="selectedDeal.investment_score"
                color="success"
                height="20"
              >
                <strong>{{ selectedDeal.investment_score }}%</strong>
              </v-progress-linear>
            </v-col>
            <v-col cols="12">
              <div class="text-caption mb-2">Fraud Risk</div>
              <v-progress-linear
                :model-value="selectedDeal.fraud_risk_score"
                color="error"
                height="20"
              >
                <strong>{{ selectedDeal.fraud_risk_score }}%</strong>
              </v-progress-linear>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-btn color="primary" @click="addToWatchlist">Добавить в Watchlist</v-btn>
          <v-spacer />
          <v-btn @click="dialog = false">Закрыть</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { dealsAPI } from '../api/deals'

const deals = ref([])
const dialog = ref(false)
const selectedDeal = ref(null)

const headers = [
  { title: 'ID', key: 'id', sortable: true },
  { title: 'Район', key: 'district' },
  { title: 'Цена', key: 'start_price' },
  { title: 'Deal Score', key: 'deal_score', sortable: true },
  { title: 'Дисконт', key: 'price_deviation' }
]

const stats = computed(() => [
  { 
    label: '🔥 Hot', 
    value: deals.value.filter(d => d.deal_score >= 80).length,
    color: '#F44336'
  },
  { 
    label: '✅ Good', 
    value: deals.value.filter(d => d.deal_score >= 60 && d.deal_score < 80).length,
    color: '#4CAF50'
  },
  { 
    label: '💎 Gems', 
    value: 0,
    color: '#9C27B0'
  },
  { 
    label: '🎯 Early', 
    value: 0,
    color: '#2196F3'
  }
])

onMounted(async () => {
  try {
    deals.value = await dealsAPI.getHotDeals()
  } catch (error) {
    console.error('Failed to load deals:', error)
  }
})

function openDetail(event, { item }) {
  selectedDeal.value = item
  dialog.value = true
}

function getScoreColor(score) {
  if (score >= 80) return 'error'
  if (score >= 60) return 'warning'
  return 'grey'
}

function formatPrice(price) {
  return new Intl.NumberFormat('ru-RU').format(price)
}

function addToWatchlist() {
  alert('Добавлено в Watchlist!')
}
</script>
