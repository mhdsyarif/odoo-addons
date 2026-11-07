# Cloud Storage AWS (Amazon S3)

Seamlessly store and serve Odoo chatter attachments and binary files using **Amazon Simple Storage Service (Amazon S3)** instead of local server storage.

---

## Overview

`cloud_storage_aws` extends Odoo's native `cloud_storage` framework to support **Amazon Web Services (AWS) S3** as a storage provider. It offloads attachment storage from the database/filestore to AWS S3, improving performance, scalability, and reducing hosting disk usage.

---

## Features

* **Direct Client-to-S3 Uploads (Chatter):**
  Uploads from the chatter go directly from the browser to Amazon S3 using secure, short-lived presigned `PUT` URLs. This prevents large file uploads from consuming Odoo server bandwidth and worker threads.

* **Secure Presigned Downloads:**
  Downloads and inline document previews (such as PDF and image previews) are accessed via temporary, signed `GET` URLs with custom `Content-Disposition` headers to retain original filenames.

* **Server-Side Upload Fallback:**
  Files uploaded outside the chatter (e.g., standard `many2many_binary` fields, record forms) that exceed the configured minimum file size threshold are automatically transferred to S3 by the Odoo server.

* **Transaction-Safe Blob Deletion:**
  S3 object deletion is deferred until the database transaction has committed (`postcommit`). If a database transaction rolls back, blobs are not prematurely deleted from S3.

* **Deduplication & Shared File Protection:**
  When attachments are duplicated or copied across multiple records, the underlying S3 blob is safely preserved until the last referring attachment record is deleted.

* **Automatic CORS Setup:**
  The module automatically configures CORS (Cross-Origin Resource Sharing) on the designated S3 bucket to allow direct browser uploads and document previews.

* **Database Neutralization (`neutralize.sql`):**
  Automatically clears AWS credentials when the database is duplicated or restored in staging and test environments, safeguarding production buckets against accidental modifications.

* **Safe Uninstallation:**
  Includes an uninstall hook that checks if active S3 attachments still exist in the database, preventing accidental data disconnection before attachments are migrated.

---

## Requirements

* **Odoo**: Version 18.0, 19.0, or 20.0
* **Base Module**: `cloud_storage` (included in standard Odoo addons)
* **Python Dependency**: `boto3`

Install `boto3` in your Odoo Python environment:
```bash
pip install boto3
```

---

## AWS Configuration & Permissions

### 1. S3 Bucket Guidelines
* Create a dedicated Amazon S3 bucket (or use an existing one).
* **Important:** Avoid using dots (`.`) in the bucket name (e.g., prefer `my-company-odoo-storage` instead of `my.company.odoo.storage`). Virtual-hosted style HTTPS URLs (`https://<bucket>.s3.<region>.amazonaws.com`) rely on wildcard SSL certificates (`*.s3.<region>.amazonaws.com`), which do not support multi-level dot-separated subdomains.

### 2. IAM Policy
Create an IAM User (or IAM Role) with programmatic access credentials (`Access Key ID` and `Secret Access Key`). Attach an IAM policy granting the following permissions on your bucket:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "OdooCloudStorageBucketCORS",
            "Effect": "Allow",
            "Action": [
                "s3:PutBucketCORS"
            ],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"
        },
        {
            "Sid": "OdooCloudStorageObjectOperations",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        }
    ]
}
```

> **Note:** Replace `YOUR-BUCKET-NAME` with your actual S3 bucket name.

---

## Odoo Configuration

1. Log in to Odoo as an Administrator.
2. Go to **Settings > General Settings**.
3. Scroll down to the **Discuss / Cloud Storage** section.
4. Select **Amazon S3** as the **Cloud Storage Provider**.
5. Fill in the required fields:
   * **S3 Bucket Name**: e.g., `my-company-odoo-storage`
   * **S3 Region**: e.g., `ap-southeast-3` or `us-east-1`
   * **AWS Access Key ID**: Your AWS Access Key ID
   * **AWS Secret Access Key**: Your AWS Secret Access Key
6. Click **Save**. Odoo will automatically:
   * Verify upload, download, and delete permissions against a temporary test file.
   * Configure the necessary bucket CORS rules.

---

## Technical Details

### Blob Naming Convention
Stored object keys follow this format:
```text
<database_name>/<attachment_id>/<sha256_hash>.<extension>
```
* The file name is salted with a random UUID and SHA-256 hashed to make object URLs unpredictable and protect sensitive filenames.
* The original filename is restored upon download via HTTP `Content-Disposition`.

### Batch Deletions
Deletions are automatically grouped into batches of up to 1,000 keys per call using `DeleteObjects`, adhering strictly to AWS S3 API batch size limits.

---

## Author & License

* **Author:** Muhammad Syarif ([mhdsyarif.com](https://mhdsyarif.com))
* **Email:** mhdsyarif.ms@gmail.com
* **License:** LGPL-3
