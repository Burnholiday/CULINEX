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
el('invoiceText').value = 'Patagonia, 1, KG, 80';
el('invoiceSupplier').value = 'Test Supplier';
el('invoiceName').value = 'Test Invoice';
context.importInvoice();
const reviews = context.invoiceReviewItems();
if (reviews.length !== 1) throw new Error('Expected one review item, got ' + reviews.length);
if (!/1 item needs stock review/.test(context.lastAlert || '')) throw new Error('Expected singular stock review alert, got: ' + context.lastAlert);
console.log(JSON.stringify({reviews: reviews.length, alert: context.lastAlert}));
