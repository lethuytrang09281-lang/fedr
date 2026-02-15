<template>
  <v-container fluid class="pa-4">
    <v-alert v-if="error" type="error" class="mb-4" closable @click:close="error = null">
      {{ error }}
    </v-alert>

    <StatsCards :deals="deals" />

    <DealsTable :deals="deals" @select="openDetail" />

    <v-dialog v-model="dialog" max-width="800">
      <DealDetail :deal="selectedDeal" @close="dialog = false" />
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { dealsAPI } from '@/api/deals'
import StatsCards from '@/components/StatsCards.vue'
import DealsTable from '@/components/DealsTable.vue'
import DealDetail from '@/components/DealDetail.vue'

const deals = ref([])
const dialog = ref(false)
const selectedDeal = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    deals.value = await dealsAPI.getHotDeals()
  } catch (e) {
    error.value = 'Не удалось загрузить данные: ' + e.message
  }
})

function openDetail(deal) {
  selectedDeal.value = deal
  dialog.value = true
}
</script>
