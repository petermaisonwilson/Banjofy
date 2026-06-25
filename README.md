# Banjofy 0.1.0

A clean, native Windows desktop starter for Banjofy.

This first version is the application shell:

- dark desktop UI
- search/results area placeholder
- Current and Coming Next chord panels
- readable 5-string banjo chord diagrams
- capo selector
- Beginner / Intermediate / Professional mode selector
- 4/4 beat grid: 1 square = 1 beat, 16 squares per row
- GitHub Actions workflow to build a Windows executable

## Local run

```bash
pip install -r requirements.txt
python -m banjofy
```

## GitHub build

Upload these files to your GitHub repo root, then go to:

Actions → Build Windows EXE → Run workflow

Download the `Banjofy-Windows` artifact.
