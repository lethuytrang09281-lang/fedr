import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import './assets/main.css'

import App from './App.vue'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'dark',
    themes: {
      dark: {
        colors: {
          primary: '#D4781C',
          success: '#4CAF50',
          error: '#F44336',
          warning: '#FF9800'
        }
      }
    }
  }
})

createApp(App)
  .use(vuetify)
  .mount('#app')
