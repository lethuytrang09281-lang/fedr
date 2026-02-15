<template>
  <v-app>
    <v-app-bar color="surface" flat>
      <v-app-bar-title>
        Fedresurs Pro
      </v-app-bar-title>
    </v-app-bar>
    <v-main>
      <Dashboard />
    </v-main>
  </v-app>
</template>

<script setup>
import Dashboard from './views/Dashboard.vue'
</script>
