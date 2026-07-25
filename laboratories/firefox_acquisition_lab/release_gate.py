from pathlib import Path

root = Path(__file__).resolve().parent
main = (root / "main.py").read_text(encoding="utf-8")
spec = (root / "firefox_acquisition_lab.spec").read_text(encoding="utf-8")
required = [
    'APP_TITLE = "Banjofy Firefox Acquisition Laboratory 003"',
    'temporary = target.with_name(f"{target.stem}.working{target.suffix}")',
    '"-c:a", "aac", "-b:a", "192k", str(temporary)',
    'inspect_media(audio_target)',
    'Keep audio only — Recommended',
]
for text in required:
    assert text in main, f"Missing required implementation: {text}"
assert 'target.with_suffix(target.suffix + ".working")' not in main, "Invalid .m4a.working output naming remains"
assert 'name="BanjofyFirefoxAcquisitionLab003"' in spec
print("Firefox Acquisition Laboratory 003 release gate: passed")
