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
      if (specifier.startsWith('/')) return extras.modules?.[specifier];
      throw new Error(`Unexpected require: ${specifier}`);
    },
    ...extras.globals,
  };
  vm.runInNewContext(source, sandbox, { filename });
  return { exports: sandbox.module.exports, sandbox };
}

function loadPage(relativePath, { api = {}, wx = {} } = {}) {
  let definition;
  const { sandbox } = loadScript(relativePath, {
    modules: { '/utils/api': api, '/utils/format': api },
    globals: {
      Page(value) { definition = value; },
      getApp() { return { ensureSession: async () => true }; },
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

test('compose converts a two-decimal yuan price to integer cents', () => {
  const { exports } = loadScript('miniprogram/utils/format.js');
  assert.equal(exports.yuanToCents('12.34'), 1234);
  assert.equal(exports.yuanToCents('0.01'), 1);
  assert.equal(exports.yuanToCents('12.345'), null);
  assert.equal(exports.yuanToCents(''), null);
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
