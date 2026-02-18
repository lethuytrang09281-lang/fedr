<template>
  <div class="glass-panel rounded overflow-hidden">
    <div class="p-4 border-b border-white/5 bg-white/[0.02]">
      <h3 class="text-[11px] font-bold uppercase tracking-widest text-slate-400">
        Горячие сделки • Топ-лоты
      </h3>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-[11px] bloomberg-grid text-left">
        <thead class="bg-white/5">
          <tr class="text-slate-500 font-bold uppercase text-[9px]">
            <th class="px-4 py-2">ID</th>
            <th class="px-4 py-2">Район</th>
            <th class="px-4 py-2">Текущая цена</th>
            <th class="px-4 py-2">Рыночная</th>
            <th class="px-4 py-2">Deal Score</th>
            <th class="px-4 py-2">Дисконт</th>
            <th class="px-4 py-2">Статус</th>
          </tr>
        </thead>
        <tbody class="text-slate-300">
          <tr
            v-for="deal in sortedDeals"
            :key="deal.id"
            class="hover:bg-white/[0.02] cursor-pointer transition-colors border-b border-white/5"
            @click="onRowClick(deal)"
          >
            <td class="px-4 py-3 font-mono text-slate-500">{{ deal.id }}</td>
            <td class="px-4 py-3 text-white">{{ deal.district }}</td>
            <td class="px-4 py-3 font-mono text-white font-bold">{{ formatPrice(deal.start_price) }}</td>
            <td class="px-4 py-3 font-mono text-accent-copper">{{ formatPrice(deal.rosreestr_value) }}</td>
            <td class="px-4 py-3">
              <span
                class="px-2 py-0.5 rounded text-[9px] font-bold uppercase"
                :class="scoreClass(deal.deal_score)"
              >
                {{ deal.deal_score }}
              </span>
            </td>
            <td class="px-4 py-3">
              <span class="font-mono font-bold text-red-500">
                -{{ deal.price_deviation }}%
              </span>
            </td>
            <td class="px-4 py-3">
              <span
                v-if="deal.is_hidden_gem"
                class="text-[8px] font-black px-1.5 py-0.5 bg-accent-copper/10 text-accent-copper border border-accent-copper/30 rounded uppercase"
              >
                Hidden
              </span>
              <span
                v-else-if="deal.is_early_bird"
                class="text-[8px] font-black px-1.5 py-0.5 bg-blue-900/20 text-blue-400 border border-blue-900/40 rounded uppercase"
              >
                Early
              </span>
              <span
                v-else
                class="text-[8px] font-black px-1.5 py-0.5 bg-slate-800 text-slate-400 border border-slate-700 rounded uppercase"
              >
                Active
              </span>
            </td>
          </tr>
        </tbody>
      </table>
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

const emit = defineEmits(['select'])

const sortedDeals = computed(() => {
  return [...props.deals].sort((a, b) => b.deal_score - a.deal_score)
})

function formatPrice(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function scoreClass(score) {
  if (score >= 80) return 'bg-red-900/20 text-red-500 border border-red-900/40'
  if (score >= 60) return 'bg-accent-copper/10 text-accent-copper border border-accent-copper/30'
  return 'bg-slate-800 text-slate-400 border border-slate-700'
}

function onRowClick(deal) {
  emit('select', deal)
}
</script>

