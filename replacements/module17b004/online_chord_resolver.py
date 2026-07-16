from __future__ import annotations
from dataclasses import dataclass
import html
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

@dataclass(frozen=True)
class ChordSourceFinding:
    source_name: str
    source_url: str
    key: str | None
    chords: tuple[str, ...]
    snippet: str

@dataclass(frozen=True)
class ChordDataConsensus:
    artist: str
    title: str
    key: str | None
    chords: tuple[str, ...]
    findings: tuple[ChordSourceFinding, ...]
    confidence: float
    diagnostic: str
    @property
    def usable(self) -> bool:
        return len(self.chords) >= 2

class OnlineChordResolver:
    SEARCH_URL = "https://html.duckduckgo.com/html/"
    SOURCE_DOMAINS = (
        "ultimate-guitar.com","chordify.net","songsterr.com",
        "e-chords.com","chordie.com"
    )
    NOTE = r"(?:C#|Db|D#|Eb|F#|Gb|G#|Ab|A#|Bb|[A-G])"
    CHORD_RE = re.compile(
        rf"(?<![A-Za-z0-9#b])({NOTE}(?:m|maj|min|sus|dim|aug)?(?:2|5|6|7|9|11|13)?)(?![A-Za-z0-9#b])",
        re.I
    )
    KEY_RE = re.compile(rf"\bkey\s*(?:of|:|-)?\s*({NOTE})(\s*(?:major|minor|m))?\b",re.I)

    def _clean(self,artist,title):
        artist=re.sub(r"\s+"," ",artist or "").strip()
        title=re.sub(r"\((?:official|lyrics?|audio|video|music video|live|hd|4k)[^)]*\)","",title or "",flags=re.I)
        title=re.sub(r"\[(?:official|lyrics?|audio|video|live)[^\]]*\]","",title,flags=re.I)
        return artist,re.sub(r"\s+"," ",title).strip(" -_")

    def _norm(self,value):
        value=value.strip()
        m=re.match(r"^(C#|Db|D#|Eb|F#|Gb|G#|Ab|A#|Bb|[A-G])",value,re.I)
        if not m:return value
        root=m.group(1)[0].upper()+m.group(1)[1:]
        suffix=value[len(m.group(1)):]
        suffix=re.sub(r"(?i)min","m",suffix)
        suffix=re.sub(r"(?i)maj","maj",suffix)
        return root+suffix

    def resolve(self,artist,title,progress=None):
        artist,title=self._clean(artist,title)
        if not title:raise RuntimeError("Song title could not be identified")
        if progress:progress("Searching multiple chord sources")
        domains=" OR ".join(f"site:{d}" for d in self.SOURCE_DOMAINS)
        query=f'"{artist}" "{title}" chords key ({domains})'
        response=requests.post(
            self.SEARCH_URL,data={"q":query},
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"},
            timeout=25
        )
        response.raise_for_status()
        soup=BeautifulSoup(response.text,"html.parser")
        findings=[]
        for result in soup.select(".result"):
            link=result.select_one(".result__a")
            snippet=result.select_one(".result__snippet")
            if link is None:continue
            url=link.get("href","")
            combined=html.unescape(
                link.get_text(" ",strip=True)+". "+
                (snippet.get_text(" ",strip=True) if snippet else "")
            )
            host=urlparse(url).netloc.lower()
            source=next((d for d in self.SOURCE_DOMAINS if d in host or d in url.lower()),host or "Search")
            km=self.KEY_RE.search(combined)
            key=None
            if km:
                key=self._norm(km.group(1))
                if (km.group(2) or "").strip().lower() in ("minor","m"):key+="m"
            context=bool(re.search(r"\b(chords?|key|capo|progression|tabs?)\b",combined,re.I))
            chords=[]
            if context:
                for match in self.CHORD_RE.finditer(combined):
                    chord=self._norm(match.group(1))
                    if chord not in chords:chords.append(chord)
            if key or len(chords)>=2:
                findings.append(ChordSourceFinding(source,url,key,tuple(chords[:16]),combined[:500]))
            if len(findings)>=10:break
        if not findings:
            raise RuntimeError("No usable key or chord facts found in public search results")
        key_counts={}; chord_counts={}
        for finding in findings:
            if finding.key:key_counts[finding.key]=key_counts.get(finding.key,0)+1
            for chord in finding.chords:chord_counts[chord]=chord_counts.get(chord,0)+1
        key=max(key_counts,key=key_counts.get) if key_counts else None
        ranked=sorted(chord_counts,key=lambda c:(-chord_counts[c],c))
        chords=tuple(c for c in ranked if chord_counts[c]>=2 or len(findings)<=2)[:12]
        if key:
            root=key[:-1] if key.endswith("m") else key
            if root not in chords:chords=(root,)+chords
        confidence=min(1.0,.2+.1*len(findings)+.05*len(chords))
        return ChordDataConsensus(
            artist,title,key,chords,tuple(findings),confidence,
            f"{len(findings)} findings; {len(chords)} consensus chord candidates"
        )
