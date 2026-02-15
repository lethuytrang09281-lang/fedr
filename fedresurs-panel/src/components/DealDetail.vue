<template>
  <v-card v-if="deal">
    <v-card-title class="d-flex align-center">
      <span>{{ deal.district }}</span>
      <v-spacer />
      <v-btn icon="mdi-close" variant="text" @click="$emit('close')" />
    </v-card-title>

    <v-card-text>
      <v-row class="mb-4">
        <v-col cols="6">
          <div class="text-caption">Текущая цена</div>
          <div class="text-h6">{{ formatPrice(deal.start_price) }}</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption">Рыночная цена</div>
          <div class="text-h6">{{ formatPrice(deal.rosreestr_value) }}</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption">Deal Score</div>
          <div class="text-h6">
            <v-chip :color="scoreColor(deal.deal_score)" size="small" variant="flat">
              {{ deal.deal_score }}
            </v-chip>
          </div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption">Дисконт</div>
          <div class="text-h6 text-error font-weight-bold">-{{ deal.price_deviation }}%</div>
        </v-col>
      </v-row>

      <div class="mb-4">
        <div class="text-caption mb-1">Investment Score: {{ deal.investment_score }}</div>
        <v-progress-linear
          :model-value="deal.investment_score"
          color="success"
          height="8"
          rounded
        />
      </div>

      <div class="mb-4">
        <div class="text-caption mb-1">Fraud Risk: {{ deal.fraud_risk_score }}</div>
        <v-progress-linear
          :model-value="deal.fraud_risk_score"
          color="error"
          height="8"
          rounded
        />
      </div>
    </v-card-text>

    <v-card-actions>
      <v-btn color="primary" variant="flat" @click="addToWatchlist">
        Добавить в Watchlist
      </v-btn>
      <v-btn variant="text" @click="$emit('close')">
        Закрыть
      </v-btn>
    </v-card-actions>
  </v-card>
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
  return new Intl.NumberFormat('ru-RU').format(value) + ' \u20BD'
}

function scoreColor(score) {
  if (score >= 80) return 'error'
  if (score >= 60) return 'warning'
  return 'grey'
}

function addToWatchlist() {
  alert('Лот добавлен в Watchlist!')
}
</script>
