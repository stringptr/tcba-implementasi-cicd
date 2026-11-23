# CI/CD Web Scraping → Azure Data Lake Storage

Scrapes two public hydrology/meteorology APIs with GitHub Actions and lands the
raw JSON in Azure Data Lake Storage (Gen2). Based on the reference ingestion
project (Prefect + Garage/S3), with the orchestration moved to GitHub Actions
and the storage backend swapped to Azure.

## Data sources

| Source | Endpoint | Parameters |
| --- | --- | --- |
| [USGS Water Data OGC API](https://api.waterdata.usgs.gov/ogcapi/v1/collections) | `daily`, `continuous` | `00060` discharge, `00065` gage height |
| [Open-Meteo archive API](https://archive-api.open-meteo.com/v1/archive) | hourly | precipitation, rain, 3× soil moisture, temperature, humidity, pressure, ET0, wind, radiation, cloud cover |

Three California stations (`11525670`, `11150500`, `11454000`) are configured in
`ingest/stations.py`.

## Storage layout

One ADLS container, raw payloads stored verbatim:

```
<container>/bronze/usgs/{daily|continuous}/parameter_code=<code>/station_id=<id>/ingest_date=YYYY-MM-DD/part-000.json
<container>/bronze/open-meteo/station_id=<id>/ingest_date=YYYY-MM-DD/part-000.json
```

Each `ingest_date` partition holds that UTC day plus the previous `LOOKBACK_DAYS`
days (default 7). Missing days are backfilled and existing days skipped, so a
long run can be stopped and resumed without repeating work.

## Configuration

### A. GitHub repository
Two long-lived branches are used: `main` and `dev`. Work on a feature branch,
open a PR into `dev`, then merge `dev` into `main`. CI runs on every push/PR to
both branches.

### B. Azure Storage Account
Create a Storage Account with **hierarchical namespace enabled** (Data Lake
Storage Gen2) and a container (e.g. `datalake`).

### C/D. Microsoft Entra ID app + federated credential
1. **Entra ID → App registrations → New registration**. Save the
   **Application (Client) ID** and **Directory (Tenant) ID**.
2. **Certificates & secrets → Federated credentials → Add credential →
   GitHub Actions deploying Azure resources**. Set Organization, Repository,
   Entity type **Branch**, Branch (e.g. `main`), and a credential name.

### E. Grant blob access (corrected)
The task's *Roles and administrators* screen assigns an Entra **directory**
role, which does **not** grant data-plane access. To let the workflow write
blobs, grant a storage data role:

> Storage Account → **Access control (IAM) → Add role assignment →
> Storage Blob Data Contributor** → assign to the registered app.

### F. GitHub repository variables
**Settings → Secrets and variables → Actions**. Add these **Variables**:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | Application (Client) ID |
| `AZURE_TENANT_ID` | Directory (Tenant) ID |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID |
| `AZURE_STORAGE_ACCOUNT` | Storage Account name |
| `AZURE_STORAGE_CONTAINER` | Container name (e.g. `datalake`) |

Add one **Secret** (the USGS API key is sensitive):

| Secret | Value |
| --- | --- |
| `USGS_API_KEY` | USGS Water Data API key |

## Workflows

- `.github/workflows/ci.yml` — on push/PR to `main`/`dev`: ruff lint, import
  smoke test, then run the scraping code over a 1-day window into a local
  directory (needs the `USGS_API_KEY` secret).
- `.github/workflows/cd.yml` — on a `0 */6 * * *` schedule and via
  **Run workflow** (`workflow_dispatch`): OIDC login, then run the pipeline.

## Running locally

```bash
pip install -r requirements.txt
export AZURE_STORAGE_ACCOUNT=<account>
export AZURE_STORAGE_CONTAINER=<container>
export USGS_API_KEY=<key>
az login          # DefaultAzureCredential uses your CLI session
python -m ingest.pipeline
```

Optional env overrides: `USGS_HISTORIC_START_DATE`, `OPEN_METEO_HISTORIC_START_DATE`,
`BRONZE_PREFIX` (default `bronze`), `LOOKBACK_DAYS` (default 7),
`EMPTY_GRACE_DAYS` (default 3), `STATIONS`, `BRONZE_LOCAL_DIR` (default `./data`).

When `AZURE_STORAGE_ACCOUNT`/`AZURE_STORAGE_CONTAINER` are unset, output is
written under `BRONZE_LOCAL_DIR` instead of Azure (used by CI and local runs).
