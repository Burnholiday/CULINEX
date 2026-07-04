const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync('work/restaurant-costing-app-script.js', 'utf8');
const elements = {};
function el(id) {
  if (!elements[id]) elements[id] = { id, innerHTML: '', textContent: '', value: '', style: {}, classList: { add() {}, remove() {} }, appendChild() {}, querySelectorAll() { return []; }, querySelector() { return null; }, scrollIntoView() {}, focus() {} };
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
  document: { getElementById: el, querySelectorAll() { return []; }, querySelector() { return null; }, createElement() { return el('created_' + Math.random()); } },
  XLSX: { utils: { sheet_to_json(sheet) { return sheet.__rows; } } },
  window: {}
};
context.window = context;
vm.createContext(context);
vm.runInContext(script, context);
const workbook = {
  SheetNames: ['Recipes Import', 'Ingredients Import'],
  Sheets: {
    'Recipes Import': { __rows: [
      ['Recipe Code', 'Recipe Name', 'Category', 'Yield Quantity', 'Yield Unit'],
      ['FOCACCIA', 'Focaccia', 'Pastry', 1000, 'pc'],
      ['TERIYAKI', 'Teriyaki Sauce', 'Sauces', 1000, 'each']
    ] },
    'Ingredients Import': { __rows: [
      ['Recipe Code', 'Recipe Name', 'Line No', 'Ingredient', 'Quantity Used', 'Unit'],
      ['FOCACCIA', 'Focaccia', 1, 'Flour', 1000, 'g'],
      ['FOCACCIA', 'Focaccia', 2, 'Water', 600, 'ml'],
      ['TERIYAKI', 'Teriyaki Sauce', 1, 'Soy Sauce', 500, 'ml'],
      ['TERIYAKI', 'Teriyaki Sauce', 2, 'Mirin', 500, 'ml'],
      ['TERIYAKI', 'Teriyaki Sauce', 3, 'Sugar', 500, 'g']
    ] }
  }
};
const items = context.extractPrepItemsFromWorkbookRows(workbook);
const focaccia = items.find(item => item.name === 'Focaccia');
const teriyaki = items.find(item => item.name === 'Teriyaki Sauce');
if (!focaccia || focaccia.yieldUnit !== 'g') throw new Error('Expected Focaccia large count yield to normalize to g, got ' + focaccia?.yieldUnit);
if (!teriyaki || teriyaki.yieldUnit !== 'ml') throw new Error('Expected Teriyaki large count yield to normalize to ml, got ' + teriyaki?.yieldUnit);
const impossible = context.stockUnitsForRecipeUnit('EACH', 'g');
if (impossible !== 0) throw new Error('Expected EACH to g conversion to be blocked');
console.log(JSON.stringify({ focaccia: focaccia.yieldUnit, teriyaki: teriyaki.yieldUnit, impossible }));
