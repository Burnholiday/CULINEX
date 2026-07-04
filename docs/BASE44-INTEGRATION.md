# Recipe Vault Base44 Integration

This file maps the local Recipe Vault prototype data to the Base44 entities.

## Safety

The Base44 `api_key` must not be hard-coded into `restaurant-costing-app.html`.
For a production app, rotate any key that was pasted into chat or screenshots, then keep the new key in Base44's server-side configuration or a local helper environment variable.

## Entity Mapping

### StockItem

Local stock item fields map to Base44 like this:

| Local field | Base44 field |
| --- | --- |
| `name` | `name` |
| `unit` | `unit` |
| `unitPrice` | `unit_price` |
| `supplier` | `category` |
| `parLevel` | `par_level` |
| `qty` | `total_stock_qty` |
| `invoiceQty` | `last_invoice_qty` |
| `lastInvoiceUnit` | `last_invoice_unit` |
| `lastInvoice` | `last_invoice_date` |
| `lastInvoiceName` | `last_invoice_name` |

### Recipe

Local recipe fields map to Base44 like this:

| Local field | Base44 field |
| --- | --- |
| `name` | `name` |
| `ingredients` | `ingredients` |
| `notes` | `notes` |
| `sourceFileUrl` | `source_file_url` |

Recommended ingredient shape:

```json
{
  "ingredient": "SALMON",
  "qty": 20,
  "unit": "g",
  "linkedStockId": "stock-record-id",
  "ignoreCost": false
}
```

### PrepItem

Local prep item fields map to Base44 like this:

| Local field | Base44 field |
| --- | --- |
| `name` | `name` |
| `yieldQty` | `yield_quantity` |
| `yieldUnit` | `yield_unit` |
| `ingredients` | `ingredients` |
| `notes` | `notes` |
| `sourceFileUrl` | `source_file_url` |

### InvoiceImport

Local invoice fields map to Base44 like this:

| Local field | Base44 field |
| --- | --- |
| `name` | `import_name` |
| `supplier` | `supplier` |
| `date` | `invoice_date` |
| `attachment.previewUrl` or uploaded URL | `source_file_url` |
| confirmed/review state | `status` |
| `rows` | `line_items` |

Recommended line item shape:

```json
{
  "item": "CARROT",
  "quantity": 1.08,
  "unit": "KG",
  "unit_price": 23.65,
  "vat_amount": 0,
  "line_total": 25.54,
  "stock_item_id": "stock-record-id",
  "status": "confirmed"
}
```

### SalesImport

Local sales usage can map to Base44 as:

| Local field | Base44 field |
| --- | --- |
| import label | `import_name` |
| selected period | `date_range` |
| sold menu items | `sales_items` |
| calculated usage | `ingredient_usage` |

## Recommended Sync Flow

1. Load `StockItem`, `Recipe`, `PrepItem`, and `InvoiceImport` from Base44 when the restaurant opens the app.
2. Keep working locally while importing invoices and reviewing stock links.
3. Save confirmed changes back to Base44 only after the manager approves them.
4. Store failed OCR attempts locally first, then sync only confirmed invoice imports.
5. Keep invoice image files in Base44/file storage and save the URL in `source_file_url`.

## SDK Shape

In the Base44-hosted React app, the SDK can be used like this:

```javascript
const recipes = await base44.entities.Recipe.list("-created_date");
const stock = await base44.entities.StockItem.list("name");
const invoice = await base44.entities.InvoiceImport.create({
  import_name: "Farm Fresh Direct - INV1776",
  supplier: "Farm Fresh Direct",
  invoice_date: "30/06/2026",
  status: "pending_review",
  line_items: []
});
```

For the local standalone app, use a local helper/proxy so the browser never sees the API key.
