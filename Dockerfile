# =============================================================================
# A4I 2026 · Challenge 04 ("First Milestones")
# Unified Cloud Run Container:
#   - Official Google MCP Toolbox for Databases (`v0.27.0`)
#   - Python ADK Agent (`first_milestones`) + Gemini on Vertex AI
#   - FastAPI + Split-Pane 45-Day Pathway & Bottleneck Brief Web UI
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TOOLBOX_URL=http://127.0.0.1:5000

WORKDIR /app

# Install curl + CA certificates and download official Google MCP Toolbox binary
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && curl -fsSL -o /usr/local/bin/toolbox \
      https://storage.googleapis.com/genai-toolbox/v0.27.0/linux/amd64/toolbox \
    && chmod +x /usr/local/bin/toolbox \
    && rm -rf /var/lib/apt/lists/*

COPY agent/requirements.txt /app/agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agent/requirements.txt

# Copy starter GeoParquet tables & ADK application + static Workbench UI
COPY data /app/data
COPY agent /app/agent
RUN chmod +x /app/agent/entrypoint.sh

EXPOSE 8080

CMD ["/app/agent/entrypoint.sh"]
