<template>
  <div class="glass-morphism rounded-3xl overflow-hidden border border-white/5">
    <div class="p-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
      <h2 class="text-[11px] font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-accent-copper animate-pulse"></span>
        Лента горячих лотов
      </h2>
      <div class="text-[10px] font-mono text-accent-copper">{{ deals.length }} ОБЪЕКТОВ НАЙДЕНО</div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-left bloomberg-grid">
        <thead class="bg-white/5">
          <tr class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">
            <th class="p-4">ID</th>
            <th class="p-4">Локация</th>
            <th class="p-4">Цена / Рынок</th>
            <th class="p-4">Дисконт</th>
            <th class="p-4">Score</th>
            <th class="p-4">Статус</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-white/5">
          <tr v-for="deal in deals" :key="deal.id"
              class="hover:bg-white/[0.03] cursor-pointer transition-colors group"
              @click="$emit('select', deal)">
            <td class="p-4">
              <span class="text-[10px] font-mono text-slate-500">#{{ deal.id }}</span>
            </td>
            <td class="p-4">
              <div class="text-xs font-bold text-white group-hover:text-accent-copper">{{ deal.district }} комплекс</div>
              <div class="text-[9px] text-slate-500 uppercase tracking-tighter">{{ deal.strategy }} strategy</div>
            </td>
            <td class="p-4">
              <div class="text-xs font-mono font-bold text-white">{{ formatPrice(deal.start_price) }}</div>
              <div class="text-[9px] font-mono text-slate-600">{{ formatPrice(deal.rosreestr_value) }}</div>
            </td>
            <td class="p-4">
              <div class="inline-block px-2 py-0.5 rounded-sm bg-accent-copper/10 text-accent-copper text-[10px] font-bold">
                -{{ deal.price_deviation }}%
              </div>
            </td>
            <td class="p-4">
              <div class="relative w-10 h-10 flex items-center justify-center">
                <svg class="w-full h-full -rotate-90">
                  <circle cx="20" cy="20" r="18" fill="transparent" stroke="rgba(255,255,255,0.05)" stroke-width="2"/>
                  <circle cx="20" cy="20" r="18" fill="transparent" :stroke="scoreColor(deal.deal_score)" stroke-width="2"
                          :stroke-dasharray="113.1" :stroke-dashoffset="113.1 * (1 - deal.deal_score / 100)"/>
                </svg>
                <span class="absolute text-[10px] font-bold text-white">{{ deal.deal_score }}</span>
              </div>
            </td>
            <td class="p-4">
              <div class="flex flex-wrap gap-1">
                <span v-if="deal.is_sweet_spot" class="text-[8px] font-black px-1.5 py-0.5 bg-accent-copper text-white rounded uppercase">Sweet</span>
                <span v-if="deal.is_early_bird" class="text-[8px] font-black px-1.5 py-0.5 bg-green-600 text-white rounded uppercase">Early</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

defineEmits(['select'])

function formatPrice(value) {
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function scoreColor(score) {
  if (score >= 80) return '#D4781C'
  if (score >= 60) return '#94a3b8'
  return '#475569'
}
</script>
