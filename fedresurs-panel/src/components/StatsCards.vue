<template>
  <v-row class="mb-4">
    <v-col v-for="stat in stats" :key="stat.label" cols="12" sm="6" md="3">
      <v-card>
        <v-card-text class="text-center">
          <div class="text-h4" :style="{ color: stat.color }">{{ stat.value }}</div>
          <div class="text-caption mt-1">{{ stat.label }}</div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  deals: {
    type: Array,
    default: () => []
  }
})

const stats = computed(() => [
  {
    label: 'Hot Deals',
    value: props.deals.filter(d => d.deal_score >= 80).length,
    color: '#F44336'
  },
  {
    label: 'Good Deals',
    value: props.deals.filter(d => d.deal_score >= 60 && d.deal_score < 80).length,
    color: '#4CAF50'
  },
  {
    label: 'Hidden Gems',
    value: props.deals.filter(d => d.is_hidden_gem).length,
    color: '#FF7A00'
  },
  {
    label: 'Early Bird',
    value: props.deals.filter(d => d.is_early_bird).length,
    color: '#2196F3'
  }
])
</script>
