<template>
  <div class="h-full flex flex-col overflow-hidden bg-[#0B0C0E] text-slate-200 font-sans w-full">
    <!-- Sidebar Navigation -->
    <v-navigation-drawer
      v-model="drawer"
      permanent
      rail
      expand-on-hover
      color="#0B0C0E"
      class="border-r border-white/5"
    >
      <v-list density="compact" nav>
        <v-list-item
          prepend-icon="mdi-radar"
          title="FEDRESURS PRO"
          class="mb-4 text-[#D4781C]"
        ></v-list-item>

        <v-list-item
          v-for="item in navItems"
          :key="item.id"
          :prepend-icon="item.icon"
          :title="item.title"
          :value="item.id"
          :active="activeView === item.id"
          @click="activeView = item.id"
          :color="activeView === item.id ? '#D4781C' : ''"
        ></v-list-item>
      </v-list>

      <template v-slot:append>
        <div class="pa-2">
          <v-list-item prepend-icon="mdi-account-circle" title="ID_88241"></v-list-item>
        </div>
      </template>
    </v-navigation-drawer>

    <!-- Header -->
    <v-app-bar flat color="#0B0C0E" class="border-b border-white/5 px-4">
      <div class="flex flex-col">
        <span class="text-[10px] font-mono text-slate-500 uppercase tracking-widest">System Status</span>
        <div class="flex items-center gap-2">
          <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
          <span class="text-[11px] font-bold text-white uppercase">{{ currentTitle }}</span>
        </div>
      </div>

      <v-spacer></v-spacer>

      <div class="flex items-center gap-4">
        <div class="text-right hidden sm:block">
          <div class="text-[9px] font-bold text-slate-500 uppercase">Обновление: 0.4 сек</div>
          <div class="text-[10px] font-mono text-[#D4781C]">Link Stable</div>
        </div>
      </div>
    </v-app-bar>

    <v-main class="bg-[#0B0C0E] overflow-hidden">
      <div class="h-full w-full flex flex-col p-4 md:p-6 overflow-hidden">

        <!-- Loading / Error States -->
        <div v-if="loading" class="flex-grow flex flex-col items-center justify-center">
          <v-progress-circular indeterminate color="#D4781C" size="48"></v-progress-circular>
          <div class="mt-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">Hunter Terminal Initialization...</div>
        </div>

        <div v-else-if="error" class="p-4 bg-red-500/10 border border-red-500/50 rounded text-red-500 text-sm">
          {{ error }}
        </div>

        <!-- Main View Router-like content -->
        <div v-else class="flex-grow overflow-hidden flex flex-col">

          <!-- Section 1: Statistics -->
          <div v-if="activeView === 'stats'" class="flex-grow overflow-y-auto custom-scrollbar">
            <h2 class="text-[#D4781C] font-mono text-sm tracking-[0.2em] mb-6 flex items-center gap-2 uppercase">
              <span class="w-2 h-2 bg-[#D4781C]"></span>
              Global Market Intelligence
            </h2>
            <StatsCards :deals="deals" />
          </div>

          <!-- Section 2: Live Deals Feed (Table) -->
          <div v-if="activeView === 'deals'" class="flex-grow overflow-y-auto custom-scrollbar">
             <h2 class="text-[#D4781C] font-mono text-sm tracking-[0.2em] mb-6 flex items-center gap-2 uppercase">
              <span class="w-2 h-2 bg-[#D4781C]"></span>
              Live Acquisition Stream
            </h2>
            <DealsTable :deals="deals" @select="selectDeal" />
          </div>

          <!-- Section 3: Deep Analysis -->
          <div v-if="activeView === 'analysis'" class="flex-grow overflow-hidden flex flex-col">
            <template v-if="selectedDeal">
               <DealDetail
                 :deal="selectedDeal"
                 @close="activeView = 'deals'"
                 @open-memo="activeView = 'reports'"
               />
            </template>
            <div v-else class="flex-grow flex flex-col items-center justify-center text-slate-600 border border-white/5 border-dashed rounded-xl">
               <v-icon size="64" class="mb-4">mdi-database-search</v-icon>
               <p class="text-xs uppercase tracking-widest font-bold">Выберите объект в ленте для анализа</p>
               <v-btn variant="text" color="#D4781C" class="mt-4" @click="activeView = 'deals'">Перейти к ленте</v-btn>
            </div>
          </div>

          <!-- Section 4: Reports / Memo -->
          <div v-if="activeView === 'reports'" class="flex-grow overflow-hidden flex flex-col">
            <template v-if="selectedDeal">
               <div class="flex-grow overflow-y-auto custom-scrollbar">
                 <InvestmentMemo :deal="selectedDeal" @close="activeView = 'analysis'" />
               </div>
            </template>
            <div v-else class="flex-grow flex flex-col items-center justify-center text-slate-600 border border-white/5 border-dashed rounded-xl">
               <v-icon size="64" class="mb-4">mdi-file-document-edit</v-icon>
               <p class="text-xs uppercase tracking-widest font-bold">Выберите объект для генерации меморандума</p>
            </div>
          </div>

        </div>
      </div>
    </v-main>

    <!-- Footer -->
    <v-footer app color="#0B0C0E" class="border-t border-white/5 text-[9px] uppercase tracking-widest text-slate-600 py-1">
      <div class="flex justify-between w-full px-4">
        <span>© 2024 Fedresurs Pro • v3.3 Terminal</span>
        <span class="hidden md:inline">Quantum Encryption: ACTIVE</span>
      </div>
    </v-footer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { dealsAPI } from '@/api/deals'
import StatsCards from '@/components/StatsCards.vue'
import DealsTable from '@/components/DealsTable.vue'
import DealDetail from '@/components/DealDetail.vue'
import InvestmentMemo from '@/components/InvestmentMemo.vue'

const deals = ref([])
const loading = ref(true)
const error = ref(null)
const selectedDeal = ref(null)
const activeView = ref('stats')
const drawer = ref(true)

const navItems = [
  { id: 'stats', title: 'Dashboard', icon: 'mdi-view-dashboard' },
  { id: 'deals', title: 'Live Feed', icon: 'mdi-format-list-bulleted' },
  { id: 'analysis', title: 'Deep Analysis', icon: 'mdi-google-analytics' },
  { id: 'reports', title: 'Memorandum', icon: 'mdi-file-document-outline' },
]

const currentTitle = computed(() => {
  const item = navItems.find(i => i.id === activeView.value)
  return item ? item.title : 'System'
})

onMounted(async () => {
  try {
    loading.value = true
    const data = await dealsAPI.getHotDeals()
    deals.value = data
  } catch (e) {
    error.value = 'Ошибка инициализации: ' + e.message
  } finally {
    loading.value = false
  }
})

function selectDeal(deal) {
  selectedDeal.value = deal
  activeView.value = 'analysis'
}
</script>

<style>
/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(212, 120, 28, 0.3);
  border-radius: 2px;
}
</style>
