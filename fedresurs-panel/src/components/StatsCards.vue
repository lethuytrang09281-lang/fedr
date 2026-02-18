<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
    <div v-for="stat in stats" :key="stat.label" class="glass-panel rounded p-4">
      <h4 class="text-[9px] font-bold uppercase tracking-widest text-slate-500 mb-2">
        {{ stat.label }}
      </h4>
      <div class="flex items-end gap-2">
        <span class="text-3xl font-display font-bold" :style="{ color: stat.color }">
          {{ stat.value }}
        </span>
        <span class="text-[10px] text-slate-600 mb-1 uppercase">
          {{ stat.suffix }}
        </span>
      </div>
      <div v-if="stat.showBar" class="h-1 w-full bg-white/5 rounded-full overflow-hidden mt-3">
        <div class="h-full" :style="{ width: stat.barWidth + '%', backgroundColor: stat.color }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

const stats = computed(() => {
  const total = props.deals.length || 1
  const hotCount = props.deals.filter(d => d.deal_score >= 80).length
  const goodCount = props.deals.filter(d => d.deal_score >= 60 && d.deal_score < 80).length
  const hiddenCount = props.deals.filter(d => d.is_hidden_gem).length
  const earlyCount = props.deals.filter(d => d.is_early_bird).length

  return [
    {
      label: 'Hot Deals',
      value: hotCount,
      color: '#D4781C',
      suffix: 'лотов',
      showBar: true,
      barWidth: (hotCount / total) * 100
    },
    {
      label: 'Good Deals',
      value: goodCount,
      color: '#4CAF50',
      suffix: 'лотов',
      showBar: true,
      barWidth: (goodCount / total) * 100
    },
    {
      label: 'Hidden Gems',
      value: hiddenCount,
      color: '#D4781C',
      suffix: 'скрытых',
      showBar: true,
      barWidth: (hiddenCount / total) * 100
    },
    {
      label: 'Early Bird',
      value: earlyCount,
      color: '#3B82F6',
      suffix: 'ранних',
      showBar: true,
      barWidth: (earlyCount / total) * 100
    }
  ]
})
</script>

