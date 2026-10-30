import path from 'node:path';
import { seoContentDir, normalizeRouteFromMarkdown, collectMarkdownFiles } from './utils.js';

export function getBlogRoutes() {
  const files = collectMarkdownFiles(seoContentDir);
  // A fresh project has no blog. Only existing content opts into blog rendering.
  const routes = new Set(files.length > 0 ? ['/blog/'] : []);

  for (const filePath of files) {
    const relativePath = path.relative(seoContentDir, filePath);
    routes.add(normalizeRouteFromMarkdown(relativePath));
  }

  return Array.from(routes).sort();
}
