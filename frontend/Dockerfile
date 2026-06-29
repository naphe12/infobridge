FROM node:22-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM caddy:2-alpine

WORKDIR /srv

COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

