const { request } = require('../../utils/api');
const { dateTime } = require('../../utils/format');

const statusText = { queued: '等待发送', sending: '正在发送', mock: '本地模拟', sent: '已送达供应商', failed: '发送失败', unknown: '结果待核对' };
Page({
  data: { messages: [], mode: '', smsProvider: '', loading: true, error: '' },
  onShow() { if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() { this.setData({ loading: true, error: '' }); try { const data = await request('/api/messages'); this.setData({ ...data, messages: data.messages.map((entry) => ({ ...entry, timeText: dateTime(entry.createdAt), statusText: statusText[entry.status] || entry.status })) }); } catch (error) { this.setData({ error: error.message }); } finally { this.setData({ loading: false }); } },
  openApproval(event) { wx.navigateTo({ url: `/miniprogram/pages/approval-detail/index?id=${event.currentTarget.dataset.id}` }); },
});
