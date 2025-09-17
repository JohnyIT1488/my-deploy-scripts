#!/bin/bash
set -e

# === БАЗОВАЯ НАСТРОЙКА СЕРВЕРА ===
apt update && apt upgrade -y
apt install -y curl wget git ufw htop unzip

# Установка Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Установка docker compose plugin
apt install -y docker-compose-plugin

# Настройка firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# === ПРОЕКТ ===
mkdir -p /opt/scam-app
cd /opt/scam-app

# package.json
cat > package.json <<'EOF'
{
  "name": "scam-app",
  "version": "1.0.0",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "body-parser": "^1.20.2",
    "express": "^4.18.2",
    "sqlite3": "^5.1.6"
  }
}
EOF

# server.js
cat > server.js <<'EOF'
const express = require('express');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// база в отдельной папке /app/data/data.db
const dbPath = path.join(__dirname, 'data', 'data.db');
const db = new sqlite3.Database(dbPath);

db.run(`
  CREATE TABLE IF NOT EXISTS form_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
`);

app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());

// отдаём статику
app.use(express.static(path.join(__dirname)));

app.post('/submit', (req, res) => {
  const { name, email, message } = req.body;
  db.run(
    'INSERT INTO form_data (name, email, message) VALUES (?, ?, ?)',
    [name, email, message],
    function (err) {
      if (err) {
        console.error(err);
        return res.status(500).send('Ошибка сервера');
      }
      res.send('Данные сохранены');
    }
  );
});

app.get('/data', (req, res) => {
  db.all('SELECT * FROM form_data ORDER BY created_at DESC', [], (err, rows) => {
    if (err) {
      return res.status(500).send('Ошибка сервера');
    }
    res.json(rows);
  });
});

app.listen(PORT, () => {
  console.log(`Сервер работает на порту ${PORT}`);
});
EOF

# index.html
cat > index.html <<'EOF'
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>Форма</title>
</head>
<body>
  <h1>Простая форма</h1>
  <form method="POST" action="/submit">
    <input type="text" name="name" placeholder="Имя" required /><br/>
    <input type="email" name="email" placeholder="Email" required /><br/>
    <textarea name="message" placeholder="Сообщение"></textarea><br/>
    <button type="submit">Отправить</button>
  </form>
  <p><a href="/data">Посмотреть сохранённые данные</a></p>
</body>
</html>
EOF

# Dockerfile
cat > Dockerfile <<'EOF'
FROM node:18

WORKDIR /app

# ставим пакеты для сборки sqlite3
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install
COPY . .

EXPOSE 3000
CMD ["npm", "start"]
EOF

# docker-compose.yml
cat > docker-compose.yml <<'EOF'
version: "3.8"

services:
  app:
    build: .
    ports:
      - "80:3000"
    volumes:
      - ./data:/app/data
    restart: always
EOF

# создаём папку data для базы
mkdir -p data

# === ЗАПУСК ===
docker compose up -d --build
