<template>
  <aside class="w-[380px] border-r border-white/5 flex flex-col bg-deep-charcoal">
    <div class="p-3 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
      <h2 class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Лента лотов (Live)</h2>
      <div class="flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-accent-copper"></span>
        <span class="text-[10px] font-mono text-accent-copper">{{ deals.length }} АКТИВНО</span>
      </div>
    </div>
    <div class="flex-grow overflow-y-auto custom-scrollbar">
      <div
        v-for="deal in deals"
        :key="deal.id"
        class="block p-4 border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors group"
      >
        <div class="flex gap-2 mb-2">
          <span
            v-if="deal.is_hidden_gem"
            class="text-[8px] font-black px-1.5 py-0.5 bg-accent-copper/10 text-accent-copper border border-accent-copper/30 rounded uppercase"
          >
            Скрытый лот
          </span>
          <span
            v-if="deal.deal_score >= 80"
            class="text-[8px] font-black px-1.5 py-0.5 bg-red-900/20 text-red-500 border border-red-900/40 rounded uppercase"
          >
            HOT DEAL
          </span>
          <span
            class="text-[8px] font-black px-1.5 py-0.5 bg-slate-800 text-slate-400 border border-slate-700 rounded uppercase"
          >
            {{ getCategoryLabel(deal) }}
          </span>
        </div>
        <h3 class="text-xs font-bold text-white mb-1 leading-snug group-hover:text-accent-copper">
          {{ deal.title || deal.district || 'Лот #' + deal.id }}
        </h3>
        <div class="text-[10px] text-slate-500 mb-3 flex items-center gap-1">
          <span class="material-symbols-outlined text-[12px]">location_on</span>
          {{ deal.district }}
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <span class="block text-[8px] text-slate-600 uppercase font-bold">Тек. цена</span>
            <span class="text-xs font-mono font-bold text-white">{{ formatPrice(deal.start_price) }}</span>
          </div>
          <div class="text-right">
            <span class="block text-[8px] text-slate-600 uppercase font-bold">Рынок</span>
            <span class="text-xs font-mono font-bold" :class="deal.deal_score >= 70 ? 'text-accent-copper' : 'text-slate-400'">
              {{ formatPrice(deal.rosreestr_value) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

function formatPrice(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function getCategoryLabel(deal) {
  if (deal.is_early_bird) return 'Ранняя птица'
  if (deal.investment_score > 80) return 'Инвестиция'
  return 'Торги'
}
</script>
