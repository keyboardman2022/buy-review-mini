const BASE_URL = 'http://127.0.0.1:3210';

function token() { return wx.getStorageSync('token') || ''; }

function clearSession() {
  wx.removeStorageSync('token');
  try { getApp().globalData.user = null; } catch (_) {}
}

function request(path, options = {}) {
  const method = options.method || 'GET';
  const headers = { 'content-type': 'application/json', ...(options.header || {}) };
  const bearer = token();
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${path}`,
      method,
      data: options.data,
      header: headers,
      timeout: 12000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        const message = response.data && response.data.error ? response.data.error : `请求失败（${response.statusCode}）`;
        if (response.statusCode === 401) clearSession();
        const error = new Error(message);
        error.statusCode = response.statusCode;
        reject(error);
      },
      fail(error) { reject(new Error(error.errMsg || '网络连接失败，请确认本地服务已启动')); },
    });
  });
}

function absoluteMediaUrl(url) {
  if (!url) return '';
  return /^https?:\/\//.test(url) ? url : `${BASE_URL}${url}`;
}

function uploadImage(filePath) {
  const ext = (filePath.split('.').pop() || '').toLowerCase();
  const mime = ext === 'png' ? 'image/png' : ext === 'webp' ? 'image/webp' : 'image/jpeg';
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      encoding: 'base64',
      success: async ({ data }) => {
        try { resolve(await request('/api/media', { method: 'POST', data: { base64: data, mime } })); }
        catch (error) { reject(error); }
      },
      fail: () => reject(new Error('读取图片失败，请重新选择')),
    });
  });
}

module.exports = { BASE_URL, token, clearSession, request, absoluteMediaUrl, uploadImage };
