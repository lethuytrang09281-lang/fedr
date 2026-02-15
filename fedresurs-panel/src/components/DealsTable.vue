<template>
  <v-card>
    <v-card-title>Горячие сделки</v-card-title>
    <v-data-table
      :headers="headers"
      :items="deals"
      :sort-by="[{ key: 'deal_score', order: 'desc' }]"
      @click:row="onRowClick"
      hover
    >
      <template #item.start_price="{ value }">
        {{ formatPrice(value) }}
      </template>

      <template #item.deal_score="{ value }">
        <v-chip :color="scoreColor(value)" size="small" variant="flat">
          {{ value }}
        </v-chip>
      </template>

      <template #item.price_deviation="{ value }">
        <span class="text-error font-weight-bold">-{{ value }}%</span>
      </template>
    </v-data-table>
  </v-card>
</template>

<script setup>
defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select'])

const headers = [
  { title: 'ID', key: 'id', width: '80px' },
  { title: 'Район', key: 'district' },
  { title: 'Цена', key: 'start_price' },
  { title: 'Deal Score', key: 'deal_score' },
  { title: 'Дисконт', key: 'price_deviation' }
]

function formatPrice(value) {
  return new Intl.NumberFormat('ru-RU').format(value) + ' \u20BD'
}

function scoreColor(score) {
  if (score >= 80) return 'error'
  if (score >= 60) return 'warning'
  return 'grey'
}

function onRowClick(event, { item }) {
  emit('select', item)
}
</script>
