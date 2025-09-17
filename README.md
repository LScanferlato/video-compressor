# video-compressor

podman build -t video-compressor .
podman run -p 5000:5000 --replace --name compressor video-compressor
