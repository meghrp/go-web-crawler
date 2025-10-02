# Web Crawler API

## Local run
```bash
go build -o api/gocrawler .
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Docker
```bash
docker compose up crawler-api
```

## Cloud Run
```bash
./deploy.sh PROJECT_ID REGION
# or: gcloud builds submit --config cloudbuild.yaml
```

## Generic container
```bash
docker build -f api/Dockerfile -t crawler-api .
docker run -p 8080:8080 crawler-api
```
