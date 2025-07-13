# Use Node.js base image with Python support
FROM node:18-slim

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install Node.js dependencies
RUN npm install --legacy-peer-deps

# Copy Python requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Copy application files
COPY . .

# Set environment variables
ENV NODE_ENV=production
ENV PYTHON_EXECUTABLE=/usr/bin/python3

# Build the Next.js application
RUN npm run build

# Expose port
EXPOSE 3000

# Start command
CMD ["npm", "start"] 