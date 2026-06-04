FROM node:20-alpine AS dev

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_API_BASE_URL=https://qfsplatform.com/insta_backtester
ARG VITE_MCP_STATUS_PATH=/api/mcp/status/
ARG VITE_FRONTEND_BASE=/insta_backtester_frontend/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_MCP_STATUS_PATH=$VITE_MCP_STATUS_PATH
ENV VITE_FRONTEND_BASE=$VITE_FRONTEND_BASE

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html/insta_backtester_frontend
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8000

CMD ["nginx", "-g", "daemon off;"]
