const { request, absoluteMediaUrl } = require('/utils/api');
const { money, dateTime } = require('/utils/format');

const ruleText = { veto: '一票否决', majority: '多数决定', unanimous: '全员一致' };
const statusText = { pending: '待审批', approved: '已通过', rejected: '已拒绝', expired: '已过期', cancelled: '已撤回' };
const decisionText = { accept: '接受购买', reject: '拒绝购买' };

Page({
  data: { id: '', approval: null, comment: '', loading: true, submitting: false, error: '', isOwner: false, canVote: false },
  onLoad(options) { this.setData({ id: options.id || '' }); if (getApp().ensureSession()) this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },
  async load() {
    this.setData({ loading: true, error: '' });
    try {
      const { approval } = await request(`/api/approvals/${this.data.id}`);
      const user = getApp().globalData.user;
      const mine = user && approval.reviewers.find((entry) => entry.user.id === user.id);
      this.setData({
        approval: {
          ...approval,
          priceText: money(approval.price),
          createdText: dateTime(approval.createdAt),
          expiresText: dateTime(approval.expiresAt),
          statusText: statusText[approval.status] || approval.status,
          ruleText: ruleText[approval.rule] || approval.rule,
          photos: (approval.imageUrls || []).map(absoluteMediaUrl),
          reviewers: approval.reviewers.map((entry) => ({ ...entry, decisionText: entry.decision ? decisionText[entry.decision] : '等待意见', votedText: entry.votedAt ? dateTime(entry.votedAt) : '' })),
        },
        isOwner: Boolean(user && user.id === approval.ownerId),
        canVote: Boolean(mine && !mine.decision && approval.status === 'pending'),
      });
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ loading: false }); }
  },
  inputComment(event) { this.setData({ comment: event.detail.value, error: '' }); },
  async submitVote(event) {
    if (this.data.submitting) return;
    const comment = (this.data.comment || '').trim();
    if (!comment) { this.setData({ error: '请填写审批意见' }); return; }
    const decision = event.currentTarget.dataset.decision;
    this.setData({ submitting: true, error: '' });
    try {
      await request(`/api/approvals/${this.data.id}/vote`, { method: 'POST', data: { decision, comment } });
      this.setData({ comment: '' });
      await this.load();
      wx.showToast({ title: '意见已提交', icon: 'success' });
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ submitting: false }); }
  },
  cancel() {
    wx.showModal({ title: '撤回审批？', content: '好友将不能再提交意见。', confirmColor: '#D95F45', success: async ({ confirm }) => {
      if (!confirm || this.data.submitting) return;
      this.setData({ submitting: true, error: '' });
      try { await request(`/api/approvals/${this.data.id}/cancel`, { method: 'POST' }); await this.load(); }
      catch (error) { this.setData({ error: error.message }); }
      finally { this.setData({ submitting: false }); }
    } });
  },
  onShareAppMessage() { return { title: `请帮我看看：${this.data.approval ? this.data.approval.title : '购买审批'}`, path: `/miniprogram/pages/login/index?approvalId=${encodeURIComponent(this.data.id)}` }; },
});
