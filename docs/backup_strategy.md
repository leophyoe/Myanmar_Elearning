# Myanmar E-Learning (MEL) — Production Backup & Disaster Recovery Strategy

**Document Version:** 1.0  
**Effective Date:** 2026-10-03  
**Target Environment:** Production (`mel.edu.mm`)

---

## 1. Objectives & Metrics

- **Recovery Point Objective (RPO):** Maximum 1 hour data loss window.
- **Recovery Time Objective (RTO):** Maximum 30 minutes to full service restoration.
- **Integrity Guarantee:** Cryptographic verification (SHA-256) of every archived snapshot.

---

## 2. Backup Scope

| Asset Component | Path / Store | Backup Method | Frequency | Retention Window |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | Relational DB (`cyberrange_db`) | `pg_dump --format=custom --blobs` | Hourly (diff/WAL) / Daily full | 7 days daily, 4 weeks weekly, 12 months monthly |
| **Media & User Uploads** | `/app/media` (Receipts, avatars, certs) | `tar -czf` compressed archive | Daily at 02:00 UTC | 30 days rolling |
| **System Configuration** | Environment & Manifest | Cryptographic checksum manifest (`manifest.json`) | Every backup run | Indefinite with DB dump |
| **Static Assets** | `/app/staticfiles` | Rebuilt from source via `collectstatic` | On deploy | Tracked in Git release tags |

---

## 3. Automation & Execution

### 3.1 Cron Job Setup
On the host or dedicated backup sidecar container, configure `/etc/cron.d/mel_backup`:

```bash
# Full daily backup at 02:00 UTC
0 2 * * * root /app/backups/backup.sh >> /var/log/mel_backup.log 2>&1

# WAL archiving / hourly DB snapshot (optional for high-traffic environments)
0 * * * * root PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h db -U cyberrange_user -d cyberrange_db -F c > /app/backups/hourly/db_$(date +\%H).dump
```

### 3.2 Backup Script Architecture (`backups/backup.sh`)
1. **Dumps Database:** Executes custom-format PostgreSQL dump including large objects (blobs) and constraints.
2. **Archives Media:** Gzip-compresses `/app/media/`.
3. **Generates Checksums:** Calculates SHA-256 hashes of all artifacts for tamper detection.
4. **Prunes Retention:** Automatically purges backups older than the configured `RETENTION_DAYS`.

---

## 4. Offsite Cloud Storage Replication

To prevent total loss from host failure:
1. Backups are synced to an offsite S3/GCS bucket with Object Lock (WORM - Write Once, Read Many).
2. Example sync command:
   ```bash
   aws s3 sync /app/backups/ s3://mel-backups-secure/production/ --sse aws:kms
   ```
3. Bucket lifecycle rules automatically transition archives to Glacier/Coldline storage after 30 days.

---

## 5. Restoration Procedure

To restore from a backup:
```bash
# 1. Verify and restore from target directory:
/app/backups/restore.sh /app/backups/20261003_020000

# 2. Run post-restore sanity checks:
python manage.py check
python manage.py showmigrations
```

---

## 6. Disaster Recovery Drill Frequency

- **Automated restoration testing:** Monthly test restore in staging environment.
- **Failover simulation:** Quarterly dry-run disaster drill.
