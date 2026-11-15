# Emerrr — Early Emergency Alert & Authority–Villager Bridge Platform

**Emerrr** is a real-time civic emergency and hazard response platform built as a resilient digital bridge between municipal authorities, local emergency medical teams, and residents across 32 numbered village/ward houses.

---

## 📁 Repository Structure

```
ALARM-ALERT-SYSTEM/
├── frontend/                      # Web & Mobile Client Application
│   ├── index.html                 # Main Emergency Operations & 3D Spatial Portal
│   ├── mobile.html                # 1-to-1 QR Mobile Companion & Background Siren Receiver
│   ├── qrcode.min.js              # Client-side QR generation engine
│   ├── sw.js                      # Progressive Web App (PWA) Service Worker & Caching
│   ├── netlify.toml               # Edge deployment headers and routing rules
│   ├── supabase-config.js         # Public Supabase client configuration template
│   ├── supabase-config.example.js # Reference configuration with instructions
│   └── assets/                    # Optimized SVG vectors, icons, and geo-tagged images
│       ├── badge-72.png
│       ├── icon-192.png
│       ├── house_1.jpg
│       ├── broken_road.svg
│       ├── fallen_pole.svg
│       ├── pipe_burst.svg
│       └── sewage_overflow.svg
│
├── backend/                       # Python Emergency Telemetry & Dispatch Server
│   ├── server.py                  # Threading HTTP server with SSE & long-polling
│   ├── house_accounts.json        # Designated 32-House whitelist and authentication records
│   ├── complaints.json            # Persistent municipal civic hazard register
│   ├── update_house_accounts.py   # Utility script to manage resident designations
│   ├── supabase-schema.sql        # Database schema, RLS policies, and telemetry tables
│   └── requirements.txt           # Python dependency specifications (Standard Library)
│
├── .gitignore                     # Git exclusion rules for secrets, logs, and cache
└── README.md                      # Platform documentation and deployment guide
```

---

## 🚀 Quick Start

### 1. Launch the Backend Server

The backend runs entirely on Python standard library modules (no third-party pip dependencies required):

```bash
cd backend
python server.py
```

*The server will start on port `8765` and automatically serve the `frontend/` directory:*
- **Main Portal**: `http://localhost:8765/index.html`
- **Mobile Companion**: `http://localhost:8765/mobile.html`

### 2. Frontend-Only Deployment (Netlify / Static Hosting)

The `frontend/` folder is completely static and ready for direct deployment to Netlify, Vercel, or GitHub Pages. A pre-configured `netlify.toml` is included.

### 3. Optional Supabase Cloud Integration

To enable cloud persistence across devices:
1. Create a project on [Supabase](https://supabase.com).
2. Execute `backend/supabase-schema.sql` in the Supabase SQL Editor to establish tables and RLS security policies.
3. Update `frontend/supabase-config.js` with your project URL and public publishable anon key:
   ```javascript
   window.SUPABASE_CONFIG = {
     url: 'https://YOUR_PROJECT_ID.supabase.co',
     anonKey: 'YOUR_SUPABASE_ANON_KEY_HERE'
   };
   ```

---

## 🔒 Security & Role-Based Access Control (RBAC)

1. **Strict 32-House Whitelist**:
   - Only pre-registered resident accounts (e.g., `House 1 Prabakar`, `House 13 Venkatesh`) and designated emergency authority accounts can access the system.
2. **Hospital Role Lockdown**:
   - Hospital Command clearance is strictly isolated to **Hospital Alert**, **🔥 Fire Alert**, and the **3D Map**; administrative policy controls and case report submissions are restricted.
3. **Citizen Photo Privacy Shield**:
   - Civic hazard photos uploaded by citizens are encrypted and accessible exclusively to the Municipal Administrator desk; other residents and facilities cannot view photo submissions.
4. **Zero Secrets in Source**:
   - All personal emails, private credentials, and production secret keys have been stripped and replaced with generic environment templates.

---

## 📡 Core Capabilities

- **500m Structural Fire Emergency Broadcast**: Immediate proximity calculation triggering synchronized sirens and shockwave broadcasts for all homes within a 500-meter radius.
- **1-to-1 QR Mobile Siren Pairing**: Instant camera scan pairing any smartphone directly to a designated house without app store installation.
- **3D Spatial Digital Twin**: Interactive Three.js spatial model visualizing water quality, contamination vectors, and emergency routes.
- **Bilingual Interface**: Native English and Telugu (తెలుగు) operational language switching.
