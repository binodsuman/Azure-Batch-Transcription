# Azure Batch Speech-to-Text Transcription

A Python-based solution for Azure Speech Batch Transcription that processes audio files stored in Azure Blob Storage using SAS URLs and generates conversation transcripts for analytics, customer conversation insights, compliance review, call-center analysis, meeting transcription, and archival purposes.

This solution is designed for **cost optimization** when real-time transcription is not required.

---

# Why Batch Transcription?

Azure provides two primary Speech-to-Text options:

## Real-Time Speech-to-Text

Use when:

- Live captioning is required
- Agent assist is required
- Real-time call analytics is required
- Immediate response is needed

Pros:

- Near real-time results
- Suitable for live applications

Cons:

- Higher operational complexity
- Continuous streaming required
- More infrastructure components

---

## Batch Transcription (Recommended)

Use when:

- Audio is already recorded
- Thousands of conversations need processing
- Historical calls need analysis
- Contact center recordings need transcription
- Meeting recordings need transcription
- Cost optimization is important

Pros:

- Lower operational cost
- Easy integration
- Supports large-scale processing
- No streaming infrastructure required
- Supports Blob Storage directly

Cons:

- Not real-time
- Processing starts asynchronously

---

# Architecture

```text
+------------------+
| Audio Recording  |
| WAV File         |
+--------+---------+
         |
         |
         v
+------------------+
| Azure Blob       |
| Storage (Input)  |
+--------+---------+
         |
         |
         v
+------------------+
| Submit Job       |
| submit_transcription.py
+--------+---------+
         |
         |
         v
+------------------+
| Azure Speech     |
| Batch Service    |
+--------+---------+
         |
         |
         v
+------------------+
| Azure Output     |
| Container        |
+--------+---------+
         |
         |
         v
+------------------+
| poll_transcription.py
+--------+---------+
         |
         |
         v
+------------------+
| Processed JSON   |
+------------------+
```

---

# Features

- Azure Speech Batch Transcription
- Audio file via SAS URL
- Automatic polling
- Azure-managed output storage
- Processed JSON generation
- Speaker diarization support
- Word-level timestamps
- Blob Storage integration
- Suitable for large-scale processing

---

# Azure Resources Required

## 1. Azure Speech Service

Create:

```text
Azure Portal
   -> Create Resource
   -> AI + Machine Learning
   -> Speech Service
   -> Storage Service
```

Required values:

```text
Speech Key
Speech Region
Speech Endpoint
```

Example:

```text
Key:
xxxxxxxxxxxxxxxxxxxxxxxx

Region:
eastus

Endpoint:
https://eastus.api.cognitive.microsoft.com
```

---

## 2. Azure Storage Account

# Azure Storage Requirements

Only two SAS URLs are required.

## 1. Input Audio Blob SAS URL

Upload your audio file to Azure Blob Storage and generate a **Blob SAS URL** with **Read** permission.

Example:

```text
https://<storage-account>.blob.core.windows.net/audio/customer_call.wav?<sas-token>
```

This URL is configured in:

```yaml
audio:
  sas_url: "<INPUT_AUDIO_BLOB_SAS_URL>"
```

---

## 2. Destination Container SAS URL

Create (or choose) a destination container where Azure Speech and this application will store transcription results.

Generate a **Container SAS URL** with at least the following permissions:

- Read
- Write
- List

Example:

```text
https://<storage-account>.blob.core.windows.net/transcript-output?<sas-token>
```

Configure it as:

```yaml
speech:
  destination_container_sas_url: "<DESTINATION_CONTAINER_SAS_URL>"
```

No Azure Storage connection string is required.
No storage account key is required.
Only these two SAS URLs are needed.
---

# Project Structure

```text
project/
│
├── submit_transcription.py
├── poll_transcription.py
├── config.yaml
├── transcription_job.json
├── requirements.txt
│
└── output/
```

---

# Python Version

Recommended:

```text
Python 3.11
```

Minimum:

```text
Python 3.8
```

Avoid:

```text
Python 3.7
```

Azure SDK support is being removed.

---

# Installation

## Create Virtual Environment

Linux / Mac

```bash
python3.11 -m venv venv
source venv/bin/activate
```

Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# requirements.txt

```text
requests
PyYAML
azure-storage-blob
```

---

# Configuration

Update `config.yaml`

