<template>
  <div v-if="deal" class="bg-[#0B0C0E] text-white h-full flex flex-col overflow-hidden">
    <div class="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
      <div>
        <div class="text-[10px] font-bold text-accent-copper uppercase tracking-[0.2em] mb-1">Анализ объекта</div>
        <h2 class="text-xl font-display font-bold tracking-tight">{{ deal.district }} логистический хаб</h2>
      </div>
      <v-btn icon="mdi-close" variant="text" density="comfortable" @click="$emit('close')"></v-btn>
    </div>

    <div class="flex-grow overflow-y-auto custom-scrollbar p-6 space-y-8">
      <!-- Top Metrics -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="glass-morphism p-4 rounded-xl">
          <span class="text-[9px] text-slate-500 font-bold uppercase tracking-widest block mb-2">Текущая цена</span>
          <div class="flex items-baseline gap-2">
            <span class="text-xl font-mono font-bold text-white">{{ formatPrice(deal.start_price) }}</span>
            <span class="text-[10px] text-accent-copper font-bold">-{{ deal.price_deviation }}%</span>
          </div>
        </div>
        <div class="glass-morphism p-4 rounded-xl">
          <span class="text-[9px] text-slate-500 font-bold uppercase tracking-widest block mb-2">Рыночная оценка</span>
          <div class="text-xl font-mono font-bold text-slate-300">{{ formatPrice(deal.rosreestr_value) }}</div>
        </div>
      </div>

      <!-- Scavenger Chart -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">График падения (Sniper Window)</h4>
          <div class="text-[10px] text-accent-copper font-mono">ID: RU-{{ deal.id }}-B</div>
        </div>
        <div class="h-48 border border-white/5 bg-white/[0.01] relative overflow-hidden rounded-lg">
          <div class="absolute inset-0 opacity-[0.05]" style="background-image: radial-gradient(circle, #fff 1px, transparent 1px); background-size: 20px 20px;"></div>
          <svg class="absolute inset-0 w-full h-full px-4 py-8" preserveAspectRatio="none" viewBox="0 0 100 100">
            <path d="M 0,20 L 20,30 L 40,50 L 60,65 L 80,85 L 100,95" fill="none" stroke="#D4781C" stroke-width="2" stroke-dasharray="4 2"></path>
            <circle cx="70" cy="75" r="3" fill="#D4781C"></circle>
            <text x="75" y="70" font-size="6" fill="#D4781C" font-family="monospace">TARGET</text>
          </svg>
          <div class="absolute bottom-0 right-0 w-1/3 h-1/2 scavenger-gradient border-l border-t border-accent-copper/20 flex items-center justify-center">
            <span class="text-[8px] font-black text-accent-copper uppercase tracking-tighter">Оптимальный вход</span>
          </div>
        </div>
      </div>

      <!-- Risk Meters -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div class="starlight-card p-4 rounded-xl">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[9px] font-bold text-slate-500 uppercase">Юридический риск</span>
            <span class="text-xs font-bold">{{ deal.fraud_risk_score }}%</span>
          </div>
          <div class="h-1 w-full bg-white/5 rounded-full overflow-hidden">
            <div class="h-full bg-green-500 transition-all duration-1000" :style="{ width: deal.fraud_risk_score + '%' }"></div>
          </div>
        </div>
        <div class="starlight-card p-4 rounded-xl">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[9px] font-bold text-slate-500 uppercase">Investment Score</span>
            <span class="text-xs font-bold">{{ deal.investment_score }}</span>
          </div>
          <div class="h-1 w-full bg-white/5 rounded-full overflow-hidden">
            <div class="h-full bg-accent-copper transition-all duration-1000" :style="{ width: deal.investment_score + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Details Grid -->
      <div class="glass-morphism rounded-xl overflow-hidden border border-white/5">
        <table class="w-full text-[11px] bloomberg-grid">
          <tbody class="divide-y divide-white/5">
            <tr>
              <td class="p-3 font-bold uppercase tracking-tighter text-slate-600 w-1/3">Стратегия</td>
              <td class="p-3 text-white">{{ deal.strategy }}</td>
            </tr>
            <tr>
              <td class="p-3 font-bold uppercase tracking-tighter text-slate-600">Стадия</td>
              <td class="p-3 text-white font-bold text-accent-copper">{{ deal.stage }}</td>
            </tr>
            <tr>
              <td class="p-3 font-bold uppercase tracking-tighter text-slate-600">Координаты</td>
              <td class="p-3 text-white font-mono">{{ deal.coordinates.join(', ') }}</td>
            </tr>
            <tr>
              <td class="p-3 font-bold uppercase tracking-tighter text-slate-600">Арбитражный упр.</td>
              <td class="p-3 text-white flex items-center gap-2">
                Константинопольский А.В.
                <span class="text-[8px] px-1 bg-green-500/20 text-green-500 rounded">Karma: 4.9</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Actions -->
    <div class="p-6 border-t border-white/5 bg-white/[0.01] grid grid-cols-2 gap-4">
      <v-btn
        color="#D4781C"
        class="text-[10px] font-black uppercase tracking-widest h-12 rounded-xl"
        prepend-icon="mdi-bookmark"
        @click="addToWatchlist"
      >
        В избранное
      </v-btn>
      <v-btn
        variant="tonal"
        color="white"
        class="text-[10px] font-bold uppercase tracking-widest h-12 rounded-xl"
        prepend-icon="mdi-file-document"
        @click="$emit('open-memo')"
      >
        Меморандум
      </v-btn>
    </div>
  </div>
</template>

<script setup>
defineProps({
  deal: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'open-memo'])

function formatPrice(value) {
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function addToWatchlist() {
  alert('Лот добавлен в Watchlist!')
}
</script>
