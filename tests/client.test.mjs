import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function loadScript(relativePath, extras = {}) {
  const filename = path.join(root, relativePath);
  const source = fs.readFileSync(filename, 'utf8');
  const sandbox = {
    console,
    module: { exports: {} },
    exports: {},
    require(specifier) {
      if (extras.modules && Object.hasOwn(extras.modules, specifier)) return extras.modules[specifier];
      throw new Error(`Unexpected require: ${specifier}`);
    },
    ...extras.globals,
  };
  vm.runInNewContext(source, sandbox, { filename });
  return { exports: sandbox.module.exports, sandbox };
}

function loadPage(relativePath, { api = {}, wx = {}, app = { ensureSession: async () => true, globalData: {}, openLaunchTarget() {} } } = {}) {
  let definition;
  const { sandbox } = loadScript(relativePath, {
    modules: { '../../utils/api': api, '../../utils/format': api,
      '../../utils/approval': loadScript('miniprogram/utils/approval.js', { modules: { './format': loadScript('miniprogram/utils/format.js').exports } }).exports,
      '../../utils/share-card': { createShareCard: async () => '' } },
    globals: {
      Page(value) { definition = value; },
      getApp() { return app; },
      wx: {
        showToast() {},
        navigateBack() {},
        navigateTo() {},
        ...wx,
      },
    },
  });
  assert.ok(definition, `${relativePath} must register Page(...)`);
  definition.data = structuredClone(definition.data || {});
  definition.setData = function setData(values) { Object.assign(this.data, values); };
  return { page: definition, sandbox };
}

function loadApp({ api = {}, wx = {} } = {}) {
  let definition;
  const { sandbox } = loadScript('app.js', {
    modules: { './miniprogram/utils/api': api },
    globals: {
      App(value) { definition = value; },
      wx,
    },
  });
  assert.ok(definition, 'app.js must register App(...)');
  return { app: definition, sandbox };
}

test('compose converts a two-decimal yuan price to integer cents', () => {
  const { exports } = loadScript('miniprogram/utils/format.js');
  assert.equal(exports.yuanToCents('12.34'), 1234);
  assert.equal(exports.yuanToCents('0.01'), 1);
  assert.equal(exports.yuanToCents('12.345'), null);
  assert.equal(exports.yuanToCents(''), null);
});

test('login uses wx.login and never asks for phone registration', async () => {
  const calls = [];
  const app = { globalData: {}, openLaunchTarget() {} };
  const { page } = loadPage('miniprogram/pages/login/index.js', {
    app,
    api: { request: async (path, options) => { calls.push({ path, data: options.data }); return { token: 'session-token', user: { id: 'wx-user' } }; }, token: () => '' },
    wx: {
      login({ success }) { success({ code: 'wx-temporary-code' }); },
      setStorageSync() {},
      switchTab() {},
    },
  });
  await page.wechatLogin();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/auth/wechat');
  assert.equal(calls[0].data.code, 'wx-temporary-code');
  const markup = fs.readFileSync(path.join(root, 'miniprogram/pages/login/index.wxml'), 'utf8');
  assert.equal(markup.includes('手机号'), false);
  assert.equal(markup.includes('验证码'), false);
});

test('vote refuses blank mandatory comment without issuing an API call', async () => {
  let calls = 0;
  const { page } = loadPage('miniprogram/pages/approval-detail/index.js', {
    api: { request: async () => { calls += 1; } },
  });
  page.data = { id: 'approval-1', comment: '   ', submitting: false };
  await page.submitVote({ currentTarget: { dataset: { decision: 'accept' } } });
  assert.equal(calls, 0);
  assert.equal(page.data.error, '请填写审批意见');
});

test('approval creation selects reviewers once and enforces the ten-person cap', () => {
  const { page } = loadPage('miniprogram/pages/approval-create/index.js');
  page.data = { selectedIds: [], error: '' };
  for (let index = 1; index <= 10; index += 1) {
    page.toggleReviewer({ currentTarget: { dataset: { id: `friend-${index}` } } });
  }
  page.toggleReviewer({ currentTarget: { dataset: { id: 'friend-11' } } });
  assert.equal(page.data.selectedIds.length, 10);
  assert.equal(page.data.error, '最多选择10位好友');
  page.toggleReviewer({ currentTarget: { dataset: { id: 'friend-1' } } });
  assert.equal(page.data.selectedIds.includes('friend-1'), false);
});

