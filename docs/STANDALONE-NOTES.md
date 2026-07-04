# Recipe Vault Standalone Notes

## Current local launcher

Run `start-recipe-vault.bat` to start Recipe Vault as a local app.

It starts:
- the Recipe Vault web interface on `http://127.0.0.1:8766`
- the local PaddleOCR helper on `http://127.0.0.1:8765`

Run `stop-recipe-vault.bat` to stop the local app started by this launcher.

## Best development workflow

Keep improving the current Recipe Vault source first. Do not maintain a second standalone copy while the layout, OCR, invoice capture, food cost, prep items, and stock linking workflows are still changing.

The local launcher serves the same app file, so UI and logic changes made here are already reflected when Recipe Vault is run locally. Later, the standalone desktop app should wrap this same source instead of rebuilding it.

## Full desktop app path

To turn this into a proper installable Windows app:

1. Finish the core workflows in the current app: recipes, prep items, stock sheet, invoices, OCR review, relinking, and costing.
2. Move the browser UI into a desktop shell such as Electron or Tauri.
3. Keep the OCR helper local and start it automatically in the background.
4. Replace browser `localStorage` with SQLite so restaurants have reliable local data files and backups.
5. Add import/export tools for backup, restore, and moving data between machines.
6. Add a Windows installer, desktop shortcut, app icon, and auto-start/update process.
7. Add subscription/login licensing only if the product will be sold commercially.
