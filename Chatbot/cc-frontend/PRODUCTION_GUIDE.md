# Production Deployment Guide

## 🎯 The Issue: "Works in Dev but Not in Prod"

The problem was **corrupted Next.js build cache** causing missing webpack chunks. Here's how to properly test and deploy:

## 🔧 Solution Steps

### 1. **Local Development (✅ Works)**
```bash
npm run dev
# Runs on http://localhost:3000 in development mode
```

### 2. **Local Production Testing**
```bash
# Clean build
Remove-Item -Recurse -Force .next
npm run build
npm start
# Test on http://localhost:3000 in production mode
```

### 3. **Actual Production Deployment**

#### Option A: Domain Deployment (www.clerkcrawler.com)
1. **Update environment variables for production domain:**
   ```env
   NEXTAUTH_URL=https://www.clerkcrawler.com
   NODE_ENV=production
   DATABASE_URL=your_production_db_url
   ```

2. **Build and deploy:**
   ```bash
   npm run build
   # Deploy .next folder and all files to your server
   npm start
   ```

#### Option B: Local Production with Custom Domain
1. **Update your hosts file** (C:\Windows\System32\drivers\etc\hosts):
   ```
   127.0.0.1 www.clerkcrawler.com
   ```

2. **Update .env:**
   ```env
   NEXTAUTH_URL=http://www.clerkcrawler.com:3000
   ```

3. **Access via:** http://www.clerkcrawler.com:3000

## 🎯 Key Points

- **Development**: Uses hot reloading, loose error handling
- **Production**: Optimized build, strict error handling, different session behavior
- **Domain matters**: NextAuth sessions are domain-specific

## 🔍 Testing Your Fix

1. **Run the job worker:**
   ```bash
   npm run job-worker
   ```

2. **Test the API:**
   - Login to your application
   - Create a scraping job 
   - Check if records appear in dashboard

## 🚨 Common Issues

1. **Missing NEXTAUTH_URL**: Causes session issues
2. **Domain mismatch**: Sessions won't work across different domains
3. **Corrupted build**: Clean .next folder and rebuild
4. **Missing environment variables**: Copy all .env files to production

## ✅ Success Indicators

- ✅ Job worker processes jobs without errors
- ✅ Records appear in database with correct userId
- ✅ Dashboard shows the scraped records
- ✅ No foreign key constraint errors 