```yaml
speech:
  endpoint: "https://<region>.api.cognitive.microsoft.com"
  api_key: "<YOUR_SPEECH_KEY>"
  locale: "en-US"

  # Destination container SAS URL
  destination_container_sas_url: "<DESTINATION_CONTAINER_SAS_URL>"

audio:
  # Input audio blob SAS URL
  sas_url: "<INPUT_AUDIO_BLOB_SAS_URL>"

polling:
  interval_seconds: 30
```

---

# Submit Transcription Job

Run:

```bash
python submit_transcription.py
```

Example output:

```text
JOB SUBMITTED SUCCESSFULLY

Job ID:
e83f02a7-ce41-4dfe-ae87-cfe6cc8e88d5
```

Creates:

```text
transcription_job.json
```

---

# Poll Job Status

Run:

```bash
python poll_transcription.py
```

Example:

```text
Status: Running
Status: Running
Status: Succeeded
```

---

# Manual Status Check

```bash
curl -X GET \
"https://<endpoint>/speechtotext/v3.2/transcriptions/<jobId>" \
-H "Ocp-Apim-Subscription-Key: <speech-key>"
```

---

# Audio Requirements

## Recommended Format

```text
WAV
PCM
16-bit
Mono
16kHz
```

Best compatibility with Azure Speech.

---

## Supported Format

```text
WAV
PCM
48kHz
Mono
```

Also supported.

---

# Speaker Diarization

Speaker diarization identifies different speakers.

Example:

```text
Speaker 1:
Hello John.

Speaker 2:
Hello Mike.
```

---

## Enable Diarization

In submit_transcription.py:

```python
"diarizationEnabled": True
```

---

## Disable Diarization

```python
"diarizationEnabled": False
```

---

# Diarization Requirements

Recommended:

```text
Mono audio
PCM WAV
16kHz+
```

Many stereo recordings fail diarization validation.

---

# Convert Stereo to Mono

```bash
ffmpeg -i input.wav \
-ac 1 \
-ar 16000 \
-c:a pcm_s16le \
output.wav
```

---

# Verify Audio

```bash
ffprobe input.wav
```

Check:

```text
Codec
Sample Rate
Channels
```

---

# Quick Start

## Step 1 - Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2 - Submit Batch Transcription Job

```bash
python submit_transcription.py
```

This submits the transcription request to Azure Speech and creates:

```
transcription_job.json
```

---

## Step 3 - Monitor Job

```bash
python poll_transcription.py
```

The script will:

- Poll Azure every 30 seconds
- Wait until the job completes
- Download Azure transcript
- Generate simplified JSON
- Upload `<filename>_transcript.json` to the destination container

---


# Output JSON Structure

Example:

```json
{
  "job_id": "e83f02a7-ce41-4dfe-ae87-cfe6cc8e88d5",
  "status": "Succeeded",
  "processed_at": "2026-06-17T12:00:00Z",
  "transcript": "Hello how are you today...",
  "speakers": [
    {
      "speaker": "Speaker 1",
      "text": "Hello"
    },
    {
      "speaker": "Speaker 2",
      "text": "Hi"
    }
  ]
}
```

---

# Azure Batch API Version

Current implementation uses:

```text
Speech-to-Text REST API v3.2
```

---

# Common Errors

## InvalidData

Example:

```json
{
  "code": "InvalidData"
}
```

Possible causes:

- Unsupported codec
- Stereo audio with diarization enabled
- Corrupt audio file

---

## Authentication Failure

```text
401 Unauthorized
```

Verify:

- Speech Key
- Endpoint
- Region

---

## SAS URL Expired

```text
403 Forbidden
```

Generate a new SAS token.

---

# Cost Optimization Tips

Batch Transcription is recommended when:

- Processing recorded calls
- Analyzing customer interactions
- Generating conversation insights
- Creating searchable transcripts
- Compliance review
- Historical meeting transcription

Avoid using real-time speech services if immediate transcription is not required.

For large volumes of recordings, Batch Transcription significantly reduces operational complexity while maintaining high transcription accuracy.

---

# Future Enhancements

- Multiple audio file support
- Queue-based processing
- Azure Functions integration
- Azure Data Factory integration
- Sentiment analysis
- Key phrase extraction
- Conversation intelligence
- Speaker analytics
- Transcript summarization using Azure OpenAI