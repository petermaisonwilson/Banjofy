from __future__ import annotations
from dataclasses import dataclass
import json, subprocess, tempfile, wave
from pathlib import Path
from typing import Callable
import imageio_ffmpeg
import numpy as np
from banjofy.storage.paths import get_library_path

ProgressCallback = Callable[[str], None]

@dataclass(frozen=True)
class ChordAnalysis:
    beat_chords: tuple[str, ...]
    bar_chords: tuple[str, ...]
    confidence: float
    source_kind: str
    diagnostic: str
    tonal_center: str
    mode: str
    tonal_center_source: str
    @property
    def usable(self) -> bool:
        return len(self.beat_chords)>=4 and any(c not in ('N','') for c in self.beat_chords)

class ChordAnalyzer:
    CACHE_VERSION=3
    SAMPLE_RATE=22050
    FRAME_SIZE=8192
    HOP_SIZE=2048
    NOTE_NAMES=('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')

    def _cache_folder(self):
        lib=get_library_path()
        if lib is None: raise RuntimeError('Library folder is not configured')
        p=Path(lib)/'chords'; p.mkdir(parents=True,exist_ok=True); return p
    def cache_path_for(self,audio_path:Path):
        safe=''.join(c if c.isalnum() or c in '._-' else '_' for c in audio_path.stem)[:120]
        return self._cache_folder()/f'{safe}.chords.json'
    def delete_cache(self,audio_path:Path):
        p=self.cache_path_for(audio_path)
        if p.exists(): p.unlink()
    def save_tonal_center_override(self,audio_path:Path,value:str|None):
        p=self.cache_path_for(audio_path); data={}
        if p.exists():
            try:data=json.loads(p.read_text(encoding='utf-8'))
            except Exception:data={}
        if value is None:data.pop('tonal_center_override',None)
        elif value in self.NOTE_NAMES:data['tonal_center_override']=value
        else:raise ValueError('Invalid tonal centre')
        p.write_text(json.dumps(data,indent=2),encoding='utf-8')
    def tonal_center_override(self,audio_path:Path):
        p=self.cache_path_for(audio_path)
        if not p.exists():return None
        try:
            v=json.loads(p.read_text(encoding='utf-8')).get('tonal_center_override')
            return v if v in self.NOTE_NAMES else None
        except Exception:return None
    def load_cached(self,audio_path:Path):
        p=self.cache_path_for(audio_path)
        if not p.exists():return None
        try:
            d=json.loads(p.read_text(encoding='utf-8')); st=audio_path.stat()
            if d.get('cache_version')!=self.CACHE_VERSION or d.get('audio_size')!=st.st_size or int(d.get('audio_mtime',0))!=int(st.st_mtime):return None
            r=ChordAnalysis(tuple(d['beat_chords']),tuple(d['bar_chords']),float(d.get('confidence',0)), 'Cached analysis',d.get('diagnostic','Cached chord analysis loaded'),d.get('tonal_center','Not detected'),d.get('mode','Uncertain'),d.get('tonal_center_source','Automatic'))
            return r if r.usable else None
        except Exception:return None
    def save_cached(self,audio_path:Path,r:ChordAnalysis):
        st=audio_path.stat(); d={'cache_version':self.CACHE_VERSION,'audio_size':st.st_size,'audio_mtime':int(st.st_mtime),'beat_chords':list(r.beat_chords),'bar_chords':list(r.bar_chords),'confidence':r.confidence,'diagnostic':r.diagnostic,'tonal_center':r.tonal_center,'mode':r.mode,'tonal_center_source':r.tonal_center_source}
        ov=self.tonal_center_override(audio_path)
        if ov:d['tonal_center_override']=ov
        self.cache_path_for(audio_path).write_text(json.dumps(d,indent=2),encoding='utf-8')
    def _decode(self,p:Path):
        ff=imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory(prefix='banjofy_chords_') as td:
            wav=Path(td)/'a.wav'; cmd=[ff,'-hide_banner','-loglevel','error','-y','-i',str(p),'-vn','-ac','1','-ar',str(self.SAMPLE_RATE),'-c:a','pcm_s16le',str(wav)]
            c=subprocess.run(cmd,capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=420)
            if c.returncode!=0 or not wav.exists():raise RuntimeError('FFmpeg decode failed: '+(c.stderr.strip() or 'no output'))
            with wave.open(str(wav),'rb') as w: frames=w.readframes(w.getnframes()); rate=w.getframerate(); width=w.getsampwidth()
        if rate!=self.SAMPLE_RATE or width!=2:raise RuntimeError('Unexpected decoded WAV format')
        x=np.frombuffer(frames,dtype=np.int16).astype(np.float32)/32768.0
        peak=float(np.max(np.abs(x))) if x.size else 0
        if peak<.003:raise RuntimeError('Audio is silent or too quiet')
        return x/peak
    def _frame_chroma(self,frame):
        spec=np.abs(np.fft.rfft(frame*np.hanning(len(frame)))); f=np.fft.rfftfreq(len(frame),d=1/self.SAMPLE_RATE); ok=(f>=55)&(f<=3000); f=f[ok]; spec=spec[ok]
        if not spec.size:return np.zeros(12)
        midi=69+12*np.log2(f/440); pc=np.mod(np.rint(midi).astype(int),12); weights=np.power(np.maximum(spec,0),.32); c=np.bincount(pc,weights=weights,minlength=12).astype(float); s=c.sum(); return c/s if s else c
    def _chroma(self,x,start_ms,end_ms):
        a=max(0,int(start_ms*self.SAMPLE_RATE/1000)); b=min(len(x),int(end_ms*self.SAMPLE_RATE/1000)); agg=np.zeros(12); used=0
        for pos in range(a,max(a,b-self.FRAME_SIZE+1),self.HOP_SIZE):
            fr=x[pos:pos+self.FRAME_SIZE]
            if len(fr)<self.FRAME_SIZE or float(np.sqrt(np.mean(fr*fr)))<.008:continue
            agg+=self._frame_chroma(fr); used+=1
        if not used or agg.sum()<=0:return np.zeros(12)
        return agg/agg.sum()
    def _global(self,x):
        dur=int(len(x)*1000/self.SAMPLE_RATE); agg=np.zeros(12)
        for a in range(0,max(1,dur-5000),2500):agg+=self._chroma(x,a,a+5000)
        return agg/agg.sum() if agg.sum()>0 else agg
    def _tonic(self,c):
        scores=[]
        for r in range(12): scores.append((1.45*c[r]+.95*c[(r+7)%12]+.30*c[(r+5)%12]+.22*c[(r+10)%12]+.18*max(c[(r+4)%12],c[(r+3)%12]),r))
        scores.sort(reverse=True); best,r=scores[0]; second=scores[1][0]; conf=max(0,min(1,(best-second)/max(.01,best)))
        maj,minor=c[(r+4)%12],c[(r+3)%12]
        if max(maj,minor)<c[r]*.72:mode='Uncertain/Power'
        elif maj>minor*1.18: mode='Mixolydian' if c[(r+10)%12]>c[(r+11)%12]*1.1 else 'Major'
        elif minor>maj*1.18:mode='Minor'
        else:mode='Uncertain/Power'
        return r,mode,conf
    def _templates(self):
        out=[]
        for r,n in enumerate(self.NOTE_NAMES):
            for q,third,label in [('major',4,n),('minor',3,n+'m'),('power',None,n)]:
                t=np.full(12,.008); t[r]=1; t[(r+7)%12]=.94 if q=='power' else .88
                if third is not None:t[(r+third)%12]=.62
                out.append((label,r,q,t/np.linalg.norm(t)))
        return out
    def _classify(self,c,tonic,mode):
        if c.sum()<=0:return 'N',0
        v=c/(np.linalg.norm(c)+1e-12); compat={tonic,(tonic+5)%12,(tonic+7)%12,(tonic+10)%12,(tonic+2)%12,(tonic+9)%12}; ranked=[]
        for name,r,q,t in self._templates():
            s=float(np.dot(v,t))+(.045 if r in compat else -.055)+(.035 if r==tonic else 0)
            if mode in ('Uncertain/Power','Mixolydian') and q=='minor':s-=.05
            ranked.append((s,name))
        ranked.sort(reverse=True); best,name=ranked[0]; margin=best-ranked[1][0]; conf=max(0,min(1,margin/.14))
        return (name,conf) if best>=.61 and margin>=.022 else ('N',conf)
    def analyse(self,audio_path,beat_times_ms,beats_per_bar,progress=None):
        cached=self.load_cached(audio_path)
        if cached is not None and len(cached.beat_chords)==len(beat_times_ms):
            if progress:progress('Loaded cached chord analysis')
            return cached
        if progress:progress('Decoding audio for segment-aligned analysis')
        x=self._decode(audio_path); auto,mode,keyconf=self._tonic(self._global(x)); ov=self.tonal_center_override(audio_path); tonic=self.NOTE_NAMES.index(ov) if ov else auto; tonal=ov or self.NOTE_NAMES[auto]; source='Manual' if ov else 'Automatic'
        if ov and mode=='Minor':mode='Uncertain/Power'
        segsize=3 if beats_per_bar==3 else 2; segments=[]; raw=[]; confs=[]
        if progress:progress('Analysing exact beat-aligned segments')
        for sb in range(0,len(beat_times_ms),segsize):
            eb=min(len(beat_times_ms),sb+segsize); start=int(beat_times_ms[sb]); end=int(beat_times_ms[eb]) if eb<len(beat_times_ms) else int(beat_times_ms[-1]+(beat_times_ms[-1]-beat_times_ms[-2] if len(beat_times_ms)>1 else 500)); segments.append((sb,eb,start,end)); ch,cf=self._classify(self._chroma(x,start,end),tonic,mode); raw.append(ch); confs.append(cf)
        stable=raw[:]
        for i in range(1,len(stable)-1):
            if stable[i]=='N' and stable[i-1]==stable[i+1]:stable[i]=stable[i-1]
            elif stable[i-1]==stable[i+1] and stable[i]!=stable[i-1] and confs[i]<.68:stable[i]=stable[i-1]
        current=next((c for c in stable if c!='N'),'N'); beat=['N']*len(beat_times_ms)
        for (sb,eb,_,_),ch,cf in zip(segments,stable,confs):
            if ch=='N' or (ch!=current and cf<.42):ch=current
            else:current=ch
            for i in range(sb,eb):beat[i]=ch
        bars=[]
        for s in range(0,len(beat),beats_per_bar):
            g=[c for c in beat[s:s+beats_per_bar] if c!='N']; bars.append(max(set(g),key=g.count) if g else 'N')
        changes=sum(1 for i,c in enumerate(beat) if i==0 or c!=beat[i-1]); confidence=.72*(float(np.mean(confs)) if confs else 0)+.28*keyconf
        r=ChordAnalysis(tuple(beat),tuple(bars),confidence,'Fresh analysis',f'{len(segments)} beat-aligned segments; {changes} stable chord events',tonal,mode,source); self.save_cached(audio_path,r)
        if progress:progress('Segment-aligned chord analysis complete')
        return r
