import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://157.22.231.149:8000',
  timeout: 10000
})

export const dealsAPI = {
  async getHotDeals() {
    const response = await apiClient.get('/api/v1/hunter/hot-deals-demo')
    return response.data.hot_deals
  }
}
