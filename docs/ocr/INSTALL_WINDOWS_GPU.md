# Windows GPU 설치 — 검증 환경

## 검증된 조합

```text
Windows
Python 3.11.9
NVIDIA GeForce RTX 3070
NVIDIA driver 581.42
paddlepaddle-gpu 3.3.0 (CUDA 12.9 build)
PaddleOCR 3.7.0
PaddleX 3.7.2
device gpu:0
```

`nvidia-smi`의 CUDA 표시는 드라이버가 지원하는 최대 capability이며 로컬 runtime 버전으로 해석하지 않습니다.

## 별도 가상환경 설치

```powershell
py -3.11 -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
.\.venv-gpu\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

다른 GPU/driver에서는 위 wheel을 그대로 설치하지 말고 PaddlePaddle 공식 설치 문서에서 지원 조합을 먼저 확인합니다.

## 확인

```powershell
.\.venv-gpu\Scripts\python.exe -c "import paddle; paddle.utils.run_check(); print(paddle.__version__); print(paddle.version.cuda()); print(paddle.is_compiled_with_cuda()); print(paddle.device.cuda.device_count()); print(paddle.device.cuda.get_device_name(0))"
```

성공 기준:

- `paddle.is_compiled_with_cuda() == True`
- CUDA device count가 1 이상
- GPU 이름이 실제 장치와 일치

CPU 가상환경과 GPU 가상환경에 `paddlepaddle`과 `paddlepaddle-gpu`를 섞어 설치하지 않습니다.
