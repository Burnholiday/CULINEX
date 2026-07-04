import React, { useState, useMemo } from 'react';
import { base44 } from '@/api/base44Client';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Search, Trash2, DollarSign, ChefHat, AlertCircle, Link2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import LinkStockItemDialog from '@/components/food-cost/LinkStockItemDialog';

function matchStockPrice(ingredientName, stockItems) {
  if (!stockItems?.length) return null;
  const name = ingredientName.toLowerCase().trim();

  let match = stockItems.find(s => s.name.toLowerCase() === name);
  if (match) return match;

  match = stockItems.find(s => s.name.toLowerCase().includes(name) || name.includes(s.name.toLowerCase()));
  return match || null;
}

function calcCost(ingredient, stockItems) {
  const stock = matchStockPrice(ingredient.ingredient_name, stockItems);
  if (!stock || !stock.unit_price) return null;

  return {
    unit_price: stock.unit_price,
    stock_unit: stock.unit,
    stock_name: stock.name,
    cost: (ingredient.quantity / (stock.unit === 'KG' || stock.unit === 'LTR' ? 1000 : 1)) * stock.unit_price,
    adjusted_cost: (() => {
      const ru = (ingredient.unit || '').toLowerCase();
      const su = (stock.unit || '').toLowerCase();
      const stockMatch = su.match(/^([\d.]+)\s*([a-z]+)$/i);

      if (stockMatch) {
        const stockQty = parseFloat(stockMatch[1]);
        const stockBaseUnit = stockMatch[2].toLowerCase();

        if ((ru === 'g' && stockBaseUnit === 'g') ||
            (ru === 'ml' && stockBaseUnit === 'ml') ||
            ru === stockBaseUnit) {
          return (ingredient.quantity / stockQty) * stock.unit_price;
        }

        if ((ru === 'g' && stockBaseUnit === 'kg') || (ru === 'ml' && stockBaseUnit === 'ltr')) {
          return (ingredient.quantity / (stockQty * 1000)) * stock.unit_price;
        }

        if ((ru === 'kg' && stockBaseUnit === 'g') || (ru === 'ltr' && stockBaseUnit === 'ml')) {
          return (ingredient.quantity * 1000 / stockQty) * stock.unit_price;
        }
      }

      if ((ru === 'g' && su === 'kg') || (ru === 'ml' && su === 'ltr')) {
        return (ingredient.quantity / 1000) * stock.unit_price;
      }

      if ((ru === 'kg' && su === 'g') || (ru === 'ltr' && su === 'ml')) {
        return (ingredient.quantity * 1000) * stock.unit_price;
      }

      if (ru === su) {
        return ingredient.quantity * stock.unit_price;
      }

      return ingredient.quantity * stock.unit_price;
    })(),
  };
}

