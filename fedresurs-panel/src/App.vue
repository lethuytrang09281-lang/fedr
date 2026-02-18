<template>
  <div class="h-screen flex flex-col font-sans antialiased bg-deep-charcoal text-slate-300">
    <!-- Bloomberg Terminal Header -->
    <header class="h-14 border-b border-white/5 bg-deep-charcoal z-50 flex items-center px-4 gap-6">
      <div class="flex items-center gap-3 min-w-[220px]">
        <div class="w-6 h-6 border border-accent-copper/50 flex items-center justify-center">
          <span class="material-symbols-outlined text-accent-copper text-base">radar</span>
        </div>
        <span class="font-display font-bold text-xs tracking-widest text-white uppercase">
          FEDRESURS <span class="text-accent-copper">PRO</span>
          <span class="text-[9px] text-slate-500 ml-1">v3.3</span>
        </span>
      </div>
      <nav class="flex-grow flex items-center gap-8">
        <div class="h-6 w-px bg-white/10"></div>
        <div class="flex flex-col gap-0.5">
          <span class="text-[9px] font-bold uppercase tracking-tighter text-slate-500">Дисконт</span>
          <div class="flex items-center gap-3">
            <span class="text-[11px] font-mono text-white">30% — 80%</span>
            <div class="w-24 h-1 bg-white/5 rounded-full overflow-hidden relative">
              <div class="absolute inset-y-0 left-[20%] right-[15%] bg-accent-copper"></div>
            </div>
          </div>
        </div>
        <div class="flex flex-col gap-0.5">
          <span class="text-[9px] font-bold uppercase tracking-tighter text-slate-500">Стратегия</span>
          <select class="bg-transparent border-none p-0 text-[11px] font-bold text-accent-copper focus:ring-0 cursor-pointer uppercase">
            <option class="bg-deep-charcoal">Агрессивный рост</option>
            <option class="bg-deep-charcoal">Консервативный / Жилье</option>
            <option class="bg-deep-charcoal">Промплощадки</option>
          </select>
        </div>
      </nav>
      <div class="flex items-center gap-4">
        <div class="text-right">
          <div class="text-[9px] font-bold text-slate-500 uppercase">Индекс Ликвидности</div>
          <div class="text-[11px] font-mono text-accent-copper">74.2 PPS</div>
        </div>
        <div class="w-8 h-8 rounded border border-white/10 flex items-center justify-center cursor-pointer hover:bg-white/5">
          <span class="material-symbols-outlined text-lg text-slate-400">account_balance_wallet</span>
        </div>
      </div>
    </header>

    <!-- Main Layout -->
    <main class="flex-grow flex overflow-hidden">
      <!-- Feed Sidebar -->
      <FeedSidebar :deals="deals" />

      <!-- Dashboard Area -->
      <section class="flex-grow bg-[#090a0c] overflow-y-auto custom-scrollbar">
        <Dashboard :deals="deals" />
      </section>
    </main>

    <!-- Footer -->
    <footer class="h-8 border-t border-white/5 bg-deep-charcoal flex items-center px-4 justify-between text-[9px] font-bold uppercase tracking-widest text-slate-600">
      <div class="flex gap-6">
        <div class="flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-green-600"></span>
          Соединение: Стабильно
        </div>
        <div>Обновление: 0.4 сек</div>
        <div>Пользователь: ID_88241_PRO</div>
      </div>
      <div class="flex gap-4">
        <span>© 2024 Fedresurs Pro • Редакция 3.3</span>
        <span class="text-accent-copper/60">Крипто-сессия активна</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { dealsAPI } from '@/api/deals'
import Dashboard from './views/Dashboard.vue'
import FeedSidebar from './components/FeedSidebar.vue'

const deals = ref([])

onMounted(async () => {
  try {
    deals.value = await dealsAPI.getHotDeals()
  } catch (e) {
    console.error('Failed to load deals:', e)
  }
})
</script>
