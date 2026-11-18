// Source-pinned characterization of NASA FRET's real exportComponent method.
// The method and mapping helpers run unchanged; the UI database and Webpack/EJS
// loader are substituted. These tests do not claim an Electron GUI replay.
const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const os = require('node:os');
const fs = require('node:fs');
const {spawnSync} = require('node:child_process');
const {exportFromSource} = require('./fret_export_method.cjs');

const fretDir = path.resolve(process.env.FRET_SOURCE_DIR || path.join(__dirname, '../../fret_live'));
const casePath = path.join(fretDir, 'caseStudies/LiftPlusCruise/LPC_full_reqts_and_vars.json');

test('FRET source method emits unchanged LPC_REARPROP XOR semantics with two typed signals', async () => {
  const result = await exportFromSource({
    fretDir, casePath, reqIds: ['LPC_REARPROP'],
    variableNames: ['rearprop', 'hover_control_mode'],
  });
  assert.equal(result.files.length, 1);
  assert.equal(result.files[0].name, 'vehicleSpec.json');
  const contract = JSON.parse(result.files[0].content).vehicleSpec;
  assert.deepEqual(contract.Other_variables, [
    {name: 'hover_control_mode', type: 'bool'},
    {name: 'rearprop', type: 'bool'},
  ]);
  assert.equal(contract.Requirements.length, 1);
  assert.equal(contract.Requirements[0].name, 'LPC_REARPROP');
  assert.equal(contract.Requirements[0].CoCoSpecCode,
    'H((rearprop xor hover_control_mode))');
  assert.equal(contract.Requirements[0].ptLTL,
    '(H (rearprop xor hover_control_mode))');
});

test('FRET source method propagates changed stored formula without normalizing it', async () => {
  const result = await exportFromSource({
    fretDir, casePath, reqIds: ['LPC_REARPROP'],
    variableNames: ['rearprop', 'hover_control_mode'],
    changeFormula: 'H((rearprop and hover_control_mode))',
  });
  const actual = JSON.parse(result.files[0].content).vehicleSpec.Requirements[0];
  assert.equal(actual.CoCoSpecCode, 'H((rearprop and hover_control_mode))');
});

test('FRET source method full project exports every admissible matching requirement', async () => {
  const result = await exportFromSource({fretDir, casePath});
  assert.equal(result.files.length, 1);
  const contract = JSON.parse(result.files[0].content).vehicleSpec;
  assert.equal(contract.Other_variables.length, 9);
  assert.equal(contract.Requirements.length, 57);
  assert.equal(contract.Requirements.filter(r => r.name === 'LPC_REARPROP').length, 1);
});

test('source method emits empty contract when selected project has no records', async () => {
  const result = await exportFromSource({
    fretDir, casePath, project: 'non-existent-project',
  });
  assert.equal(result.files.length, 1);
  const contract = JSON.parse(result.files[0].content).vehicleSpec;
  assert.deepEqual(contract.Other_variables, []);
  assert.deepEqual(contract.Requirements, []);
});

test('research runner preserves original and changed-formula contracts with an evidence receipt', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fret-source-method-'));
  try {
    const runner = path.join(__dirname, 'run_fret_export_method.cjs');
    const result = spawnSync(process.execPath, [runner, '--fret', fretDir, '--out', dir],
      {encoding: 'utf8'});
    assert.equal(result.status, 0, result.stderr);
    const originalPath = path.join(dir, 'method-original.json');
    const controlPath = path.join(dir, 'method-control.json');
    const receiptPath = path.join(dir, 'method-receipt.json');
    const original = JSON.parse(fs.readFileSync(originalPath)).vehicleSpec;
    const control = JSON.parse(fs.readFileSync(controlPath)).vehicleSpec;
    const receipt = JSON.parse(fs.readFileSync(receiptPath));
    assert.equal(original.Requirements[0].CoCoSpecCode,
      'H((rearprop xor hover_control_mode))');
    assert.equal(control.Requirements[0].CoCoSpecCode,
      'H(((rearprop or hover_control_mode) and not (rearprop and hover_control_mode)))');
    assert.deepEqual(original.Other_variables, control.Other_variables);
    assert.equal(receipt.originalSha256.length, 64);
    assert.equal(receipt.controlSha256.length, 64);
    assert.equal(receipt.fullProjectVariables, 9);
    assert.equal(receipt.fullProjectRequirements, 57);
  } finally {
    fs.rmSync(dir, {recursive: true, force: true});
  }
});
