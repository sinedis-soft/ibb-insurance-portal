import fs from "node:fs";
import path from "node:path";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const publicDir = path.join(root, "public");
const manifestPath = path.join(publicDir, "manifest.webmanifest");
const swPath = path.join(publicDir, "sw.js");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const requiredFields = ["name", "short_name", "description", "start_url", "scope", "display", "background_color", "theme_color", "lang", "icons"];
const failures = [];
for (const field of requiredFields) {
  if (!manifest[field] || (Array.isArray(manifest[field]) && manifest[field].length === 0)) failures.push(`manifest missing ${field}`);
}
if (manifest.start_url !== "/" || manifest.scope !== "/") failures.push("manifest start_url/scope must stay public root");
if (manifest.display !== "standalone") failures.push("manifest display must be standalone");
for (const icon of manifest.icons ?? []) {
  if (!icon.src?.startsWith("/icons/")) failures.push(`icon path is not public-safe: ${icon.src}`);
  const iconPath = path.join(publicDir, icon.src.replace(/^\//, ""));
  if (!fs.existsSync(iconPath)) failures.push(`icon missing: ${icon.src}`);
}
const sw = fs.readFileSync(swPath, "utf8");
const privateRoutes = ["/api/auth", "/api/applications", "/api/documents", "/api/superadmin", "/api/delegations", "/api/partner"];
for (const pattern of privateRoutes) {
  if (!sw.includes(pattern)) failures.push(`service worker missing explicit private-route guard: ${pattern}`);
}
const forbidden = ["backgroundSync", "sync.register", "cache.put"];
for (const pattern of forbidden) {
  if (sw.includes(pattern)) failures.push(`service worker contains forbidden cache/sync pattern: ${pattern}`);
}
if (/\.addAll\([^)]*api\//s.test(sw)) failures.push("service worker must not cache API responses");
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
