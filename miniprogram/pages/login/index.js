const { request, token } = require('/utils/api');

Page({
  data: { phone: '', name: '', code: '', challengeId: '', demoCode: '', countdown: 0, submitting: false, sending: false, error: '', invite: '', approvalId: '' },
  onLoad(options) {
    if (options.invite) getApp().globalData.launchTarget = { invite: options.invite };
    if (options.approvalId) getApp().globalData.launchTarget = { approvalId: options.approvalId };
    this.setData({ invite: options.invite || '', approvalId: options.approvalId || '' });
    if (token()) wx.switchTab({ url: '/miniprogram/pages/feed/index', success: () => setTimeout(() => getApp().openLaunchTarget(), 120) });
  },
  onUnload() { if (this.timer) clearInterval(this.timer); },
  inputPhone(event) { this.setData({ phone: event.detail.value, error: '' }); },
  inputName(event) { this.setData({ name: event.detail.value }); },
  inputCode(event) { this.setData({ code: event.detail.value, error: '' }); },
  async sendCode() {
    if (this.data.sending || this.data.countdown) return;
    if (!/^1\d{10}$/.test(this.data.phone)) { this.setData({ error: '请输入11位手机号' }); return; }
    this.setData({ sending: true, error: '' });
    try {
      const result = await request('/api/auth/code', { method: 'POST', data: { phone: this.data.phone } });
      this.setData({ challengeId: result.challengeId, demoCode: result.demoCode || '', countdown: result.retryAfter || 60 });
      this.timer = setInterval(() => {
        const countdown = Math.max(0, this.data.countdown - 1);
        this.setData({ countdown });
        if (!countdown) { clearInterval(this.timer); this.timer = null; }
      }, 1000);
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ sending: false }); }
  },
  async login() {
    if (this.data.submitting) return;
    if (!this.data.challengeId || !this.data.code.trim()) { this.setData({ error: '请先获取并填写验证码' }); return; }
    this.setData({ submitting: true, error: '' });
    try {
      const result = await request('/api/auth/login', { method: 'POST', data: { phone: this.data.phone, challengeId: this.data.challengeId, code: this.data.code.trim(), name: this.data.name.trim() || undefined } });
      this.finishLogin(result);
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ submitting: false }); }
  },
  async demoLogin(event) {
    if (this.data.submitting) return;
    this.setData({ submitting: true, error: '' });
    try {
      const result = await request('/api/auth/demo', { method: 'POST', data: { account: event.currentTarget.dataset.account } });
      this.finishLogin(result);
    } catch (error) { this.setData({ error: error.message }); }
    finally { this.setData({ submitting: false }); }
  },
  finishLogin(result) {
    wx.setStorageSync('token', result.token);
    getApp().globalData.user = result.user;
    wx.switchTab({ url: '/miniprogram/pages/feed/index', success: () => setTimeout(() => getApp().openLaunchTarget(), 120) });
  },
});
