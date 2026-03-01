# RunPod Pod Setup & Docker Build Guide

This guide explains step-by-step how to test your project inside a GPU Pod on RunPod and then prepare your Docker image for deployment.

## Step 1: Launch RunPod Pod

1. **GPU Selection**: Go to the RunPod panel and select a GPU instance (A6000, L4, or RTX 4090 are ideal).
2. **Template/Image Selection**: 
   - You can use `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime` or `python:3.11` image.
   - **Container Disk (Temporary Storage)**: Set at least **50 GB**. `torch`, `cuda`, and `docling` packages take up significant space.
   - **Expose HTTP Ports**: Open ports `8888, 8080`.
3. **Volume**: It is recommended to attach a network volume to persist your code.

## Step 2: Installing Dependencies (Inside Pod)

After connecting to the Pod via terminal, run the following commands in order:

### 1. System Packages
```bash
apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 curl zstd procps build-essential git
```

### 2. Clone the Project
```bash
git clone <repo_url>
cd <repo_directory>
```

### 3. Ollama Installation & Model Download
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve & # Start in background
sleep 5
ollama pull llama3 # Or whichever model you plan to use
```

### 4. Python Dependencies
```bash
pip install -r requirements.txt
```

## Step 3: Running & Testing

To start the application inside the Pod:
```bash
chmod +x start.sh
./start.sh
```

- **Testing**: You can send POST requests to the `/process` endpoint using your Pod's assigned public IP and port 8080.

---

## Step 4: Docker Build (Preparing for Deployment)

After confirming the code works, build the image and push it to Docker Hub or RunPod Registry (on your local machine):

1. **Build**:
   ```bash
   docker build -t your_username/docling-rfq:latest .
   ```
2. **Push**:
   ```bash
   docker push your_username/docling-rfq:latest
   ```

## Important Tips
- **Memory (VRAM)**: Since Docling and Ollama both use the GPU simultaneously, prefer a GPU with at least 16GB-24GB VRAM.
- **Port Forwarding**: We set the `uvicorn` host to `0.0.0.0` so FastAPI is accessible externally. Make sure the port is marked as HTTP in the RunPod interface.
