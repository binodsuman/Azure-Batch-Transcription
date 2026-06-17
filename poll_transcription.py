import json
import time
import yaml
import requests
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient

CONFIG_FILE = "config.yaml"
JOB_FILE = "transcription_job.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)

def load_job():
    with open(JOB_FILE, "r") as f:
        return json.load(f)

def get_blob_service(connection_string):
    return BlobServiceClient.from_connection_string(
        connection_string
    )

def upload_json(
    blob_service,
    container_name,
    blob_name,
    content
):
    client = blob_service.get_blob_client(
        container=container_name,
        blob=blob_name
    )
    client.upload_blob(
        json.dumps(content, indent=2),
        overwrite=True
    )

def poll_until_done(
    status_url,
    headers,
    interval_seconds
):
    while True:
        response = requests.get(
            status_url,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()

        payload = response.json()

        status = payload.get("status")

        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Status: {status}"
        )

        if status == "Succeeded":
            return

        if status == "Failed":
            raise Exception(
                json.dumps(payload, indent=2)
            )

        time.sleep(interval_seconds)

def get_transcription_content_url(
    endpoint,
    api_key,
    job_id
):
    files_url = (
        f"{endpoint.rstrip('/')}"
        f"/speechtotext/v3.2/transcriptions/"
        f"{job_id}/files"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": api_key
    }

    response = requests.get(
        files_url,
        headers=headers,
        timeout=60
    )

    response.raise_for_status()

    payload = response.json()

    for item in payload.get("values", []):

        if item.get("kind") == "Transcription":

            return item["links"]["contentUrl"]

    raise Exception(
        "Could not locate transcription content URL."
    )

def download_transcription_json(
    content_url
):
    response = requests.get(
        content_url,
        timeout=120
    )
    response.raise_for_status()

    return response.json()

def build_processed_json(
    job_id,
    transcription_json
):
    transcript_parts = []
    speakers = []
    phrases = transcription_json.get(
        "recognizedPhrases",
        []
    )

    for phrase in phrases:

        speaker_id = phrase.get(
            "speaker",
            "Unknown"
        )

        n_best = phrase.get(
            "nBest",
            []
        )

        text = ""

        if n_best:
            text = (
                n_best[0]
                .get("display", "")
                .strip()
            )

        if not text:
            text = (
                phrase.get(
                    "display",
                    ""
                ).strip()
            )

        if not text:
            continue

        transcript_parts.append(text)

        speakers.append(
            {
                "speaker":
                    f"Speaker {speaker_id}",
                "text": text
            }
        )

    return {
        "job_id": job_id,
        "status": "Succeeded",
        "processed_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "transcript":
            " ".join(transcript_parts),
        "speakers":
            speakers
    }

def main():

    cfg = load_config()
    job = load_job()

    endpoint = cfg["speech"]["endpoint"]
    api_key = cfg["speech"]["api_key"]

    interval = cfg["polling"]["interval_seconds"]

    status_url = job["status_url"]
    job_id = job["job_id"]

    print("=" * 60)
    print(f"Monitoring Job : {job_id}")
    print(f"Polling every  : {interval} seconds")
    print("=" * 60)

    headers = {
        "Ocp-Apim-Subscription-Key":
            api_key
    }

    poll_until_done(
        status_url,
        headers,
        interval
    )

    print()
    print(
        "Fetching transcript from Azure..."
    )

    content_url = (
        get_transcription_content_url(
            endpoint,
            api_key,
            job_id
        )
    )

    print(
        f"Transcript URL found."
    )

    transcription_json = (
        download_transcription_json(
            content_url
        )
    )

    processed_json = (
        build_processed_json(
            job_id,
            transcription_json
        )
    )

    blob_service = (
        get_blob_service(
            cfg["storage"][
                "connection_string"
            ]
        )
    )

    processed_blob_name = (
        f"{cfg['output']['processed_folder']}/"
        f"{job_id}.json"
    )

    upload_json(
        blob_service,
        cfg["storage"][
            "container_name"
        ],
        processed_blob_name,
        processed_json
    )

    print()
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print(
        f"Processed JSON uploaded:"
    )
    print(
        processed_blob_name
    )

    print()
    print(
        f"Transcript length: "
        f"{len(processed_json['transcript'])}"
    )

    print(
        f"Speaker entries: "
        f"{len(processed_json['speakers'])}"
    )

if __name__ == "__main__":
    main()