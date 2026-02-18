<template>
  <div v-if="deal" class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-white/5 pb-4">
      <div>
        <div class="flex items-center gap-3 mb-2">
          <span class="text-[9px] font-bold text-accent-copper uppercase tracking-widest">
            ID Объекта: RU-{{ deal.id }}
          </span>
          <span
            v-if="deal.is_hidden_gem"
            class="text-[8px] font-black px-1.5 py-0.5 bg-accent-copper/10 text-accent-copper border border-accent-copper/30 rounded uppercase"
          >
            Скрытый лот
          </span>
        </div>
        <h1 class="font-display text-2xl font-bold text-white leading-tight">
          {{ deal.district }}
        </h1>
      </div>
      <button
        @click="$emit('close')"
        class="w-8 h-8 rounded border border-white/10 flex items-center justify-center cursor-pointer hover:bg-white/5"
      >
        <span class="material-symbols-outlined text-slate-400">close</span>
      </button>
    </div>

    <!-- Price Grid -->
    <div class="grid grid-cols-2 gap-4">
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Текущая цена</h5>
        <div class="text-2xl font-display font-bold text-white">
          {{ formatPrice(deal.start_price) }}
        </div>
      </div>
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Рыночная цена</h5>
        <div class="text-2xl font-display font-bold text-accent-copper">
          {{ formatPrice(deal.rosreestr_value) }}
        </div>
      </div>
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Deal Score</h5>
        <div class="flex items-end gap-2">
          <span class="text-2xl font-display font-bold" :class="scoreTextClass(deal.deal_score)">
            {{ deal.deal_score }}
          </span>
          <span class="text-[9px] text-slate-500 font-bold mb-1 uppercase">/ 100</span>
        </div>
      </div>
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Дисконт</h5>
        <div class="text-2xl font-display font-bold text-red-500">
          -{{ deal.price_deviation }}%
        </div>
      </div>
    </div>

    <!-- Progress Bars -->
    <div class="grid grid-cols-2 gap-4">
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Investment Score</h5>
        <div class="flex items-end gap-2 mb-2">
          <span class="text-xl font-display font-bold text-green-500">{{ deal.investment_score }}</span>
          <span class="text-[9px] text-slate-500 font-bold mb-1 uppercase">/ 100</span>
        </div>
        <div class="h-2 w-full bg-white/5 rounded-full overflow-hidden">
          <div
            class="h-full bg-green-500 transition-all"
            :style="{ width: deal.investment_score + '%' }"
          ></div>
        </div>
      </div>
      <div class="border border-white/5 p-4 rounded bg-white/[0.01]">
        <h5 class="text-[9px] font-bold text-slate-500 uppercase mb-3">Fraud Risk</h5>
        <div class="flex items-end gap-2 mb-2">
          <span class="text-xl font-display font-bold text-red-500">{{ deal.fraud_risk_score }}</span>
          <span class="text-[9px] text-slate-500 font-bold mb-1 uppercase">/ 100</span>
        </div>
        <div class="h-2 w-full bg-white/5 rounded-full overflow-hidden">
          <div
            class="h-full bg-red-500 transition-all"
            :style="{ width: deal.fraud_risk_score + '%' }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="pt-4 space-y-3 border-t border-white/5">
      <button
        @click="addToWatchlist"
        class="w-full bg-accent-copper hover:bg-[#b36315] text-white py-3.5 rounded font-bold text-xs uppercase tracking-widest transition-all flex items-center justify-center gap-2"
      >
        <span class="material-symbols-outlined text-lg">bookmark_add</span>
        Добавить в Watchlist
      </button>
      <div class="grid grid-cols-2 gap-3">
        <button
          class="bg-white/5 hover:bg-white/10 border border-white/10 text-white py-3 rounded font-bold text-[10px] uppercase tracking-widest transition-all"
        >
          Документация
        </button>
        <button
          @click="$emit('close')"
          class="bg-white/5 hover:bg-white/10 border border-white/10 text-white py-3 rounded font-bold text-[10px] uppercase tracking-widest transition-all"
        >
          Закрыть
        </button>
      </div>
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

defineEmits(['close'])

function formatPrice(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function scoreTextClass(score) {
  if (score >= 80) return 'text-red-500'
  if (score >= 60) return 'text-accent-copper'
  return 'text-slate-400'
}

function addToWatchlist() {
  alert('Лот добавлен в Watchlist!')
}
</script>

