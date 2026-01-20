# Alterado para 20 para garantir suporte nativo a Headers/Fetch e cumprir o requisito do Supabase
FROM node:20-alpine

WORKDIR /app

# Copiar ficheiros de dependências primeiro (otimiza a cache do Docker)
COPY package*.json ./
RUN npm install

# Copiar o resto do código
COPY . .

# Porta do Webhook Listener (conforme definido no teu processor.js)
EXPOSE 3000

CMD ["node", "src/processor.js"]