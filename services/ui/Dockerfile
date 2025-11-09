FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies (including dev dependencies for vite) - updated
RUN npm install

# Add node_modules/.bin to PATH
ENV PATH="/app/node_modules/.bin:$PATH"

# Copy source
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start dev server
CMD ["node", "/app/node_modules/vite/bin/vite.js", "--host"]
