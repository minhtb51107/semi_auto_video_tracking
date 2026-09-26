"""Fetch one KITTI sequence with bounded HTTP ranges, never the full image ZIP."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

IMAGE_URL='https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_2.zip'
LABEL_URL='https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_label_2.zip'


class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url=url
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60) as response:
            self.size=int(response.headers['Content-Length'])
            self.etag=response.headers['ETag']
        self.position=0
        self.transferred=0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        pos=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if pos<0: raise ValueError('negative seek')
        self.position=pos
        return pos

    def read(self, count=-1):
        count=self.size-self.position if count<0 else min(count,self.size-self.position)
        if count<=0: return b''
        if count>8*1024*1024: raise ValueError('Refuse range larger than 8MiB')
        end=self.position+count-1
        req=urllib.request.Request(self.url,headers={'Range':f'bytes={self.position}-{end}','If-Match':self.etag})
        with urllib.request.urlopen(req,timeout=60) as response:
            if response.status!=206: raise ValueError('Server ignored Range; refuse full archive')
            expected=f'bytes {self.position}-{end}/{self.size}'
            if response.headers['Content-Range']!=expected: raise ValueError('Wrong Content-Range')
            data=response.read(count+1)
        if len(data)!=count: raise ValueError('Incomplete/oversized range')
        self.position+=count; self.transferred+=count
        return data


def selected(infos,sequence,labels=False):
    prefix=f'training/image_02/{sequence}/'
    target=f'training/label_02/{sequence}.txt'
    return sorted([x for x in infos if x.filename==target] if labels else
                  [x for x in infos if x.filename.startswith(prefix) and x.filename.endswith('.png')],key=lambda x:x.filename)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sequence',default='0000')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--download',action='store_true')
    p.add_argument('--labels',action='store_true')
    a=p.parse_args(); url=LABEL_URL if a.labels else IMAGE_URL
    a.out.mkdir(parents=True,exist_ok=True)
    remote=RemoteZip(url)
    with zipfile.ZipFile(remote) as z:
        entries=selected(z.infolist(),a.sequence,a.labels)
        if not entries: raise ValueError('Sequence not found')
        record=dict(url=url,etag=remote.etag,archive_bytes=remote.size,sequence=a.sequence,
                    files=[dict(path=i.filename,size=i.file_size,compressed=i.compress_size,crc32=f'{i.CRC:08x}') for i in entries])
        stem='labels' if a.labels else 'images'
        if a.download:
            for n,i in enumerate(entries,1):
                target=a.out/'source'/i.filename
                if target.exists(): raise ValueError(f'Preserve existing {target}')
                data=z.read(i) # zipfile validates CRC
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
                record['files'][n-1]['sha256']=hashlib.sha256(data).hexdigest()
                if n%25==0: print(f'{n}/{len(entries)} downloaded',flush=True)
        record['http_bytes_transferred']=remote.transferred
        target=a.out/f'{stem}_{"download" if a.download else "inventory"}.json'
        if target.exists(): raise ValueError(f'Preserve existing {target}')
        target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in record.items() if k!='files'}))
        print('Selected files:',len(entries),'uncompressed:',sum(x.file_size for x in entries),'compressed:',sum(x.compress_size for x in entries))


if __name__=='__main__': main()
