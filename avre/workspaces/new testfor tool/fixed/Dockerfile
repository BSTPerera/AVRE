FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
# Legacy peer deps often needed for older repos like NodeGoat
RUN npm install --ignore-scripts --legacy-peer-deps
COPY . .
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]