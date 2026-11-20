import fs from "node:fs/promises";
import path from "node:path";

const TOKEN = process.env.STRATZ_TOKEN;
if (!TOKEN) { console.error("STRATZ_TOKEN is required"); process.exit(1); }

const ROOT = process.cwd();
const OUT = path.join(ROOT, "data", "matchups");
const QUERY = `query HeroMatchups($heroId: Short!) {
  heroStats { heroVsHeroMatchup(heroId: $heroId) { advantage { vs { heroId2 matchCount winCount } } } }
}`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function gql(heroId) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const res = await fetch("https://api.stratz.com/graphql", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Content-Type": "application/json",
        "User-Agent": "STRATZ_API",
        Accept: "application/json",
      },
      body: JSON.stringify({ query: QUERY, variables: { heroId } }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.errors) throw new Error(data.errors[0].message);
      return data;
    }
    if (res.status === 403 || res.status === 429) { await sleep(45000); continue; }
    throw new Error(`HTTP ${res.status}`);
  }
  throw new Error("rate limited");
}

const heroes = JSON.parse(await fs.readFile(path.join(ROOT, "data", "heroes.json"), "utf8"));
await fs.mkdir(OUT, { recursive: true });

let ok = 0;
const failed = [];
for (const hero of heroes) {
  try {
    const data = await gql(hero.id);
    const adv = data.data?.heroStats?.heroVsHeroMatchup?.advantage?.[0]?.vs || [];
    const rows = adv
      .filter((r) => r.matchCount > 0 && r.winCount != null)
      .map((r) => ({ hero_id: r.heroId2, games_played: r.matchCount, wins: r.winCount }));
    await fs.writeFile(path.join(OUT, `${hero.id}.json`), JSON.stringify(rows));
    ok++;
    if (ok % 10 === 0) console.log(`synced ${ok}/${heroes.length}`);
  } catch (err) {
    failed.push(`${hero.id}:${err.message}`);
    console.log(`fail ${hero.key}: ${err.message}`);
  }
  await sleep(3200);
}

await fs.writeFile(path.join(OUT, "_meta.json"), JSON.stringify({ source: "stratz", updated: Math.floor(Date.now() / 1000), heroes: ok, failed: failed.length }));
console.log(`DONE ${ok}/${heroes.length}, failed ${failed.length}`);
