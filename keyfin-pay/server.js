import mysql from 'mysql2/promise';
import { createApp } from './lib/createApp.js';

const db = mysql.createPool({
  host: process.env.DB_HOST || 'mysql',
  port: Number(process.env.DB_PORT || 3306),
  user: process.env.DB_USER || 'keyfin',
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'keyfin',
  connectionLimit: 5,
  charset: 'utf8mb4',
});

for (const name of ['FINANCE_API_BASE_URL', 'FINANCE_API_KEY']) {
  if (!process.env[name]) {
    console.error(`${name} 환경변수가 필요합니다.`);
    process.exit(1);
  }
}

const app = createApp({
  finBaseUrl: process.env.FINANCE_API_BASE_URL,
  finApiKey: process.env.FINANCE_API_KEY,
  db,
});

const PORT = process.env.PORT || 4100;
app.listen(PORT, () => console.log(`keyfin-pay listening on :${PORT}`));
