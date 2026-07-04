const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync('work/restaurant-costing-app-script.js', 'utf8');
const elements = {};
function el(id) {
  if (!elements[id]) {
    elements[id] = {
      id,
      innerHTML: '',
      textContent: '',
      value: '',
      style: {},
      files: [],
      classList: { add() {}, remove() {} },
      appendChild() {},
      remove() {},
      querySelectorAll() { return []; },
      querySelector() { return null; },
      scrollIntoView() {},
      focus() {}
    };
  }
  return elements[id];
}
const context = {
  console,
  structuredClone,
  setTimeout(fn) { if (typeof fn === 'function') fn(); return 0; },
  clearTimeout() {},
  alert(message) { context.lastAlert = message; },
  confirm() { return true; },
  localStorage: { getItem() { return null; }, setItem() {} },
  document: {
    getElementById: el,
    querySelectorAll() { return []; },
    querySelector() { return null; },
    createElement() { return el('created_' + Math.random()); }
  },
  window: {}
};
context.window = context;
vm.createContext(context);
vm.runInContext(script, context);
const rows = context.parseInvoiceRows('Calamari, 2, KG, 50\nPatagonia, 1, KG, 80');
const match = context.findInvoiceStockMatch({ raw: 'Patagonia', qty: 1, unit: 'KG', unitPrice: 80 });
if (rows.length !== 2) throw new Error('Expected 2 rows, got ' + rows.length);
if (!match || match.type !== 'suggested' || !match.needsReview) throw new Error('Expected suggested review match for Patagonia');
console.log(JSON.stringify({ rows: rows.length, patagoniaMatch: match.stock.name, review: match.needsReview }));
