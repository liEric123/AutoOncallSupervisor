# AutoOncallSupervisor

Automatically detects and retries Buildkite builds that failed due to agent disconnection.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy and configure:
```bash
cp config.json.template config.json
# Edit config.json with your actual values
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