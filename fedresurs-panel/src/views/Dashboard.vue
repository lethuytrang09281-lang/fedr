<template>
  <div class="p-6 space-y-6">
    <!-- Error Alert -->
    <div
      v-if="error"
      class="glass-panel rounded p-4 border-l-4 border-red-500 flex items-center justify-between"
    >
      <div class="flex items-center gap-3">
        <span class="material-symbols-outlined text-red-500">error</span>
        <span class="text-sm text-red-400">{{ error }}</span>
      </div>
      <button
        @click="error = null"
        class="text-slate-400 hover:text-white"
      >
        <span class="material-symbols-outlined">close</span>
      </button>
    </div>

    <!-- Stats Cards -->
    <StatsCards :deals="deals" />

    <!-- Deals Table -->
    <DealsTable :deals="deals" @select="openDetail" />

    <!-- Deal Detail Modal -->
    <div
      v-if="dialog"
      class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      @click.self="dialog = false"
    >
      <div class="glass-panel rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto custom-scrollbar">
        <DealDetail :deal="selectedDeal" @close="dialog = false" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import StatsCards from '@/components/StatsCards.vue'
import DealsTable from '@/components/DealsTable.vue'
import DealDetail from '@/components/DealDetail.vue'

const props = defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

const dialog = ref(false)
const selectedDeal = ref(null)
const error = ref(null)

function openDetail(deal) {
  selectedDeal.value = deal
  dialog.value = true
}
</script>