test('API wrapper exposes backend errors and clears an invalid saved session', async () => {
  const removed = [];
  const { exports } = loadScript('miniprogram/utils/api.js', {
    globals: {
      wx: {
        getStorageSync: () => 'expired-token',
        removeStorageSync: (key) => removed.push(key),
        request({ success }) {
          success({ statusCode: 401, data: { error: '登录已过期，请重新登录' } });
        },
      },
      getApp: () => ({ globalData: {} }),
    },
  });
  await assert.rejects(exports.request('/api/me'), /登录已过期，请重新登录/);
  assert.deepEqual(removed, ['token']);
});

test('duplicate vote taps share one in-flight request', async () => {
  let calls = 0;
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const { page } = loadPage('miniprogram/pages/approval-detail/index.js', {
    api: {
      request: async () => {
        calls += 1;
        await pending;
        return { approval: { id: 'approval-1', reviewers: [] } };
      },
      absoluteMediaUrl: (value) => value,
    },
  });
  page.data = { id: 'approval-1', comment: '同意购买，价格合适', submitting: false };
  const event = { currentTarget: { dataset: { decision: 'accept' } } };
  const first = page.submitVote(event);
  const second = page.submitVote(event);
  assert.equal(calls, 1);
  release();
  await Promise.all([first, second]);
  assert.equal(page.data.submitting, false);
});

test('approval share card opens the approval detail page directly', () => {
  const { page } = loadPage('miniprogram/pages/approval-detail/index.js');
  page.data = { id: 'approval / 1', approval: { title: '降噪耳机' } };
  const share = page.onShareAppMessage();
  assert.equal(share.title, '帮我拿个主意：降噪耳机');
  assert.equal(share.path, '/miniprogram/pages/approval-detail/index?id=approval%20%2F%201');
});

test('approval deep link resumes after automatic WeChat login', () => {
  let destination = '';
  const { app } = loadApp({
    api: { token: () => '', clearSession() {} },
    wx: { reLaunch({ url }) { destination = url; } },
  });
  const authenticated = app.ensureSession({ approvalId: 'approval-1' });
  assert.equal(authenticated, false);
  assert.deepEqual(app.globalData.launchTarget, { approvalId: 'approval-1' });
  assert.equal(destination, '/miniprogram/pages/login/index');
});

test('approval deep link restores the current user before enabling voting', async () => {
  const app = { ensureSession: () => true, globalData: {}, openLaunchTarget() {} };
  const approval = {
    id: 'approval-1', ownerId: 'owner-1', owner: { id: 'owner-1' }, title: '降噪耳机',
    price: 89900, createdAt: 1, expiresAt: 2, status: 'pending', rule: 'majority', imageUrls: [],
    reviewers: [{ id: 'reviewer-1', user: { id: 'reviewer-1' }, decision: null, comment: null, votedAt: null }],
  };
  const { page } = loadPage('miniprogram/pages/approval-detail/index.js', {
    app,
    api: {
      request: async (path) => path === '/api/me' ? { user: { id: 'reviewer-1' } } : { approval },
      absoluteMediaUrl: (value) => value,
      money: () => '¥899.00',
      dateTime: () => '刚刚',
    },
  });
  page.data.id = 'approval-1';
  await page.load();
  assert.equal(app.globalData.user.id, 'reviewer-1');
  assert.equal(page.data.canVote, true);
});

