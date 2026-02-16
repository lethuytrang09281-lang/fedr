<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
    <div v-for="stat in stats" :key="stat.label"
         class="glass-morphism p-4 rounded-2xl border-l-2"
         :style="{ borderLeftColor: stat.color }">
      <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{{ stat.label }}</div>
      <div class="flex items-baseline gap-2">
        <div class="text-3xl font-display font-black text-white leading-none">{{ stat.value }}</div>
        <div class="text-[10px] font-bold uppercase" :style="{ color: stat.color }">{{ stat.suffix }}</div>
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

const stats = computed(() => [
  {
    label: 'Hot Deals',
    value: props.deals.filter(d => d.deal_score >= 80).length,
    suffix: 'Активно',
    color: '#D4781C'
  },
  {
    label: 'Good Deals',
    value: props.deals.filter(d => d.deal_score >= 60 && d.deal_score < 80).length,
    suffix: 'Ожидание',
    color: '#94a3b8'
  },
  {
    label: 'Hidden Gems',
    value: props.deals.filter(d => d.is_sweet_spot).length,
    suffix: 'Sweet Spot',
    color: '#D4781C'
  },
  {
    label: 'Early Bird',
    value: props.deals.filter(d => d.is_early_bird).length,
    suffix: 'Сегодня',
    color: '#22c55e'
  }
])
</script>
