'use strict';

const path = require('path');
const { execFile } = require('child_process');
const { promisify } = require('util');

const execFileAsync = promisify(execFile);

const SKILL_DIR = path.resolve(__dirname, '..', 'skills', 'research-report');
const SCRIPTS_DIR = path.join(SKILL_DIR, 'scripts');

/**
 * Run a bundled Python script inside skills/research-report/scripts.
 * @param {string} pythonBin
 * @param {string} scriptName
 * @param {string[]} args
 */
async function runSkillScript(pythonBin, scriptName, args) {
  const scriptPath = path.join(SCRIPTS_DIR, scriptName);
  const { stdout, stderr } = await execFileAsync(pythonBin, [scriptPath, ...args], {
    windowsHide: true,
    maxBuffer: 10 * 1024 * 1024,
  });
  return {
    stdout: (stdout || '').trim(),
    stderr: (stderr || '').trim(),
  };
}

/**
 * DeepSeek Harness (Cordis) Plugin Entry
 * Registers the `research-report` skill and exposes helper tools for thread checking and DOCX building.
 */
function apply(ctx, config = {}) {
  const pythonBin = config.pythonExecutable || 'python';

  const checkThreadsTool = {
    name: 'check_research_report_threads',
    description:
      '启发式检查中文调研报告 Markdown 源稿是否已将“核心问题/技术难点”与“自研/采购优劣判断”两条主线编入各章节。',
    parameters: {
      type: 'object',
      properties: {
        markdownPath: {
          type: 'string',
          description: '待检查的调研报告 Markdown 文件路径',
        },
      },
      required: ['markdownPath'],
    },
    async execute({ markdownPath }) {
      const { stdout } = await runSkillScript(pythonBin, 'check_threads.py', [markdownPath]);
      return stdout;
    },
  };

  const buildDocxTool = {
    name: 'build_research_report_docx',
    description:
      '将调研报告 Markdown 源稿一键编译为标准中文版式 Word (.docx)，自动插入三级自动目录、刷新页码字段并支持中文路径。',
    parameters: {
      type: 'object',
      properties: {
        markdownPath: {
          type: 'string',
          description: '输入的调研报告 Markdown 文件路径',
        },
        outputPath: {
          type: 'string',
          description: '输出的 Word (.docx) 文件路径',
        },
        renderDir: {
          type: 'string',
          description: '可选：导出 PDF 与逐页预览 PNG 的目录路径',
        },
      },
      required: ['markdownPath', 'outputPath'],
    },
    async execute({ markdownPath, outputPath, renderDir }) {
      const args = [markdownPath, '--out', outputPath];
      if (renderDir) {
        args.push('--render-dir', renderDir);
      }
      const { stdout } = await runSkillScript(pythonBin, 'build_docx.py', args);
      try {
        return JSON.parse(stdout);
      } catch (_) {
        return { ok: true, rawOutput: stdout };
      }
    },
  };

  // Register tools with DeepSeek Harness tool service if available in current Cordis context
  if (ctx && ctx.tools && typeof ctx.tools.register === 'function') {
    ctx.tools.register(checkThreadsTool);
    ctx.tools.register(buildDocxTool);
  } else if (ctx && typeof ctx.tool === 'function') {
    ctx.tool(checkThreadsTool);
    ctx.tool(buildDocxTool);
  }

  // Register bundled skill path if the DSH skills service is present
  if (ctx && ctx.skills && typeof ctx.skills.register === 'function') {
    ctx.skills.register(SKILL_DIR);
  }
}

module.exports = {
  name: 'dsh-plugin-research-report',
  SKILL_DIR,
  SCRIPTS_DIR,
  apply,
  default: {
    name: 'dsh-plugin-research-report',
    apply,
  },
};
