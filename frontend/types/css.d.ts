// Next ships ambient types for `*.module.css` only. Plain global stylesheets
// imported for their side effect (app/globals.css) have no declaration, which
// some TypeScript versions report as TS2882.
declare module "*.css";
