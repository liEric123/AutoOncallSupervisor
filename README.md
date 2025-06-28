# AutoOncallSupervisor

Automatically detects and retries Buildkite builds that failed due to agent disconnection.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `config.json`:
```json
{
    "buildkite_token": "your_buildkite_api_token",
    "org_slug": "your_organization_slug", 
    "pipeline_slug": "your_pipeline_slug",
    "target_branch": "prod",
    "lark_webhook_url": "your_lark_webhook_url"
}
```

3. Run:
```bash
python auto_oncall_supervisor.py
```

## Configuration

| Setting | Description
|---------|------------|
| `buildkite_token` | Buildkite API token
| `org_slug` | Organization slug
| `pipeline_slug` | Pipeline slug
| `target_branch` | Branch to monitor
| `lark_webhook_url` | Lark webhook URL

## Testing

```bash
python simple_test.py
```

## How it works

1. Fetches recent builds from specified pipeline/branch
2. Identifies builds that failed with `exit_status == -1` (agent lost)
3. Automatically retries those jobs
4. Sends notifications to Lark webhook