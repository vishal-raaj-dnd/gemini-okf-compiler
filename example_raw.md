# Company Knowledge Handbook

This is the central handbook for company operations, engineering standards, and incident response guidelines.

## Incident Response Protocol

This process defines how engineering teams handle production alerts and system outages.
Any engineer on-call must follow these steps when an alert triggers.

1. **Acknowledge the Alert**: Claim ownership of the alert in PagerDuty within 15 minutes.
2. **Mitigation**: Focus on resolving the user-facing issue before doing a deep root-cause analysis. Refer to the Database Setup Guide if the issue relates to database replication lag.
3. **Communication**: Update the internal Slack channel every 20 minutes with the current status.
4. **Post-Mortem**: File an incident report within 48 hours of resolution.

## Database Setup Guide

This guide details how to spin up and configure PostgreSQL database instances for production services.
All new database clusters must adhere to our Backup Standards to prevent data loss.

### Replication Config
We use standard streaming replication. Make sure your `postgresql.conf` contains:
```ini
wal_level = replica
max_wal_senders = 10
hot_standby = on
```

## Backup Standards

This reference document defines standard policies for data durability and disaster recovery.
If a restore is required during an active outage, coordinate actions using the Incident Response Protocol.

### Backup Schedule
- **Daily**: Full logical backups are taken at 02:00 UTC and stored in secure S3 buckets.
- **Hourly**: WAL archives are continuously shipped to cloud storage.
- **Retention**: Daily backups are retained for 30 days.
- **Recovery Testing**: Restores must be verified monthly to ensure compliance.
