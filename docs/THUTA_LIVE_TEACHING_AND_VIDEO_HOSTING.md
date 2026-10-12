# THUTA E-Learning Platform — Live Teaching & Video Hosting Architecture

**Document Version:** 1.0.0  
**Status:** Approved Architecture Reference  
**Author:** THUTA Engineering Team  
**Scope:** Real-Time Virtual Classrooms, Video Transcoding, Adaptive Bitrate Streaming, and Cloud Object Storage

---

## 1. Virtual Classroom Architecture (Live Teaching)

### 1.1 Technology Evaluation & Selection (Excluding Jitsi & LiveKit)

| Platform | Architectural Type | LMS Fit | Bandwidth Efficiency | Verdict |
|---|---|---|---|---|
| **BigBlueButton (BBB)** | Native Pedagogical WebRTC / HTML5 | **Industry Gold Standard** (Multi-user whiteboard, shared notes, breakout rooms, slide sync, attendance roster) | Adaptive audio/video prioritization; server-side recording compositing | **SELECTED PRIMARY** |
| **Apache OpenMeetings** | WebRTC / Java backend | Academic whiteboard, polling | Moderate; heavier server memory footprint | Viable secondary alternative |
| **Janus / mediasoup** | Low-level WebRTC SFU | Raw media server (requires building custom whiteboard, chat, slides from scratch) | High, but high custom frontend engineering overhead | Infrastructure SFU only |
| **Zoom / Google Meet** | Proprietary Cloud Fallback | High reliability external link fallback | Managed by external provider | **INTEGRATED AS REDUNDANT FALLBACK** |

### 1.2 THUTA BigBlueButton Integration (`apps/courses/live/bigbluebutton.py`)

THUTA interfaces with BigBlueButton via its official REST API utilizing **HMAC-SHA1 checksum verification**:
1. **Meeting Provisioning (`/create`):**
   - Automatically provisions room with moderator password (for instructor) and attendee password (for students).
   - Injects custom platform branding banner (`THUTA Virtual Classroom`), logout URL, and automated lecture recording flags.
2. **Seamless Single-Sign-On Join (`/join`):**
   - Instructors and enrolled students never see or enter meeting passwords.
   - The platform calculates a cryptographic checksum and redirects the student's browser directly into the BigBlueButton HTML5 client with their authenticated platform identity and role.
3. **Attendance & Participation Synchronization (`/getMeetingInfo`):**
   - Periodic Celery/Cron tasks query BBB to record attendee join times, duration in classroom, and active participation.
4. **Automated Lecture Recording Sync (`/getRecordings`):**
   - Once BBB finishes processing the recording, THUTA automatically captures the playback URL and exposes the replay within the course module for absent students.
5. **Offline & Test Simulation Mode:**
   - Exception handling safely intercepts DNS resolution failures and network timeouts, returning simulated meeting descriptors during local development and CI testing.

---

## 2. Cloud Video Hosting & Streaming Architecture

### 2.1 The Anti-Pattern: Local Disk / Database Video Storage

Storing raw MP4 video files inside PostgreSQL `bytea` columns or local VPS Docker volumes (`/app/media/`) causes critical production failures:
- **Exhausted Disk Space:** 10 courses with 50 video lectures can consume 100+ GB within weeks.
- **Bandwidth Saturation & Buffering:** Direct MP4 file downloads lack adaptive bitrate streaming. In Myanmar, where mobile data bandwidth fluctuates significantly across operators (MPT, Atom, Ooredoo, Mytel), learners experience severe buffering.
- **Content Piracy:** Direct file URLs can be copied, hotlinked, or scraped by unauthorized users.

### 2.2 Recommended Production Video Architecture: Bunny Stream & Cloudflare Stream

```
+-----------------------------------------------------------------------------------+
|                            INSTRUCTOR VIDEO UPLOAD FLOW                            |
+-----------------------------------------------------------------------------------+
  [Instructor]
       │
       ▼ (Direct resumable upload via Tus protocol / Signed API)
  [Bunny Stream / Cloudflare Stream Ingestion]
       │
       ▼ (Automatic Server-Side Transcoding)
  ┌────────────────────────────────────────────────────────┐
  │  Adaptive Bitrate HLS Playlist (.m3u8):                │
  │  ├── 1080p (Full HD for desktop broadband)             │
  │  ├── 720p  (HD default)                                │
  │  ├── 480p  (Standard mobile 4G)                        │
  │  └── 360p / 240p (Low bandwidth fallback for Myanmar)  │
  └────────────────────────────────────────────────────────┘
       │
       ▼ (APAC Edge CDN - Singapore / Bangkok PoPs)
  [THUTA Embedded Player in templates/courses/lesson_detail.html]
```

### 2.3 Cost & Feature Comparison for Myanmar LMS Deployment

| Feature | Bunny Stream (Recommended) | Cloudflare Stream | AWS CloudFront + S3 |
|---|---|---|---|
| **Storage Cost** | **\$0.005 / GB-month** | \$5.00 / 1,000 mins | \$0.023 / GB-month |
| **Bandwidth (APAC)** | **\$0.01 / GB** | \$1.00 / 1,000 mins | \$0.12 / GB (Expensive) |
| **Adaptive Bitrate** | Automatic HLS | Automatic HLS/DASH | Requires AWS Elemental MediaConvert |
| **Hotlink Protection** | Signed Token URLs (`token_hash`) | Signed Web Tokens (JWT) | CloudFront Signed Cookies |
| **Myanmar Latency** | Low (Direct routing via Singapore PoP) | Low (Global Anycast edge) | Moderate to High |

### 2.4 Cloudflare R2 / AWS S3 for Lecture Materials & Document Attachments

For non-streaming assets (PDF slide decks, cheat sheets, exercise archives, and lab code files):
- **Cloudflare R2:** S3-compatible API with **\$0.00 egress bandwidth fees**, making it exceptionally cost-effective for large student downloads.
- Integrated via `django-storages[s3]` with environment configuration:
  ```env
  AWS_ACCESS_KEY_ID=r2_access_key
  AWS_SECRET_ACCESS_KEY=r2_secret_key
  AWS_STORAGE_BUCKET_NAME=thuta-course-materials
  AWS_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
  ```

---

## 3. Video Player Theater in THUTA

Implemented in `templates/courses/lesson_detail.html` (Reference Images 3 & 5):
1. **Dynamic Media Embed Resolution:**
   - Detects whether video is hosted locally, on Bunny Stream, Cloudflare Stream, YouTube, or Vimeo, and automatically injects the appropriate responsive iframe or HTML5 player.
2. **Speed Controls:**
   - 0.75x, 1.0x, 1.25x, 1.5x, 2.0x playback speeds.
3. **Tabbed Pedagogical Metadata:**
   - **Overview:** Lesson description and objectives.
   - **Transcript:** Full lecture text transcript for low-bandwidth reading.
   - **Materials:** Downloadable slides and PDF guides.
   - **Private Notes:** Student personal study notes with local persistence.
   - **Curriculum Sidebar:** Lesson sequence with duration indicators and automatic completion checkmarks.