function RecipeRow({ recipe, quantity, stockItems, onReload }) {
  const [expanded, setExpanded] = useState(true);
  const [linkDialog, setLinkDialog] = useState(null);

  const ingredientsWithCost = useMemo(() => {
    return (recipe.ingredients || []).map(ing => {
      const costInfo = calcCost(ing, stockItems);
      return { ...ing, costInfo, totalCost: costInfo ? costInfo.adjusted_cost * quantity : null };
    });
  }, [recipe, quantity, stockItems]);

  const totalCost = ingredientsWithCost.reduce((sum, i) => sum + (i.totalCost || 0), 0);
  const missingPrices = ingredientsWithCost.filter(i => !i.costInfo).length;

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <ChefHat className="w-4 h-4 text-primary" />
            </div>
            <div>
              <CardTitle className="font-heading text-base">{recipe.name}</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                Quantity: <span className="font-semibold text-foreground">{quantity}</span> . {recipe.ingredients?.length || 0} ingredients
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Total Cost</p>
            <p className="text-xl font-bold text-primary font-mono">R{totalCost.toFixed(2)}</p>
            {missingPrices > 0 && (
              <p className="text-xs text-orange-500 flex items-center gap-1 justify-end mt-0.5">
                <AlertCircle className="w-3 h-3" />{missingPrices} unpriced
              </p>
            )}
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs uppercase tracking-wider">Ingredient</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-right">Per Portion</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-right">x {quantity}</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-right">Stock Price</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-right">Total Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ingredientsWithCost.map((ing, idx) => (
                <TableRow key={idx} className={!ing.costInfo ? 'opacity-60' : ''}>
                  <TableCell className="font-medium text-sm">{ing.ingredient_name}</TableCell>
                  <TableCell className="text-right text-sm font-mono">
                    {ing.quantity} {ing.unit}
                  </TableCell>
                  <TableCell className="text-right text-sm font-mono text-muted-foreground">
                    {ing.quantity * quantity} {ing.unit}
                  </TableCell>
                  <TableCell className="text-right">
                    {ing.costInfo ? (
                      <Badge variant="secondary" className="font-mono text-xs">
                        R{ing.costInfo.unit_price.toFixed(2)}/{ing.costInfo.stock_unit}
                      </Badge>
                    ) : (
                      <button
                        onClick={() => setLinkDialog({ ingredientName: ing.ingredient_name, ingredientIndex: idx })}
                        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-orange-200 text-orange-500 hover:bg-orange-50 transition-colors"
                      >
                        <Link2 className="w-3 h-3" /> Link to stock
                      </button>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono font-semibold text-sm">
                    {ing.totalCost != null ? (
                      <span className="text-primary">R{ing.totalCost.toFixed(2)}</span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              <TableRow className="bg-muted/40 font-semibold">
                <TableCell colSpan={4} className="text-sm">Total Food Cost</TableCell>
                <TableCell className="text-right font-mono text-primary font-bold">
                  R{totalCost.toFixed(2)}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      )}

      {linkDialog && (
        <LinkStockItemDialog
          open={!!linkDialog}
          ingredientName={linkDialog.ingredientName}
          ingredientIndex={linkDialog.ingredientIndex}
          recipeId={recipe.id}
          onClose={() => setLinkDialog(null)}
          onLinked={() => { setLinkDialog(null); onReload?.(); }}
        />
      )}
    </Card>
  );
}

export default function FoodCost() {
  const [search, setSearch] = useState('');
  const [entries, setEntries] = useState([]);

  const queryClient = useQueryClient();
  const { data: recipes = [], isLoading: loadingRecipes } = useQuery({
    queryKey: ['recipes'],
    queryFn: () => base44.entities.Recipe.list('-created_date'),
  });

  const { data: stockItems = [] } = useQuery({
    queryKey: ['stock-items'],
    queryFn: () => base44.entities.StockItem.list('name'),
  });

  const filteredRecipes = useMemo(() => {
    if (!search.trim()) return recipes;
    const q = search.toLowerCase();
    return recipes.filter(r => r.name.toLowerCase().includes(q));
  }, [search, recipes]);

  const addRecipe = (recipe) => {
    if (entries.find(e => e.recipe_id === recipe.id)) return;
    setEntries([...entries, { recipe_id: recipe.id, recipe, quantity: 1 }]);
    setSearch('');
  };

  const updateQty = (recipe_id, qty) => {
    setEntries(entries.map(e => e.recipe_id === recipe_id ? { ...e, quantity: Math.max(1, parseInt(qty, 10) || 1) } : e));
  };

  const removeEntry = (recipe_id) => {
    setEntries(entries.filter(e => e.recipe_id !== recipe_id));
  };

  const grandTotal = entries.reduce((sum, e) => {
    const ingredientsWithCost = (e.recipe.ingredients || []).map(ing => {
      const costInfo = calcCost(ing, stockItems);
      return costInfo ? costInfo.adjusted_cost * e.quantity : 0;
    });
    return sum + ingredientsWithCost.reduce((a, b) => a + b, 0);
  }, 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-heading text-3xl md:text-4xl font-bold tracking-tight">Food Cost Calculator</h1>
        <p className="text-muted-foreground mt-2">
          Search for a recipe, set the quantity, and see ingredient costs broken down using your stock sheet prices.
        </p>
      </div>

      <div className="space-y-2">
        <div className="relative max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search recipes to add..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-10 h-12 rounded-xl"
          />
        </div>

        {search.trim() && (
          <div className="max-w-md rounded-xl border bg-card shadow-md overflow-hidden">
            {loadingRecipes ? (
              <div className="p-3 space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : filteredRecipes.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No recipes found for "{search}"</p>
            ) : (
              <ul className="divide-y max-h-60 overflow-y-auto">
                {filteredRecipes.map(r => {
                  const already = entries.find(e => e.recipe_id === r.id);
                  return (
                    <li key={r.id}>
                      <button
                        onClick={() => addRecipe(r)}
                        disabled={!!already}
                        className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-muted/50 transition-colors text-left disabled:opacity-40"
                      >
                        <span className="font-medium">{r.name}</span>
                        <span className="text-xs text-muted-foreground">{r.ingredients?.length || 0} ingredients</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>

      {entries.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Added Recipes</p>
          <div className="flex flex-wrap gap-3">
            {entries.map(e => (
              <div key={e.recipe_id} className="flex items-center gap-2 bg-card border rounded-xl px-3 py-2 shadow-sm">
                <span className="text-sm font-medium">{e.recipe.name}</span>
                <span className="text-muted-foreground text-xs">x</span>
                <Input
                  type="number"
                  min="1"
                  value={e.quantity}
                  onChange={ev => updateQty(e.recipe_id, ev.target.value)}
                  className="w-16 h-7 text-sm rounded-lg px-2"
                />
                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => removeEntry(e.recipe_id)}>
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {entries.length > 0 && (
        <div className="space-y-5">
          {entries.map(e => (
            <RecipeRow
              key={e.recipe_id}
              recipe={e.recipe}
              quantity={e.quantity}
              stockItems={stockItems}
              onReload={() => queryClient.invalidateQueries({ queryKey: ['recipes'] })}
            />
          ))}

          {entries.length > 1 && (
            <div className="flex justify-end">
              <div className="bg-primary/10 border border-primary/20 rounded-2xl px-6 py-4 text-right">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Grand Total Food Cost</p>
                <p className="text-3xl font-bold text-primary font-mono">R{grandTotal.toFixed(2)}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {entries.length === 0 && !search && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
            <DollarSign className="w-7 h-7 text-muted-foreground" />
          </div>
          <h3 className="font-heading font-semibold text-lg">No recipes added yet</h3>
          <p className="text-sm text-muted-foreground mt-1">Search for a recipe above to calculate its food cost.</p>
        </div>
      )}
    </div>
  );
}
