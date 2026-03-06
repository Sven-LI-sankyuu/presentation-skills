#!/usr/bin/env node
/**
 * 网页 demo 录制器（Playwright）
 *
 * 作用：
 * - 打开目标 URL，按步骤脚本执行页面操作。
 * - 录制原始视频（webm），用于后续字幕烧录和转码。
 *
 * 关键点：
 * - 显式区分 viewport、record size、device scale factor。
 * - 输入错误时直接失败，避免静默降级。
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      throw new Error(`非法参数: ${token}`);
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      args[key] = 'true';
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

function parseSize(input, keyName) {
  const match = /^(\d+)x(\d+)$/i.exec(input || '');
  if (!match) {
    throw new Error(`${keyName} 格式错误，应为 WIDTHxHEIGHT，例如 1920x1080`);
  }
  return { width: Number(match[1]), height: Number(match[2]) };
}

function parseNumber(input, keyName) {
  const value = Number(input);
  if (!Number.isFinite(value)) {
    throw new Error(`${keyName} 必须是数字`);
  }
  return value;
}

function parseBool(input, defaultValue) {
  if (input === undefined) return defaultValue;
  const normalized = String(input).toLowerCase();
  if (['true', '1', 'yes', 'y'].includes(normalized)) return true;
  if (['false', '0', 'no', 'n'].includes(normalized)) return false;
  throw new Error(`布尔参数取值错误: ${input}`);
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadSteps(stepsPath) {
  if (!stepsPath) return [];
  const raw = await fs.readFile(stepsPath, 'utf8');
  const data = JSON.parse(raw);
  if (!Array.isArray(data)) {
    throw new Error('steps 文件必须是数组');
  }
  return data;
}

async function runStep(page, step, index) {
  const action = step.action;
  if (!action) {
    throw new Error(`steps[${index}] 缺少 action`);
  }

  switch (action) {
    case 'wait': {
      const ms = parseNumber(step.ms, `steps[${index}].ms`);
      await sleep(ms);
      return;
    }
    case 'click': {
      if (!step.selector) throw new Error(`steps[${index}].selector 不能为空`);
      await page.locator(step.selector).first().click({ timeout: step.timeoutMs || 15000 });
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    case 'type': {
      if (!step.selector) throw new Error(`steps[${index}].selector 不能为空`);
      if (step.text === undefined) throw new Error(`steps[${index}].text 不能为空`);
      const locator = page.locator(step.selector).first();
      await locator.fill('');
      await locator.type(String(step.text), { delay: step.delayMs ? parseNumber(step.delayMs, `steps[${index}].delayMs`) : 20 });
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    case 'press': {
      if (!step.key) throw new Error(`steps[${index}].key 不能为空`);
      await page.keyboard.press(step.key);
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    case 'scroll_to': {
      if (!step.selector) throw new Error(`steps[${index}].selector 不能为空`);
      await page.locator(step.selector).first().scrollIntoViewIfNeeded({ timeout: step.timeoutMs || 15000 });
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    case 'wheel': {
      const dx = step.deltaX ? parseNumber(step.deltaX, `steps[${index}].deltaX`) : 0;
      const dy = step.deltaY ? parseNumber(step.deltaY, `steps[${index}].deltaY`) : 0;
      await page.mouse.wheel(dx, dy);
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    case 'goto': {
      if (!step.url) throw new Error(`steps[${index}].url 不能为空`);
      await page.goto(step.url, {
        timeout: step.timeoutMs || 30000,
        waitUntil: step.waitUntil || 'networkidle',
      });
      if (step.afterMs) await sleep(parseNumber(step.afterMs, `steps[${index}].afterMs`));
      return;
    }
    default:
      throw new Error(`不支持的 action: ${action}`);
  }
}

async function main() {
  const args = parseArgs(process.argv);

  if (!args.url) {
    throw new Error('缺少 --url');
  }

  const outDir = args['out-dir'] || 'temp/demo_video';
  const viewport = parseSize(args.viewport || '1920x1080', '--viewport');
  const recordSize = parseSize(args['record-size'] || `${viewport.width}x${viewport.height}`, '--record-size');
  const deviceScaleFactor = parseNumber(args['device-scale-factor'] || '1', '--device-scale-factor');
  const waitBeforeMs = parseNumber(args['wait-before-ms'] || '1200', '--wait-before-ms');
  const waitAfterMs = parseNumber(args['wait-after-ms'] || '1200', '--wait-after-ms');
  const timeoutMs = parseNumber(args['timeout-ms'] || '30000', '--timeout-ms');
  const headless = parseBool(args.headless, true);
  const outName = args['out-name'] || 'raw.webm';

  await fs.mkdir(outDir, { recursive: true });
  const steps = await loadSteps(args.steps);

  const browser = await chromium.launch({
    headless,
    args: [`--force-device-scale-factor=${deviceScaleFactor}`],
  });

  const context = await browser.newContext({
    viewport,
    deviceScaleFactor,
    recordVideo: {
      dir: outDir,
      size: recordSize,
    },
  });

  const page = await context.newPage();
  await page.goto(args.url, { waitUntil: 'networkidle', timeout: timeoutMs });
  await sleep(waitBeforeMs);

  for (let i = 0; i < steps.length; i += 1) {
    await runStep(page, steps[i], i);
  }

  await sleep(waitAfterMs);

  const video = page.video();
  await context.close();
  await browser.close();

  if (!video) {
    throw new Error('未获得录制视频对象');
  }

  const rawPath = await video.path();
  const finalPath = path.resolve(outDir, outName);

  if (path.resolve(rawPath) !== finalPath) {
    await fs.copyFile(rawPath, finalPath);
  }

  const summary = {
    url: args.url,
    out: finalPath,
    viewport,
    recordSize,
    deviceScaleFactor,
    steps: steps.length,
  };

  console.log(JSON.stringify(summary, null, 2));
}

main().catch((err) => {
  console.error(`[record_web_demo_with_playwright] ${err.message}`);
  process.exit(1);
});
