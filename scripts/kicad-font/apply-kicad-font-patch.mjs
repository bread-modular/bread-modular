#!/usr/bin/env node
/**
 * Generate a KiCad-font @tscircuit/alphabet dist from kicad-alphabet.json
 * (produced by extract-glyphs.py) and patch node_modules.
 *
 * Usage: node apply-kicad-font-patch.mjs [ts-modules-dir]
 *
 * Rewrites node_modules/@tscircuit/alphabet/dist/index.js with the KiCad
 * glyph strokes + metrics so silkscreen text in gerbers uses the same
 * "KiCad Font: Sans" stroke geometry as the KiCad originals.
 *
 * Convention (matches the tscircuit gerber writer):
 *   - glyph coords scale with font_size*0.7, advances with font_size
 *   - cap band spans 1/0.7 = 1.4286 norm units, baseline at 0.051, so
 *     cap height == font_size (KiCad semantics)
 *   - advanceRatio is in font-size units: advance_mm / capH
 *   - glyph ink is centered inside its advance cell
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(
  fs.readFileSync(path.join(here, 'kicad-alphabet.json'), 'utf8'));

const root = path.resolve(process.argv[2] ?? path.resolve(here, '..'));
const distPath = path.join(root, 'node_modules', '@tscircuit', 'alphabet',
  'dist', 'index.js');

const capH = data.capH_mm;
const SCALE = 1 / 0.7 / capH;   // mm -> normalized units
const BASELINE_NORM = 0.051;    // baseline y (line space, y-up)

function fmt(n) {
  if (!isFinite(n) || Math.abs(n) < 1e-9) return '0';
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(5).replace(/0+$/, '').replace(/\.$/, '');
}

// per-char advance ratio in font-size units (physical advance = ratio * font_size)
const advNorm = {};
for (const [ch, g] of Object.entries(data.glyphs)) {
  advNorm[ch] = +(g.advance_mm / capH).toFixed(6);
}
advNorm[' '] = +(data.space_advance_mm / capH).toFixed(6);

function glyphPath(ch, adv) {
  const g = data.glyphs[ch];
  if (!g) return '';
  // ink center at the middle of the advance cell (norm units)
  const half = advNorm[ch] / 2 / 1.4;
  return g.lines
    .map(([x1, y1, x2, y2]) => {
      const ax = half + x1 * SCALE, ay = 1 - (BASELINE_NORM + y1 * SCALE);
      const bx = half + x2 * SCALE, by = 1 - (BASELINE_NORM + y2 * SCALE);
      return `M${fmt(ax)} ${fmt(ay)} L${fmt(bx)} ${fmt(by)}`;
    })
    .join(' ');
}

const caps = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').filter((c) => data.glyphs[c]);
const meanAdv = caps.reduce((s, c) => s + advNorm[c], 0) / caps.length;

const svgAlphabetSrc = 'var svgAlphabet = {\n' +
  Object.keys(data.glyphs).map((ch) => {
    const key = /^[A-Za-z0-9_]+$/.test(ch) ? ch : JSON.stringify(ch);
    return `  ${key}: "${glyphPath(ch, advNorm[ch])}"`;
  }).join(',\n') + '\n};';

const glyphAdvSrc = 'var glyphAdvanceRatio = {\n' +
  Object.keys(data.glyphs).map((ch) => {
    const key = /^[A-Za-z0-9_]+$/.test(ch) ? ch : JSON.stringify(ch);
    return `  ${key}: ${advNorm[ch]}`;
  }).join(',\n') + ',\n  " ": ' + advNorm[' '] + '\n};';

let src = fs.readFileSync(distPath, 'utf8');
if (!fs.existsSync(distPath + '.orig')) {
  fs.writeFileSync(distPath + '.orig', src);
}

function replaceBlock(text, startMarker, replacement) {
  const i = text.indexOf(startMarker);
  if (i < 0) throw new Error(`patch target not found: ${startMarker}`);
  const j = text.indexOf('\n};', i);
  if (j < 0) throw new Error(`block end not found for ${startMarker}`);
  return text.slice(0, i) + replacement + text.slice(j + 3);
}

src = replaceBlock(src, 'var svgAlphabet = {\n', svgAlphabetSrc);
src = replaceBlock(src, 'var glyphAdvanceRatio = {\n', glyphAdvSrc);
src = src.replace('var strokeWidthRatio = 0.09;', 'var strokeWidthRatio = 0.15;');
src = src.replace(/var glyphWidthRatio = [0-9.]+;/, `var glyphWidthRatio = ${meanAdv.toFixed(6)};`);
src = src.replace(/var spaceWidthRatio = [0-9.]+;/, `var spaceWidthRatio = ${advNorm[' ']};`);

fs.writeFileSync(distPath, src);
console.log(`patched ${distPath} (${Object.keys(data.glyphs).length} KiCad glyphs)`);

// ---------------------------------------------------------------------------
// KiCad bold-title stroke: tscircuit computes silkscreen text stroke as
// fontSize * strokeWidthRatio (0.15 after the patch above). KiCad uses 0.15
// for 1mm text but 0.2 for the 2mm bold module title (0.4mm stroke), so make
// the ratio size-aware inside the tscircuit CLI bundle:
//   - gerber aperture: getApertureConfigFromPcbSilkscreenText
//   - text layout (SVG stroke + gerber cursor offset): getAlphabetLayout
// Idempotent + non-fatal (upstream refactors shouldn't break builds).
const cliPath = path.join(root, 'node_modules', '@tscircuit', 'cli',
  'dist', 'cli', 'main.js');
if (fs.existsSync(cliPath)) {
  let cli = fs.readFileSync(cliPath, 'utf8');
  const GOOD = 'elm.font_size > 1.5 ? 0.2 : 0.15';
  const ORIGINAL =
    '      diameter: elm.font_size * strokeWidthRatio\n' +
    '    };\n' +
    '  }\n' +
    '  throw new Error(`Provide font_size for: ${elm}`);\n' +
    '}, getApertureConfigFromPcbCopperText';
  const PATCHED =
    `      diameter: elm.font_size * (${GOOD})\n` +
    '    };\n' +
    '  }\n' +
    '  throw new Error(`Provide font_size for: ${elm}`);\n' +
    '}, getApertureConfigFromPcbCopperText';
  let cliPatched = cli.includes(GOOD);
  // repair a previously (buggy) patched file: bare `font_size` -> `elm.font_size`
  cli = cli.replace(
    'diameter: elm.font_size * (font_size > 1.5 ? 0.2 : 0.15)',
    `diameter: elm.font_size * (${GOOD})`);
  if (!cliPatched && cli.includes(ORIGINAL)) {
    cli = cli.replace(ORIGINAL, PATCHED);
    cli = cli.replace(
      'const strokeWidth = fontSize * textMetrics.strokeWidthRatio;',
      'const strokeWidth = fontSize * (fontSize > 1.5 ? 0.2 : 0.15);');
  }
  if (cli.includes(GOOD) && !cli.includes('(font_size > 1.5')) {
    fs.writeFileSync(cliPath, cli);
    cliPatched = true;
  }
  console.log(cliPatched
    ? `patched ${cliPath} (size-aware silkscreen stroke: 0.4mm @ 2mm text)`
    : `warn: could not patch ${cliPath} (upstream changed?)`);
}
