FROM node:22-alpine
WORKDIR /app
RUN apk add --no-cache tzdata
ENV TZ=Asia/Seoul
COPY package.json package-lock.json ./
RUN npm install --omit=dev
COPY . .
ENV PORT=4100
EXPOSE 4100
CMD ["node", "server.js"]