test('approval progress explains each rule without claiming premature approval', () => {
  const { exports: { decorateApproval } } = loadScript('miniprogram/utils/approval.js', { modules: { './format': loadScript('miniprogram/utils/format.js').exports } });
  const base = { status: 'pending', expiresAt: 7200000, reviewers: [{ decision: 'accept' }, { decision: 'reject' }, { decision: null }] };
  assert.equal(decorateApproval({ ...base, rule: 'majority' }, undefined, 0).progressText, '还需要 1 票支持');
  assert.equal(decorateApproval({ ...base, rule: 'unanimous' }, undefined, 0).progressText, '还等 1 位朋友，全部回复后判定');
  assert.equal(decorateApproval({ ...base, rule: 'veto', reviewers: [{ decision: 'accept' }, { decision: null }] }, undefined, 0).progressText, '还等 1 位朋友，任意一票反对即结束');
  assert.equal(decorateApproval({ ...base, status: 'expired' }, undefined, 0).deadlineText, '本次已结束');
});

test('switching approval tabs ignores an older response and updates the pending badge', async () => {
  const responses = [];
  const badges = [];
  const { page } = loadPage('miniprogram/pages/approvals/index.js', {
    api: { request: () => new Promise((resolve) => responses.push(resolve)) },
    wx: { setTabBarBadge: (value) => badges.push(value.text), removeTabBarBadge() {} },
  });
  const first = page.load();
  page.data.scope = 'handled';
  const second = page.load();
  responses[1]({ approvals: [{ id: 'handled-1', status: 'approved', reviewers: [] }], pendingCount: 3 });
  await second;
  responses[0]({ approvals: [{ id: 'pending-1', status: 'pending', reviewers: [] }], pendingCount: 4 });
  await first;
  assert.equal(page.data.approvals[0].id, 'handled-1');
  assert.deepEqual(badges, ['3']);
});

test('reaction toggles update only the item and preserve draft comments', async () => {
  const calls = [];
  const { page } = loadPage('miniprogram/pages/item-detail/index.js', { api: { request: async (path, options) => { calls.push({ path, options }); return { ok: true }; } } });
  page.data = { id: 'item-1', item: { myReaction: 1, likes: 4, dislikes: 2 }, comment: '写了一半的评论', reacting: false };
  await page.react({ currentTarget: { dataset: { value: -1 } } });
  assert.equal(page.data.item.likes, 3);
  assert.equal(page.data.item.dislikes, 3);
  assert.equal(page.data.comment, '写了一半的评论');
  await page.react({ currentTarget: { dataset: { value: -1 } } });
  assert.equal(page.data.item.dislikes, 2);
  assert.equal(page.data.item.myReaction, 0);
  assert.equal(calls.length, 2);
  assert.ok(calls.every((entry) => entry.options.method === 'POST'));
});

test('image preview opens the selected photo in the complete gallery', () => {
  let preview;
  const { page } = loadPage('miniprogram/pages/approval-detail/index.js', { wx: { previewImage: (value) => { preview = value; } } });
  page.data.approval = { photos: ['https://example.test/1.png', 'https://example.test/2.png'] };
  page.previewPhotos({ currentTarget: { dataset: { index: 1 } } });
  assert.equal(preview.current, 'https://example.test/2.png');
  assert.equal(preview.urls.length, 2);
});

test('share card still exports a branded image when the product photo fails', async () => {
  const labels = [];
  const context = new Proxy({}, { get(_, key) {
    if (key === 'measureText') return (text) => ({ width: Array.from(text).length * 22 });
    if (key === 'fillText') return (text) => labels.push(text);
    if (key === 'draw') return (_, callback) => callback();
    return () => {};
  } });
  const { exports } = loadScript('miniprogram/utils/share-card.js', { globals: { wx: {
    getImageInfo({ fail }) { fail(); },
    createCanvasContext() { return context; },
    canvasToTempFilePath({ success }) { success({ tempFilePath: '/tmp/share.png' }); },
  } } });
  const image = await exports.createShareCard({}, {
    photos: ['https://example.test/broken.png'], title: '一个特别长的商品标题需要正确截断避免与价格重叠', priceText: '¥899.00', ruleText: '多数决定',
    reviewers: [{ comment: '这条私密意见不该出现在封面' }],
  });
  assert.equal(image, '/tmp/share.png');
  assert.ok(labels.includes('¥899.00'));
  assert.ok(labels.some((text) => text.endsWith('…')));
  assert.ok(!labels.some((text) => text.includes('私密意见')));
});
