// Копирует веб-часть приложения из ../mobile в www/ (то, что попадает в APK).
import { cpSync, rmSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const src = resolve(root, '..', 'mobile'), dst = resolve(root, 'www');
rmSync(dst, { recursive: true, force: true }); mkdirSync(dst, { recursive: true });
for (const f of ['index.html', 'styles.css', 'app.js', 'remote.js', 'data.js', 'news.json', 'changelog.json', 'version.json']) cpSync(resolve(src, f), resolve(dst, f));
if (existsSync(resolve(src, 'assets'))) cpSync(resolve(src, 'assets'), resolve(dst, 'assets'), { recursive: true });
console.log('www обновлён из', src);
