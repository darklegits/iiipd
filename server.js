#!/usr/bin/env node
/**
 * Мини-сервер для CounterPick: отдаёт статику из текущей папки.
 * Без зависимостей. Запуск: node server.js [порт]
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { createReadStream, promises: fsp } = fs;

const ROOT = __dirname;
const PORT = Number(process.argv[2] || process.env.PORT || 3000);
const HOST = process.env.HOST || "0.0.0.0";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".map": "application/json; charset=utf-8",
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
    if (url.pathname === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, uptime: process.uptime() }));
      return;
    }

    let pathname = decodeURIComponent(url.pathname);
    if (pathname.endsWith("/")) pathname += "index.html";
    const filePath = path.join(ROOT, path.normalize(pathname));

    // защита от выхода за пределы каталога сайта
    if (!filePath.startsWith(ROOT + path.sep)) {
      res.writeHead(403).end("Forbidden");
      return;
    }

    const stat = await fsp.stat(filePath).catch(() => null);
    if (!stat || !stat.isFile()) {
      res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
      res.end("<h1>404</h1><p>Страница не найдена. <a href=\"/\">На главную</a></p>");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const etag = `W/"${stat.size}-${stat.mtimeMs}"`;
    if (req.headers["if-none-match"] === etag) {
      res.writeHead(304).end();
      return;
    }

    const cache = ext === ".html" ? "no-cache" : "public, max-age=3600";
    res.writeHead(200, {
      "Content-Type": MIME[ext] || "application/octet-stream",
      "Content-Length": stat.size,
      "Cache-Control": cache,
      ETag: etag,
    });
    createReadStream(filePath).pipe(res);
  } catch (err) {
    console.error(err);
    if (!res.headersSent) res.writeHead(500);
    res.end("Internal Server Error");
  }
});

server.listen(PORT, HOST, () => {
  console.log(`CounterPick запущен: http://${HOST === "0.0.0.0" ? "localhost" : HOST}:${PORT}`);
});
