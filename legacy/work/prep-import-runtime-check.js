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
      ['TERIYAKI', 'Teriyaki Sauce', 'Sushi', 1000, 'ml'],
      ['FOCACCIA', 'Focaccia', 'Pastry', 100, 'pc']
    ] },
    'Ingredients Import': { __rows: [
      ['Recipe Code', 'Recipe Name', 'Line No', 'Ingredient', 'Quantity Used', 'Unit'],
      ['TERIYAKI', 'Teriyaki Sauce', 1, 'Soy Sauce', 500, 'ml'],
      ['TERIYAKI', 'Teriyaki Sauce', 2, 'Mirin', 500, 'ml'],
      ['FOCACCIA', 'Focaccia', 1, 'Flour', 1000, 'g']
    ] }
  }
};
const items = context.extractPrepItemsFromWorkbookRows(workbook);
if (items.length !== 2) throw new Error('Expected 2 prep items, got ' + items.length);
if (items[0].category !== 'Sushi') throw new Error('Expected Sushi section, got ' + items[0].category);
if (items[1].category !== 'Pastry') throw new Error('Expected Pastry section, got ' + items[1].category);
if (items[0].ingredients.length !== 2) throw new Error('Expected Teriyaki 2 ingredients');
const tabsHtml = context.prepSectionTabs();
if (!tabsHtml.includes('Hot Section') || !tabsHtml.includes('Pastry')) throw new Error('Section tabs missing defaults');
console.log(JSON.stringify({ imported: items.length, first: items[0].name, firstSection: items[0].category, tabs: tabsHtml.includes('Hot Section') }));
