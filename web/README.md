# Enterprise AI Workspace Web Dashboard

Modern Next.js 16 + React 19 web application serving as the frontend dashboard for the Multi-Agent AI Workspace.

## Quick Setup

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env.local
   ```
   *Ensure `.env.local` has:*
   ```env
   NEXT_PUBLIC_APP_URL=http://localhost:3000
   NEXT_PUBLIC_API_URL=http://localhost:8001
   ```

3. **Start Development Server**:
   ```bash
   npm run dev
   ```
   *Open [http://localhost:3000](http://localhost:3000) in your browser.*
