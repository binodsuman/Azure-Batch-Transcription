import json
import uuid
import yaml
import requests

CONFIG_FILE = "config.yaml"
JOB_FILE = "transcription_job.json"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def validate_config(cfg):
    """Validate required config keys exist and are non-empty."""
    required = {
        "speech.endpoint": cfg.get("speech", {}).get("endpoint"),
        "speech.api_key": cfg.get("speech", {}).get("api_key"),
        "speech.locale": cfg.get("speech", {}).get("locale"),
        "audio.sas_url": cfg.get("audio", {}).get("sas_url"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(
            f"Missing or empty required config keys: {', '.join(missing)}"
        )



def main():
    cfg = load_config()
    validate_config(cfg)

    endpoint = cfg["speech"]["endpoint"].rstrip("/")
    api_key = cfg["speech"]["api_key"]
    locale = cfg["speech"]["locale"]

    transcription_url = f"{endpoint}/speechtotext/v3.2/transcriptions"

    # How long Azure keeps the job + raw results after completion.
    # Azure allows 6 hours - 31 days; 48 hours is Microsoft's recommended
    # default for pipelines that consume results right away.
    time_to_live_hours = cfg["speech"].get("time_to_live_hours", 48)

    payload = {
        "displayName": f"transcription-{uuid.uuid4()}",
        "locale": locale,
        "contentUrls": [
            cfg["audio"]["sas_url"]
        ],
        "properties": {
            "diarizationEnabled": True,
            "wordLevelTimestampsEnabled": True,
            "punctuationMode": "DictatedAndAutomatic",
            "profanityFilterMode": "Masked",
            "timeToLiveHours": time_to_live_hours
        }
    }

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json"
    }

    print("Submitting transcription job to Azure Speech...")

    try:
        response = requests.post(
            transcription_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Surface Azure's error body for easier debugging
        try:
            error_body = response.json()
        except Exception:
            error_body = response.text
        raise Exception(
            f"Azure returned HTTP {response.status_code}:\n"
            f"{json.dumps(error_body, indent=2)}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request to Azure failed: {e}") from e

    location = response.headers.get("Location")
    if not location:
        raise Exception(
            "Azure did not return a Location header. "
            f"Response headers: {dict(response.headers)}"
        )

    # Extract job ID from the end of the Location URL
    job_id = location.rstrip("/").split("/")[-1]
    if not job_id:
        raise Exception(
            f"Could not parse job ID from Location header: {location}"
        )

    job_data = {
        "job_id": job_id,
        "status_url": location
    }

    with open(JOB_FILE, "w") as f:
        json.dump(job_data, f, indent=2)

    print("=" * 80)
    print("JOB SUBMITTED SUCCESSFULLY")
    print("=" * 80)
    print(f"Job ID      : {job_id}")
    print(f"Status URL  : {location}")
    print(f"TTL (hours) : {time_to_live_hours}")
    print()
    print("CURL (to check status manually):")
    print(
        f'  curl -X GET "{location}" \\\n'
        f'       -H "Ocp-Apim-Subscription-Key: {api_key}"'
    )
    print()
    print(f'Job metadata saved to: {JOB_FILE}')
    print('Next step   : run  python poll_transcription.py')


if __name__ == "__main__":
    main()
