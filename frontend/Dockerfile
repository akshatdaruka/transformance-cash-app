# Use Node.js for building and running
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first to leverage Docker cache
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Expose the Vite development port
EXPOSE 5173

# Run the dev server, bind to 0.0.0.0 so it's accessible outside container
CMD ["npm", "run", "dev", "--", "--host"]