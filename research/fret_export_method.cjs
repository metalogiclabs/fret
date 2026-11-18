// Pinned NASA FRET source-method research harness, not an Electron UI export.
// The actual original exportComponent and variable-mapping functions execute
// verbatim in a constrained VM.  Only PouchDB and Webpack's EJS loader are
// substituted, so this tests the method boundary, not a packaged FRET build.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');

const PINNED_FRET = 'cf0f913cc15c41705e803593297e89cd6056b839';

function sha256(content) {
  return createHash('sha256').update(content).digest('hex');
}

function assertSourcePin(fretDir) {
  const sha = execFileSync('git', ['-C', fretDir, 'rev-parse', 'HEAD'],
    {encoding: 'utf8'}).trim();
  if (sha !== PINNED_FRET) {
    throw new Error(`Expected FRET ${PINNED_FRET}, got ${sha}`);
  }
}

function readSource(fretDir, rel) {
  return fs.readFileSync(path.join(fretDir, 'fret-electron', rel), 'utf8');
}

function readRealMappingFunctions(fretDir) {
  const file = readSource(fretDir, 'model/modelDbSupport/variableMappingSupports.js');
  const source = file.replace(/^import\s+[^\n]+\n/gm, '')
    .replace(/^export\s*\{[\s\S]*?\}\s*;?/m, '');
  if (source === file || source.includes('export {')) {
    throw new Error('Unrecognized FRET mapping module structure');
  }
  const utils = require(path.join(fretDir, 'fret-electron/support/utils.js'));
  const constants = require(path.join(fretDir, 'fret-electron/app/parser/Constants.js'));
  const context = {
    require: name => ({
      '../../support/utils': utils,
      '../../app/parser/Constants': constants,
      '../../support/cocospecSemantics': {},
      '../../support/xform': {},
    })[name] ?? (() => {throw new Error(`Unknown mapping require: ${name}`);})(),
  };
  return vm.runInNewContext(source + '\n;({getContractInfo,getPropertyInfo,getDelayInfo,variableIdentifierReplacement})',
    context, {filename: 'variableMappingSupports.js', timeout: 5000});
}

function expandIncludes(fretDir, templateName) {
  const dir = path.join(fretDir, 'fret-electron');
  let content = fs.readFileSync(path.join(dir, 'support/CoPilotTemplates', templateName), 'utf8');
  for (let pass = 0; pass < 10; pass++) {
    const next = content.replace(/<%-\s*include\s+([^\s%]+)\s*%>/g,
      (_match, rel) => {
        if (!/^\.\/support\/CoPilotTemplates\/[\w.-]+\.ejs$/.test(rel)) {
          throw new Error(`Unrecognized EJS include ${rel}`);
        }
        return fs.readFileSync(path.join(dir, rel), 'utf8');
      });
    if (next === content) return next;
    content = next;
  }
  throw new Error('EJS includes did not converge');
}

// Interprets the source's exact EJS control blocks and raw output expressions;
// unlike the real ejs-compiled-loader, this does not escape/render HTML.
function renderSourceTemplate(fretDir, contract) {
  const source = expandIncludes(fretDir, 'Complete.ejs');
  const token = /<%([=-]?)([\s\S]*?)%>/g;
  const statements = [];
  let lastIndex = 0;
  for (const match of source.matchAll(token)) {
    statements.push(`__out += ${JSON.stringify(source.slice(lastIndex, match.index))};`);
    if (match[1] === '-' || match[1] === '=') {
      statements.push(`{const __v = (${match[2].trim()}); __out += __v == null ? '' : String(__v);}`);
    } else {
      statements.push(match[2]);
    }
    lastIndex = match.index + match[0].length;
  }
  statements.push(`__out += ${JSON.stringify(source.slice(lastIndex))};`);
  return new Function('locals', `let __out = ''; with (locals) { ${statements.join('\n')} } return __out;`)(contract);
}

function readRealExportMethod(fretDir, dependencies) {
  const file = readSource(fretDir, 'model/FretModel.js');
  const begin = file.indexOf('  async exportComponent(evt,args){');
  const end = file.indexOf('\n  async exportTestObligations(', begin);
  if (begin < 0 || end < 0) throw new Error('Unrecognized exportComponent method boundaries');
  const method = file.slice(begin, end);
  const context = vm.createContext(dependencies);
  return vm.runInContext(`(class FretModel {\n${method}\n})`, context,
    {filename: 'FretModel.exportComponent.js', timeout: 5000});
}

async function exportFromSource({
  fretDir, casePath, reqIds, variableNames, changeFormula, project = 'LPC',
}) {
  assertSourcePin(fretDir);
  const bytes = fs.readFileSync(casePath);
  const data = JSON.parse(bytes);
  const wantedReq = reqIds && new Set(reqIds);
  const wantedVars = variableNames && new Set(variableNames);
  const variables = data.variables.filter(v => !wantedVars || wantedVars.has(v.variable_name));
  const requirements = data.requirements.filter(r => !wantedReq || wantedReq.has(r.reqid));
  if (changeFormula) {
    if (requirements.length !== 1) throw new Error('Formula control requires one requirement');
    requirements[0].semantics.CoCoSpecCode = changeFormula;
  }
  const modelDB = {find: async ({selector}) => ({docs: variables.filter(v =>
    Object.entries(selector).every(([key, value]) => v[key] === value))})};
  const leveldbDB = {find: async ({selector}) => ({docs: requirements.filter(r =>
    Object.entries(selector).every(([key, value]) => r[key] === value))})};
  const mapping = readRealMappingFunctions(fretDir);
  const FretModel = readRealExportMethod(fretDir, {
    modelDB, leveldbDB,
    ...mapping,
    ejsCacheCoPilot: {renderCoPilotSpec: () => ({
      contract: {complete: c => renderSourceTemplate(fretDir, c)},
    })},
  });
  const files = await new FretModel().exportComponent(null, ['vehicle', project, 'copilot']);
  return {
    files: JSON.parse(JSON.stringify(files)),
    sourcePin: PINNED_FRET,
    caseSha256: sha256(bytes),
    methodSha256: sha256(readSource(fretDir, 'model/FretModel.js')),
  };
}

module.exports = {exportFromSource, PINNED_FRET};
