import json
import time
import yaml
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from azure.storage.blob import ContainerClient

CONFIG_FILE = "config.yaml"
JOB_FILE = "transcription_job.json"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def load_job():
    with open(JOB_FILE, "r") as f:
        return json.load(f)


def get_filename_from_url(url):
    """Extract just the blob filename from a SAS URL (strips query string)."""
    path_only = url.split("?", 1)[0]
    return path_only.rstrip("/").split("/")[-1]


def strip_sas_signature(url):
    """
    Return a URL with its query string (SAS token / signature) removed,
    safe to print to console or logs. The path itself is not a secret;
    the sig=... query parameter is.
    """
    return url.split("?", 1)[0]


def get_destination_container_client(destination_container_sas_url):
    """
    Build a ContainerClient scoped to the destination SAS URL.
    A container-level SAS already carries its own auth (sig=...), so no
    account key / connection string is needed -- but the SAS must have
    been generated with write permission.
    """
    parsed = urlparse(destination_container_sas_url)
    query_params = parse_qs(parsed.query)
    permissions = query_params.get("sp", [""])[0]

    if "w" not in permissions:
        raise ValueError(
            "speech.destination_container_sas_url does not have write "
            f"permission (sp='{permissions}'). Regenerate the SAS with "
            "write access included (e.g. sp=rw or sp=rwl)."
        )

    return ContainerClient.from_container_url(destination_container_sas_url)


def upload_json(container_client, blob_name, content):
    client = container_client.get_blob_client(blob_name)
    client.upload_blob(
        json.dumps(content, indent=2),
        overwrite=True
    )


def poll_until_done(status_url, headers, interval_seconds):
    while True:
        response = requests.get(status_url, headers=headers, timeout=60)
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
            raise Exception(json.dumps(payload, indent=2))

        time.sleep(interval_seconds)


def list_transcription_files(endpoint, api_key, job_id):
    """
    Returns the full list of result files Azure produced for this job
    (typically one 'Transcription' file per audio file, plus one
    'TranscriptionReport' summary file). Since destinationContainerUrl
    is not set at submit time, these live in Azure's own Microsoft-
    managed temporary storage, reachable only via the contentUrl this
    API hands back (valid until the job's timeToLiveHours expires).
    """
    files_url = (
        f"{endpoint.rstrip('/')}"
        f"/speechtotext/v3.2/transcriptions/"
        f"{job_id}/files"
    )
    headers = {"Ocp-Apim-Subscription-Key": api_key}

    response = requests.get(files_url, headers=headers, timeout=60)
    response.raise_for_status()

    return response.json().get("values", [])


def get_transcription_content_url(files):
    for item in files:
        if item.get("kind") == "Transcription":
            return item["links"]["contentUrl"], item.get("name")

    raise Exception("Could not locate transcription content URL.")


def download_transcription_json(content_url):
    response = requests.get(content_url, timeout=120)
    response.raise_for_status()
    return response.json()


def build_processed_json(job_id, transcription_json):
    transcript_parts = []
    speakers = []
    phrases = transcription_json.get("recognizedPhrases", [])

    for phrase in phrases:
        speaker_id = phrase.get("speaker", "Unknown")
        n_best = phrase.get("nBest", [])

        text = ""
        if n_best:
            text = n_best[0].get("display", "").strip()
        if not text:
            text = phrase.get("display", "").strip()
        if not text:
            continue

        transcript_parts.append(text)
        speakers.append(
            {
                "speaker": f"Speaker {speaker_id}",
                "text": text
            }
        )

    return {
        "job_id": job_id,
        "status": "Succeeded",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "transcript": " ".join(transcript_parts),
        "speakers": speakers
    }


def main():
    cfg = load_config()
    job = load_job()

    endpoint = cfg["speech"]["endpoint"]
    api_key = cfg["speech"]["api_key"]

    destination_container_sas_url = cfg["speech"].get(
        "destination_container_sas_url"
    )
    if not destination_container_sas_url:
        raise ValueError(
            "Missing config key: speech.destination_container_sas_url"
        )

    audio_url = cfg["audio"]["sas_url"]
    audio_filename = get_filename_from_url(audio_url)
    filename_stem = audio_filename.rsplit(".", 1)[0]

    interval = cfg["polling"]["interval_seconds"]

    status_url = job["status_url"]
    job_id = job["job_id"]

    print("=" * 60)
    print(f"Monitoring Job : {job_id}")
    print(f"Input file     : {audio_filename}")
    print(f"Polling every  : {interval} seconds")
    print("=" * 60)

    headers = {"Ocp-Apim-Subscription-Key": api_key}

    poll_until_done(status_url, headers, interval)

    print()
    print("Fetching result file list from Azure...")

    files = list_transcription_files(endpoint, api_key, job_id)

    print(f"Azure produced {len(files)} result file(s) in the destination container:")
    for item in files:
        # Print just the name/kind -- never the contentUrl itself, since
        # it's a SAS-bearing credential and shouldn't hit the console.
        print(f"  - [{item.get('kind')}] {item.get('name')}")

    content_url, raw_blob_name = get_transcription_content_url(files)

    print("Raw content URL ", content_url)
    transcription_json = download_transcription_json(content_url)

    processed_json = build_processed_json(job_id, transcription_json)

    container_client = get_destination_container_client(
        destination_container_sas_url
    )

    raw_upload_blob_name = f"{filename_stem}_raw.json"
    processed_blob_name = f"{filename_stem}_transcript.json"

    upload_json(container_client, raw_upload_blob_name, transcription_json)
    upload_json(container_client, processed_blob_name, processed_json)

    # Base container path (SAS stripped) -- used to build permanent,
    # printable paths to both files now sitting in the destination
    # container. This is NOT a working URL on its own (no SAS token),
    # just a human-readable reference to where the blobs live.
    container_base_path = strip_sas_signature(container_client.url)

    print()
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print("Both files uploaded to your destination container:")
    print()
    print("1) Raw Azure output -- permanent")
    print(f"     {container_base_path}/{raw_upload_blob_name}")
    print()
    print("2) Enriched transcript -- permanent")
    print(f"     {container_base_path}/{processed_blob_name}")

    print()
    print(f"Transcript length: {len(processed_json['transcript'])}")
    print(f"Speaker entries: {len(processed_json['speakers'])}")


if __name__ == "__main__":
    main()
