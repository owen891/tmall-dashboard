#!/usr/bin/env node
'use strict';

// 选择 electron-builder 配置并透传额外参数。
//
// 为什么需要这层：CI 在没有 Developer ID 证书时必须显式退到 ad-hoc 签名，
// 否则 electron-builder 会「静默跳过签名」，产出的 .app 没有
// _CodeSignature/CodeResources 封印，用户下载后 macOS 直接报「文件已损坏」。
// 而 CLI 追加 `-c.mac.identity=-` 走不通：yargs 把它当成 config 文件路径，
// 报 ENOENT open '...\.mac.identity=-'。所以改用独立 overlay 配置文件切换。
//
// 用法：
//   npm run dist:mac -- --arm64              # 有证书，走 electron-builder.yml
//   MAC_ADHOC=1 npm run dist:mac -- --arm64  # 无证书，走 electron-builder.adhoc.yml

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const adhoc = process.env.MAC_ADHOC === '1' || process.env.MAC_ADHOC === 'true';
const config = adhoc ? 'electron-builder.adhoc.yml' : 'electron-builder.yml';
const repoDesktop = path.resolve(__dirname, '..');

const args = [
  path.join(repoDesktop, 'node_modules', 'electron-builder', 'out', 'cli', 'cli.js'),
  '--config', config,
  '--mac', 'dmg', 'zip',
  '--publish', 'never',
  ...process.argv.slice(2),
];

console.log(`[dist-mac] config=${config} adhoc=${adhoc}`);
const result = spawnSync(process.execPath, args, {
  cwd: repoDesktop,
  stdio: 'inherit',
  env: process.env,
});
process.exit(result.status === null ? 1 : result.status);
