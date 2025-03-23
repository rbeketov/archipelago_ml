FROM nvcr.io/nvidia/tritonserver:23.12-py3

RUN pip install numpy==1.26.4 torch==2.0.1 transformers==4.30.2 pillow==10.4.0

WORKDIR /workspace

CMD ["tritonserver", "--model-repository=/models"]
