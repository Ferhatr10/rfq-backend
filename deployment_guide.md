# RunPod Pod Kurulum ve Docker Build Rehberi

Bu rehber, projenizi RunPod üzerinde bir GPU Pod içinde nasıl test edeceğinizi ve sonrasında Docker imajınızı nasıl hazır hale getireceğinizi adım adım açıklar.

## Adım 1: RunPod Pod Başlatma

1. **GPU Seçimi**: RunPod paneline gidin ve bir GPU instance seçin (A6000, L4 veya RTX 4090 idealdir).
2. **Template/Image Seçimi**: 
   - `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime` veya `python:3.11` imajını kullanabilirsiniz.
   - **Container Disk (Temporary Storage)**: En az **50 GB** yapın. `torch`, `cuda` ve `docling` paketleri çok yer kaplar.
   - **Expose HTTP Ports**: `8888, 8080` portlarını açın.
3. **Volume**: Kodunuzu saklamak için bir network volume bağlamanız önerilir.

## Adım 2: Bağımlılıkların Kurulumu (Pod İçinde)

Pod'a terminalden bağlandıktan sonra şu komutları sırasıyla çalıştırın:

### 1. Sistem Paketleri
```bash
apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 curl zstd procps build-essential git
```

### 2. Projeyi Klonlama
```bash
git clone <repo_url>
cd <repo_dizini>
```

### 3. Ollama Kurulumu ve Model Yükleme
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve & # Arkaplanda başlat
sleep 5
ollama pull llama3 # Veya hangi modeli kullanacaksanız
```

### 3. Python Bağımlılıkları
```bash
pip install -r requirements.txt
```

## Adım 3: Çalıştırma ve Test

Pod içinde uygulamayı başlatmak için:
```bash
chmod +x start.sh
./start.sh
```

- **Test**: Pod'unuza atanan public IP ve 8080 portunu kullanarak `/process` endpoint'ine POST isteği atabilirsiniz.

---

## Adım 4: Docker Build (Dışarıya Hazırlama)

Kodun çalıştığından emin olduktan sonra, imajı build edip Docker Hub veya RunPod Registry'ye yüklemek için (kendi bilgisayarınızda):

1. **Build**:
   ```bash
   docker build -t kullanıcı_adınız/docling-rfq:latest .
   ```
2. **Push**:
   ```bash
   docker push kullanıcı_adınız/docling-rfq:latest
   ```

## Önemli İpuçları
- **Bellek (VRAM)**: Docling ve Ollama aynı anda GPU kullandığı için en az 16GB-24GB VRAM'li bir GPU tercih edin.
- **Port Yönlendirme**: FastAPI'nin dışarıdan erişilebilir olması için `uvicorn` host ayarını `0.0.0.0` yaptık, RunPod arayüzünde portun HTTP olarak işaretlendiğinden emin olun.
