# CountyPuller

A comprehensive property data enrichment and county records management platform with chatbot capabilities, address enrichment pipelines, and job processing systems.

## Project Structure

```
Countypuller/
├── Chatbot/
│   ├── cc-frontend/          # Next.js frontend application
│   │   ├── src/              # Source code
│   │   ├── scripts/          # Python scripts for data processing
│   │   └── prisma/           # Database schema and migrations
│   └── Chatbot/              # Chatbot agent and OCR components
│       ├── orchestrator/     # Orchestration layer for scrapers and enrichment
│       └── PullingBots/      # Web scraping bots
├── src/                      # Shared API endpoints
└── requirements.txt          # Python dependencies
```

## Features

- **Property Data Enrichment**: Address validation and enrichment using ATTOM and SmartyStreets
- **Job Processing System**: Background job worker for asynchronous data processing
- **Chatbot Interface**: AI-powered chatbot with OCR capabilities
- **County Records Management**: Harris County filing management and property summaries
- **Skip Trace Functionality**: Property owner search and contact information
- **Real-time Job Status**: Monitor and manage background jobs

## Tech Stack

### Frontend
- Next.js 15
- React 18
- TypeScript
- Tailwind CSS
- Material-UI
- Prisma ORM
- NextAuth.js

### Backend
- Node.js
- Python 3
- PostgreSQL
- Playwright

### Services & APIs
- ATTOM Data Solutions
- SmartyStreets
- Stripe (payment processing)
- Google Maps API

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.8+
- PostgreSQL
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Countypuller
```

2. Install frontend dependencies:
```bash
cd Chatbot/cc-frontend
npm install --legacy-peer-deps
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in `Chatbot/cc-frontend/`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
NEXTAUTH_SECRET=your-secret-key
NEXTAUTH_URL=http://localhost:3000
```

5. Set up the database:
```bash
cd Chatbot/cc-frontend
npx prisma generate
npx prisma migrate dev
```

### Running the Application

#### Development Mode

**Frontend:**
```bash
cd Chatbot/cc-frontend
npm run dev
```

**Job Worker:**
```bash
cd Chatbot/cc-frontend
npm run job-worker
```

Or use the provided scripts:
- Windows: `Start-Dev.ps1` and `Start-JobWorker.ps1`
- Unix: `start-dev.bat` and `start-job-worker-daemon.sh`

#### Docker

Build and run with Docker:
```bash
docker build -t countypuller .
docker run -p 3000:3000 countypuller
```

## Documentation

Detailed documentation is available in the project:

- [Quick Start Guide](Chatbot/cc-frontend/QUICK_START.md)
- [Setup Guide](Chatbot/cc-frontend/SETUP_GUIDE.md)
- [Job System Documentation](Chatbot/cc-frontend/JOB_SYSTEM_README.md)
- [Address Enrichment Pipeline](Chatbot/cc-frontend/scripts/ADDRESS_ENRICHMENT_README.md)
- [Skip Trace Setup](Chatbot/cc-frontend/SKIP_TRACE_SETUP.md)
- [Live Support Documentation](Chatbot/cc-frontend/LIVE_SUPPORT_README.md)

## Key Components

### Frontend (`Chatbot/cc-frontend`)
Next.js application with user interface, authentication, and job management.

### Address Enrichment (`scripts/`)
Python scripts for property address validation and enrichment using multiple data sources.

### Job Worker (`scripts/job-worker.js`)
Background worker for processing asynchronous jobs including address enrichment and skip trace operations.

### Chatbot Orchestrator (`Chatbot/orchestrator/`)
ReAct-based agent with property summary and filtering capabilities.

## Scripts

### Frontend Scripts
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run job-worker` - Start job worker

### Utility Scripts
- `check-jobs.js` - Check job status
- `cancel-all-jobs.js` - Cancel all pending jobs
- `reset-jobs.js` - Reset job queue

## Environment Variables

Required environment variables:

```env
DATABASE_URL=postgresql://...
NEXTAUTH_SECRET=...
NEXTAUTH_URL=http://localhost:3000
ATTOM_API_KEY=...
SMARTYSTREETS_AUTH_ID=...
SMARTYSTREETS_AUTH_TOKEN=...
```

See individual component documentation for complete environment variable lists.

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## Authorization and Access Control

**IMPORTANT:** This system operates exclusively within pre-authenticated user sessions. All scraping operations:

1. **Require Valid User Credentials**: Users must authenticate through legitimate means (username/password, session cookies obtained through normal login) before any data collection occurs.

2. **Respect Access Controls**: The system does not bypass, circumvent, or defeat any authentication or authorization mechanisms. All operations occur within the context of an authenticated user session.

3. **Operate Within User Context**: All actions are performed as if the authenticated user were manually using the website. The automation replicates user actions but does not extend authorization beyond what the user already possesses.

4. **Comply with Terms of Service**: Users are responsible for ensuring their use complies with target website terms of service. The system provides tools to assist with data collection but does not enable unauthorized access.

**What This System Does NOT Do:**
- Create or extend authorization beyond what the user already possesses
- Automate authentication or credential management without user credentials
- Defeat CAPTCHA or other security measures without explicit user interaction
- Replay sessions beyond their intended expiration
- Bypass rate limiting or access controls

**Session Management:**
- Session cookies must be obtained through legitimate user authentication
- Cookies expire and require re-authentication when they become invalid
- No hardcoded credentials or session tokens in source code
- All sensitive configuration stored in environment variables

## License

[Add license information]

## Support

For issues and questions, please refer to the documentation files in the project or open an issue in the repository.

