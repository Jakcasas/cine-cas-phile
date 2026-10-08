"""Local CLIP image retrieval over indexed film stills and posters."""
from io import BytesIO
import json
from pathlib import Path
import threading
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 20_000_000


def decode_image(data):
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("Ảnh phải nhỏ hơn 8 MB.")
    try:
        image=Image.open(BytesIO(data))
        if image.format not in {'JPEG','PNG','WEBP'}:
            raise ValueError("Hãy dùng ảnh JPEG, PNG hoặc WebP.")
        if image.width*image.height > 20_000_000 or min(image.size)<16:
            raise ValueError("Ảnh phải có ít nhất 16 pixel mỗi chiều và không quá 20 megapixel.")
        image.load()
        return ImageOps.exif_transpose(image).convert('RGB')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as error:
        raise ValueError("Không đọc được ảnh. Hãy dùng JPEG, PNG hoặc WebP hợp lệ.") from error


class ClipEncoder:
    def __init__(self, folder):
        import onnxruntime as ort
        config=json.loads((folder/'preprocessor_config.json').read_text())
        self.mean=np.array(config['image_mean'],dtype=np.float32)
        self.std=np.array(config['image_std'],dtype=np.float32)
        options=ort.SessionOptions();options.intra_op_num_threads=4
        self.session=ort.InferenceSession(str(folder/'clip-vit-b32-int8.onnx'),options,providers=['CPUExecutionProvider'])

    def encode(self, images):
        tensors=[]
        for image in images:
            image=ImageOps.fit(image,(224,224),method=Image.Resampling.BICUBIC,centering=(.5,.5))
            array=np.asarray(image,dtype=np.float32)/255
            tensors.append(((array-self.mean)/self.std).transpose(2,0,1))
        embeddings=self.session.run(['image_embeds'],{'pixel_values':np.stack(tensors).astype(np.float32)})[0]
        return embeddings / np.maximum(np.linalg.norm(embeddings,axis=1,keepdims=True),1e-12)


class VisualSearch:
    def __init__(self, folder, catalog_fingerprint):
        self.folder=Path(folder);self.encoder=None;self.lock=threading.Lock()
        self.ready=False;self.count=0;self.stills_count=0
        path=self.folder/'image_index.npz'
        if not path.exists():return
        with np.load(path,allow_pickle=False) as index:
            if str(index['catalog_fingerprint'])!=catalog_fingerprint:return
            self.vectors=index['embeddings'].copy()
            self.movie_ids=index['movie_ids'].copy()
            self.urls=index['urls'].copy()
            self.kinds=index['kinds'].copy()
        self.count=len(set(self.movie_ids.tolist()))
        self.stills_count=int((self.kinds=='still').sum())
        self.ready=True

    def search(self, data, k=12):
        image=decode_image(data)
        if not self.ready:
            raise RuntimeError("Kho tìm ảnh chưa sẵn sàng. Chạy tools/build_visual_index.py.")
        with self.lock:
            if self.encoder is None:self.encoder=ClipEncoder(self.folder)
            vector=self.encoder.encode([image])[0]
        scores=self.vectors @ vector
        order=np.argsort(-scores,kind='stable')
        selected=[];seen=set()
        for position in order:
            mid=int(self.movie_ids[position])
            if mid in seen:continue
            seen.add(mid)
            selected.append({'movie_id':mid,'visual_similarity':round(float(scores[position]),4),
                             'matched_image_url':str(self.urls[position]),'matched_image_kind':str(self.kinds[position])})
            if len(selected)>=k:break
        return selected
