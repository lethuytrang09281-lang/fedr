<template>
  <div class="investment-memo bg-[#0B0C0E] text-[#E0E0E0] p-8 rounded-lg border border-[#D4781C]/30 shadow-2xl max-w-4xl mx-auto my-4 font-mono">
    <!-- Header -->
    <div class="flex justify-between items-start border-b border-[#D4781C]/50 pb-6 mb-8">
      <div>
        <h1 class="text-3xl font-bold text-[#D4781C] mb-2 uppercase tracking-tighter">Investment Memorandum</h1>
        <p class="text-sm text-gray-400">FEDRESURS PRO // HUNTER TERMINAL v3.3</p>
      </div>
      <div class="text-right">
        <div class="text-2xl font-bold text-white">#{{ deal.id }}</div>
        <div class="text-xs text-gray-500 uppercase">Object Identifier</div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="grid grid-cols-3 gap-8 mb-8">
      <!-- Left Column: Primary Details -->
      <div class="col-span-2 space-y-6">
        <section>
          <h2 class="text-xs font-bold text-[#D4781C] uppercase mb-3 tracking-widest">Property Description</h2>
          <div class="bg-[#15171A] p-4 border-l-2 border-[#D4781C]">
            <div class="text-xl font-medium mb-1">{{ deal.district }} комплекс</div>
            <div class="text-sm text-gray-400">Локация: {{ deal.district }}, Координаты: {{ deal.coordinates?.join(', ') }}</div>
          </div>
        </section>

        <section class="grid grid-cols-2 gap-4">
          <div>
            <h2 class="text-xs font-bold text-[#D4781C] uppercase mb-3 tracking-widest">Financial Summary</h2>
            <div class="space-y-2">
              <div class="flex justify-between border-b border-gray-800 pb-1">
                <span class="text-gray-500 text-sm">Current Price:</span>
                <span class="text-white font-bold">{{ formatPrice(deal.start_price) }} ₽</span>
              </div>
              <div class="flex justify-between border-b border-gray-800 pb-1">
                <span class="text-gray-500 text-sm">Market Value:</span>
                <span class="text-white font-bold">{{ formatPrice(deal.rosreestr_value) }} ₽</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500 text-sm">Discount:</span>
                <span class="text-[#D4781C] font-bold">-{{ deal.price_deviation }}%</span>
              </div>
            </div>
          </div>
          <div>
            <h2 class="text-xs font-bold text-[#D4781C] uppercase mb-3 tracking-widest">Deal Intelligence</h2>
            <div class="space-y-2">
              <div class="flex justify-between border-b border-gray-800 pb-1">
                <span class="text-gray-500 text-sm">Strategy:</span>
                <span class="text-white uppercase">{{ deal.strategy }}</span>
              </div>
              <div class="flex justify-between border-b border-gray-800 pb-1">
                <span class="text-gray-500 text-sm">Stage:</span>
                <span class="text-white uppercase">{{ deal.stage }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500 text-sm">Status:</span>
                <span :class="getStatusClass(deal)" class="font-bold px-2 rounded text-xs uppercase">
                  {{ deal.is_sweet_spot ? 'Sweet Spot' : (deal.is_early_bird ? 'Early Bird' : 'Active') }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 class="text-xs font-bold text-[#D4781C] uppercase mb-3 tracking-widest">Sniper Analysis (Price Drop Path)</h2>
          <div class="bg-[#0B0C0E] border border-gray-800 h-32 relative rounded overflow-hidden">
             <!-- Simplified chart representation -->
             <svg class="w-full h-full opacity-50" viewBox="0 0 400 100">
               <path d="M0,20 L100,35 L200,55 L300,75 L400,85" fill="none" stroke="#D4781C" stroke-width="2" />
               <circle cx="300" cy="75" r="4" fill="#D4781C" />
               <text x="310" y="70" fill="#D4781C" font-size="8">OPTIMAL ENTRY</text>
             </svg>
          </div>
        </section>
      </div>

      <!-- Right Column: Scores & Metrics -->
      <div class="col-span-1 space-y-6">
        <div class="bg-[#15171A] p-6 border border-[#D4781C]/20 rounded text-center">
          <div class="text-xs text-gray-500 uppercase mb-2">Deal Score</div>
          <div class="text-5xl font-bold text-[#D4781C]">{{ deal.deal_score }}</div>
          <div class="mt-2 h-1 bg-gray-800 rounded-full overflow-hidden">
            <div class="h-full bg-[#D4781C]" :style="{ width: deal.deal_score + '%' }"></div>
          </div>
        </div>

        <div>
          <h2 class="text-xs font-bold text-[#D4781C] uppercase mb-3 tracking-widest">Risk Profile</h2>
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-400">Legal Risk</span>
                <span :class="getRiskColor(deal.fraud_risk_score)">{{ deal.fraud_risk_score }}%</span>
              </div>
              <div class="h-1 bg-gray-800 rounded-full">
                <div class="h-full bg-red-500" :style="{ width: (deal.fraud_risk_score || 0) + '%' }"></div>
              </div>
            </div>
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-400">Investment Potential</span>
                <span class="text-green-500">{{ deal.investment_score }}%</span>
              </div>
              <div class="h-1 bg-gray-800 rounded-full">
                <div class="h-full bg-green-500" :style="{ width: (deal.investment_score || 0) + '%' }"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 border border-gray-800 rounded bg-[#0B0C0E]">
          <h3 class="text-xs font-bold text-gray-400 uppercase mb-2">Arbitrage Manager</h3>
          <p class="text-sm text-white">Константинопольский А.В.</p>
          <div class="text-xs text-[#D4781C] mt-1 italic">Karma: 4.9</div>
        </div>
      </div>
    </div>

    <!-- Footer / Actions -->
    <div class="flex justify-between items-center border-t border-gray-800 pt-6 mt-8">
      <div class="text-[10px] text-gray-600 uppercase">
        Generated by Fedresurs AI System // Confidential
      </div>
      <div class="space-x-4 no-print flex">
        <v-btn variant="text" class="text-slate-400 font-mono" @click="$emit('close')">CANCEL</v-btn>
        <v-btn variant="flat" color="primary" class="font-mono px-6" @click="printMemo">PRINT MEMO</v-btn>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  deal: {
    type: Object,
    required: true
  }
})

defineEmits(['close'])

const formatPrice = (price) => {
  return new Intl.NumberFormat('ru-RU').format(price)
}

const getStatusClass = (deal) => {
  if (deal.is_sweet_spot) return 'bg-[#D4781C] text-black'
  if (deal.is_early_bird) return 'bg-green-600 text-white'
  return 'bg-gray-700 text-white'
}

const getRiskColor = (risk) => {
  if (risk > 50) return 'text-red-500'
  if (risk > 25) return 'text-yellow-500'
  return 'text-green-500'
}

const printMemo = () => {
  window.print()
}
</script>

<style scoped>
@media print {
  .no-print {
    display: none !important;
  }
  .investment-memo {
    background: white !important;
    color: black !important;
    border: none !important;
    box-shadow: none !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
  }
  .bg-[#0B0C0E], .bg-[#15171A] {
    background: white !important;
    color: black !important;
    border: 1px solid #ccc !important;
  }
  .text-[#D4781C] {
    color: #8B4513 !important; /* Darker copper for printing */
  }
  .text-gray-400, .text-gray-500, .text-gray-600 {
    color: #444 !important;
  }
}
</style>
