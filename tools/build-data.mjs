// Собирает data/heroes.json и data/items.json из сырых данных OpenDota
// и проверяет, что в курируемых данных нет опечаток в ключах героев и предметов.
import { readFile, writeFile } from "node:fs/promises";
import { META } from "./meta.mjs";

const CDN = "https://cdn.cloudflare.steamstatic.com";
const root = new URL("../", import.meta.url);

const heroStats = JSON.parse(await readFile(new URL("heroes.raw.json", root), "utf8"));
const itemsRaw = JSON.parse(await readFile(new URL("items.raw.json", root), "utf8"));
const counters = JSON.parse(await readFile(new URL("data/counters.json", root), "utf8"));
const tagItems = JSON.parse(await readFile(new URL("data/tag-items.json", root), "utf8"));

const errors = [];

const heroes = heroStats.map((h) => {
  const key = h.name.replace("npc_dota_hero_", "");
  const meta = META[key];
  if (!meta) errors.push(`META: нет записи для героя ${key}`);
  return {
    id: h.id,
    key,
    en: h.localized_name,
    ru: meta?.ru || h.localized_name,
    alias: meta?.alias || [],
    tags: meta?.tags || [],
    attr: h.primary_attr,
    attack: h.attack_type,
    roles: h.roles,
    img: CDN + h.img,
    icon: CDN + h.icon,
  };
});
const byKey = new Map(heroes.map((h) => [h.key, h]));

for (const target of Object.keys(counters)) {
  if (!byKey.has(target)) errors.push(`counters: неизвестный герой-цель ${target}`);
  for (const c of counters[target].counters) {
    if (!byKey.has(c.hero)) errors.push(`counters.${target}: неизвестный контрпик ${c.hero}`);
  }
}

const usedItems = new Set();
for (const t of Object.values(counters)) {
  t.items.forEach((i) => usedItems.add(i));
  t.counters.forEach((c) => c.items.forEach((i) => usedItems.add(i)));
}
Object.values(tagItems).forEach((arr) => arr.forEach((i) => usedItems.add(i)));

const items = {};
for (const key of [...usedItems].sort()) {
  const raw = itemsRaw[key];
  if (!raw) { errors.push(`items: неизвестный ключ предмета ${key}`); continue; }
  items[key] = { name: raw.dname, img: CDN + raw.img };
}

for (const tag of Object.keys(tagItems)) {
  const used = heroes.some((h) => h.tags.includes(tag));
  if (!used) console.warn(`tag-items: тег «${tag}» не используется ни одним героем`);
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

const sortByName = (a, b) => a.en.localeCompare(b.en);
await writeFile(new URL("data/heroes.json", root), JSON.stringify(heroes.sort(sortByName), null, 0));
await writeFile(new URL("data/items.json", root), JSON.stringify(items, null, 0));

console.log(`heroes: ${heroes.length}, items: ${Object.keys(items).length}, curated targets: ${Object.keys(counters).length}`);
