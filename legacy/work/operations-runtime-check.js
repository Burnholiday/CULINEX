const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync('work/restaurant-costing-app-script.js', 'utf8');
const elements = {};
function el(id) {
  if (!elements[id]) {
    elements[id] = { id, innerHTML: '', textContent: '', value: '', style: {}, files: [], classList: { add() {}, remove() {} }, appendChild() {}, remove() {}, querySelectorAll() { return []; }, querySelector() { return null; }, scrollIntoView() {}, focus() {} };
  }
  return elements[id];
}
const context = { console, structuredClone, setTimeout(fn) { if (typeof fn === 'function') fn(); return 0; }, clearTimeout() {}, alert(message) { context.lastAlert = message; }, confirm() { return true; }, localStorage: { getItem() { return null; }, setItem() {} }, document: { getElementById: el, querySelectorAll() { return []; }, querySelector() { return null; }, createElement() { return el('created_' + Math.random()); } }, window: {} };
context.window = context;
vm.createContext(context);
vm.runInContext(script, context);
context.setPage('operations');
el('opsQuestion').value = 'Which recipes have missing stock prices?';
context.askOperationsManager();
const html = el('operations').innerHTML;
const answer = el('opsAnswer').innerHTML;
if (!html.includes('Operations Manager Core')) throw new Error('Operations page did not render base model');
if (!answer || !answer.includes('ingredient')) throw new Error('Operations answer did not render expected content');
console.log(JSON.stringify({pageRendered: html.includes('Restaurant copy'), answerLength: answer.length}));
