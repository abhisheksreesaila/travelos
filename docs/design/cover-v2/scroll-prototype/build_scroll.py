"""Build the standalone scroll prototype; no server, dependencies or app edits."""
import base64,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from gitaway.icons import icon
HERE=Path(__file__).resolve().parent
source=(HERE/"source.html").read_text()
script=(HERE/"scroll.js").read_text().replace("/*WORLDS*/",(HERE/"immersive.js").read_text())
source=source.replace("/*STYLES*/",(HERE/"scroll.css").read_text()).replace("/*SCRIPT*/",script)
def font_url(m):
    path=(HERE/m[1]).resolve()
    return 'url("data:font/woff2;base64,'+base64.b64encode(path.read_bytes()).decode()+'")'
source=re.sub(r'url\("([^\"]+\.woff2)"\)',font_url,source)
source=re.sub(r"@ICON\(([-\w]+)\)@",lambda m:str(icon(m[1],size=20,stroke=1.7)),source)
def image_url(m,embed):
    path=(HERE/m[1]).resolve()
    if not path.is_file():raise FileNotFoundError(path)
    return 'src="'+("data:image/webp;base64,"+base64.b64encode(path.read_bytes()).decode() if embed else str(path))+'"'
(HERE/"index.html").write_text(re.sub(r'src="([^"]+\.webp)"',lambda m:image_url(m,True),source))
review=re.sub(r'src="([^"]+\.webp)"',lambda m:image_url(m,False),source)
review=review.replace('<html lang="en">','<html lang="en" data-embed="730" data-start="go">')
review=review.replace("</style>","html,body{background:transparent!important}.scroller{border-radius:12px}.prototype-label{display:none}</style>")
(HERE/"review.html").write_text(review)
print(f"Built {HERE/'index.html'} — {len(source):,} source characters; self-contained images")

