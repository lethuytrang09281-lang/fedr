import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://157.22.231.149:8000',
  timeout: 10000
})

export const dealsAPI = {
  async getHotDeals() {
    const response = await apiClient.get('/api/v1/hunter/hot-deals-demo')
    // Transform demo data to match expected format
    const deals = response.data.deals || []
    return deals.map(deal => ({
      id: deal.id,
      district: deal.location || deal.title,
      title: deal.title,
      start_price: deal.price,
      rosreestr_value: deal.price ? Math.round(deal.price / (1 - deal.discount / 100)) : 0,
      deal_score: Math.round(deal.score * 10),
      price_deviation: deal.discount,
      investment_score: Math.round(deal.score * 10),
      fraud_risk_score: Math.max(0, 100 - Math.round(deal.score * 10)),
      is_hidden_gem: deal.discount > 50,
      is_early_bird: deal.score > 9
    }))
  }
}
