# Support Update Studio

A Streamlit application that transforms technical support notes, terminal output, screenshots, and reference links into complete support communications using Google Gemini.

It generates three drafts for each case:

* Customer update
* Detailed internal case note
* Engineering escalation summary

## Features

* Paste technical logs, commands, errors, and case notes.
* Paste screenshots directly into the case-notes editor.
* Include GitHub issues, pull requests, KB articles, and special instructions.
* Generate structured drafts with clear headings and preserved technical evidence.
* Copy output as formatted Salesforce rich text or raw Markdown.
* Use Gemini API securely through an environment variable or Kubernetes Secret.

## Architecture

```text
GitHub repository
        ↓
GitHub Actions builds the container image
        ↓
GitHub Container Registry (GHCR)
        ↓
RKE2 Kubernetes cluster
        ↓
Traefik Ingress / temporary nip.io URL
```

## Prerequisites

* Python 3.11 or later for local development
* A Google Gemini API key
* Docker for local container testing
* An RKE2 Kubernetes cluster for deployment
* Access to GitHub Container Registry

## Local Development

Clone the repository and install dependencies:

```bash
git clone https://github.com/prabhassasi/support-update-studio.git
cd support-update-studio

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Set the Gemini API key:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

Start the application:

```bash
streamlit run app.py
```

Open the URL shown in the terminal, normally:

```text
http://localhost:8501
```

## Container Build and Test

Build the container image locally:

```bash
docker build -t support-update-studio:local .
```

Run it locally:

```bash
docker run --rm -p 8501:8501 \
  -e GEMINI_API_KEY="your-gemini-api-key" \
  support-update-studio:local
```

Open:

```text
http://localhost:8501
```

## Kubernetes Deployment

Kubernetes manifests are stored in the `k8s/` directory.

The Gemini API key must be created as a Kubernetes Secret. Do not add the actual API key to:

* GitHub source code
* Kubernetes YAML committed to GitHub
* Dockerfiles
* Screenshots, logs, or support bundles

Example secret creation command:

```bash
kubectl create namespace support-update-studio

kubectl -n support-update-studio create secret generic support-update-studio-secrets \
  --from-literal=GEMINI_API_KEY="your-gemini-api-key"
```

The application Deployment reads this secret as the `GEMINI_API_KEY` environment variable.

## Security Notes

* Keep this repository private.
* Keep the container image private in GitHub Container Registry.
* Never commit API keys, passwords, access tokens, customer secrets, or unredacted support bundles.
* Review and redact customer data before submitting it to the application.
* Use Kubernetes Secrets for runtime credentials.
* The current local authentication code must be replaced before production use; access should be controlled by the cluster ingress or an approved identity provider.

## License

Internal use only.
