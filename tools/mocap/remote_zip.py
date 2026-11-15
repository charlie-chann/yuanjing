"""从网上的大压缩包里只取需要的几个文件（按字节范围下载，不用把几个 G 的包整个下下来）。
用法：python3 remote_zip.py <网址> <输出目录> [文件名里包含的字 ...]   不带关键字就只列目录"""
import io
import os
import sys
import urllib.request
import zipfile


class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method='HEAD')
        self.size = int(urllib.request.urlopen(req).headers['Content-Length'])

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{self.pos + n - 1}'})
        data = urllib.request.urlopen(req).read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


url, out, keys = sys.argv[1], sys.argv[2], sys.argv[3:]
z = zipfile.ZipFile(io.BufferedReader(HttpFile(url), buffer_size=1 << 20))
names = z.namelist()
if not keys:
    print(len(names))
    for n in names[:400]:
        print(n)
    sys.exit()
os.makedirs(out, exist_ok=True)
for n in names:
    if any(k in n for k in keys) and not n.endswith('/'):
        dst = os.path.join(out, os.path.basename(n))
        with open(dst, 'wb') as f:
            f.write(z.read(n))
        print('取', n, os.path.getsize(dst))
