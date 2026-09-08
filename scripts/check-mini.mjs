import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mini = path.join(root, 'miniprogram');
const errors = [];
function readJson(filename) {
  try { return JSON.parse(fs.readFileSync(filename, 'utf8')); }
  catch (error) { errors.push(`${path.relative(root, filename)}: ${error.message}`); return {}; }
}
const app = readJson(path.join(mini, 'app.json'));
readJson(path.join(root, 'project.config.json'));
readJson(path.join(mini, 'sitemap.json'));
for (const page of app.pages || []) {
  const base = path.join(mini, page);
  for (const ext of ['.js', '.json', '.wxml']) {
    if (!fs.existsSync(base + ext)) errors.push(`missing ${path.relative(root, base + ext)}`);
  }
  const config = fs.existsSync(base + '.json') ? readJson(base + '.json') : {};
  for (const componentPath of Object.values(config.usingComponents || {})) {
    const target = path.join(mini, componentPath.replace(/^\//, ''));
    if (!fs.existsSync(target + '.json')) errors.push(`missing component ${componentPath}`);
  }
  if (fs.existsSync(base + '.wxml') && fs.existsSync(base + '.js')) {
    const markup = fs.readFileSync(base + '.wxml', 'utf8');
    const script = fs.readFileSync(base + '.js', 'utf8');
    const handlers = [...markup.matchAll(/(?:bind|catch)(?:tap|input|change|submit|longpress)="([A-Za-z_$][\w$]*)"/g)].map((match) => match[1]);
    for (const handler of new Set(handlers)) {
      const signature = new RegExp(`(?:async\\s+)?${handler}\\s*\\(`);
      if (!signature.test(script)) errors.push(`${page}: missing event handler ${handler}`);
    }
  }
}
const scripts = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(filename);
    else if (entry.name.endsWith('.js')) scripts.push(filename);
  }
}
walk(mini);
for (const filename of scripts) {
  const result = spawnSync(process.execPath, ['--check', filename], { encoding: 'utf8' });
  if (result.status !== 0) errors.push(`${path.relative(root, filename)}: ${result.stderr.trim()}`);
}
if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`mini-program static check passed: ${app.pages.length} pages, ${scripts.length} scripts`);
