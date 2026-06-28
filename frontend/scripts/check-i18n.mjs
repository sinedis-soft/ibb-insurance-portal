import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const roots = ["app", "components", "features", "lib"].map((path) => join("frontend", path));
const allowed = new Set([join("frontend", "lib", "i18n.ts")]);
const localizedText = /[\u0400-\u04ff\u10a0-\u10ff]/;
const checkedExtensions = new Set([".ts", ".tsx"]);

const violations = [];

for (const root of roots) {
  scan(root);
}

if (violations.length > 0) {
  console.error("Hardcoded localized UI text found outside dictionaries:");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

function scan(path) {
  let stats;
  try {
    stats = statSync(path);
  } catch {
    return;
  }
  if (stats.isDirectory()) {
    for (const item of readdirSync(path)) {
      scan(join(path, item));
    }
    return;
  }
  if (!checkedExtensions.has(path.slice(path.lastIndexOf(".")))) {
    return;
  }
  if (allowed.has(path)) {
    return;
  }
  const content = readFileSync(path, "utf8");
  if (localizedText.test(content)) {
    violations.push(path);
  }
}
